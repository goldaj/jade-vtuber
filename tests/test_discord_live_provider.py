import asyncio
import base64
import copy
import json
import math
import struct
import unittest
from unittest.mock import patch

from openai.types.live.input_audio_append_event import InputAudioAppendEvent
from openai.types.live.session_close_event import SessionCloseEvent
from openai.types.live.session_start_event import SessionStartEvent

from src.jade_runtime.discord_live_provider import (
    DiscordLiveProvider, PCM48StereoTo24Mono, build_discord_live_config,
)
from src.jade_runtime import discord_live_provider as provider_module
from src.jade_runtime.live_config import LiveConfig
from src.jade_runtime.live_provider import LiveProviderError


class Socket:
    def __init__(self, *, start=True, terminal=True):
        self.start, self.terminal = start, terminal
        self.incoming = asyncio.Queue()
        self.sent = []
        self.config = None
        self.transport_closed = False

    def emit(self, event):
        self.incoming.put_nowait(json.dumps(event) if isinstance(event, dict) else event)

    def started(self):
        self.emit({"type": "session.started", "event_id": "evt_started",
                   "session": {**self.config, "id": "live_discord_test",
                               "expires_at": 1900000000, "status": "active"}})

    async def send(self, raw):
        event = json.loads(raw)
        self.sent.append(event)
        if event["type"] == "session.start":
            self.config = event["session"]
            if self.start:
                self.started()
        elif event["type"] == "session.close" and self.terminal:
            self.emit({"type": "session.closed", "event_id": "evt_closed",
                       "session": {"id": "live_discord_test"},
                       "usage": {"seconds": 15.0}, "reason": "close_requested"})

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.incoming.get()
        if item is None:
            raise StopAsyncIteration
        return item


class Connection:
    def __init__(self, socket):
        self.socket = socket

    async def __aenter__(self):
        return self.socket

    async def __aexit__(self, *args):
        self.socket.transport_closed = True
        self.socket.emit(None)


class Factory:
    def __init__(self, socket):
        self.socket = socket
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Connection(self.socket)


