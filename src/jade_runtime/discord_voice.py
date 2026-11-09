"""Experimental opt-in Discord PCM transport. STT/TTS remain **OpenAI only**.

Uses discord-ext-voice-recv as an audio *transport*, NOT a recognition engine.
Segments audio with experimental energy-based turn detection. Explicit
informed consent of people in the channel is required
before enabling recording. Never stores received audio to disk.
"""
import asyncio
from dataclasses import dataclass
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
import tempfile
import threading
import time
import secrets
import wave

from .messages import Incoming
from .orchestrator import Work
from .voice_turns import PcmTurnSegmenter
from .voice_decision import ConversationTurnDecider

PCM_CHUNK_BYTES = 48000 * 2 * 2 * 2  # 2 sec × stereo × signed 16-bit
MAX_PENDING_USERS = 12
MAX_TURN_BYTES = 48000 * 4 * 20
MAX_ASSEMBLY_BYTES = 48000 * 4 * 40
MAX_ASSEMBLY_SECONDS = 25


@dataclass(frozen=True, repr=False)
class _VoiceChunk:
    user_id: int
    author: str
    pcm: bytes
    generation: int
    session_id: str
    audio_epoch: int = 0


def pcm_48k_stereo_wav(data: bytes) -> bytes:
    if not data or len(data) % 4:
        raise ValueError("invalid 48 kHz stereo PCM")
    out = BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(data)
    return out.getvalue()


