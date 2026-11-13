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
    async def test_shutdown_closes_audio_session_before_client(self):
        order = []

        async def close_audio():
            order.append("audio")

        async def close_client():
            order.append("client")

        service = OpenAIServices(Settings(), client=SimpleNamespace(close=close_client))
        service._stream_pool = SimpleNamespace(close=close_audio)
        await service.close()
        self.assertEqual(order, ["audio", "client"])

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
                                            speed=1.5,
                                            timeout_seconds=settings.timeout_seconds,
                                            verify_transcript=False)
            adapter.return_value.synthesize.assert_awaited_once_with("Il y a 3 chats.")
            client.audio.speech.create.assert_not_awaited()

    async def test_configured_speed_reaches_legacy_speech_api_once(self):
        create = AsyncMock(return_value=SimpleNamespace(content=b"RIFFsynthetic"))
        client = SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(create=create)))
        service = OpenAIServices(Settings(tts_model="gpt-4o-mini-tts", tts_speed=1.25), client=client)
        await service.synthesize_speech("Bonjour")
        self.assertEqual(create.await_args.kwargs["speed"], 1.25)

    async def test_streamed_synthesis_uses_same_speed_and_one_request(self):
        sentinel = object()
        with patch("src.jade_runtime.openai_services.RealtimeTTS") as adapter:
            adapter.return_value.stream_pcm.return_value = sentinel
            service = OpenAIServices(Settings(tts_speed=1.25), client=object())
            self.assertIs(service.stream_speech_pcm("Bonjour"), sentinel)
            adapter.return_value.stream_pcm.assert_called_once_with("Bonjour")
            self.assertEqual(adapter.call_args.kwargs["speed"], 1.25)
            self.assertIs(adapter.call_args.kwargs["connection_pool"], service._stream_pool)
        non_realtime = OpenAIServices(Settings(tts_model="gpt-4o-mini-tts"), client=object())
        self.assertIsNone(non_realtime.stream_speech_pcm("Bonjour"))

    async def test_streamed_completion_yields_deltas_and_closes(self):
        class Stream:
            def __init__(self):
                self.closed = False
            def __aiter__(self):
                self.parts = iter([
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Bon"), finish_reason=None)]),
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="jour"), finish_reason=None)]),
                    SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="stop")]),
                ])
                return self
            async def __anext__(self):
                try:
                    return next(self.parts)
                except StopIteration:
                    raise StopAsyncIteration
            async def close(self):
                self.closed = True
        stream = Stream()
        create = AsyncMock(return_value=stream)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        service = OpenAIServices(Settings(), client=client)
        self.assertEqual([part async for part in service.complete_stream([])], ["Bon", "jour"])
        self.assertTrue(stream.closed)
        self.assertTrue(create.await_args.kwargs["stream"])

        stream = Stream()
        create.return_value = stream
        generator = service.complete_stream([])
        self.assertEqual(await anext(generator), "Bon")
        await generator.aclose()
        self.assertTrue(stream.closed)

    async def test_speed_rejects_invalid_values(self):
        for value in (True, 0.0, 1.6, float("nan"), float("inf"), "1.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Settings(tts_speed=value).validate()

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
