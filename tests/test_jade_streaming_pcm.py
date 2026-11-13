"""Targeted offline regressions for progressive TTS and Discord PCM playback."""
import asyncio
from io import BytesIO
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

from src.jade_runtime.discord_pcm import DiscordPCMBuffer, FRAME_BYTES
from src.jade_runtime.discord_voice import OpenVoiceBridge
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.output import SpeechOutput
from src.jade_runtime.realtime_tts import RealtimeTTS, RealtimeTTSError, RealtimeConnectionPool
from tests.test_demo_realtime_tts import FakeClient, configured, created, delta, transcript, done


class PCMBufferTests(unittest.IsolatedAsyncioTestCase):
    async def test_progressive_frames_maintain_interpolation_across_deltas(self):
        pcm = struct.pack("<" + "h" * 480, *([1000, -1000] * 240))
        buffer = DiscordPCMBuffer()
        self.assertEqual(buffer.read(), b"\x00" * FRAME_BYTES)
        await buffer.feed(pcm[:64])
        await buffer.feed(pcm[64:])
        frame = buffer.read()
        self.assertEqual(len(frame), FRAME_BYTES)
        self.assertEqual(struct.unpack_from("<hhhhhhhh", frame),
                         (1000, 1000, 1000, 1000, 0, 0, -1000, -1000))
        await buffer.finish()
        self.assertEqual(buffer.read(), b"")
        self.assertEqual(len(frame), FRAME_BYTES)

    async def test_temporary_gap_is_silence_but_finish_is_real_eof(self):
        buffer = DiscordPCMBuffer()
        self.assertEqual(buffer.read(), b"\x00" * FRAME_BYTES)
        await buffer.feed(b"\x01\x00" * 100)
        self.assertEqual(buffer.read(), b"\x00" * FRAME_BYTES)
        await buffer.finish()
        self.assertEqual(len(buffer.read()), FRAME_BYTES)
        self.assertEqual(buffer.read(), b"")

    async def test_backpressure_bounded_and_abort_unblocks_writer(self):
        buffer = DiscordPCMBuffer(max_frames=5)
        task = asyncio.create_task(buffer.feed(b"\x10\x00" * (480 * 8)))
        await asyncio.sleep(0.03)
        self.assertFalse(task.done())
        buffer.abort()
        with self.assertRaises(RuntimeError):
            await asyncio.wait_for(task, 1)
        self.assertEqual(buffer.read(), b"")

    async def test_metrics_separate_initial_silence_from_live_underruns(self):
        buffer = DiscordPCMBuffer(prebuffer_frames=2)
        self.assertEqual(buffer.read(), b"\x00" * FRAME_BYTES)
        await buffer.feed(b"\x12\x00" * (480 * 2))
        self.assertTrue(any(buffer.read()))
        self.assertTrue(any(buffer.read()))
        self.assertEqual(buffer.read(), b"\x00" * FRAME_BYTES)
        stats = buffer.metrics()
        self.assertEqual(stats.frames_read, 4)
        self.assertEqual(stats.prebuffer_silence_frames, 1)
        self.assertEqual(stats.underrun_silence_frames, 1)
        self.assertEqual(stats.max_queued_frames, 2)
        self.assertIsNotNone(stats.first_nonzero_read_ms)
        self.assertGreaterEqual(stats.first_nonzero_read_ms, 0)
        self.assertNotIn("pcm", repr(stats).lower())
        buffer.abort()

    async def test_large_pcm_input_never_buffers_full_expansion(self):
        buffer = DiscordPCMBuffer(max_frames=5)
        task = asyncio.create_task(buffer.feed(b"\x11\x00" * (480 * 200)))
        await asyncio.sleep(0.03)
        self.assertFalse(task.done())
        self.assertLessEqual(len(buffer._tail), FRAME_BYTES)
        self.assertLessEqual(buffer.metrics().max_queued_frames, 5)
        buffer.abort()
        with self.assertRaises(RuntimeError):
            await asyncio.wait_for(task, 1)

    async def test_invalid_pcm_never_becomes_audio(self):
        buffer = DiscordPCMBuffer()
        with self.assertRaises(ValueError):
            await buffer.feed(b"\x00")
        with self.assertRaises(ValueError):
            await buffer.feed(b"")
        with self.assertRaises(ValueError):
            await buffer.finish()


class TTSStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_audio_is_available_before_terminal_response(self):
        waiting = asyncio.Event()
        release = asyncio.Event()
        client = FakeClient([configured(), created(), delta(b"\x04\x00" * 20),
                             transcript(), done()])
        original = client.connection.recv
        calls = 0

        async def recv():
            nonlocal calls
            calls += 1
            if calls == 4:
                waiting.set()
                await release.wait()
            return await original()

        client.connection.recv = recv
        stream = RealtimeTTS(client).stream_pcm("Bonjour Jade.")
        first = await asyncio.wait_for(anext(stream), 1)
        self.assertEqual(first, b"\x04\x00" * 20)
        await asyncio.wait_for(waiting.wait(), 1)
        self.assertFalse(client.manager.closed)
        release.set()
        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), 1)
        self.assertTrue(client.manager.closed)
        self.assertEqual(len(client.calls), 1)
        client.connection.response.cancel.assert_not_awaited()

    async def test_closing_stream_cancels_provider_without_replay(self):
        client = FakeClient([configured(), created(), delta(b"\x01\x00" * 20)])
        stream = RealtimeTTS(client).stream_pcm("Bonjour Jade.")
        self.assertEqual(len(await asyncio.wait_for(anext(stream), 1)), 40)
        await asyncio.wait_for(stream.aclose(), 1)
        self.assertTrue(client.manager.closed)
        client.connection.response.cancel.assert_awaited_once_with(response_id="response-1")

    async def test_failure_after_emission_propagates_with_no_second_request(self):
        client = FakeClient([configured(), created(), delta(b"\x01\x00" * 20),
                             {"type": "error", "error": {"message": "private"}}])
        stream = RealtimeTTS(client).stream_pcm("Bonjour Jade.")
        self.assertTrue(await asyncio.wait_for(anext(stream), 1))
        with self.assertRaises(RealtimeTTSError) as caught:
            await asyncio.wait_for(anext(stream), 1)
        self.assertNotIn("private", str(caught.exception))
        self.assertEqual(len(client.calls), 1)


class RealtimePoolTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_turns_reuse_socket_without_repeating_requests(self):
        client = FakeClient([configured(), created(), delta(), transcript(), done(),
                             configured(), created(), delta(), transcript(), done()])
        pool = RealtimeConnectionPool(client)
        adapter = RealtimeTTS(client, connection_pool=pool)
        first = await adapter.synthesize("Bonjour Jade.")
        second = await adapter.synthesize("Bonjour Jade.")
        self.assertEqual(first.audio, second.audio)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.connection.response.create.await_count, 2)
        self.assertFalse(client.manager.closed)
        await pool.close()
        self.assertTrue(client.manager.closed)

    async def test_failed_turn_drops_pool_and_never_retries(self):
        client = FakeClient([configured(), created(), delta(),
                             {"type": "error", "error": {"message": "private"}}])
        pool = RealtimeConnectionPool(client)
        with self.assertRaises(RealtimeTTSError):
            await RealtimeTTS(client, connection_pool=pool).synthesize("Bonjour Jade.")
        self.assertTrue(client.manager.closed)
        self.assertEqual(len(client.calls), 1)
        await pool.close()


