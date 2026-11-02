"""Offline integration harness: synthetic PCM, mocked SDK, no device or network."""
import asyncio
import sys
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.microphone import AudioCoordinator, pcm_to_wav
from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.output import SpeechOutput
from src.jade_runtime.voice_pipeline import VoiceInput


class SyntheticFlow(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, level):
        pcm = array('h', [level] * 8000)
        output_wav = pcm_to_wav(array('h', [1600] * 400).tobytes())

        class InputStream:
            def __init__(self, **kwargs):
                self.callback = kwargs['callback']
            def __enter__(self):
                self.callback(pcm, len(pcm), None, None)
                return self
            def __exit__(self, *args):
                pass

        async def transcribe(**kwargs):
            with wave.open(kwargs['file'], 'rb') as wav:
                self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getnframes()), (1, 16000, 8000))
            return SimpleNamespace(text='Bonjour Jade')

        stt = AsyncMock(side_effect=transcribe)
        chat = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Bonjour !'))]))
        tts = AsyncMock(return_value=SimpleNamespace(content=output_wav))
        sdk = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=stt),
                                                    speech=SimpleNamespace(create=tts)),
                              chat=SimpleNamespace(completions=SimpleNamespace(create=chat)))
        services = OpenAIServices(Settings(), client=sdk)
        gate = AudioCoordinator()
        player = SimpleNamespace(play=AsyncMock())
        with tempfile.TemporaryDirectory() as directory:
            subtitle = Path(directory) / 'subtitle.txt'
            speech = SpeechOutput(services, player, subtitle, audio_gate=gate)
            async def output(reply):
                await speech.speak(reply)
            dialogue = Dialogue(services, 'Prompt synthétique')
            runtime = Runtime(dialogue, output)
            await runtime.start()
            try:
                voice = VoiceInput(services, runtime, audio_gate=gate)
                with patch.dict(sys.modules, {'sounddevice': SimpleNamespace(InputStream=InputStream)}):
                    result = await asyncio.wait_for(voice.once(.5), 5)
                if level:
                    self.assertTrue(result)
                    stt.assert_awaited_once()
                    chat.assert_awaited_once()
                    tts.assert_awaited_once()
                    player.play.assert_awaited_once_with(output_wav)
                    self.assertEqual(subtitle.read_text(), '')
                    self.assertEqual(len(dialogue.history[('microphone', 'mic')]), 2)
                else:
                    self.assertFalse(result)
                    stt.assert_not_awaited()
                    chat.assert_not_awaited()
                    tts.assert_not_awaited()
                    player.play.assert_not_awaited()
            finally:
                await gate.close()
                await runtime.stop(graceful=False)

    async def test_synthetic_speech_through_full_pipeline(self):
        await self.exercise(1500)

    async def test_silence_does_not_call_providers(self):
        await self.exercise(0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