class DiscordLiveProviderTests(unittest.IsolatedAsyncioTestCase):
    def provider(self, socket=None, **kwargs):
        socket = socket or Socket()
        factory = Factory(socket)
        provider = DiscordLiveProvider("test-key", websocket_connect=factory,
                                       opening_timeout_seconds=0.05, close_timeout_seconds=0.05,
                                       **kwargs)
        return provider, socket, factory

    async def test_primary_start_payload_passes_official_sdk_without_webrtc_fields(self):
        provider, socket, factory = self.provider()
        config = build_discord_live_config(LiveConfig(), instructions="Jade",
            input=[{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "Bonjour"}]}])
        self.assertEqual(factory.calls, [])
        session = await provider.open(config)
        try:
            self.assertEqual(session.session_id, "live_discord_test")
            self.assertEqual(factory.calls[0][0], "wss://api.openai.com/v1/live/sessions")
            self.assertEqual(factory.calls[0][1]["extra_headers"], {"Authorization": "Bearer test-key"})
            self.assertEqual(len(socket.sent), 1)
            validated = SessionStartEvent.model_validate(socket.sent[0], strict=True)
            self.assertEqual(validated.session.audio.format.rate, 24000)
            self.assertFalse(validated.session.store)
            self.assertEqual(validated.session.delegation.type, "client")
            self.assertTrue({"client", "idle_timeout_s", "wake_policy"}.isdisjoint(config))
        finally:
            result = await session.close()
        self.assertTrue(result["confirmed"])
        self.assertEqual(result["usage"], {"seconds": 15.0})
        self.assertTrue(socket.transport_closed)

    async def test_bad_config_and_key_do_not_open_socket(self):
        provider, socket, factory = self.provider()
        config = build_discord_live_config(LiveConfig())
        variants = [dict(config, store=True), dict(config, wake_policy={"type": "speech"}),
                    dict(config, delegation={"type": "responses"})]
        bad_audio = copy.deepcopy(config)
        bad_audio["audio"]["format"]["rate"] = 48000
        variants.append(bad_audio)
        for value in variants:
            with self.assertRaises(LiveProviderError):
                await provider.open(value)
        provider._api_key = ""
        with self.assertRaises(LiveProviderError):
            await provider.open(config)
        self.assertEqual(factory.calls, [])

    async def test_paced_input_preserves_pcm_and_emits_sdk_valid_appends(self):
        provider, socket, _ = self.provider()
        session = await provider.open(build_discord_live_config(LiveConfig()))
        clock = [100.0]
        sleeps = []
        session._clock = lambda: clock[0]

        async def sleep(delay):
            sleeps.append(delay)
            clock[0] += delay

        pcm = b"\x01\x02" * 1200  # 50 ms, two full frames and a partial frame.
        try:
            with patch("src.jade_runtime.discord_live_provider.asyncio.sleep", new=sleep):
                await session.send_audio(pcm)
            events = [event for event in socket.sent if event["type"] == "session.input_audio.append"]
            self.assertEqual(len(events), 3)
            self.assertEqual(b"".join(base64.b64decode(event["audio"]) for event in events), pcm)
            self.assertAlmostEqual(sum(sleeps), 0.04)
            for event in events:
                InputAudioAppendEvent.model_validate(event, strict=True)
            self.assertFalse(any(e["type"].startswith("response.") for e in socket.sent))
        finally:
            await session.close()

    async def test_audio_transcripts_delegation_and_cumulative_usage_are_available(self):
        provider, socket, _ = self.provider()
        session = await provider.open(build_discord_live_config(LiveConfig()))
        try:
            self.assertEqual((await anext(session))["type"], "session.started")
            pcm = b"\x00\x01" * 480
            socket.emit({"type": "session.output_audio.delta", "delta": base64.b64encode(pcm).decode()})
            socket.emit({"type": "session.input_transcript.delta", "event_id": "in-1",
                         "delta": "Bonjour", "start_ms": 0, "end_ms": 100})
            socket.emit({"type": "session.delegation.created", "event_id": "d-1", "offset_ms": 100,
                         "delegation": {"id": "delegation_1", "target": "client"}})
            for seconds in (12, 15, 15):
                socket.emit({"type": "session.usage.updated", "usage": {"seconds": seconds}})
            audio = await anext(session)
            self.assertEqual(audio["pcm"], pcm)
            self.assertNotIn("delta", audio)
            self.assertEqual((await anext(session))["delta"], "Bonjour")
            self.assertEqual((await anext(session))["delegation"]["id"], "delegation_1")
            for _ in range(3):
                await anext(session)
            self.assertEqual(session.usage["seconds"], 15)
            await session.send({"type": "session.thinking.append", "delegation_id": "delegation_1",
                                "content": "", "event_id": "quiet-1"})
            for kind in ("response.create", "response.cancel", "session.start", "session.output_audio.cleared"):
                with self.assertRaises(LiveProviderError):
                    await session.send({"type": kind})
        finally:
            await session.close()

    async def test_close_does_not_need_application_iterator_and_is_idempotent(self):
        provider, socket, _ = self.provider()
        session = await provider.open(build_discord_live_config(LiveConfig()))
        first, second = await asyncio.gather(session.close(), session.close())
        self.assertEqual(first, second)
        self.assertTrue(first["confirmed"])
        self.assertEqual([e["type"] for e in socket.sent].count("session.close"), 1)
        with self.assertRaises(LiveProviderError):
            await session.send_audio(b"\x00\x00")

    async def test_missing_terminal_is_not_claimed_confirmed_or_retried(self):
        provider, socket, factory = self.provider(Socket(terminal=False))
        session = await provider.open(build_discord_live_config(LiveConfig()))
        result = await asyncio.wait_for(session.close(), timeout=0.4)
        self.assertFalse(result["confirmed"])
        self.assertEqual(result["reason"], "close_unconfirmed")
        self.assertEqual(len(factory.calls), 1)
        self.assertEqual([e["type"] for e in socket.sent].count("session.start"), 1)

    async def test_late_start_after_open_timeout_is_closed_without_new_connection(self):
        provider, socket, factory = self.provider(Socket(start=False))
        async def start_late():
            await asyncio.sleep(0.06)
            socket.started()
        late = asyncio.create_task(start_late())
        try:
            with self.assertRaises(LiveProviderError) as raised:
                await provider.open(build_discord_live_config(LiveConfig()))
            self.assertEqual(raised.exception.code, "discord_live_open_timeout")
            self.assertEqual(raised.exception.session_id, "live_discord_test")
            self.assertFalse(raised.exception.ambiguous)
            self.assertEqual(len(factory.calls), 1)
            self.assertTrue(socket.transport_closed)
        finally:
            await late

    async def test_startup_without_id_remains_ambiguous_and_never_retries(self):
        provider, socket, factory = self.provider(Socket(start=False, terminal=False))
        with self.assertRaises(LiveProviderError) as raised:
            await asyncio.wait_for(provider.open(build_discord_live_config(LiveConfig())), timeout=0.4)
        self.assertTrue(raised.exception.ambiguous)
        self.assertIsNone(raised.exception.session_id)
        self.assertEqual(len(factory.calls), 1)
        self.assertEqual([event["type"] for event in socket.sent], ["session.start"])
        self.assertTrue(socket.transport_closed)

    async def test_start_write_and_ack_share_the_reserved_opening_deadline(self):
        provider, socket, _ = self.provider(Socket(start=False, terminal=False))
        write = socket.send
        bounded = provider_module._bounded
        ack_timeouts = []

        async def slow_write(raw):
            await write(raw)
            if json.loads(raw)["type"] == "session.start":
                await asyncio.sleep(.03)

        async def observed_bound(awaitable, timeout, code):
            if code == "discord_live_open_timeout":
                ack_timeouts.append(timeout)
            return await bounded(awaitable, timeout, code)

        socket.send = slow_write
        with patch.object(provider_module, "_bounded", observed_bound):
            with self.assertRaises(LiveProviderError):
                await provider.open(build_discord_live_config(LiveConfig()))
        self.assertEqual(len(ack_timeouts), 1)
        # The send already used 30 ms of a 50 ms paid opening envelope; the
        # acknowledgment cannot get a fresh 50 ms allowance afterwards.
        self.assertLess(ack_timeouts[0], .035)
        self.assertTrue(socket.transport_closed)

    async def test_cancel_open_preserves_confirmed_or_unknown_finalization(self):
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                provider, socket, factory = self.provider(Socket(start=False, terminal=terminal))
                opening = asyncio.create_task(provider.open(build_discord_live_config(LiveConfig())))
                for _ in range(50):
                    if socket.config is not None:
                        break
                    await asyncio.sleep(.001)
                self.assertIsNotNone(socket.config)
                opening.cancel()
                # The original paid attempt becomes identifiable during its
                # cancellation cleanup, before any replacement can be opened.
                socket.started()
                with self.assertRaises(asyncio.CancelledError) as raised:
                    await opening
                error = raised.exception
                self.assertEqual(error.session_id, "live_discord_test")
                self.assertEqual(error.close_confirmed, terminal)
                self.assertEqual(error.ambiguous, not terminal)
                self.assertEqual(error.close_result["confirmed"], terminal)
                if terminal:
                    self.assertEqual(error.close_result["usage"], {"seconds": 15.0})
                self.assertEqual(len(factory.calls), 1)
                self.assertEqual([e["type"] for e in socket.sent], ["session.start", "session.close"])

    async def test_second_cancellation_during_open_cleanup_keeps_ambiguity(self):
        provider, socket, _ = self.provider(Socket(start=False, terminal=False))
        opening = asyncio.create_task(provider.open(build_discord_live_config(LiveConfig())))
        for _ in range(50):
            if socket.config is not None:
                break
            await asyncio.sleep(.001)
        opening.cancel()
        socket.started()
        for _ in range(50):
            if any(event["type"] == "session.close" for event in socket.sent):
                break
            await asyncio.sleep(.001)
        opening.cancel()
        with self.assertRaises(asyncio.CancelledError) as raised:
            await opening
        self.assertTrue(raised.exception.ambiguous)
        self.assertFalse(raised.exception.close_confirmed)
        self.assertEqual(raised.exception.session_id, "live_discord_test")
        for _ in range(100):
            if socket.transport_closed:
                break
            await asyncio.sleep(.001)
        self.assertTrue(socket.transport_closed)

    async def test_abandoned_connection_is_closed_if_enter_ignores_cancellation(self):
        socket = Socket()
        entered = asyncio.Event()
        release = asyncio.Event()

        class LateConnection(Connection):
            async def __aenter__(self):
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                return self.socket

        provider = DiscordLiveProvider("test-key", websocket_connect=lambda *a, **k: LateConnection(socket))
        opening = asyncio.create_task(provider.open(build_discord_live_config(LiveConfig())))
        await entered.wait()
        opening.cancel()
        with self.assertRaises(asyncio.CancelledError) as raised:
            await opening
        self.assertFalse(raised.exception.ambiguous)
        self.assertFalse(raised.exception.close_result["started"])
        release.set()
        for _ in range(50):
            if socket.transport_closed:
                break
            await asyncio.sleep(.001)
        self.assertTrue(socket.transport_closed)
        self.assertEqual(socket.sent, [])

    async def test_reconcile_only_closes_saved_session_without_start_or_audio(self):
        for terminal in (False, True):
            with self.subTest(terminal=terminal):
                provider, socket, factory = self.provider(Socket(start=False, terminal=terminal))
                result = await provider.reconcile_close("live_discord_test")
                self.assertEqual(result["confirmed"], terminal)
                self.assertEqual(result["session_id"], "live_discord_test")
                self.assertEqual(len(factory.calls), 1)
                self.assertEqual(factory.calls[0][0],
                                 "wss://api.openai.com/v1/live/sessions/live_discord_test/attach")
                self.assertEqual([e["type"] for e in socket.sent], ["session.close"])
                SessionCloseEvent.model_validate(socket.sent[0], strict=True)
                self.assertTrue(socket.transport_closed)

    async def test_close_revokes_pcm_sender_without_replaying_the_buffer(self):
        provider, socket, _ = self.provider()
        session = await provider.open(build_discord_live_config(LiveConfig()))
        sending = asyncio.create_task(session.send_audio(b"\x01\x01" * 4800))
        for _ in range(50):
            if len(socket.sent) > 1:
                break
            await asyncio.sleep(0.001)
        result = await session.close()
        with self.assertRaises(LiveProviderError):
            await sending
        self.assertTrue(result["confirmed"])
        close_index = next(i for i, event in enumerate(socket.sent) if event["type"] == "session.close")
        self.assertTrue(all(event["type"] != "session.input_audio.append"
                            for event in socket.sent[close_index:]))
        self.assertLess(sum(event["type"] == "session.input_audio.append" for event in socket.sent), 10)

    async def test_backpressure_stops_session_but_receiver_still_observes_terminal(self):
        provider, socket, _ = self.provider(max_events=4)
        session = await provider.open(build_discord_live_config(LiveConfig()))
        for _ in range(8):
            socket.emit({"type": "session.output_audio.delta", "delta": "AAAAAA=="})
        # Wait for the independent receiver to request close without consuming it.
        for _ in range(50):
            if session._close_task is not None:
                break
            await asyncio.sleep(0.001)
        result = await session.close()
        self.assertTrue(result["confirmed"])
        with self.assertRaises(LiveProviderError) as raised:
            await anext(session)
        self.assertEqual(raised.exception.code, "discord_live_event_backpressure")

    async def test_provider_error_body_is_not_exposed_and_shutdown_stays_confirmed(self):
        provider, socket, _ = self.provider()
        session = await provider.open(build_discord_live_config(LiveConfig()))
        await anext(session)
        socket.emit({"type": "error", "error": {"message": "secret-key private-account"}})
        with self.assertRaises(LiveProviderError) as raised:
            await anext(session)
        self.assertNotIn("secret", str(raised.exception))
        result = await session.close()
        self.assertTrue(result["confirmed"])


