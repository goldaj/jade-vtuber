"""Offline concurrency and cleanup contracts: no microphone or process launched."""
import asyncio
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.microphone import AudioCoordinator, MicrophoneCapture
from src.jade_runtime.output import AudioOutput, SpeechOutput
from src.jade_runtime.voice_pipeline import VoiceInput


class AudioSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_speech_invalidates_active_capture_before_stt(self):
        gate = AudioCoordinator()
        active, stopped = asyncio.Event(), asyncio.Event()

        class Capture:
            async def __call__(self, duration):
                active.set()
                await stopped.wait()
                return b"captured"
            def stop(self):
                stopped.set()

        services = type("Services", (), {"transcribe_wav": AsyncMock(return_value="voice")})()
        runtime = type("Runtime", (), {"submit": AsyncMock(), "idle": AsyncMock()})()
        voice = VoiceInput(services, runtime, capture=Capture(), audio_gate=gate)
        listening = asyncio.create_task(voice.once())
        await active.wait()
        await gate.begin_speech()
        self.assertFalse(await listening)
        services.transcribe_wav.assert_not_awaited()
        await gate.end_speech()
        await gate.close()

    async def test_capture_waits_while_speech_active(self):
        gate = AudioCoordinator()
        await gate.begin_speech()
        capture = AsyncMock(return_value=None)
        task = asyncio.create_task(gate.capture(capture, 3))
        await asyncio.sleep(0)
        capture.assert_not_awaited()
        await gate.end_speech()
        self.assertIsNone((await asyncio.wait_for(task, 1))[0])
        capture.assert_awaited_once()
        await gate.close()

    async def test_timed_out_capture_remains_barrier(self):
        gate = AudioCoordinator(capture_stop_timeout=0.01)
        active, release = asyncio.Event(), asyncio.Event()
        async def capture(duration):
            active.set()
            await release.wait()
            return None
        first = asyncio.create_task(gate.capture(capture, 3))
        await active.wait()
        with self.assertRaises(TimeoutError):
            await gate.begin_speech()
        second = asyncio.create_task(gate.capture(capture, 3))
        await asyncio.sleep(0)
        self.assertFalse(second.done())
        release.set()
        await asyncio.wait_for(first, 1)
        await asyncio.wait_for(second, 1)
        await gate.close()

    async def test_capture_thread_single_owner_after_cancel(self):
        entered = asyncio.Event()
        release = threading.Event()
        loop = asyncio.get_running_loop()
        def blocking(duration, *, stop_event):
            loop.call_soon_threadsafe(entered.set)
            release.wait(2)
            return None
        owner = MicrophoneCapture()
        with patch("src.jade_runtime.microphone.capture_wav", blocking):
            first = asyncio.create_task(owner(3))
            await entered.wait()
            first.cancel()
            await asyncio.sleep(0)
            with self.assertRaises(RuntimeError):
                await owner(3)
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await first

    async def test_capture_stop_closes_its_own_stream(self):
        entered, closed = asyncio.Event(), asyncio.Event()
        loop = asyncio.get_running_loop()
        class Stream:
            def __init__(self, **options):
                pass
            def __enter__(self):
                loop.call_soon_threadsafe(entered.set)
                return self
            def __exit__(self, *args):
                loop.call_soon_threadsafe(closed.set)
        owner = MicrophoneCapture()
        with patch.dict(sys.modules, {"sounddevice": types.SimpleNamespace(InputStream=Stream)}):
            task = asyncio.create_task(owner(3))
            await asyncio.wait_for(entered.wait(), 1)
            owner.stop()
            self.assertIsNone(await asyncio.wait_for(task, 1))
            await asyncio.wait_for(closed.wait(), 1)

    async def test_cancel_ffplay_terminates_and_waits(self):
        started = asyncio.Event()
        stopped = asyncio.Event()
        class FakeProcess:
            returncode = None
            terminated = False
            killed = False
            def terminate(self):
                self.terminated = True
                self.returncode = -1
                stopped.set()
            def kill(self):
                self.killed = True
                self.returncode = -1
                stopped.set()
            async def wait(self):
                started.set()
                await stopped.wait()
                return self.returncode
        process = FakeProcess()
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            player = asyncio.create_task(AudioOutput("ffplay").play(b"fake wav"))
            await started.wait()
            player.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await player
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)

    async def test_one_player_failure_cancels_and_awaits_other(self):
        started, cleaned = asyncio.Event(), asyncio.Event()
        class Slow:
            async def play(self, wav):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()
        class Fails:
            def reply_authorized(self, source):
                return True
            async def play_for_reply(self, wav, source):
                await started.wait()
                raise RuntimeError("synthetic failure")
        services = type("Services", (), {"synthesize_wav": AsyncMock(return_value=b"wav")})()
        reply = Reply(Incoming("discord_voice", "test", "hello"), "reply")
        with tempfile.TemporaryDirectory() as directory:
            subtitle = Path(directory) / "subtitle.txt"
            output = SpeechOutput(services, Slow(), subtitle, secondary_player=Fails())
            with self.assertRaises(ExceptionGroup):
                await output.speak(reply)
            self.assertTrue(cleaned.is_set())
            self.assertEqual(subtitle.read_text(encoding="utf-8"), "")
