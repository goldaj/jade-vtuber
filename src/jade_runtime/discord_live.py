"""Discord native Live routing with an independent monthly admission policy.

Solo capture streams directly after local speech detection. Group audio reaches
Live only after the existing STT/participation decision, at the documented PCM
rate. A consumed utterance is never automatically replayed through classic.
"""
from __future__ import annotations

import asyncio
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
import inspect
import json
import logging
from pathlib import Path
import secrets
import sqlite3
import struct
import threading
import time

from .discord_live_provider import (
    DiscordLiveProvider, PCM48StereoTo24Mono, build_discord_live_config,
)
from .live_bridge import LiveConversationBridge
from .live_provider import LiveProviderError
from .messages import Incoming, Reply


LOG = logging.getLogger("jade.discord.live")
_FRAME = 3840  # 20 ms, 48 kHz stereo PCM16LE from Discord.
_RATE = 192000
_SPEECH_ONSET_BYTES = 3 * _FRAME
_ONSET_PACKET_GAP_SECONDS = .08
_SPEECH_GAP_SECONDS = .3
_CONTROL_QUEUE_LIMIT = 256
_SILENCE = bytes(_FRAME)


def _voiced(pcm, threshold):
    if not pcm:
        return False
    samples = struct.iter_unpack("<h", pcm)
    return sum(value * value for (value,) in samples) / (len(pcm) // 2) >= threshold ** 2


def _consume(task):
    if not task.cancelled():
        task.exception()


async def _await(value):
    return await value if inspect.isawaitable(value) else value


class DiscordLiveRegistry:
    """One durable provider attempt; an absent terminal never means closed.

    Only opaque transport identifiers are stored here, without speech or
    identity. The row is written before session.start can leave this process.
    """
    def __init__(self, path):
        self.path = Path(path)
        if (not self.path.is_absolute() or self.path.suffix != ".sqlite3"
                or self.path.is_symlink()):
            raise ValueError("use an absolute private Discord Live journal path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS discord_live_transport (
                slot INTEGER PRIMARY KEY CHECK(slot=1), attempt TEXT NOT NULL,
                provider_id TEXT NOT NULL DEFAULT '', phase TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '', usage_json TEXT NOT NULL DEFAULT '{}')""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(discord_live_transport)")}
            if "usage_json" not in columns:
                db.execute("ALTER TABLE discord_live_transport ADD COLUMN usage_json TEXT NOT NULL DEFAULT '{}'")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def pending(self):
        with self._db() as db:
            row = db.execute("SELECT * FROM discord_live_transport WHERE slot=1").fetchone()
            return dict(row) if row is not None else None

    def begin(self, attempt):
        with self._db() as db:
            return db.execute("INSERT OR IGNORE INTO discord_live_transport(slot,attempt,phase) "
                              "VALUES(1,?,'opening')", (attempt,)).rowcount == 1

    def identified(self, attempt, provider_id):
        with self._db() as db:
            changed = db.execute("UPDATE discord_live_transport SET provider_id=?,phase='active' "
                                 "WHERE slot=1 AND attempt=?", (provider_id, attempt)).rowcount
            if changed != 1:
                raise RuntimeError("Discord Live transport reservation lost")

    def finish(self, attempt, result):
        with self._db() as db:
            # The cost write is idempotent, so its small final counter can be
            # retried after a crash. A never-started reservation also needs its
            # settlement to complete before this recovery pointer disappears.
            phase = ("unstarted_pending_usage" if result.get("started") is False else
                     "closed_pending_usage" if result.get("confirmed") is True else "unknown")
            usage = result.get("usage", {})
            safe_usage = {"seconds": usage["seconds"]} if "seconds" in usage else {}
            db.execute("UPDATE discord_live_transport SET phase=?,reason=?,usage_json=?,"
                       "provider_id=CASE WHEN ?<>'' THEN ? ELSE provider_id END "
                       "WHERE slot=1 AND attempt=?",
                       (phase, str(result.get("reason", "close_unconfirmed"))[:80],
                        json.dumps(safe_usage, allow_nan=False),
                        result.get("session_id") or "", result.get("session_id") or "", attempt))

    def accounted(self, attempt):
        with self._db() as db:
            db.execute("DELETE FROM discord_live_transport WHERE slot=1 AND attempt=? "
                       "AND phase IN ('closed_pending_usage','unstarted_pending_usage')", (attempt,))


@dataclass
class _Conversation:
    source: Incoming
    transport: object
    mode: str
    context: dict
    opened_at: float
    last_input: float
    last_output: float
    active: bool = True
    remote: object | None = None
    opening: asyncio.Task | None = None
    sender: asyncio.Task | None = None
    receiver: asyncio.Task | None = None
    close_task: asyncio.Task | None = None
    playback: asyncio.Task | None = None
    output: asyncio.Queue | None = None
    accepting_output: bool = False
    output_seen: bool = False
    attempt_started: bool = False
    opening_called: bool = False
    fallback_classic: bool = False
    attempt_id: str = ""
    open_result: dict | None = None
    input_pcm: bytearray = field(default_factory=bytearray)
    interruption_pcm: bytearray = field(default_factory=bytearray)
    interruption_sample_at: float = float("-inf")
    converter: PCM48StereoTo24Mono = field(default_factory=PCM48StereoTo24Mono)
    speech_active: bool = False
    pending_control_events: int = 0
    output_bytes: int = 0
    muted_until: float = 0.0
    last_capture: float = float("-inf")
    sent_audio: bool = False
    accounted: set = field(default_factory=set)
    delivered: set = field(default_factory=set)
    transcript: str = ""


class DiscordLiveAdapter:
    def __init__(self, bridge, runtime, config, policy, provider, conversation,
                 *, publish_reply=None, set_avatar_intent=None,
                 registry=None, clock=time.monotonic, poll_seconds=1.0):
        self.bridge, self.runtime, self.config = bridge, runtime, config
        self.policy, self.provider, self.conversation = policy, provider, conversation
        self.publish_reply = publish_reply
        self.set_avatar_intent = set_avatar_intent
        self.registry = registry
        self.clock, self.poll_seconds = clock, poll_seconds
        self._loop = None
        self._running = False
        self._allow_live = False
        self._owner_preference_revision = 0
        self._blocked = False
        self._block_reason = ""
        self._recovery_checked = False
        self._last_diagnostic = None
        self._current = None
        self._watchdog = None
        self._tasks = set()
        self._capture_lock = threading.Lock()
        self._scheduled_bytes = 0
        self._preroll = bytearray()
        self._candidate = 0
        self._preroll_speaker = None
        self._suppressed = {}
        self._starts = deque()
        self.last_reason = "not_started"

    def _task(self, coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        task.add_done_callback(_consume)
        return task

    def _solo(self, user_id):
        channel = getattr(self.bridge.connection, "channel", None)
        members = getattr(channel, "members", None)
        if not isinstance(members, (list, tuple)):
            return False
        humans = {m.id for m in members if type(getattr(m, "id", None)) is int
                  and getattr(m, "bot", None) is False and m.id != self.bridge.own_bot_id}
        return humans == {user_id}

    def _valid(self, state):
        return (self._running and state.active and self._current is state
                and self.bridge.delivery_context_valid(state.transport)
                and self.bridge.reply_authorized(state.source)
                and (state.mode != "solo" or self._solo(state.source.speaker_id)))

    def playback_allowed(self, live_session=None):
        """Live owns the speaking lane until its local teardown completes."""
        state = self._current
        if live_session is None:
            return state is None
        return (self._allow_live and state is not None
                and state.context["session_id"] == live_session and self._valid(state))

    async def start(self):
        if self._running:
            return
        self._running = True
        self._loop = asyncio.get_running_loop()
        await self._recover_transport()
        await self._decision()
        self._watchdog = self._task(self._monitor(), "jade-discord-live-policy")

    async def _decision(self):
        revision = self._owner_preference_revision
        try:
            decision = await self.policy.decision()
        except Exception:
            decision = {"allow_live": False, "reason": "spend_status_unavailable"}
        if revision != self._owner_preference_revision:
            return self._allow_live
        self._allow_live = bool(decision.get("allow_live")) and not self._blocked
        self.last_reason = self._block_reason or str(decision.get("reason", "policy"))[:80]
        threshold = decision.get("threshold_eur")
        while self._starts and self.clock() - self._starts[0] >= 60:
            self._starts.popleft()
        if (self._allow_live and self._current is None
                and len(self._starts) >= self.config.max_starts_per_minute):
            self._allow_live = False
            self.last_reason = "live_start_rate_limit"
        diagnostic = ("live" if self._allow_live else "classic", self.last_reason, threshold)
        if diagnostic != self._last_diagnostic:
            LOG.info("Discord voice mode=%s reason=%s monthly_threshold_eur=%s", *diagnostic)
            self._last_diagnostic = diagnostic
        return self._allow_live

    async def apply_owner_preference(self, enabled):
        # An already-running policy read can finish after the owner's write.
        self._owner_preference_revision += 1
        if enabled:
            if self._running:
                await self._decision()
            return
        self._allow_live = False
        self.last_reason = "manual_classic"
        state = self._current
        if state is not None:
            await self._close_session(state, "manual_classic")

    def _block(self, reason):
        self._blocked, self._allow_live = True, False
        self._block_reason = self.last_reason = reason

    async def _record_usage(self, session_id, usage):
        record = getattr(self.policy, "record_live_usage", None)
        if callable(record) and session_id:
            try:
                await _await(record(session_id, usage, model=self.config.model))
            except Exception:
                self._block("live_usage_unavailable")
                return False
        return True

    def _save_outcome(self, state, result):
        state.open_result = result
        certain = result.get("confirmed") is True or result.get("started") is False
        if not certain:
            self._block("close_unconfirmed")
        if self.registry is not None and state.attempt_started:
            try:
                self.registry.finish(state.attempt_id, result)
            except (OSError, sqlite3.Error):
                self._block("live_journal_unavailable")

    async def _finish_attempt(self, state, result):
        # Persist before optional accounting awaits; a second cancellation must
        # never turn an unresolved paid creation into an empty registry.
        self._save_outcome(state, result)
        recorded = await self._settle_attempt(state.attempt_id, result)
        certain = result.get("confirmed") is True or result.get("started") is False
        if recorded and certain and self.registry is not None:
            try:
                self.registry.accounted(state.attempt_id)
                if (self._block_reason in ("close_unconfirmed", "previous_close_unconfirmed",
                                            "live_usage_pending", "live_usage_unavailable")
                        and self.registry.pending() is None):
                    self._blocked, self._block_reason = False, ""
            except (OSError, sqlite3.Error):
                self._block("live_journal_unavailable")

    async def _settle_attempt(self, attempt, result):
        settle = getattr(self.policy, "settle_live", None)
        if callable(settle):
            try:
                await _await(settle(attempt, confirmed=result.get("confirmed") is True,
                    never_started=result.get("started") is False,
                    session_id=result.get("session_id"), usage=result.get("usage", {}),
                    model=self.config.model))
                return True
            except Exception:
                self._block("live_usage_unavailable")
                return False
        if result.get("started") is False:
            return True
        return await self._record_usage(result.get("session_id"), result.get("usage", {}))

    async def _recover_transport(self):
        if self.registry is None or self._recovery_checked:
            return
        self._recovery_checked = True
        try:
            pending = self.registry.pending()
            if pending is None:
                return
            self._block("previous_close_unconfirmed")
            provider_id = pending["provider_id"]
            reconcile = getattr(self.provider, "reconcile_close", None)
            if pending["phase"] in ("closed_pending_usage", "unstarted_pending_usage"):
                result = {"confirmed": pending["phase"] == "closed_pending_usage",
                          "started": pending["phase"] != "unstarted_pending_usage", "session_id": provider_id,
                          "usage": json.loads(pending["usage_json"])}
            elif not provider_id or not callable(reconcile):
                return
            else:
                result = await reconcile(provider_id)
                self.registry.finish(pending["attempt"], result)
            recorded = await self._settle_attempt(pending["attempt"], result)
            certain = result.get("confirmed") is True or result.get("started") is False
            if recorded and certain:
                self.registry.accounted(pending["attempt"])
            if recorded and certain and self._block_reason == "previous_close_unconfirmed":
                self._blocked, self._block_reason = False, ""
        except asyncio.CancelledError:
            raise
        except Exception:
            self._block("previous_close_unconfirmed")

    def _classic_busy(self):
        # A policy refresh can enable Live halfway through a classic utterance.
        # Finish that entire captured turn through its original admission path.
        with self.bridge.buffers_lock:
            return bool(self.bridge._segmenter._users or self.bridge._assemblies
                        or self.bridge._scheduled or self.bridge.pending._unfinished_tasks
                        or self.bridge._transcribing is not None or self._classic_output_busy())

    def _classic_output_busy(self):
        return self.bridge._playback_active or any(
            not work.cancelled and (work.task is None or not work.task.done())
            for _, work in self.bridge._submitted)

    def offer_pcm(self, user_id, author, pcm):
        """Called from Discord's capture thread; admission never performs I/O."""
        if (not self._running or self._loop is None or type(user_id) is not int
                or user_id <= 0 or not isinstance(pcm, bytes) or not pcm or len(pcm) % 4
                or len(pcm) > _RATE * 2 or not author):
            return False
        if not self.bridge._capture_authorized(user_id):
            return False
        # A cut-over must not reinterpret the remainder of an already consumed
        # Live utterance as a new classic request. Silence releases the guard.
        with self._capture_lock:
            if self._current is not None and self._current.fallback_classic:
                return False
            if user_id in self._suppressed:
                quiet = 0 if _voiced(pcm, self.bridge.threshold) else self._suppressed[user_id] + len(pcm)
                if quiet >= int(_RATE * .65):
                    self._suppressed.pop(user_id, None)
                else:
                    self._suppressed[user_id] = quiet
                return True
        if (not self._allow_live or self.bridge.voice_muted() or not self._solo(user_id)
                or (self._current is None and self._classic_busy())):
            return False
        with self._capture_lock:
            if self._scheduled_bytes + len(pcm) > _RATE * 8:
                self._suppressed[user_id] = 0
                try:
                    self._loop.call_soon_threadsafe(self._overflow)
                except RuntimeError:
                    pass
                return True
            self._scheduled_bytes += len(pcm)
        generation, session_id = self.bridge.generation, self.bridge.session_id
        try:
            self._loop.call_soon_threadsafe(self._receive_solo, user_id, author, pcm, generation, session_id)
        except RuntimeError:
            with self._capture_lock:
                self._scheduled_bytes -= len(pcm)
        return True

    def _overflow(self):
        if self._current:
            self._task(self._close_session(self._current, "input_backpressure"), "jade-discord-live-overflow")

    def _source(self, user_id, author):
        session = self.bridge.session_id
        conversation = self.bridge.voice_conversation_id(user_id, session)
        if not conversation:
            return None
        return Incoming("discord_voice", author, "Ouverture de la conversation Live.",
                        channel=str(self.bridge.channel_id), speaker_id=user_id,
                        account_id=str(user_id), voice_session_id=session,
                        conversation_id=conversation, force_reply=True,
                        input_modality="voice", requested_speech=False, direct_request=True)

    def _new(self, source, mode):
        transport = self.bridge.delivery_context()
        if transport is None:
            return None
        now = self.clock()
        context = {"owner": f"discord:{source.speaker_id}", "thread_id": source.conversation_id,
                   "session_id": "discord-live-" + secrets.token_hex(16),
                   "generation": self.bridge.generation, "source": source}
        state = _Conversation(source, transport, mode, context, now, now, now)
        state.attempt_id = context["session_id"]
        context["valid"] = lambda: self._valid(state)
        self._current = state
        return state

    def _receive_solo(self, user_id, author, pcm, generation, session_id):
        with self._capture_lock:
            self._scheduled_bytes -= len(pcm)
        if (not self._running or not self._allow_live or not self._solo(user_id)
                or not self.bridge._capture_authorized(user_id, generation, session_id)):
            return
        current = self._current
        if current and (current.mode != "solo" or current.source.speaker_id != user_id
                        or not self._valid(current)):
            self._task(self._close_session(current, "speaker_changed"), "jade-discord-live-speaker")
            return
        voiced = _voiced(pcm, self.bridge.threshold)
        now = self.clock()
        if current is None:
            # Playback can start between the capture thread's admission check
            # and this callback. Do not claim the lane over an existing reply.
            if self._classic_busy():
                return
            if self._preroll_speaker != user_id:
                self._preroll.clear()
                self._candidate = 0
                self._preroll_speaker = user_id
            self._preroll.extend(pcm)
            if voiced:
                self._candidate += len(pcm)
            else:
                self._candidate = 0
            del self._preroll[:max(0, len(self._preroll) - int(_RATE * .5) - self._candidate)]
            if self._candidate < _SPEECH_ONSET_BYTES:
                return
            source = self._source(user_id, author)
            if source is None:
                self._preroll.clear()
                return
            current = self._new(source, "solo")
            if current is None:
                return
            current.input_pcm.extend(self._preroll)
            self._preroll.clear()
            self._candidate = 0
            current.opening = self._task(self._open(current), "jade-discord-live-open")
        else:
            playing = current.playback is not None and not current.playback.done()
            new_speech = not current.speech_active or now - current.last_capture >= _SPEECH_GAP_SECONDS
            if playing and (new_speech or current.interruption_pcm):
                # Hold the candidate until sustained speech is confirmed.
                # Sending an isolated noise to the provider could interrupt it
                # even if Discord kept playing the local response.
                if not voiced or now - current.interruption_sample_at >= _ONSET_PACKET_GAP_SECONDS:
                    current.interruption_pcm.clear()
                if not voiced:
                    current.speech_active = False
                    return
                current.interruption_sample_at = now
                current.interruption_pcm.extend(pcm)
                if len(current.interruption_pcm) < _SPEECH_ONSET_BYTES:
                    return
                pcm = bytes(current.interruption_pcm)
                self._interrupt_output(current)
            elif (current.interruption_pcm and voiced
                  and now - current.interruption_sample_at < _ONSET_PACKET_GAP_SECONDS):
                # Playback drained while the next utterance was starting.
                pcm = bytes(current.interruption_pcm) + pcm
            current.interruption_pcm.clear()
            if len(current.input_pcm) + len(pcm) > _RATE * 8:
                self._overflow()
                return
            current.input_pcm.extend(pcm)
        if voiced:
            current.last_input = current.last_capture = now
        current.speech_active = voiced

    async def handle_turn(self, source, pcm, valid=None):
        """Use Live only for a completed turn already admitted by Discord policy.

        False means no provider operation started and classic may process it.
        Once accepted, errors never cause an automatic classic replay.
        """
        if not self._running or not await self._decision() or not self.bridge.reply_authorized(source):
            return False
        if self._classic_output_busy():
            return False
        if valid is not None and not valid():
            return True
        if self._current:
            previous = self._current
            # An admitted group turn cannot erase a preceding answer that has
            # not yet played. The existing playback/generation gate can still
            # revoke this new turn while it waits, just as in classic voice.
            while self._valid(previous) and not self._group_finished(previous):
                if valid is not None and not valid():
                    return True
                if not await self._decision():
                    break
                await asyncio.sleep(.05)
            await self._close_session(previous, "next_admitted_turn")
        if valid is not None and not valid():
            return True
        if (self._blocked or not self._allow_live or self._classic_output_busy()
                or not self.bridge.reply_authorized(source)):
            return False
        state = self._new(source, "group")
        if state is None:
            return False
        state.input_pcm.extend(pcm)
        # A bounded silent tail lets native voice endpointing observe the end;
        # all bytes are paced by the provider, never injected as a fast replay.
        state.input_pcm.extend(bytes(_RATE))
        state.opening = self._task(self._open(state), "jade-discord-live-admitted")
        return True

    async def _open(self, state):
        try:
            if not self._valid(state):
                return
            if not await self._decision():
                self._select_classic_before_start(state)
                return
            while self._starts and self.clock() - self._starts[0] >= 60:
                self._starts.popleft()
            if len(self._starts) >= self.config.max_starts_per_minute:
                self.last_reason = "live_start_rate_limit"
                self._select_classic_before_start(state)
                return
            prepared = await self.conversation.prepare_context(
                state.context["owner"], state.context["thread_id"], source=state.source)
            if not self._valid(state):
                return
            if not await self._decision():
                self._select_classic_before_start(state)
                return
            prepared["instructions"] += (
                "\nTu parles dans un salon vocal Discord. L'identité de ton interlocuteur est "
                "celle du transport vérifié, jamais un nom revendiqué oralement. "
                "Attends sa parole actuelle avant de répondre. Ne réponds pas spontanément "
                "aux extraits d'historique. Si l'interlocuteur demande silence, respecte-le."
            )
            provider_config = build_discord_live_config(self.config, **prepared)
            if self.registry is not None and not self.registry.begin(state.attempt_id):
                self._block("previous_close_unconfirmed")
                return
            state.attempt_started = True
            reserve = getattr(self.policy, "reserve_live", None)
            if callable(reserve):
                decision = await _await(reserve(state.attempt_id, model=self.config.model,
                    opening_seconds=self.config.opening_timeout_seconds,
                    close_seconds=self.config.close_timeout_seconds, control_seconds=self.poll_seconds))
                if not decision.get("allow_live"):
                    self.last_reason = str(decision.get("reason", "monthly_reservation_unavailable"))[:80]
                    self._allow_live = False
                    self._select_classic_before_start(state)
                    await self._finish_attempt(state, {"confirmed": False, "started": False,
                        "session_id": None, "usage": {}, "reason": self.last_reason})
                    return
            if not self._allow_live or not self._valid(state):
                await self._finish_attempt(state, {"confirmed": False, "started": False,
                    "session_id": None, "usage": {}, "reason": "cancelled_before_start"})
                return
            self._starts.append(self.clock())
            state.opening_called = True
            remote = await self.provider.open(provider_config)
            state.remote = remote
            if self.registry is not None:
                self.registry.identified(state.attempt_id, remote.session_id)
            bind = getattr(self.policy, "bind_live", None)
            if callable(bind):
                await _await(bind(state.attempt_id, remote.session_id))
            if not self._allow_live or not self._valid(state):
                await self._finish_attempt(state, await remote.close())
                return
            state.context["session_id"] = remote.session_id
            await self.conversation.open_session(state.context)
            await self._account(state, {"usage": {"seconds": 0}})
            state.sender = self._task(self._send_audio(state), "jade-discord-live-input")
            state.receiver = self._task(self._receive(state), "jade-discord-live-events")
        except asyncio.CancelledError as error:
            if state.attempt_started and state.remote is None:
                result = getattr(error, "close_result", None) or {
                    "confirmed": False, "started": state.opening_called and getattr(error, "ambiguous", True),
                    "session_id": getattr(error, "session_id", None),
                    "usage": {}, "reason": "opening_cancelled"}
                await self._finish_attempt(state, result)
            raise
        except Exception as error:
            if state.attempt_started and state.remote is None:
                result = getattr(error, "close_result", None) or {
                    "confirmed": False,
                    "started": state.opening_called and
                               (not isinstance(error, LiveProviderError) or error.ambiguous),
                    "session_id": getattr(error, "session_id", None),
                    "usage": {}, "reason": "opening_failed"}
                await self._finish_attempt(state, result)
            self.last_reason = self._block_reason or "live_open_unavailable"
            LOG.warning("Discord Live opening failed; no utterance replayed")
        finally:
            if state.active and state.sender is None:
                if state.fallback_classic:
                    self._task(self._return_to_classic(state), "jade-discord-live-before-start-classic")
                else:
                    self._task(self._close_session(state, "opening_failed"), "jade-discord-live-open-close")

    def _select_classic_before_start(self, state):
        if not self._valid(state) or state.opening_called:
            return
        # Keep the captured prefix ahead of the next capture-thread frame.
        # This is admission before provider.open, never a paid-attempt retry.
        with self._capture_lock:
            state.fallback_classic = True
            if state.mode == "solo" and state.input_pcm:
                captured = bytes(state.input_pcm)
                state.input_pcm.clear()
                self.bridge.receive_classic_pcm(state.source.speaker_id, state.source.author, captured)

    async def _return_to_classic(self, state):
        # This path is exclusively a policy/rate/reservation refusal before any
        # provider.open call. No uncertain or already-uploaded audio is replayed.
        permitted = self._valid(state) and not state.opening_called
        if permitted and state.mode == "solo" and state.input_pcm:
            captured = bytes(state.input_pcm)
            state.input_pcm.clear()
            self.bridge.receive_classic_pcm(state.source.speaker_id, state.source.author, captured)
        await self._close_session(state, "classic_before_start")
        if (permitted and state.mode == "group" and self.bridge.delivery_context_valid(state.transport)
                and self.bridge.reply_authorized(state.source)):
            await self.bridge.submit_admitted_turn(state.source, generation=state.context["generation"])

    async def _send_audio(self, state):
        try:
            while self._valid(state):
                if len(state.input_pcm) >= _FRAME:
                    pcm = bytes(state.input_pcm[:_FRAME])
                    del state.input_pcm[:_FRAME]
                elif state.input_pcm:
                    pcm = bytes(state.input_pcm).ljust(_FRAME, b"\0")
                    state.input_pcm.clear()
                else:
                    pcm = _SILENCE
                if _voiced(pcm, self.bridge.threshold):
                    state.last_input = self.clock()
                await state.remote.send_audio(state.converter.feed(pcm))
                state.sent_audio = True
        except asyncio.CancelledError:
            raise
        except Exception:
            self._task(self._close_session(state, "input_failed"), "jade-discord-live-input-close")

    def _interrupt_output(self, state):
        # The primary protocol has no response.cancel. Native input continues;
        # discard locally queued speech while the human is speaking.
        state.muted_until = self.clock() + _SPEECH_GAP_SECONDS
        if state.output is not None:
            while not state.output.empty():
                try:
                    state.output.get_nowait()
                except asyncio.QueueEmpty:
                    break
            state.output_bytes = 0
        if state.playback and not state.playback.done():
            state.playback.cancel()
            self.bridge._stop_playback(state.transport.connection)
        state.accepting_output = False
        self._task(self.conversation.observe_playback(state.context, {"state": "interrupted"}),
                   "jade-discord-live-interrupted")

    async def _account(self, state, event):
        await self._record_usage(state.remote.session_id, event.get("usage", {}))

    async def _receive_control(self, state, queue):
        while self._valid(state):
            event = await queue.get()
            if event is None:
                return
            kind = event["type"]
            try:
                if kind in ("session.usage.updated", "session.closed"):
                    await self._account(state, event)
                else:
                    await self.conversation.handle_event(event, state.context, state.remote.send)
            finally:
                state.pending_control_events -= 1
            if kind == "session.closed":
                return

    async def _receive(self, state):
        control = asyncio.Queue(maxsize=_CONTROL_QUEUE_LIMIT)
        try:
            async with asyncio.TaskGroup() as tasks:
                worker = tasks.create_task(self._receive_control(state, control),
                                           name="jade-discord-live-control-events")
                try:
                    await self._receive_media(state, control, worker)
                finally:
                    worker.cancel()
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.warning("Discord Live stream interrupted; no utterance replayed")
        finally:
            if state.active:
                self._task(self._close_session(state, "provider_stream_ended"), "jade-discord-live-ended")

    async def _receive_media(self, state, control, worker):
        async for event in state.remote:
            if not self._valid(state):
                return
            kind = event.get("type")
            if kind == "session.output_audio.delta":
                now = self.clock()
                state.last_output = now
                state.output_seen = True
                if (state.mode == "solo" and
                        (now - state.last_capture < _SPEECH_GAP_SECONDS or now < state.muted_until)):
                    continue
                await self._output(state, event["pcm"])
            elif kind in ("session.input_transcript.delta", "session.output_transcript.delta",
                          "session.delegation.created", "session.usage.updated", "session.closed"):
                if kind == "session.input_transcript.delta" and self._stop_requested(state, event):
                    self._task(self._close_session(state, "voice_muted"), "jade-discord-live-muted")
                    return
                # Keep database writes and avatar/transcript observers off the
                # PCM delivery path. A full queue ends the session safely.
                control.put_nowait(event)
                state.pending_control_events += 1
                if kind == "session.closed":
                    await asyncio.wait_for(worker, self.config.close_timeout_seconds)
                    return
        if self._valid(state):
            # Let already accepted events finish on a normal end of stream.
            async with asyncio.timeout(self.config.close_timeout_seconds):
                await control.put(None)
                await worker

    def _stop_requested(self, state, event):
        if event.get("start_ms", 0) > getattr(state, "last_transcript_end", 0) + 700:
            state.transcript = ""
        state.transcript = (state.transcript + event.get("delta", ""))[-4000:]
        state.last_transcript_end = event.get("end_ms", 0)
        if state.mode != "solo" or not self.bridge._decider.is_stop_command(state.transcript):
            return False
        with self.bridge.buffers_lock:
            self.bridge._decider.decide(state.source.voice_session_id, state.source.speaker_id,
                state.transcript, authorized=True, consent_confirmed=True, participant_count=1,
                direct_address=True)
        return True

    async def _output(self, state, pcm):
        if not state.accepting_output:
            previous = state.playback
            queue = asyncio.Queue(maxsize=100)
            state.output = queue
            state.output_bytes = 0
            state.accepting_output = True
            state.playback = self._task(self._play(state, queue, previous), "jade-discord-live-output")
        if state.output_bytes + len(pcm) > 240000:
            raise RuntimeError("Discord Live playback backlog exceeded")
        state.output.put_nowait(pcm)
        state.output_bytes += len(pcm)

    async def _play(self, state, queue, previous):
        async def chunks():
            while self._valid(state):
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=1.0)
                except TimeoutError:
                    if state.output is queue:
                        state.accepting_output = False
                    return
                state.output_bytes = max(0, state.output_bytes - len(data))
                yield data
        try:
            if previous and not previous.done():
                await asyncio.gather(previous, return_exceptions=True)
            if not self._valid(state):
                return
            await self.conversation.observe_playback(state.context, {"state": "playing"})
            played = await self.bridge.play_pcm_stream_for_reply(
                chunks(), state.source, max_input_bytes=int(48_000 * self.config.max_session_seconds),
                live_session=state.context["session_id"])
            if played and self._valid(state):
                self.bridge.mark_voice_reply_played(state.source)
                await self.conversation.observe_playback(state.context, {"state": "drained"})
        except asyncio.CancelledError:
            raise
        except Exception:
            if self._valid(state):
                self._task(self._close_session(state, "playback_failed"), "jade-discord-live-playback-close")
        finally:
            if state.output is queue:
                state.accepting_output = False

    def _has_pending_work(self, state):
        if state.pending_control_events:
            return True
        return any(
            not session.closed and session.context["session_id"] == state.context["session_id"]
            and any(not task.done() for task in session.tasks.values())
            for session in self.conversation.sessions.values()
        )

    def _group_finished(self, state):
        return (state.mode == "group" and state.output_seen and not state.input_pcm
                and (state.playback is None or state.playback.done())
                and self.clock() - state.last_output >= 1.0 and not self._has_pending_work(state))

    async def _monitor(self):
        while self._running:
            await asyncio.sleep(self.poll_seconds)
            await self._decision()
            state = self._current
            if state is None:
                continue
            reason = None
            if not self._allow_live:
                reason = "monthly_policy_classic"
            elif not self._valid(state):
                reason = "voice_transport_changed"
            elif self.clock() - state.opened_at >= self.config.max_session_seconds:
                reason = "maximum_duration"
            elif self._group_finished(state):
                reason = "turn_completed"
            elif (not self._has_pending_work(state) and not state.input_pcm
                  and self.clock() - max(state.last_input, state.last_output) >= self.config.idle_close_seconds):
                reason = "idle"
            if reason:
                await self._close_session(state, reason)

    async def _close_session(self, state, reason):
        if state.close_task is not None:
            if state.close_task is not asyncio.current_task():
                await asyncio.shield(state.close_task)
            return
        state.close_task = self._task(self._finish_close(state, reason), "jade-discord-live-close")
        await asyncio.shield(state.close_task)

    async def _finish_close(self, state, reason):
        state.active = False
        state.input_pcm.clear()
        state.interruption_pcm.clear()
        if state.mode == "solo" and reason not in ("idle", "classic_before_start"):
            with self._capture_lock:
                self._suppressed[state.source.speaker_id] = 0
        tasks = [task for task in (state.sender, state.receiver, state.playback)
                 if task is not None and task is not asyncio.current_task() and not task.done()]
        # Provider release precedes all optional persistence and task cleanup.
        for task in tasks:
            task.cancel()
        opening = state.opening
        if opening is not None and not opening.done():
            opening.cancel()
        self.bridge._stop_playback(state.transport.connection)
        # provider.open owns its partial socket until it returns. Wait for that
        # bounded cleanup before inspecting remote; never lose a late session.
        if opening is not None and opening is not asyncio.current_task() and not opening.done():
            await asyncio.wait({opening}, timeout=self.config.close_timeout_seconds + 1.0)
            if not opening.done():
                if state.open_result and state.open_result.get("confirmed") is True:
                    self._block("live_usage_pending")
                else:
                    self._save_outcome(state, {"confirmed": False, "started": True,
                        "session_id": getattr(state.remote, "session_id", None), "usage": {},
                        "reason": "opening_cleanup_unconfirmed"})
        if state.remote is not None:
            try:
                result = await state.remote.close()
                await self._finish_attempt(state, result)
            except Exception:
                await self._finish_attempt(state, {"confirmed": False, "started": True,
                    "session_id": state.remote.session_id, "usage": {}, "reason": "close_unconfirmed"})
        elif state.attempt_started and state.open_result is None:
            self._save_outcome(state, {"confirmed": False, "started": True,
                "session_id": None, "usage": {}, "reason": "opening_cleanup_unconfirmed"})
        if tasks:
            await asyncio.wait(tasks, timeout=2.0)
        try:
            await self.conversation.close_session(state.context, reason)
        finally:
            if self._current is state:
                self._current = None
            self._preroll.clear()
            self._candidate = 0

    async def _publish(self, context, event):
        state = self._current
        if state is None or not self._valid(state) or context["session_id"] != state.context["session_id"]:
            return
        kind = event.get("type")
        delegated = kind == "live_delegation" and event.get("status") == "completed"
        if self.set_avatar_intent is not None and (kind == "live_intent" or delegated):
            self.set_avatar_intent(event.get("intent", "neutral"))
        if not delegated:
            return
        if not event.get("attachments") or self.publish_reply is None:
            return
        identity = event.get("delegation_id")
        if identity in state.delivered:
            return
        # An uncertain send is not retried automatically after an external effect.
        state.delivered.add(identity)
        service = getattr(self.runtime, "document_service", None)
        attachments = []
        if service is not None:
            for record in event["attachments"]:
                item = await asyncio.to_thread(service.store.read, record.get("id", ""))
                if item is not None:
                    attachments.append(item[0])
        if attachments and self._valid(state):
            await _await(self.publish_reply(Reply(state.source,
                "Voici les documents demandés (disponibles pendant 24 h).", attachments=tuple(attachments))))

    async def close(self):
        """Stop this Discord connection; a later connect can call start again."""
        self._running = False
        self._allow_live = False
        if self._watchdog and not self._watchdog.done():
            self._watchdog.cancel()
        if self._current:
            await self._close_session(self._current, "discord_disconnected")
        if self._watchdog:
            await asyncio.gather(self._watchdog, return_exceptions=True)
        self._watchdog = None
        self._preroll.clear()
        self._candidate = 0

    async def transport_changed(self):
        if self._current is not None:
            await self._close_session(self._current, "voice_transport_changed")

    def notify_transport_changed(self):
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(
                    lambda: self._task(self.transport_changed(), "jade-discord-live-transport"))
            except RuntimeError:
                pass

    async def shutdown(self):
        await self.close()
        await self.conversation.close()


async def create_discord_live(bridge, runtime, settings, spend_policy, *,
                              provider=None, publish_reply=None, set_avatar_intent=None):
    """Create local wiring only; no provider connection opens before speech."""
    if not getattr(settings, "discord_enabled", True) or not getattr(settings, "api_key", None):
        return None
    config = settings.live
    try:
        conversation = LiveConversationBridge(runtime,
            journal_path=Path(config.usage_db_path).with_name("jade-discord-live-journal.sqlite3"))
        adapter = DiscordLiveAdapter(bridge, runtime, config, spend_policy,
            provider or DiscordLiveProvider(settings.api_key,
                opening_timeout_seconds=config.opening_timeout_seconds,
                close_timeout_seconds=config.close_timeout_seconds),
            conversation, publish_reply=publish_reply, set_avatar_intent=set_avatar_intent,
            registry=DiscordLiveRegistry(conversation.journal.path))
        conversation.publish = adapter._publish

        async def reserve(context, delegation_id):
            state = adapter._current
            return ("discord-live-" + secrets.token_hex(12)
                    if state is not None and adapter._valid(state) and await adapter._decision() else None)

        conversation.reserve_delegation = reserve
        return adapter
    except (OSError, sqlite3.Error, ValueError):
        LOG.warning("Discord Live local state unavailable; classic voice remains available")
        return None
