"""Offline tests for optional, formant-preserving FFmpeg pitch processing.

The audio is synthetic sine waves, never user speech. Integration checks do not
make OpenAI API requests. Hardware-independent assertions are always run; the
real FFmpeg test is skipped if the optional rubberband filter is unavailable.
"""
from __future__ import annotations

import asyncio
from io import BytesIO
import math
from unittest.mock import AsyncMock, patch
import struct
import unittest
import wave

from src.jade_runtime.config import Settings
from src.jade_runtime.pitch_shift import (
    _command, _rubberband_available, pitch_ratio, shift_pcm, shift_wav,
    supports_pitch_shift,
)

_RATE = 24000


def _sine(seconds: float, hz: float = 220) -> bytes:
    return b"".join(struct.pack("<h", round(9000 * math.sin(
        2 * math.pi * hz * index / _RATE)))
                    for index in range(round(seconds * _RATE)))


def _wav(pcm: bytes) -> bytes:
    out = BytesIO()
    with wave.open(out, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(_RATE)
        writer.writeframes(pcm)
    return out.getvalue()


def _frequency(data: bytes) -> float:
    # Cheap fundamental estimate for a clean synthetic sine wave. Drop
    # filter transient windows at both ends.
    samples = [s for (s,) in struct.iter_unpack("<h", data)]
    samples = samples[_RATE // 8:-_RATE // 8]
    transitions = sum(1 for prev, value in zip(samples, samples[1:])
                      if prev <= 0 < value)
    return transitions / (len(samples) / _RATE)


class PitchContractTests(unittest.TestCase):
    def test_pitch_conversion_and_bounds(self):
        self.assertAlmostEqual(pitch_ratio(2), 2 ** (1 / 6), places=9)
        self.assertEqual(pitch_ratio(0), 1)
        for value in (-7, 7, True, False, "2", float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                pitch_ratio(value)

    def test_voice_profile_is_etincelle_plus_two_by_default(self):
        config = Settings()
        self.assertEqual(config.voice, "shimmer")
        self.assertEqual(config.tts_speed, 1.25)
        self.assertEqual(config.tts_pitch_semitones, 2.0)
        for value in (-7, 7, True, False, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings(tts_pitch_semitones=value).validate()

    def test_command_has_formant_preservation_and_unchanged_tempo(self):
        command = _command(2)
        self.assertEqual(command[0], "ffmpeg")
        filter_arg = command[command.index("-af") + 1]
        self.assertIn("formant=preserved", filter_arg)
        self.assertIn("tempo=1", filter_arg)
        self.assertIn("pitchq=speed", filter_arg)
        self.assertIn("pitch=1.122", filter_arg)
        self.assertEqual(command[command.index("-ar") + 1], "24000")


class PitchStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_ffmpeg_passes_pcm_unchanged_without_subprocess(self):
        async def source():
            yield b"\x01\x00"
            yield b"\x02\x00"
        with patch("src.jade_runtime.pitch_shift.supports_pitch_shift",
                   new=AsyncMock(return_value=False)):
            with patch("src.jade_runtime.pitch_shift.asyncio.create_subprocess_exec") as spawn:
                result = [part async for part in shift_pcm(source(), 2)]
                self.assertEqual(result, [b"\x01\x00", b"\x02\x00"])
                spawn.assert_not_called()

    async def test_zero_shift_passes_pcm_unchanged(self):
        async def source():
            yield b"\x01\x00"
        with patch("src.jade_runtime.pitch_shift.supports_pitch_shift") as available:
            result = [part async for part in shift_pcm(source(), 0)]
            self.assertEqual(result, [b"\x01\x00"])
            available.assert_not_called()

    async def test_no_ffmpeg_keeps_original_wav_bytes_exactly(self):
        source = _wav(_sine(0.35))
        with patch("src.jade_runtime.pitch_shift.supports_pitch_shift",
                   new=AsyncMock(return_value=False)):
            transformed = await shift_wav(source, 2)
        self.assertEqual(transformed, source)

    async def test_real_pitch_and_tempo_with_sine_if_filter_installed(self):
        if not await supports_pitch_shift():
            self.skipTest("FFmpeg rubberband filter is not installed")
        original = _sine(1.0)
        async def source():
            for index in range(0, len(original), 997):  # odd PCM deltas
                yield original[index:index + 997]
        transformed = b"".join([part async for part in shift_pcm(source(), 2)])
        self.assertLess(abs(len(transformed) - len(original)), 150)
        self.assertAlmostEqual(_frequency(original), 220, delta=3)
        self.assertAlmostEqual(_frequency(transformed), 220 * pitch_ratio(2), delta=7)
        result = await shift_wav(_wav(original), 2)
        with wave.open(BytesIO(result), "rb") as reader:
            self.assertEqual((reader.getnchannels(), reader.getsampwidth(),
                              reader.getframerate()), (1, 2, _RATE))
            self.assertAlmostEqual(reader.getnframes(), _RATE, delta=75)

    async def test_streaming_first_chunk_before_input_ends_and_can_cancel(self):
        if not await supports_pitch_shift():
            self.skipTest("FFmpeg rubberband filter is not installed")
        release = asyncio.Event()
        original = _sine(1.0)
        closed = asyncio.Event()
        async def source():
            try:
                for index in range(0, len(original), 960):
                    yield original[index:index + 960]
                await release.wait()  # upstream Realtime is still working
                yield _sine(0.2)
            finally:
                closed.set()
        stream = shift_pcm(source(), 2)
        try:
            first = await asyncio.wait_for(anext(stream), 2.0)
            self.assertTrue(first)
            self.assertFalse(release.is_set())
        finally:
            await asyncio.wait_for(stream.aclose(), 3.0)
        self.assertTrue(closed.is_set())

    async def test_early_close_no_new_audio_request_required(self):
        async def source():
            yield _sine(0.4)
        with patch("src.jade_runtime.pitch_shift.supports_pitch_shift",
                   new=AsyncMock(return_value=False)):
            chunks = [part async for part in shift_pcm(source(), 2)]
        self.assertEqual(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
