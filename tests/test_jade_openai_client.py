"""Hostile SDK environment must not redirect or replace Jade's API key."""
import os
import unittest
from unittest.mock import patch

from src.jade_runtime.config import Settings
from src.jade_runtime.openai_client import isolated_openai_client
from src.jade_runtime.openai_services import OpenAIServices


HOSTILE_ENV = {
    "OPENAI_BASE_URL": "https://elsewhere.invalid/v1",
    "OPENAI_API_KEY": "foreign-synthetic-key",
    "OPENAI_ORG_ID": "foreign-org",
    "OPENAI_PROJECT_ID": "foreign-project",
    "OPENAI_CUSTOM_HEADERS": "authorization: Bearer foreign-token\n"
                             "X-Foreign-Private: private-value\n"
                             "content-type: text/plain\n"
                             "OpenAI-Project: foreign-project",
}


class RuntimeClientIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_factory_keeps_chat_and_multipart_on_selected_account(self):
        import httpx2
        requests = []

        def respond(request):
            requests.append(request)
            if request.url.path.endswith("/audio/transcriptions"):
                return httpx2.Response(200, json={"text": "Salut"})
            return httpx2.Response(200, json={"choices": [{"message": {"content": "Bonjour"}}]})

        http = httpx2.AsyncClient(transport=httpx2.MockTransport(respond), trust_env=False)
        with patch.dict(os.environ, HOSTILE_ENV), patch(
            "src.jade_runtime.openai_services.isolated_openai_client",
            side_effect=lambda settings: isolated_openai_client(settings, http_client=http),
        ):
            services = OpenAIServices(Settings(api_key="synthetic-key"))
            try:
                self.assertEqual(await services.complete([{"role": "user", "content": "Salut"}]), "Bonjour")
                self.assertEqual(await services.transcribe_wav(b"RIFF" + bytes(50)), "Salut")
                self.assertEqual(len(requests), 2)
                for request in requests:
                    self.assertEqual(request.url.host, "api.openai.com")
                    self.assertEqual(request.headers["Authorization"], "Bearer synthetic-key")
                    self.assertNotIn("X-Foreign-Private", request.headers)
                    self.assertNotIn("OpenAI-Project", request.headers)
                    self.assertNotIn("OpenAI-Organization", request.headers)
                self.assertTrue(requests[1].headers["Content-Type"].startswith("multipart/form-data; boundary="))
            finally:
                await services.client.close()

    async def test_runtime_realtime_websocket_keeps_selected_account(self):
        from openai.lib import _websocket
        captured = {}
        async def fake_connect(url, **kwargs):
            captured.update(url=url, **kwargs)
            return object()
        with patch.dict(os.environ, HOSTILE_ENV), patch.object(_websocket, "_WebSocketConnect", fake_connect):
            services = OpenAIServices(Settings(api_key="synthetic-key"))
            try:
                manager = services.client.realtime.connect(model="gpt-realtime-2.1-mini", max_retries=0)
                await manager._connect_ws({}, {})
                headers = {key.lower(): value for key, value in captured["additional_headers"].items()}
                self.assertTrue(str(captured["url"]).startswith("wss://api.openai.com/v1/realtime?"))
                self.assertEqual(headers["authorization"], "Bearer synthetic-key")
                self.assertNotIn("x-foreign-private", headers)
                self.assertNotIn("openai-project", headers)
                self.assertNotIn("openai-organization", headers)
            finally:
                await services.client.close()
