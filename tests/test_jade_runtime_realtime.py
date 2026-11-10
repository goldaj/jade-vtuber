"""Runtime voice migration contracts; no network, API charges or hardware."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.jade_runtime.config import Settings
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.output import SpeechOutput
from src.jade_runtime.realtime_tts import SpokenAudio


class RuntimeRealtimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_route_to_realtime_once_and_preserve_spoken_text(self):
        settings = Settings()
        self.assertEqual((settings.model, settings.stt_model, settings.tts_model),
                         ("gpt-6-luna", "gpt-transcribe", "gpt-realtime-2.1-mini"))
        client = SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(create=AsyncMock())))
        response = SpokenAudio(b"RIFFsynthetic", "Il y a trois chats.")
        with patch("src.jade_runtime.openai_services.RealtimeTTS") as adapter:
            adapter.return_value.synthesize = AsyncMock(return_value=response)
            service = OpenAIServices(settings, client=client)
            self.assertIs(await service.synthesize_speech("Il y a 3 chats."), response)
            adapter.assert_called_once_with(client, model=settings.tts_model, voice=settings.voice,
                                            timeout_seconds=settings.timeout_seconds,
                                            verify_transcript=False)
            adapter.return_value.synthesize.assert_awaited_once_with("Il y a 3 chats.")
            client.audio.speech.create.assert_not_awaited()

    async def test_realtime_failure_does_not_trigger_fallback(self):
        client = SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(create=AsyncMock())))
        with patch("src.jade_runtime.openai_services.RealtimeTTS") as adapter:
            adapter.return_value.synthesize = AsyncMock(side_effect=RuntimeError("synthetic"))
            service = OpenAIServices(Settings(), client=client)
            with self.assertRaises(RuntimeError):
                await service.synthesize_wav("Bonjour")
            adapter.return_value.synthesize.assert_awaited_once()
            client.audio.speech.create.assert_not_awaited()

    async def test_subtitle_reflects_spoken_transcript_and_is_cleared(self):
        class Services:
            async def synthesize_speech(self, text):
                return SpokenAudio(b"RIFFsynthetic", "Trois chats.")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "subtitle.txt"
            class Player:
                async def play(self, audio):
                    self.audio = audio
                    self.subtitle = path.read_text(encoding="utf-8")
            player = Player()
            await SpeechOutput(Services(), player, path).speak(
                Reply(Incoming("console", "test", "hello"), "3 chats."))
            self.assertEqual(player.audio, b"RIFFsynthetic")
            self.assertEqual(player.subtitle, "Trois chats.")
            self.assertEqual(path.read_text(encoding="utf-8"), "")

    async def test_real_sdk_client_retries_are_disabled(self):
        services = OpenAIServices(Settings(api_key="synthetic-test-value"))
        try:
            self.assertEqual(services.client.max_retries, 0)
            self.assertEqual(str(services.client.base_url), "https://api.openai.com/v1/")
        finally:
            await services.client.close()