class DiscordVoiceBridge:
    def __init__(self, services, runtime, channel_id: int, *, threshold=550,
                 authorized_user_ids=(), consent_confirmed=False):
        if type(channel_id) is not int or channel_id <= 0:
            raise ValueError("Discord voice channel must be positive")
        self.services, self.runtime = services, runtime
        self.channel_id = channel_id
        self.threshold = threshold
        self.buffers = {}
        self.buffer_updated = {}
        self.buffers_lock = threading.Lock()
        self.lifecycle_lock = asyncio.Lock()
        self.pending = asyncio.Queue(maxsize=8)
        self.worker = None
        self.loop = None
        self.connection = None
        self.seq = 0
        self.generation = 0
        self.authorized_user_ids = frozenset()
        self.consent_confirmed = False
        self.session_id = None
        self.own_bot_id = None
        self._participants = None
        self._transcribing = None
        self._transcribing_generation = None
        self._submitted = []
        self._playback_active = False
        self._audio_epoch = 0
        self._segmenter = PcmTurnSegmenter(max_users=MAX_PENDING_USERS, rms_threshold=threshold)
        self._decider = ConversationTurnDecider()
        self._assemblies = {}
        self._discard_turns = set()
        self._authors = {}
        self._turn_ids = {}
        self._poller = None
        self._scheduled = 0
        if authorized_user_ids or consent_confirmed:
            self.set_session(authorized_user_ids, consent_confirmed=consent_confirmed)

    def set_session(self, authorized_user_ids, *, consent_confirmed, _expected=None):
        """Replace the authorized participants; revoke the prior session immediately.

        The caller must obtain informed consent outside this method. Identity
        display names do not grant permission. A fresh random session also
        prevents conversation history from being reused across sessions.
        """
        if type(consent_confirmed) is not bool or isinstance(authorized_user_ids, (str, bytes)):
            raise ValueError("explicit Discord voice consent and user IDs required")
        try:
            ids = tuple(authorized_user_ids)
        except TypeError:
            raise ValueError("explicit Discord voice consent and user IDs required") from None
        if len(ids) > 100 or any(type(uid) is not int or uid <= 0 for uid in ids):
            raise ValueError("invalid Discord voice user IDs")
        allowed = frozenset(ids) if consent_confirmed else frozenset()
        participants = None
        if allowed and self.connection is not None:
            participants = self._snapshot_humans(
                getattr(self.connection, "channel", None), allowed, self.own_bot_id)
            if participants is None:
                self.set_session([], consent_confirmed=False)
                raise ValueError("Discord voice participants are not authorized")
        with self.buffers_lock:
            if _expected is not None and (self.generation, self.session_id) != _expected:
                return False
            if self.session_id:
                self._decider.revoke(self.session_id)
            self._clear_turns_locked()
            self.generation += 1
            generation = self.generation
            self.buffers.clear()
            self.buffer_updated.clear()
            self.authorized_user_ids = allowed
            self.consent_confirmed = consent_confirmed and bool(allowed)
            self.session_id = secrets.token_hex(16) if self.consent_confirmed else None
            self._participants = participants
            loop = self.loop
            connection = self.connection
        # The prior session is invalidated synchronously. Stop its current audio
        # immediately rather than waiting for STT/worker cleanup or disconnect.
        if connection is not None:
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if loop is not None and running is not loop:
                try:
                    loop.call_soon_threadsafe(self._stop_playback, connection)
                except RuntimeError:
                    pass
            else:
                self._stop_playback(connection)
        if loop is not None:
            try:
                loop.call_soon_threadsafe(self._purge_stale, generation)
                if not allowed:
                    loop.call_soon_threadsafe(self._close_revoked, generation)
            except RuntimeError:
                pass  # A closed loop cannot process more audio.
        return True

    @staticmethod
    def _stop_playback(connection):
        stop = getattr(connection, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                import logging
                logging.getLogger("jade.discord.voice").warning("Discord voice playback stop failed")

    def _close_revoked(self, generation):
        task = asyncio.create_task(self._close_if_revoked(generation))
        def finish(result):
            if not result.cancelled() and result.exception() is not None:
                import logging
                logging.getLogger("jade.discord.voice").warning("Discord voice revocation cleanup failed")
        task.add_done_callback(finish)

    async def _close_if_revoked(self, generation):
        async with self.lifecycle_lock:
            with self.buffers_lock:
                should_close = (generation == self.generation and not self.consent_confirmed
                                and self.connection is not None)
            if should_close:
                await self._close_locked()

    def _allowed(self, user_id, generation, session_id):
        with self.buffers_lock:
            return (self.consent_confirmed and self.session_id == session_id
                    and self.generation == generation and user_id in self.authorized_user_ids)

    @staticmethod
    def _snapshot_allowed(channel, authorized_user_ids, own_bot_id):
        try:
            return DiscordVoiceBridge._snapshot_allowed_checked(channel, authorized_user_ids, own_bot_id)
        except Exception:
            # Voice cache may change concurrently with the audio receiver thread.
            # Missing/inconsistent state or a read error must never permit capture.
            return False

    @staticmethod
    def _snapshot_allowed_checked(channel, authorized_user_ids, own_bot_id):
        members = getattr(channel, "members", None)
        states = getattr(channel, "voice_states", None)
        channel_id = getattr(channel, "id", None)
        if (type(own_bot_id) is not int or own_bot_id <= 0
                or not isinstance(members, (list, tuple)) or not isinstance(states, Mapping)
                or type(channel_id) is not int or channel_id <= 0):
            return False
        state_ids = set()
        for uid, state in states.items():
            if (type(uid) is not int or uid <= 0 or state is None
                    or getattr(getattr(state, "channel", None), "id", None) != channel_id):
                return False
            state_ids.add(uid)
        humans = []
        member_ids = set()
        for member in members:
            bot = getattr(member, "bot", None)
            uid = getattr(member, "id", None)
            if type(bot) is not bool or type(uid) is not int or uid <= 0 or uid in member_ids:
                return False
            member_ids.add(uid)
            if uid == own_bot_id and not bot:
                return False
            if bot and uid != own_bot_id:
                return False
            if not bot:
                humans.append(uid)
        return (state_ids == member_ids and bool(humans)
                and all(uid in authorized_user_ids for uid in humans))

    def _members_authorized(self, channel):
        """Require a complete, non-empty authorized human membership snapshot."""
        with self.buffers_lock:
            allowed = self.authorized_user_ids if self.consent_confirmed else frozenset()
            own_bot_id = self.own_bot_id
        return bool(allowed) and self._snapshot_allowed(channel, allowed, own_bot_id)

    @staticmethod
    def _snapshot_humans(channel, allowed, own_bot_id):
        if not DiscordVoiceBridge._snapshot_allowed(channel, allowed, own_bot_id):
            return None
        try:
            humans = frozenset(member.id for member in channel.members if not member.bot)
            if (not DiscordVoiceBridge._snapshot_allowed(channel, allowed, own_bot_id)
                    or humans != frozenset(member.id for member in channel.members if not member.bot)):
                return None
            return humans
        except Exception:
            return None

    def _capture_authorized(self, user_id, generation=None, session_id=None, audio_epoch=None):
        """Recheck the entire channel before buffering, queuing and STT.

        Called on the Discord audio thread as well as the event loop. A cache
        read exception or an unresolved/new participant revokes the session;
        no provider or cache exception is exposed.
        """
        with self.buffers_lock:
            if (not self.consent_confirmed or self._playback_active
                    or (generation is not None and generation != self.generation)
                    or (session_id is not None and session_id != self.session_id)
                    or (audio_epoch is not None and audio_epoch != self._audio_epoch)):
                return False
            observed_generation = self.generation
            observed_session = self.session_id
            connection = self.connection
            allowed = self.authorized_user_ids
            own_bot_id = self.own_bot_id
            participants = self._participants
        try:
            humans = (self._snapshot_humans(getattr(connection, "channel", None), allowed, own_bot_id)
                      if connection is not None else None)
            valid = (humans is not None and user_id in humans
                     and (participants is None or participants == humans))
        except Exception:
            valid = False
        if not valid:
            self.set_session([], consent_confirmed=False,
                             _expected=(observed_generation, observed_session))
            return False
        with self.buffers_lock:
            if (self._participants is None and self.generation == observed_generation
                    and self.session_id == observed_session and self.connection is connection):
                self._participants = humans
            return (self.consent_confirmed and not self._playback_active
                    and (audio_epoch is None or audio_epoch == self._audio_epoch)
                    and self.generation == observed_generation
                    and self.session_id == observed_session and self.connection is connection
                    and user_id in self.authorized_user_ids and self._participants == humans)

    def _playback_authorized(self, connection, generation, session_id):
        with self.buffers_lock:
            if (not self.consent_confirmed or self.generation != generation
                    or self.session_id != session_id or self.connection is not connection):
                return False
            allowed = self.authorized_user_ids
            own_bot_id = self.own_bot_id
            participants = self._participants
        humans = self._snapshot_humans(getattr(connection, "channel", None), allowed, own_bot_id)
        if not allowed or humans is None or (participants is not None and participants != humans):
            self.set_session([], consent_confirmed=False, _expected=(generation, session_id))
            return False
        with self.buffers_lock:
            if (self._participants is None and self.generation == generation
                    and self.session_id == session_id and self.connection is connection):
                self._participants = humans
            return (self.consent_confirmed and self.generation == generation
                    and self.session_id == session_id and self.connection is connection
                    and self._participants == humans)

    async def _require_playback_authorization(self, connection, generation, session_id):
        if not self._playback_authorized(connection, generation, session_id):
            self.set_session([], consent_confirmed=False, _expected=(generation, session_id))
            async with self.lifecycle_lock:
                with self.buffers_lock:
                    revoked = (self.generation == generation + 1 and not self.consent_confirmed
                               and self.session_id is None and self.connection is connection)
                if revoked:
                    await self._close_locked()
            raise PermissionError("Discord voice playback authorization is no longer valid")

    async def voice_state_changed(self, member, before, after, *, own_bot_id=None):
        """Revoke on human membership changes or this bot leaving the channel."""
        bot = getattr(member, "bot", None)
        before_id = getattr(getattr(before, "channel", None), "id", None)
        after_id = getattr(getattr(after, "channel", None), "id", None)
        if before_id == after_id or self.channel_id not in (before_id, after_id):
            return
        if (bot is True and type(own_bot_id) is int
                and getattr(member, "id", None) == own_bot_id and after_id == self.channel_id):
            return  # This bot joining is the expected completion of connect().
        with self.buffers_lock:
            active = self.consent_confirmed
            generation, session_id = self.generation, self.session_id
        if active:
            revoked = self.set_session([], consent_confirmed=False,
                                       _expected=(generation, session_id))
            if revoked:
                await self._close_if_revoked(generation + 1)

    def _purge_stale(self, generation):
        """Drop revoked queued audio and cancel any no-longer-authorized STT."""
        with self.buffers_lock:
            if generation != self.generation:
                return
            if self._transcribing is not None and self._transcribing_generation != generation:
                self._transcribing.cancel()
            retained_work = []
            for work_generation, work in self._submitted:
                if work_generation != generation:
                    self.runtime.cancel_work(work)
                else:
                    retained_work.append((work_generation, work))
            self._submitted = retained_work
            retained = []
            while True:
                try:
                    item = self.pending.get_nowait()
                except asyncio.QueueEmpty:
                    break
                self.pending.task_done()
                if isinstance(item, _VoiceChunk) and item.generation == generation:
                    retained.append(item)
            for item in retained:
                self.pending.put_nowait(item)

    def _clear_turns_locked(self):
        self._segmenter.revoke()
        self._assemblies.clear()
        self._discard_turns.clear()
        self._authors.clear()
        self._turn_ids.clear()

    def _collect_turns_locked(self, turns, now):
        """Join partials under fixed per-turn, aggregate and time limits."""
        ready = []
        for turn in turns:
            uid = int(turn.user_id)
            if uid in self._discard_turns:
                if not turn.partial:
                    self._discard_turns.discard(uid)
                continue
            previous = self._assemblies.get(uid)
            if previous is None:
                started, data = now, bytearray()
            else:
                started, data = previous
            used = sum(len(value[1]) for value in self._assemblies.values())
            if (now - started > MAX_ASSEMBLY_SECONDS
                    or len(data) + len(turn.pcm) > MAX_TURN_BYTES
                    or used + len(turn.pcm) > MAX_ASSEMBLY_BYTES):
                self._assemblies.pop(uid, None)
                if turn.partial:
                    self._discard_turns.add(uid)
                continue
            data.extend(turn.pcm)
            if turn.partial:
                self._assemblies[uid] = (started, data)
            else:
                self._assemblies.pop(uid, None)
                author = self._authors.get(uid)
                if data and author:
                    ready.append(_VoiceChunk(uid, author, bytes(data), self.generation,
                                             self.session_id, self._audio_epoch))
        for turn in turns:
            uid = int(turn.user_id)
            if (turn.user_id not in self._segmenter._users and uid not in self._assemblies
                    and uid not in self._discard_turns):
                self._authors.pop(uid, None)
        return ready

    async def _poll_turns(self):
        while True:
            await asyncio.sleep(.1)
            with self.buffers_lock:
                users = list(self._segmenter._users)
                generation, session_id, epoch = self.generation, self.session_id, self._audio_epoch
            if not users or not all(self._capture_authorized(int(uid), generation, session_id, epoch)
                                    for uid in users):
                continue
            with self.buffers_lock:
                if (self.generation != generation or self.session_id != session_id
                        or self._audio_epoch != epoch or self._playback_active):
                    continue
                ready = self._collect_turns_locked(self._segmenter.poll(), time.monotonic())
                for uid in users:
                    if uid not in self._segmenter._users and int(uid) not in self._assemblies:
                        self._authors.pop(int(uid), None)
            for item in ready:
                self._accept(item)

    def _accept(self, item):
        if (not self._capture_authorized(item.user_id, item.generation, item.session_id, item.audio_epoch)
                or self.worker is None or self.worker.done()):
            return
        with self.buffers_lock:
            if (not self.consent_confirmed or self._playback_active
                    or item.generation != self.generation or item.session_id != self.session_id
                    or item.audio_epoch != self._audio_epoch
                    or item.user_id not in self.authorized_user_ids):
                return
            if self.pending.full():
                return  # Bound memory; drop overload rather than block receiver.
            self.pending.put_nowait(item)

    def _accept_scheduled(self, item):
        try:
            self._accept(item)
        finally:
            with self.buffers_lock:
                self._scheduled -= 1

    def receive_pcm(self, user_id: int, author: str, pcm: bytes):
        """Called by the voice receive thread, never blocks on OpenAI/network."""
        if (type(user_id) is not int or user_id <= 0 or not author
                or not isinstance(pcm, bytes) or len(pcm) % 4):
            return
        with self.buffers_lock:
            observed_generation = self.generation
            observed_session = self.session_id
            observed_audio_epoch = self._audio_epoch
        if not self._capture_authorized(user_id, observed_generation,
                                        observed_session, observed_audio_epoch):
            return
        with self.buffers_lock:
            if (not self.consent_confirmed or self._playback_active
                    or self.generation != observed_generation
                    or self.session_id != observed_session
                    or self._audio_epoch != observed_audio_epoch
                    or user_id not in self.authorized_user_ids):
                return
            now = time.monotonic()
            self._authors[user_id] = author
            try:
                turns = self._segmenter.feed(str(user_id), pcm[:PCM_CHUNK_BYTES], now=now)
            except ValueError:
                self._authors.pop(user_id, None)
                return
            ready = self._collect_turns_locked(turns, now)
            if str(user_id) not in self._segmenter._users and user_id not in self._assemblies:
                self._authors.pop(user_id, None)
            loop = self.loop
        if loop is not None:
            for item in ready:
                with self.buffers_lock:
                    if self._scheduled >= 8:
                        continue
                    self._scheduled += 1
                try:
                    loop.call_soon_threadsafe(self._accept_scheduled, item)
                except RuntimeError:
                    with self.buffers_lock:
                        self._scheduled -= 1

    async def _transcribe_authorized(self, item):
        # Recheck when the task actually begins: session revocation can run
        # after task creation but before the coroutine gets CPU time.
        if not self._capture_authorized(item.user_id, item.generation,
                                        item.session_id, item.audio_epoch):
            return None
        return await self.services.transcribe_wav(pcm_48k_stereo_wav(item.pcm))

    async def _consume(self):
        while True:
            item = await self.pending.get()
            try:
                if item is None:
                    return
                if (not isinstance(item, _VoiceChunk)
                        or not self._capture_authorized(item.user_id, item.generation, item.session_id, item.audio_epoch)):
                    continue
                self._transcribing_generation = item.generation
                self._transcribing = asyncio.create_task(self._transcribe_authorized(item))
                try:
                    value = await self._transcribing
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        raise
                    continue  # Revocation cancels this STT, not the session worker.
                finally:
                    self._transcribing = None
                    self._transcribing_generation = None
                if value and self._capture_authorized(item.user_id, item.generation, item.session_id, item.audio_epoch):
                    channel = getattr(self.connection, 'channel', None)
                    try:
                        humans = frozenset(member.id for member in channel.members if not member.bot)
                    except Exception:
                        continue
                    if not self._capture_authorized(item.user_id, item.generation,
                                                    item.session_id, item.audio_epoch):
                        continue
                    try:
                        if humans != frozenset(member.id for member in channel.members if not member.bot):
                            continue
                    except Exception:
                        continue
                    with self.buffers_lock:
                        if (not self.consent_confirmed or self._playback_active
                                or item.generation != self.generation or item.session_id != self.session_id
                                or item.audio_epoch != self._audio_epoch):
                            continue
                        decision = self._decider.decide(
                            item.session_id, item.user_id, value, authorized=True,
                            consent_confirmed=True, participant_count=len(humans))
                    if not decision.should_reply:
                        if decision.reason == 'muted':
                            for _, work in self._submitted:
                                self.runtime.cancel_work(work)
                            self._submitted.clear()
                            with self.buffers_lock:
                                self._turn_ids.clear()
                        continue
                    self.seq += 1
                    message_id = f"discord-voice-{self.seq}"
                    with self.buffers_lock:
                        if (not self.consent_confirmed or self._playback_active
                                or item.generation != self.generation or item.session_id != self.session_id
                                or item.audio_epoch != self._audio_epoch):
                            continue
                        if len(self._turn_ids) >= 8:
                            self._turn_ids.pop(next(iter(self._turn_ids)))
                        self._turn_ids[message_id] = (item.session_id, item.user_id, decision.turn_id)
                    work = await self.runtime.submit(Incoming(
                        "discord_voice", item.author, value,
                        channel=str(self.channel_id),
                        message_id=message_id, force_reply=True,
                        speaker_id=item.user_id, voice_session_id=item.session_id))
                    if isinstance(work, Work):
                        self._submitted = [(generation, previous) for generation, previous in self._submitted
                                           if not previous.cancelled and (previous.task is None or not previous.task.done())]
                        self._submitted.append((item.generation, work))
                        if not self._allowed(item.user_id, item.generation, item.session_id):
                            self.runtime.cancel_work(work)
            except asyncio.CancelledError:
                raise
            except Exception:
                import logging
                logging.getLogger("jade.discord.voice").warning(
                    "Discord voice chunk dropped after STT or delivery failure")
            finally:
                self.pending.task_done()

    async def connect(self, client):
        async with self.lifecycle_lock:
            await self._connect_locked(client)

    async def _connect_locked(self, client):
        if self.connection is not None:
            return
        with self.buffers_lock:
            if not self.consent_confirmed or not self.authorized_user_ids or not self.session_id:
                raise ValueError("Discord voice requires explicit consent and authorized users")
            own_bot_id = getattr(getattr(client, "user", None), "id", None)
            if type(own_bot_id) is not int or own_bot_id <= 0:
                raise ValueError("Discord bot identity is not available")
            generation = self.generation
            self.own_bot_id = own_bot_id
        try:
            from discord.ext import voice_recv
        except ImportError as exc:
            raise RuntimeError("install optional discord-voice extra") from exc
        channel = client.get_channel(self.channel_id)
        if channel is None or not hasattr(channel, "connect"):
            raise ValueError("configured Discord voice channel not available")
        with self.buffers_lock:
            allowed, own_bot_id = self.authorized_user_ids, self.own_bot_id
        participants = self._snapshot_humans(channel, allowed, own_bot_id)
        if participants is None:
            raise ValueError("Discord voice participants are not authorized")
        with self.buffers_lock:
            if self.generation != generation or not self.consent_confirmed:
                raise ValueError("Discord voice authorization changed during connection")
            self._participants = participants
        connection = await channel.connect(cls=voice_recv.VoiceRecvClient)
        with self.buffers_lock:
            valid = (self.generation == generation and self.consent_confirmed
                     and bool(self.authorized_user_ids) and self.session_id is not None)
        if (not valid or self._snapshot_humans(channel, allowed, own_bot_id) != participants):
            await asyncio.wait_for(connection.disconnect(), timeout=2)
            raise ValueError("Discord voice authorization changed during connection")
        self.loop = asyncio.get_running_loop()
        bridge = self

        class Sink(voice_recv.AudioSink):
            def wants_opus(self):
                return False
            def write(self, user, data):
                if user is None or getattr(user, "bot", False):
                    return
                pcm = getattr(data, "pcm", None)
                if pcm:
                    bridge.receive_pcm(
                        user.id, getattr(user, "display_name", str(user)), bytes(pcm))
            def cleanup(self):
                pass

        try:
            self.worker = asyncio.create_task(self._consume(), name="jade-discord-voice")
            self._poller = asyncio.create_task(self._poll_turns(), name="jade-discord-turn-poll")
            self.connection = connection
            connection.listen(Sink())
        except BaseException:
            await self._close_locked()
            raise

    def reply_authorized(self, source):
        """Check the source and current session before any reply side effect."""
        speaker_id = getattr(source, "speaker_id", None)
        session_id = getattr(source, "voice_session_id", "")
        if (getattr(source, "platform", None) != "discord_voice"
                or getattr(source, "channel", None) != str(self.channel_id)
                or type(speaker_id) is not int or speaker_id <= 0 or not session_id):
            return False
        with self.buffers_lock:
            connection, generation = self.connection, self.generation
            if (connection is None or self.session_id != session_id
                    or speaker_id not in self.authorized_user_ids
                    or (self._participants is not None and speaker_id not in self._participants)):
                return False
        if not self._playback_authorized(connection, generation, session_id):
            return False
        with self.buffers_lock:
            return (self.generation == generation and self.session_id == session_id
                    and self._participants is not None and speaker_id in self._participants)

    async def play_for_reply(self, wav: bytes, source):
        """Play only a reply from an authorized speaker in the active session."""
        speaker_id = getattr(source, "speaker_id", None)
        session_id = getattr(source, "voice_session_id", "")
        if not self.reply_authorized(source):
            raise PermissionError("Discord voice reply source is not authorized")
        return await self.play(wav, expected_session=session_id, expected_speaker=speaker_id)

    def mark_voice_reply_played(self, source):
        """Acknowledge a successfully played reply in its still-valid session."""
        if not self.reply_authorized(source):
            return False
        with self.buffers_lock:
            entry = self._turn_ids.pop(getattr(source, 'message_id', ''), None)
            if (entry is None or entry[0] != self.session_id
                    or entry[0] != getattr(source, 'voice_session_id', None)
                    or entry[1] != getattr(source, 'speaker_id', None)):
                return False
            return self._decider.mark_replied(entry[0], entry[2])

    def _begin_playback(self, connection, generation, session_id):
        """Invalidate buffered input before starting a half-duplex response."""
        with self.buffers_lock:
            if (not self.consent_confirmed or self.generation != generation
                    or self.session_id != session_id or self.connection is not connection):
                raise PermissionError("Discord voice playback authorization is no longer valid")
            if self._playback_active:
                raise RuntimeError("Discord voice playback already active")
            self._playback_active = True
            self._audio_epoch += 1
            self.buffers.clear()
            self.buffer_updated.clear()
            self._segmenter.revoke()
            self._assemblies.clear()
            self._discard_turns.clear()
            self._authors.clear()
        if self._transcribing is not None:
            self._transcribing.cancel()
        while True:
            try:
                self.pending.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self.pending.task_done()

    def _end_playback(self):
        with self.buffers_lock:
            self._audio_epoch += 1
            self._playback_active = False

    async def play(self, wav: bytes, *, expected_session=None, expected_speaker=None):
        """Optional playback of OpenAI-generated WAV, never a TTS engine."""
        connection = self.connection
        if connection is None:
            return False
        with self.buffers_lock:
            generation, session_id = self.generation, self.session_id
            if (expected_session is not None and
                    (session_id != expected_session or expected_speaker not in self.authorized_user_ids)):
                raise PermissionError("Discord voice reply is from another session")
        await self._require_playback_authorization(connection, generation, session_id)
        self._begin_playback(connection, generation, session_id)
        path = None
        source = None
        try:
            import discord
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
                fp.write(wav)
                path = Path(fp.name)
            if connection.is_playing():
                # Caller serializes Jade voice; refuse overlapping attempts.
                return False
            source = discord.FFmpegPCMAudio(str(path))
            done = asyncio.Event()
            failure = []
            loop = asyncio.get_running_loop()
            def after(err):
                if err is not None:
                    failure.append(err)
                loop.call_soon_threadsafe(done.set)
            await self._require_playback_authorization(connection, generation, session_id)
            connection.play(
                source, after=after)
            await asyncio.wait_for(done.wait(), timeout=120)
            if failure:
                raise RuntimeError("Discord audio playback failed")
            await self._require_playback_authorization(connection, generation, session_id)
            return True
        finally:
            try:
                if source is not None:
                    try:
                        connection.stop()
                    finally:
                        source.cleanup()
            finally:
                try:
                    if path is not None:
                        path.unlink(missing_ok=True)
                finally:
                    self._end_playback()

    async def close(self):
        async with self.lifecycle_lock:
            await self._close_locked()

    async def _close_locked(self):
        poller, self._poller = self._poller, None
        worker, self.worker = self.worker, None
        with self.buffers_lock:
            connection, self.connection = self.connection, None
            if self.session_id:
                self._decider.revoke(self.session_id)
            self._clear_turns_locked()
            self.generation += 1
            self.loop = None
            self.authorized_user_ids = frozenset()
            self.consent_confirmed = False
            self.session_id = None
            self.own_bot_id = None
            self._participants = None
        if connection is not None:
            self._stop_playback(connection)
            try:
                connection.stop_listening()
            except Exception:
                import logging
                logging.getLogger("jade.discord.voice").warning("Discord listener cleanup failed")
        for _, work in self._submitted:
            self.runtime.cancel_work(work)
        self._submitted.clear()
        if worker is not None:
            worker.cancel()
        if poller is not None:
            poller.cancel()
            await asyncio.gather(poller, return_exceptions=True)
        if worker is not None:
            try:
                await asyncio.wait_for(asyncio.gather(worker, return_exceptions=True), timeout=2)
            except TimeoutError:
                pass
        while True:
            try:
                self.pending.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self.pending.task_done()
        with self.buffers_lock:
            self.buffers.clear()
            self.buffer_updated.clear()
        if connection is not None:
            await asyncio.wait_for(connection.disconnect(), timeout=2)
