import base64
import types
import unittest

from src.jade_runtime.mobile_audio_stream import speech_events


class MobileAudioStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_pcm_arrives_progressively_and_handles_split_samples(self):
        released = []
        async def source():
            try:
                yield b"\x01"
                yield b"\x02\x03\x04"
                released.append(True)
                yield b"\x05\x06"
            finally:
                released.append("closed")
        services = types.SimpleNamespace(
            settings=types.SimpleNamespace(tts_pitch_semitones=0),
            stream_speech_pcm=lambda text, *, intent: source(),
        )
        stream = speech_events(services, "Bonjour", "neutral")
        first = await anext(stream)
        self.assertEqual(base64.b64decode(first["pcm_b64"]), b"\x01\x02\x03\x04")
        self.assertEqual(first["sample_rate"], 24000)
        self.assertEqual(released, [])
        await stream.aclose()
        self.assertEqual(released, ["closed"])

    async def test_no_second_synthesis_after_pcm_failure(self):
        async def failing():
            yield b"\x01\x02"
            raise RuntimeError("provider error")
        class Services:
            settings = types.SimpleNamespace(tts_pitch_semitones=0)
            syntheses = 0
            def stream_speech_pcm(self, text, *, intent):
                return failing()
            async def synthesize_speech(self, text, *, intent):
                self.syntheses += 1
        services = Services()
        stream = speech_events(services, "Bonjour", "neutral")
        await anext(stream)
        with self.assertRaises(RuntimeError):
            await anext(stream)
        self.assertEqual(services.syntheses, 0)

    async def test_non_realtime_uses_one_buffered_wav(self):
        class Services:
            settings = types.SimpleNamespace(tts_pitch_semitones=0)
            syntheses = 0
            def stream_speech_pcm(self, text, *, intent):
                return None
            async def synthesize_speech(self, text, *, intent):
                self.syntheses += 1
                return types.SimpleNamespace(audio=b"a" * 44)
        services = Services()
        result = [event async for event in speech_events(services, "Bonjour", "neutral")]
        self.assertEqual(services.syntheses, 1)
        self.assertEqual(base64.b64decode(result[0]["audio_wav_b64"]), b"a" * 44)

    async def test_incomplete_pcm_fails(self):
        async def source():
            yield b"\x01"
        services = types.SimpleNamespace(
            settings=types.SimpleNamespace(tts_pitch_semitones=0),
            stream_speech_pcm=lambda text, *, intent: source(),
        )
        with self.assertRaises(ValueError):
            _ = [event async for event in speech_events(services, "Bonjour", "neutral")]


class MobileProgressContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_tts_stream_inherits_mobile_timing_context(self):
        from src.jade_runtime.pcm_timing import PCMProgressTiming, active_pcm_timing
        timing = PCMProgressTiming()
        observed = []
        async def source():
            observed.append(active_pcm_timing.get() is timing)
            yield b"\x01\x02"
        services = types.SimpleNamespace(
            settings=types.SimpleNamespace(tts_pitch_semitones=0),
            stream_speech_pcm=lambda text, *, intent: source())
        result = [item async for item in speech_events(
            services, "Bonjour", "neutral", timing=timing)]
        self.assertEqual(result[0]["type"], "pcm")
        self.assertEqual(observed, [True])
        self.assertIsNone(active_pcm_timing.get())