class DiscordLivePCMTests(unittest.TestCase):
    def test_chunk_boundaries_preserve_identical_resampled_stream(self):
        pcm = b"".join(struct.pack("<hh", n - 1500, 1500 - n // 2) for n in range(3000))
        expected = PCM48StereoTo24Mono().feed(pcm)
        converter = PCM48StereoTo24Mono()
        actual = b"".join(converter.feed(pcm[i:i + 37]) for i in range(0, len(pcm), 37))
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), len(pcm) // 4)
        converter.reset()
        self.assertEqual(converter.feed(pcm), expected)

    def test_downmix_preserves_dc_and_lowpass_rejects_alias(self):
        pcm = struct.pack("<hh", 10000, 2000) * 4800
        samples = [s[0] for s in struct.iter_unpack("<h", PCM48StereoTo24Mono().feed(pcm))]
        self.assertTrue(all(abs(sample - 6000) <= 1 for sample in samples[32:]))
        def power(frequency):
            pcm = b"".join(struct.pack("<hh", *(2 * [round(12000 * math.sin(2 * math.pi * frequency * n / 48000))]))
                            for n in range(4800))
            samples = [s[0] for s in struct.iter_unpack("<h", PCM48StereoTo24Mono().feed(pcm))][32:]
            return sum(sample * sample for sample in samples) / len(samples)
        self.assertLess(power(18000), power(1000) / 100)


if __name__ == "__main__":
    unittest.main()
