"""Offline coverage for the provider-neutral, persistent Jade web tool."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.responses_chat import ResponsesChat
from src.jade_runtime.web_search import (
    SearchHit, SearchJournal, SearchResponse, ToolActions,
    WebSearchService, build_web_search_service, WEB_PROMPT,
)
from src.jade_runtime.web_providers.tavily import TavilyProvider


class StubProvider:
    name = "stub"

    def __init__(self):
        self.queries = []

    async def search(self, query, *, max_results, timeout):
        self.queries.append((query, max_results, timeout))
        return SearchResponse((SearchHit("Titre", "https://example.org/fact", "Texte"),),
                              credits=1, provider_request_id="provider-123")


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory()
        self.addAsyncCleanup(asyncio.to_thread, self.temp.cleanup)
        self.path = Path(self.temp.name) / "web-search.jsonl"
        self.provider = StubProvider()
        self.service = WebSearchService(
            self.provider, SearchJournal(self.path), max_per_turn=2)
        self.incoming = Incoming(platform="discord", channel="test",
                                 author="utilisateur", text="Question ?",
                                 force_reply=True)

    def entries(self):
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    async def test_success_has_durable_started_and_completed_with_reason(self):
        action = self.service.for_turn(self.incoming, 42)
        result = await action(json.dumps({
            "query": "prix or aujourd'hui", "reason": "Information actuelle",
        }), call_id="c-1")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["results"][0]["url"], "https://example.org/fact")
        log = self.entries()
        self.assertEqual([entry["status"] for entry in log], ["started", "success"])
        self.assertEqual(log[0]["search_id"], log[1]["search_id"])
        self.assertEqual(log[0]["reason"], "Information actuelle")
        self.assertEqual(log[0]["turn"], 42)
        self.assertEqual(log[1]["credits"], 1)
        self.assertIn("+00:00", log[0]["timestamp"])
        self.assertNotIn("TAVILY_API_KEY", self.path.read_text())

    async def test_invalid_arguments_and_turn_limit_are_audited(self):
        action = self.service.for_turn(self.incoming, 2)
        invalid = await action('{"query": ""}', call_id="bad")
        self.assertEqual(invalid["status"], "refusé")
        for n in range(3):
            last = await action(json.dumps({"query": str(n), "reason": "Vérification"}))
        self.assertEqual(last["status"], "limite_atteinte")
        self.assertEqual(len(self.provider.queries), 2)
        self.assertEqual(
            [x["status"] for x in self.entries()],
            ["rejected", "started", "success", "started", "success", "rejected"],
        )

    async def test_no_search_when_journal_is_unwritable(self):
        # A directory masquerading as a log path prevents durable recording.
        blocked = Path(self.temp.name) / "blocked.jsonl"
        blocked.mkdir()
        service = WebSearchService(self.provider, SearchJournal(blocked))
        with self.assertRaises(OSError):
            await service.for_turn(self.incoming, 1)(
                json.dumps({"query": "test", "reason": "verification"}))
        self.assertEqual(self.provider.queries, [])

    async def test_memory_and_web_actions_coexist(self):
        class MemoryAction:
            used = False
            write_enabled = True

            async def __call__(self, arguments):
                return {"status": "enregistré"}

            async def search(self, arguments):
                return {"status": "ok", "items": []}

        memory = MemoryAction()
        tools = ToolActions(memory, self.service.for_turn(self.incoming, 1))
        self.assertTrue(tools.write_enabled)
        self.assertTrue(callable(tools.search))
        self.assertTrue(callable(tools.web_search))
        tools.used = True
        self.assertTrue(memory.used)
        self.assertEqual((await tools("{}"))["status"], "enregistré")
        web_only = ToolActions(None, self.service.for_turn(self.incoming, 2))
        self.assertFalse(web_only.write_enabled)
        self.assertIsNone(web_only.search)
        self.assertTrue(callable(web_only.web_search))

    async def test_model_can_see_web_without_memory_and_no_extra_turn_if_unused(self):
        class Backend:
            calls = 0

            async def complete_with_tools(self, messages, action):
                self.calls += 1
                self.action = action
                return "[INTENT:neutral] Réponse normale."

        backend = Backend()
        dialogue = Dialogue(backend, "Tu es Jade.", random_reply_rate=0)
        result = await dialogue.respond(self.incoming,
            web_action=self.service.for_turn(self.incoming, 7))
        self.assertIn("Réponse normale", result.text)
        self.assertEqual(backend.calls, 1)
        self.assertFalse(self.path.exists())
        fake_settings = SimpleNamespace(model="fake", reasoning_effort="low",
                                        max_completion_tokens=512)
        client = ResponsesChat(None, fake_settings)
        params = client._arguments([], with_tools=True,
                                   memory_action=backend.action)
        self.assertEqual(
            [tool["name"] for tool in params["tools"]], ["jade_web_search"])
        self.assertEqual(params["tool_choice"], "auto")
        self.assertNotIn("TAVILY_API_KEY", json.dumps(params))

    async def test_settings_require_key_only_when_web_enabled(self):
        Settings(web_enabled=False).validate()
        with self.assertRaises(ValueError):
            Settings(web_enabled=True).validate()
        cfg = Settings(web_enabled=True, tavily_api_key="tvly-test",
                       web_log_path=str(self.path))
        cfg.validate()
        service = build_web_search_service(cfg)
        self.assertEqual(service.provider.name, "tavily")
        self.assertIsNone(build_web_search_service(Settings()))


    async def test_tool_result_is_returned_to_model_before_final_answer(self):
        class FakeResponses:
            def __init__(self):
                self.calls = []

            async def create(self, **kwargs):
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    return SimpleNamespace(
                        status="completed", output_text="", output=[
                            SimpleNamespace(
                                type="function_call", call_id="web_1",
                                name="jade_web_search",
                                arguments=json.dumps({
                                    "query": "actualité", "reason": "Vérifier un fait récent"
                                }),
                            )
                        ])
                return SimpleNamespace(
                    status="completed", output_text="Voici la source consultée.",
                    output=[SimpleNamespace(type="message", content=[
                        SimpleNamespace(type="output_text", text="Voici la source consultée.")
                    ])],
                )

        fake = FakeResponses()
        backend = ResponsesChat(
            SimpleNamespace(responses=fake),
            SimpleNamespace(model="fake", reasoning_effort="low",
                            max_completion_tokens=512),
        )
        action = ToolActions(None, self.service.for_turn(self.incoming, 15))
        reply = await backend.complete_with_tools(
            [{"role": "user", "content": "Question actuelle"}], action)
        self.assertIn("source consultée", reply)
        self.assertEqual(len(fake.calls), 2)
        final_input = fake.calls[1]["input"]
        result = next(item for item in final_input
                      if isinstance(item, dict)
                      and item.get("type") == "function_call_output")
        self.assertEqual(result["call_id"], "web_1")
        self.assertIn("https://example.org/fact", result["output"])
        self.assertEqual([e["status"] for e in self.entries()],
                         ["started", "success"])

    async def test_provider_error_is_logged_without_exception_or_secret_text(self):
        class FailingProvider:
            name = "stub"

            async def search(self, *args, **kwargs):
                raise RuntimeError("private-header-token-should-not-appear")

        service = WebSearchService(
            FailingProvider(), SearchJournal(self.path))
        response = await service.for_turn(self.incoming, 16)(
            json.dumps({"query": "test", "reason": "Vérifier"}))
        self.assertEqual(response["status"], "indisponible")
        entries = self.entries()
        self.assertEqual([e["status"] for e in entries], ["started", "failed"])
        self.assertEqual(entries[1]["error_type"], "RuntimeError")
        self.assertNotIn("private-header-token-should-not-appear",
                         self.path.read_text(encoding="utf-8"))


class WebPromptBehaviorTests(unittest.TestCase):
    def test_source_urls_are_optional_in_user_facing_answers(self):
        # Documentation of the product policy, independent of provider output.
        self.assertIn("ne joins PAS automatiquement de liens", WEB_PROMPT)
        self.assertIn("demande explicitement un lien", WEB_PROMPT)
        self.assertIn("Ne prononce aucune URL à l'oral", WEB_PROMPT)
        self.assertIn("journal de recherche", WEB_PROMPT)
        self.assertNotIn("cite les URL utiles", WEB_PROMPT)


class TavilyProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_contract_and_normalization(self):
        captures = {}

        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "results": [
                        {"title": "Page", "url": "https://example.org/page",
                         "content": "Fait réel", "published_date": "2026-11-22"},
                        {"title": "Bad", "url": "javascript:alert(1)", "content": "Ignore"}
                    ],
                    "usage": {"credits": 1},
                    "request_id": "rid",
                }

        def post(url, *, headers, json, timeout):
            captures.update({"url": url, "headers": headers,
                             "body": json, "timeout": timeout})
            return Response()

        provider = TavilyProvider("tvly-test-secret", post=post)
        response = await provider.search("test", max_results=5, timeout=3)
        self.assertEqual(captures["url"], "https://api.tavily.com/search")
        self.assertEqual(captures["body"]["search_depth"], "basic")
        self.assertTrue(captures["body"]["include_usage"])
        self.assertEqual(captures["headers"]["Authorization"], "Bearer tvly-test-secret")
        self.assertEqual(response.credits, 1)
        self.assertEqual(len(response.results), 1)


if __name__ == "__main__":
    unittest.main()
