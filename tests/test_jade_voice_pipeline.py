import unittest
from array import array
from unittest.mock import AsyncMock

from src.jade_runtime.microphone import pcm_to_wav, is_speech_loud_enough
from src.jade_runtime.voice_pipeline import VoiceInput
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.orchestrator import Runtime


class Echo:
    async def complete(self, messages):
        return "Voix reçue"


class VoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_microphone_capture_transcription_and_reply_offline(self):
        seen = []
        async def sink(reply):
            seen.append((reply.source.platform, reply.source.text))
        runner = Runtime(Dialogue(Echo(), "Jade"), sink)
        await runner.start()
        services = AsyncMock()
        services.transcribe_wav.return_value = "Bonjour Jade"
        capture = AsyncMock(return_value=b"RIFFtest")
        voice = VoiceInput(services, runner, capture=capture)
        self.assertTrue(await voice.once())
        self.assertEqual(seen, [("microphone", "Bonjour Jade")])
        services.transcribe_wav.assert_awaited_once_with(b"RIFFtest")
        await runner.stop()

    async def test_silence_does_not_spend_an_openai_request(self):
        runner = Runtime(Dialogue(Echo(), "Jade"), AsyncMock())
        await runner.start()
        services = AsyncMock()
        voice = VoiceInput(services, runner, capture=AsyncMock(return_value=None))
        self.assertFalse(await voice.once())
        services.transcribe_wav.assert_not_called()
        await runner.stop()

    def test_pcm_threshold_and_valid_wav_header(self):
        samples = array("h", [1500] * 16000).tobytes()
        self.assertTrue(is_speech_loud_enough(samples))
        self.assertFalse(is_speech_loud_enough(bytes(len(samples))))
        self.assertEqual(pcm_to_wav(samples)[:4], b"RIFF")
        with self.assertRaises(ValueError):
            pcm_to_wav(b"\0")
