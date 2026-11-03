"""OpenAI transcription model compatibility without live API requests."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.jade_runtime.config import Settings
from src.jade_runtime.openai_services import OpenAIServices


class TranscriptionModelsTest(unittest.IsolatedAsyncioTestCase):
    async def test_language_fields_follow_the_selected_model(self):
        audio = b"RIFF" + b"0" * 50
        for model, expected in (
            ("gpt-transcribe", {"extra_body": {"languages": ["fr"]}}),
            ("gpt-4o-mini-transcribe", {"language": "fr"}),
            ("whisper-1", {"language": "fr"}),
        ):
            with self.subTest(model=model):
                create = AsyncMock(return_value=SimpleNamespace(text=" Bonjour "))
                client = SimpleNamespace(audio=SimpleNamespace(
                    transcriptions=SimpleNamespace(create=create)))
                services = OpenAIServices(Settings(stt_model=model), client=client)

                self.assertEqual(await services.transcribe_wav(audio), "Bonjour")
                create.assert_awaited_once()
                arguments = create.await_args.kwargs
                self.assertEqual(arguments.pop("model"), model)
                uploaded = arguments.pop("file")
                self.assertEqual(uploaded.name, "speech.wav")
                self.assertEqual(uploaded.getvalue(), audio)
                self.assertEqual(arguments, expected)

    async def test_invalid_audio_never_reaches_the_api(self):
        create = AsyncMock()
        client = SimpleNamespace(audio=SimpleNamespace(
            transcriptions=SimpleNamespace(create=create)))
        services = OpenAIServices(Settings(stt_model="gpt-transcribe"), client=client)

        with self.assertRaises(ValueError):
            await services.transcribe_wav(b"RIFF")
        create.assert_not_awaited()

    async def test_sdk_encodes_new_language_field_in_multipart(self):
        # openai 3.x uses httpx2; older supported releases use httpx.
        import openai
        if int(openai.__version__.split(".")[0]) >= 3:
            import httpx2 as httpx
        else:
            import httpx

        requests = []

        async def handle(request):
            requests.append(await request.aread())
            return httpx.Response(200, json={"text": "Bonjour"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            client = openai.AsyncOpenAI(api_key="test-placeholder", http_client=http)
            services = OpenAIServices(Settings(stt_model="gpt-transcribe"), client=client)
            self.assertEqual(await services.transcribe_wav(b"RIFF" + b"0" * 50), "Bonjour")

        self.assertEqual(len(requests), 1)
        self.assertRegex(requests[0], rb'name="languages(?:\[\])?"\r\n\r\nfr\r\n')
        self.assertNotIn(b'name="language"', requests[0])
