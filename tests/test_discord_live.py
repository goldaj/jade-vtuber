"""Discord Live routing: real voice gate, synthetic PCM and inert providers."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from src.jade_runtime.discord_live import DiscordLiveAdapter, DiscordLiveRegistry
from src.jade_runtime.discord_pcm import DiscordPCMBuffer
from src.jade_runtime.discord_live_policy import DiscordLiveSpendPolicy
from src.jade_runtime.discord_voice import OpenVoiceBridge
from src.jade_runtime.live_config import LiveConfig
from src.jade_runtime.live_provider import LiveProviderError
from src.jade_runtime.messages import Incoming


def pcm(seconds, value=1800):
    return struct.pack("<hh", value, value) * int(48000 * seconds)


async def until(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(.002)


class Remote:
    def __init__(self, identifier):
        self.session_id = identifier
        self.events = asyncio.Queue()
        self.audio = []
        self.commands = []
        self.closed = False
        self.confirmed = True

    async def send_audio(self, data):
        if self.closed:
            raise RuntimeError("closed")
        self.audio.append(data)
        # Synthetic provider only; production pacing is tested independently.
        await asyncio.sleep(.002)

    async def send(self, event):
        self.commands.append(event)

    def __aiter__(self):
        return self

    async def __anext__(self):
        event = await self.events.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def close(self):
        self.closed = True
        self.events.put_nowait(None)
        return {"confirmed": self.confirmed, "session_id": self.session_id,
                "usage": {"seconds": 1}, "reason": "close_requested"}


class Provider:
    def __init__(self):
        self.calls = []
        self.sessions = []
        self.error = None
        self.block = None

    async def open(self, config):
        self.calls.append(config)
        if self.block:
            await self.block.wait()
        if self.error:
            raise self.error
        remote = Remote("live-discord-" + str(len(self.sessions)))
        self.sessions.append(remote)
        return remote


class Conversation:
    def __init__(self):
        self.prepared = []
        self.opened = []
        self.closed = []
        self.events = []
        self.played = []
        self.sessions = {}

    async def prepare_context(self, owner, thread, *, source):
        self.prepared.append((owner, thread, source))
        return {"instructions": "Tu es Jade.", "input": []}

    async def open_session(self, context):
        self.opened.append(context)

    async def handle_event(self, event, context, send):
        self.events.append((event, context))

    async def observe_playback(self, context, event):
        self.played.append(event)

    async def close_session(self, context, reason):
        self.closed.append((context, reason))

    async def close(self):
        pass


class Policy:
    def __init__(self):
        self.allowed = True
        self.reserve_allowed = True
        self.guard_refused = False
        self.records = []
        self.reservations = []
        self.bindings = []
        self.settled = []

    async def decision(self):
        return {"allow_live": self.allowed and not self.guard_refused,
                "reason": ("live_reservation_insufficient" if self.guard_refused else
                           "under_monthly_limit" if self.allowed else "monthly_limit")}

    async def record_live_usage(self, session_id, usage, *, model):
        self.records.append((session_id, usage, model))

    async def reserve_live(self, attempt, **kwargs):
        self.reservations.append((attempt, kwargs))
        self.guard_refused = not self.reserve_allowed
        return {"allow_live": self.allowed and self.reserve_allowed,
                "reservation_id": attempt, "reason": "reserved" if self.reserve_allowed else "live_reservation_insufficient"}

    async def bind_live(self, attempt, session_id):
        self.bindings.append((attempt, session_id))

    async def settle_live(self, attempt, *, confirmed, never_started, session_id, usage, model):
        self.settled.append((attempt, confirmed, never_started, session_id))
        if not never_started and session_id:
            await self.record_live_usage(session_id, usage, model=model)


class DiscordLiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.channel = SimpleNamespace(id=45, guild=SimpleNamespace(id=123),
            members=[SimpleNamespace(id=12, bot=False)])
        self.connection = SimpleNamespace(channel=self.channel, is_playing=lambda: False,
            stop=Mock(), stop_playing=Mock(), stop_listening=Mock(), disconnect=AsyncMock())
        self.runtime = SimpleNamespace(submit=AsyncMock(), cancel_work=Mock())
        self.services = SimpleNamespace(transcribe_wav=AsyncMock(return_value="Salut Jade !"))
        self.bridge = OpenVoiceBridge(self.services, self.runtime, 45, group_reply_rate=0)
        self.bridge.connection = self.connection
        self.bridge.own_bot_id = 100
        self.bridge.generation = 1
        self.bridge.session_id = "voice-session-0123456789"
        self.bridge.consent_confirmed = True
        self.bridge.loop = asyncio.get_running_loop()
        self.bridge.worker = asyncio.create_task(self.bridge._consume())
        self.played = []

        async def play(chunks, source, **kwargs):
            # Traverse the real bounded PCM constructor: the adapter's float
            # duration must become a valid integer byte cap for Live playback.
            buffer = DiscordPCMBuffer(max_input_bytes=kwargs["max_input_bytes"])
            async for data in chunks:
                await buffer.feed(data)
                while not buffer._frames.empty():
                    self.assertEqual(len(buffer.read()), 3840)
                self.played.append((data, source))
            await buffer.finish()
            return True

        self.bridge.play_pcm_stream_for_reply = AsyncMock(side_effect=play)
        self.provider, self.policy, self.conversation = Provider(), Policy(), Conversation()
        self.directory = tempfile.TemporaryDirectory()
        self.registry = DiscordLiveRegistry(Path(self.directory.name) / "live.sqlite3")
        self.adapter = DiscordLiveAdapter(self.bridge, self.runtime, LiveConfig(), self.policy,
            self.provider, self.conversation, registry=self.registry, poll_seconds=.01)
        self.bridge.live = self.adapter
        await self.adapter.start()

    async def asyncTearDown(self):
        await self.bridge.close()
        await self.adapter.shutdown()
        if self.adapter._tasks:
            await asyncio.wait(tuple(self.adapter._tasks), timeout=2)
        self.directory.cleanup()

    async def start_solo(self):
        count = len(self.provider.sessions)
        self.bridge.receive_pcm(12, "Alice", pcm(.08))
        await until(lambda: len(self.provider.sessions) > count and self.provider.sessions[-1].audio)
        return self.provider.sessions[-1]

    def group(self):
        self.channel.members.append(SimpleNamespace(id=13, bot=False))

    def source(self, user_id=12):
        return Incoming("discord_voice", "Alice" if user_id == 12 else "Bob", "Salut Jade !",
            channel="45", speaker_id=user_id, voice_session_id=self.bridge.session_id,
            conversation_id=self.bridge.voice_conversation_id(user_id, self.bridge.session_id),
            force_reply=True, message_id="test-" + str(user_id))

    async def utterance(self, text):
        self.services.transcribe_wav.return_value = text
        self.bridge.receive_pcm(12, "Alice", pcm(.25) + pcm(.8, 0))
        await asyncio.sleep(.03)
        await asyncio.wait_for(self.bridge.pending.join(), 1)

    async def test_start_and_silence_are_free_then_solo_streams_verified_pcm(self):
        self.assertEqual(self.provider.calls, [])
        self.bridge.receive_pcm(12, "Alice", pcm(.2, 0))
        await asyncio.sleep(.01)
        self.assertEqual(self.provider.calls, [])
        remote = await self.start_solo()
        self.services.transcribe_wav.assert_not_awaited()
        self.runtime.submit.assert_not_awaited()
        self.assertEqual(len(remote.audio[0]), 960)
        owner, thread, source = self.conversation.prepared[0]
        self.assertEqual(owner, "discord:12")
        self.assertEqual(source.speaker_id, 12)
        self.assertEqual(source.conversation_id, thread)
        self.assertEqual(source.platform, "discord_voice")
        self.assertEqual(self.policy.records[0][1], {"seconds": 0})
        # Discord can stop emitting RTP silence: output must not remain muted
        # forever just because the final received frame contained speech.
        state = self.adapter._current
        state.last_capture -= 1
        remote.events.put_nowait({"type": "session.output_audio.delta", "pcm": b"\1\0" * 480})
        await until(lambda: bool(self.played))
        self.assertEqual(self.played[0][1].speaker_id, 12)

    async def test_group_requires_existing_gate_and_never_sends_sampled_out_audio(self):
        self.group()
        await self.utterance("Une conversation entre nous")
        self.assertEqual(self.services.transcribe_wav.await_count, 1)
        self.assertEqual(self.provider.calls, [])
        self.runtime.submit.assert_not_awaited()
        await self.utterance("Jade, comment vas-tu ?")
        await until(lambda: self.provider.sessions and self.provider.sessions[-1].audio)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.adapter._current.mode, "group")
        self.runtime.submit.assert_not_awaited()

    async def test_policy_classic_preserves_existing_solo_pipeline(self):
        self.policy.allowed = False
        await self.adapter._decision()
        await self.utterance("Bonjour Jade")
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.runtime.submit.await_count, 1)

    async def test_threshold_stops_live_without_replaying_partial_turn(self):
        remote = await self.start_solo()
        self.policy.allowed = False
        await until(lambda: remote.closed and self.adapter._current is None)
        self.bridge.receive_pcm(12, "Alice", pcm(.2))
        await asyncio.sleep(.01)
        self.services.transcribe_wav.assert_not_awaited()
        self.bridge.receive_pcm(12, "Alice", pcm(.7, 0))
        await self.utterance("Un nouveau tour classique")
        self.assertEqual(self.runtime.submit.await_count, 1)
        self.assertEqual(len(self.provider.calls), 1)

    async def test_presence_change_closes_before_group_and_does_not_disconnect(self):
        remote = await self.start_solo()
        self.group()
        await self.bridge.voice_state_changed(SimpleNamespace(id=13, bot=False),
            SimpleNamespace(channel=None), SimpleNamespace(channel=self.channel), own_bot_id=100)
        self.assertTrue(remote.closed)
        self.assertIsNone(self.adapter._current)
        self.assertIs(self.bridge.connection, self.connection)
        self.connection.disconnect.assert_not_awaited()

    async def test_two_group_speakers_close_previous_identity_before_next(self):
        self.group()
        self.assertTrue(await self.adapter.handle_turn(self.source(12), pcm(.1)))
        await until(lambda: bool(self.provider.sessions))
        first = self.provider.sessions[0]
        following = asyncio.create_task(self.adapter.handle_turn(self.source(13), pcm(.1)))
        await asyncio.sleep(.02)
        self.assertFalse(following.done())
        self.assertFalse(first.closed)
        first.events.put_nowait({"type": "session.output_audio.delta", "pcm": b"\1\0" * 480})
        self.assertTrue(await asyncio.wait_for(following, 2))
        await until(lambda: len(self.provider.sessions) == 2)
        self.assertTrue(first.closed)
        self.assertEqual(self.conversation.prepared[-1][0], "discord:13")
        self.assertNotEqual(self.conversation.prepared[0][1], self.conversation.prepared[1][1])

    async def test_uncertain_open_is_not_replayed_and_disables_further_live(self):
        self.provider.error = LiveProviderError("live_failed", ambiguous=True)
        self.bridge.receive_pcm(12, "Alice", pcm(.08))
        await until(lambda: self.adapter._current is None and self.provider.calls)
        self.assertTrue(self.adapter._blocked)
        self.assertEqual(self.registry.pending()["phase"], "unknown")
        self.runtime.submit.assert_not_awaited()
        self.services.transcribe_wav.assert_not_awaited()

    async def test_unconfirmed_close_blocks_live_but_not_classic(self):
        remote = await self.start_solo()
        remote.confirmed = False
        await self.adapter.transport_changed()
        self.assertTrue(self.adapter._blocked)
        self.bridge.receive_pcm(12, "Alice", pcm(.7, 0))
        await self.utterance("Bonjour à nouveau")
        self.assertEqual(self.runtime.submit.await_count, 1)
        self.assertEqual(len(self.provider.calls), 1)

    async def test_disconnect_during_open_cancels_without_late_media_or_replay(self):
        self.provider.block = asyncio.Event()
        self.bridge.receive_pcm(12, "Alice", pcm(.08))
        await until(lambda: bool(self.provider.calls))
        await self.adapter.close()
        self.provider.block.set()
        await asyncio.sleep(.01)
        self.assertEqual(self.provider.sessions, [])
        self.assertIsNone(self.adapter._current)
        self.runtime.submit.assert_not_awaited()

    async def _cancel_open(self, *, confirmed, started=True):
        async def pending_open(config):
            self.provider.calls.append(config)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError as error:
                error.close_result = {"confirmed": confirmed, "started": started,
                    "session_id": "live-cancelled" if started else None,
                    "usage": {"seconds": 2} if started else {}, "reason": "cancelled"}
                error.ambiguous = started and not confirmed
                raise
        self.provider.open = pending_open
        self.bridge.receive_pcm(12, "Alice", pcm(.08))
        await until(lambda: bool(self.provider.calls))
        self.assertEqual(self.registry.pending()["phase"], "opening")
        await self.adapter.close()

    async def test_cancelled_creation_with_terminal_clears_durable_attempt(self):
        await self._cancel_open(confirmed=True)
        self.assertIsNone(self.registry.pending())
        self.assertFalse(self.adapter._blocked)
        self.assertEqual(self.policy.records[-1][:2], ("live-cancelled", {"seconds": 2}))

    async def test_cancelled_before_session_start_does_not_claim_paid_session(self):
        await self._cancel_open(confirmed=False, started=False)
        self.assertIsNone(self.registry.pending())
        self.assertFalse(self.adapter._blocked)
        self.assertEqual(self.policy.records, [])

    async def test_cancelled_creation_without_terminal_persists_across_restart(self):
        await self._cancel_open(confirmed=False)
        self.assertEqual(self.registry.pending()["provider_id"], "live-cancelled")
        self.assertTrue(self.adapter._blocked)
        old_attempt = self.registry.pending()["attempt"]
        await self.adapter.shutdown()
        self.provider = Provider()
        self.provider.reconcile_close = AsyncMock(return_value={"confirmed": False,
            "session_id": "live-cancelled", "usage": {}, "reason": "close_unconfirmed"})
        self.adapter = DiscordLiveAdapter(self.bridge, self.runtime, LiveConfig(), self.policy,
            self.provider, self.conversation, registry=DiscordLiveRegistry(self.registry.path),
            poll_seconds=.01)
        self.bridge.live = self.adapter
        await self.adapter.start()
        self.provider.reconcile_close.assert_awaited_once_with("live-cancelled")
        self.assertEqual(self.registry.pending()["attempt"], old_attempt)
        await self.utterance("Un nouveau tour classique")
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.runtime.submit.await_count, 1)

    async def test_restart_known_id_only_reconciles_and_never_replays_audio(self):
        await self.adapter.close()
        self.assertTrue(self.registry.begin("previous-process"))
        self.registry.identified("previous-process", "live-old")
        self.provider.reconcile_close = AsyncMock(return_value={"confirmed": True,
            "session_id": "live-old", "usage": {"seconds": 3}, "reason": "session.closed"})
        self.adapter._recovery_checked = False
        await self.adapter.start()
        self.provider.reconcile_close.assert_awaited_once_with("live-old")
        self.assertEqual(self.provider.calls, [])
        self.assertIsNone(self.registry.pending())
        self.assertTrue(self.adapter._allow_live)
        await self.start_solo()
        self.assertEqual(len(self.provider.calls), 1)

    async def test_restart_without_id_retains_unknown_and_keeps_classic(self):
        await self.adapter.close()
        self.assertTrue(self.registry.begin("lost-before-id"))
        self.provider.reconcile_close = AsyncMock()
        self.adapter._recovery_checked = False
        await self.adapter.start()
        self.assertFalse(self.adapter._allow_live)
        self.provider.reconcile_close.assert_not_awaited()
        self.assertEqual(self.registry.pending()["attempt"], "lost-before-id")
        await self.utterance("Bonjour en classique")
        self.assertEqual(self.runtime.submit.await_count, 1)
        self.assertEqual(self.provider.calls, [])

    async def test_final_usage_survives_cancellation_and_recovery_never_replays_audio(self):
        await self.adapter.close()
        state = self.adapter._new(self.source(), "group")
        state.attempt_started = True
        self.assertTrue(self.registry.begin(state.attempt_id))
        entered = asyncio.Event()

        async def blocked_record(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        self.policy.record_live_usage = blocked_record
        closing = asyncio.create_task(self.adapter._finish_attempt(state, {
            "confirmed": True, "started": True, "session_id": "live-account-pending",
            "usage": {"seconds": 7}, "reason": "session.closed"}))
        await entered.wait()
        closing.cancel()
        await asyncio.gather(closing, return_exceptions=True)
        self.assertEqual(self.registry.pending()["phase"], "closed_pending_usage")
        self.adapter._current = None  # Simulate process exit after provider terminal.
        self.policy = Policy()
        self.provider.reconcile_close = AsyncMock()
        self.adapter = DiscordLiveAdapter(self.bridge, self.runtime, LiveConfig(), self.policy,
            self.provider, self.conversation, registry=DiscordLiveRegistry(self.registry.path),
            poll_seconds=.01)
        self.bridge.live = self.adapter
        await self.adapter.start()
        self.assertEqual(self.policy.records[0][:2], ("live-account-pending", {"seconds": 7}))
        self.provider.reconcile_close.assert_not_awaited()
        self.assertEqual(self.provider.calls, [])
        self.assertIsNone(self.registry.pending())
        self.assertTrue(self.adapter._allow_live)

    async def test_cancelled_live_close_still_revokes_and_disconnects_discord(self):
        entered = asyncio.Event()

        async def slow_close():
            entered.set()
            await asyncio.Event().wait()

        self.bridge.live = SimpleNamespace(close=slow_close)
        closing = asyncio.create_task(self.bridge.close())
        await entered.wait()
        closing.cancel()
        await asyncio.gather(closing, return_exceptions=True)
        self.connection.disconnect.assert_awaited_once()
        self.assertIsNone(self.bridge.connection)
        self.assertIsNone(self.bridge.session_id)
        self.assertIsNone(self.bridge.worker)
        self.bridge.live = self.adapter

    async def test_policy_diagnostics_log_only_changes_and_preserve_unknown_reason(self):
        with self.assertLogs("jade.discord.live", "INFO") as logs:
            self.policy.allowed = False
            for _ in range(5):
                await self.adapter._decision()
        self.assertEqual(len(logs.output), 1)
        self.assertIn("mode=classic reason=monthly_limit", logs.output[0])
        self.adapter._block("close_unconfirmed")
        self.policy.allowed = True
        await self.adapter._decision()
        self.assertEqual(self.adapter.last_reason, "close_unconfirmed")
        self.assertFalse(self.adapter._allow_live)

    async def test_reservation_refusal_routes_complete_solo_turn_and_following_turn_to_classic(self):
        self.policy.reserve_allowed = False
        self.bridge.receive_pcm(12, "Alice", pcm(.1))
        await until(lambda: bool(self.policy.settled) and self.adapter._current is None)
        self.assertIsNone(self.registry.pending())
        self.bridge.receive_pcm(12, "Alice", pcm(.2) + pcm(.8, 0))
        await until(lambda: self.runtime.submit.await_count == 1)
        await self.utterance("Deuxième phrase classique")
        self.assertEqual(self.runtime.submit.await_count, 2)
        self.assertEqual(self.services.transcribe_wav.await_count, 2)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(len(self.policy.reservations), 1)
        self.assertTrue(self.policy.settled[0][2])
        self.assertFalse(self.adapter._blocked)

    async def test_group_reservation_refusal_reuses_admitted_text_without_second_stt(self):
        self.group()
        self.policy.reserve_allowed = False
        await self.utterance("Jade, bonjour")
        await until(lambda: self.runtime.submit.await_count == 1)
        self.assertEqual(self.services.transcribe_wav.await_count, 1)
        self.assertEqual(self.provider.calls, [])
        self.assertIsNone(self.registry.pending())

    async def test_live_reservation_is_bound_and_settled_only_after_provider_close(self):
        remote = await self.start_solo()
        attempt = self.policy.reservations[0][0]
        self.assertEqual(self.policy.bindings, [(attempt, remote.session_id)])
        self.assertEqual(self.policy.settled, [])
        await self.adapter.transport_changed()
        self.assertTrue(remote.closed)
        self.assertEqual(self.policy.settled[-1], (attempt, True, False, remote.session_id))
        self.assertIsNone(self.registry.pending())

    async def test_new_speech_without_rtp_silence_interrupts_local_output(self):
        remote = await self.start_solo()
        state = self.adapter._current
        state.last_capture -= 1
        remote.events.put_nowait({"type": "session.output_audio.delta", "pcm": b"\1\0" * 480})
        await until(lambda: bool(self.played))
        self.bridge.receive_pcm(12, "Alice", pcm(.08))
        await until(lambda: any(event["state"] == "interrupted" for event in self.conversation.played))
        self.assertEqual(len(self.provider.calls), 1)
        self.assertFalse(remote.closed)
        self.assertEqual(remote.commands, [])  # No invented provider cancel command.

    async def test_technical_start_limit_selects_classic_without_dropping_new_turn(self):
        self.adapter._starts.extend([self.adapter.clock()] * 3)
        # Simulate capture just before the policy tick observes the rate cap.
        self.bridge.receive_pcm(12, "Alice", pcm(.1))
        await until(lambda: self.adapter._current is None and self.bridge._segmenter._users)
        self.bridge.receive_pcm(12, "Alice", pcm(.2) + pcm(.8, 0))
        await until(lambda: self.runtime.submit.await_count == 1)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.policy.reservations, [])
        self.assertEqual(self.services.transcribe_wav.await_count, 1)

    async def test_real_spend_policy_reserves_then_closes_without_usage_events(self):
        now = [datetime(2026, 11, 27, 12, tzinfo=timezone.utc)]
        snapshot = {"month": "2026-11", "spent_eur": "39.98", "coverage": "bounded",
                    "checked_at": now[0].isoformat(), "complete_through": now[0].isoformat(),
                    "sources": {"openai": {"amounts": {"USD": "39.98"}}},
                    "fx": {"rates": {"USD": "1"}}}
        collector = SimpleNamespace(db_path=Path(self.directory.name) / "spend.sqlite3",
                                    collect=AsyncMock(return_value=snapshot))
        policy = DiscordLiveSpendPolicy(collector, now=lambda: now[0])
        try:
            await policy.refresh()
            self.adapter.policy = policy
            await self.adapter._decision()
            remote = await self.start_solo()
            self.assertEqual((await policy.decision())["outstanding_live_reservations"], 1)
            now[0] += timedelta(seconds=30)
            self.assertFalse((await policy.decision())["allow_live"])
            await until(lambda: remote.closed and self.adapter._current is None)
            self.assertEqual((await policy.decision())["outstanding_live_reservations"], 0)
            self.assertIsNone(self.registry.pending())
            self.assertEqual(len(self.provider.calls), 1)
            self.runtime.submit.assert_not_awaited()
        finally:
            await self.adapter.close()
            await policy.close()

    async def test_enabling_live_mid_classic_utterance_keeps_one_complete_route(self):
        self.policy.allowed = False
        await self.adapter._decision()
        self.bridge.receive_pcm(12, "Alice", pcm(.25))
        self.policy.allowed = True
        await self.adapter._decision()
        self.bridge.receive_pcm(12, "Alice", pcm(.25))
        await asyncio.sleep(.02)
        self.assertEqual(self.provider.calls, [])
        self.bridge.receive_pcm(12, "Alice", pcm(.8, 0))
        await until(lambda: bool(self.provider.sessions))
        self.assertEqual(self.services.transcribe_wav.await_count, 1)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.adapter._current.mode, "group")
        self.runtime.submit.assert_not_awaited()

    async def test_idle_closes_and_new_speech_opens_fresh_session(self):
        remote = await self.start_solo()
        state = self.adapter._current
        state.input_pcm.clear()
        state.last_input = state.last_output = self.adapter.clock() - 40
        await until(lambda: remote.closed and self.adapter._current is None)
        await self.start_solo()
        self.assertEqual(len(self.provider.sessions), 2)

    async def test_solo_stop_uses_existing_mute_and_classic_listens_for_resume(self):
        remote = await self.start_solo()
        remote.events.put_nowait({"type": "session.input_transcript.delta", "event_id": "stop-event",
            "delta": "silence", "start_ms": 0, "end_ms": 300})
        await until(lambda: remote.closed and self.adapter._current is None)
        self.assertTrue(self.bridge.voice_muted())
        self.bridge.receive_pcm(12, "Alice", pcm(.7, 0))
        await self.utterance("tu peux reprendre")
        self.assertFalse(self.bridge.voice_muted())
        self.runtime.submit.assert_not_awaited()
        self.assertEqual(len(self.provider.calls), 1)