class FakeConnection:
    def __init__(self):
        self.channel = types.SimpleNamespace(id=45)
        self.frames = []
        self.play_task = None
        self.started_audio = asyncio.Event()
        self.stops = 0
        self._playing = False

    def is_playing(self):
        return self._playing

    def play(self, source, *, after):
        self._playing = True

        async def playback():
            try:
                for _ in range(200):
                    chunk = source.read()
                    if not chunk:
                        break
                    self.frames.append(chunk)
                    if any(chunk):
                        self.started_audio.set()
                    await asyncio.sleep(0.001)
                after(None)
            finally:
                self._playing = False

        self.play_task = asyncio.create_task(playback())

    def stop_playing(self):
        self.stops += 1
        if self.play_task is not None and not self.play_task.done():
            self.play_task.cancel()


class StreamBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.discord_mock = patch.dict("sys.modules", {
            "discord": types.SimpleNamespace(AudioSource=object)})
        self.discord_mock.start()
        self.addCleanup(self.discord_mock.stop)
        self.bridge = OpenVoiceBridge(None, None, 45)
        self.connection = FakeConnection()
        self.bridge.connection = self.connection
        self.bridge.consent_confirmed = True
        self.bridge.own_bot_id = 100
        self.bridge.session_id = "a" * 32

    async def test_reader_starts_before_stream_completion_and_drains(self):
        release = asyncio.Event()
        events = []
        self.bridge.playback_observer = lambda event, value: events.append((event, value))

        async def producer():
            yield b"\x11\x00" * (480 * 5)
            await release.wait()
            yield b"\x22\x00" * 480

        task = asyncio.create_task(self.bridge.play_pcm_stream(producer()))
        await asyncio.wait_for(self.connection.started_audio.wait(), 1)
        self.assertFalse(task.done())
        self.assertTrue(all(len(chunk) == FRAME_BYTES for chunk in self.connection.frames))
        release.set()
        self.assertTrue(await asyncio.wait_for(task, 2))
        self.assertTrue(any(event == "pcm_level" for event, _ in events))
        stats = self.bridge.last_pcm_metrics
        self.assertIsNotNone(stats)
        self.assertIsNotNone(stats.first_nonzero_read_ms)
        self.assertGreater(stats.frames_read, 0)
        self.assertEqual([event for event, _ in events if event in ("pcm_start", "pcm_end")],
                         ["pcm_start", "pcm_end"])
        self.assertGreater(self.connection.stops, 0)

    async def test_provider_error_stops_reader_and_never_replays(self):
        async def producer():
            yield b"\x11\x00" * 480
            raise RealtimeTTSError("synthesis failure")

        with self.assertRaises(RealtimeTTSError):
            await asyncio.wait_for(self.bridge.play_pcm_stream(producer()), 2)
        self.assertGreater(self.connection.stops, 0)
        self.assertFalse(self.bridge._playback_active)


class StreamOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_reply_uses_stream_once_and_clears_subtitles(self):
        class Services:
            def __init__(self):
                self.synthesized = False
                self.stream_calls = 0
            def stream_speech_pcm(self, text):
                self.stream_calls += 1
                async def iterator():
                    yield b"\x11\x00" * 480
                return iterator()
            async def synthesize_wav(self, text):
                self.synthesized = True
                return b"legacy"
        class Bridge:
            played = False
            def reply_authorized(self, source):
                return True
            async def play_pcm_stream_for_reply(self, stream, source):
                assert await anext(stream)
                self.played = True
                return True
            def mark_voice_reply_played(self, source):
                self.ack = True
        class Silent:
            mode = "none"
            async def play(self, wav):
                raise AssertionError("No local WAV player must run")
        source = Incoming("discord_voice", "A", "bonjour", channel="45",
                          voice_session_id="a" * 32, speaker_id=12, force_reply=True)
        with tempfile.TemporaryDirectory() as directory:
            service = Services()
            bridge = Bridge()
            path = Path(directory) / "subtitle.txt"
            output = SpeechOutput(service, Silent(), path, secondary_player=bridge)
            await output.speak(Reply(source, "réponse"))
            self.assertTrue(bridge.played)
            self.assertTrue(bridge.ack)
            self.assertEqual(service.stream_calls, 1)
            self.assertFalse(service.synthesized)
            self.assertEqual(path.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
