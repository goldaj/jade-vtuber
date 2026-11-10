"""Offline avatar and actual-audio playback contracts."""
import asyncio
import io
import struct
import unittest
import wave
from unittest.mock import AsyncMock, patch

from src.jade_runtime.avatar import Avatar, child_environment, levels
from src.jade_runtime.output import AudioOutput


def wav(value=12000, duration=0.2):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as out:
        out.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        out.writeframes(struct.pack("<h", value) * int(24000 * duration))
    return stream.getvalue()


class AvatarTests(unittest.IsolatedAsyncioTestCase):
    def test_environment_allowlist_excludes_secrets(self):
        env = child_environment({"PATH": "bin", "SYSTEMROOT": "system", "OPENAI_API_KEY": "secret", "JADE_TOKEN": "secret", "PYTHONPATH": "secret", "HTTP_PROXY": "secret", "UNEXPECTED_SECRET": "secret"})
        self.assertEqual(env, {"PATH": "bin", "SYSTEMROOT": "system"})

    def test_amplitudes_valid_and_invalid_audio(self):
        self.assertGreater(levels(wav())[0], .9)
        self.assertEqual(levels(wav(0))[0], 0)
        self.assertEqual(levels(b"not wav"), [])

    async def test_audio_none_never_reports_start(self):
        events = []
        player = AudioOutput("none")
        player.playback_observer = lambda *args: events.append(args)
        await player.play(wav())
        self.assertEqual(events, [])

    async def test_spawn_failure_never_reports_start(self):
        events = []
        player = AudioOutput("ffplay")
        player.playback_observer = lambda *args: events.append(args)
        with patch("asyncio.create_subprocess_exec", AsyncMock(side_effect=OSError("missing"))):
            with self.assertRaises(OSError):
                await player.play(wav())
        self.assertEqual(events, [])

    async def test_actual_start_cancel_reports_balanced_end(self):
        events = []
        started, terminated = asyncio.Event(), asyncio.Event()
        class Process:
            returncode = None
            async def wait(self):
                started.set()
                await terminated.wait()
                return self.returncode
            def terminate(self):
                self.returncode = -1
                terminated.set()
        player = AudioOutput("ffplay")
        player.playback_observer = lambda event, _: events.append(event)
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=Process())):
            task = asyncio.create_task(player.play(wav()))
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(events, ["start", "end"])

    async def test_multisource_end_does_not_stop_other(self):
        avatar = Avatar()
        local, discord = avatar.observer("local"), avatar.observer("discord")
        data = wav(duration=0.5)
        local("start", data)
        discord("start", data)
        await asyncio.sleep(.08)
        self.assertEqual(set(avatar._active), {"local", "discord"})
        local("end", data)
        await asyncio.sleep(.05)
        self.assertEqual(set(avatar._active), {"discord"})
        self.assertGreater(avatar._pending.get_nowait(), .9)
        discord("end", data)
        await avatar._animation
        self.assertEqual(avatar._pending.get_nowait(), 0.0)
        await avatar.close()

    async def test_ending_during_wav_analysis_never_reopens_mouth(self):
        avatar = Avatar()
        callback = avatar.observer("discord")
        entered, release = asyncio.Event(), asyncio.Event()
        async def delayed(*_):
            entered.set()
            await release.wait()
            return [1.0] * 10
        with patch("asyncio.to_thread", delayed):
            callback("start", wav())
            await entered.wait()
            callback("end", b"")
            release.set()
            await avatar._animation
        self.assertEqual(avatar._pending.get_nowait(), 0.0)
        await avatar.close()
