"""Guardrails for Jade's Responses output budget and safe exhaustion diagnostics."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from src.jade_runtime.config import Settings
from src.jade_runtime.responses_chat import ResponsesChat, _require_completed


class OutputBudgetTests(unittest.TestCase):
    def test_default_has_room_for_nontrivial_reasoning_and_speech(self):
        settings = Settings()
        self.assertEqual(settings.max_completion_tokens, 2048)
        api = ResponsesChat(None, settings)
        args = api._arguments([], with_tools=True)
        self.assertEqual(args["max_output_tokens"], 2048)
        self.assertEqual(args["reasoning"]["effort"], "low")

    def test_explicit_override_remains_in_effect(self):
        settings = NS(model="model", reasoning_effort="low", max_completion_tokens=320)
        self.assertEqual(ResponsesChat(None, settings)._arguments([])["max_output_tokens"], 320)

    def test_incomplete_logs_usage_without_private_text_or_retry(self):
        usage = NS(output_tokens=320, output_tokens_details=NS(reasoning_tokens=256))
        response = NS(status="incomplete", incomplete_details=NS(reason="max_output_tokens"),
                      max_output_tokens=320, usage=usage, output_text="PRIVATE CONTENT")
        with patch("src.jade_runtime.responses_chat.summary") as summary, \
             patch("src.jade_runtime.responses_chat.event") as event:
            with self.assertRaisesRegex(RuntimeError, "max_output_tokens"):
                _require_completed(response)
        summary.assert_called_once()
        event.assert_called_once()
        self.assertEqual(summary.call_args.args, ("llm_output_limit_reached",))
        fields = summary.call_args.kwargs
        self.assertEqual(fields, {"configured_cap": 320, "output_tokens": 320,
                                  "reasoning_tokens": 256})
        self.assertNotIn("PRIVATE CONTENT", str(fields))

    def test_other_errors_do_not_emit_budget_events(self):
        response = NS(status="failed", incomplete_details=None, error="failure")
        with patch("src.jade_runtime.responses_chat.summary") as summary:
            with self.assertRaises(RuntimeError):
                _require_completed(response)
        summary.assert_not_called()


class OutputLimitFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_response_exhaustion_uses_one_call_and_no_memory_action(self):
        from src.jade_runtime.responses_chat import OUTPUT_TOO_LONG_FALLBACK
        response = NS(status="incomplete",
                      incomplete_details=NS(reason="max_output_tokens"),
                      output_text="PRIVATE PARTIAL", output=[], usage=None)
        class FakeResponses:
            def __init__(self):
                self.calls = 0
            async def create(self, **kwargs):
                self.calls += 1
                return response
        stub = FakeResponses()
        backend = ResponsesChat(NS(responses=stub),
                                NS(model="test", max_completion_tokens=320,
                                   reasoning_effort="low"))
        async def forbidden_action(raw):
            raise AssertionError("Never execute incomplete memory actions")
        result = await backend.complete_with_tools([], forbidden_action)
        self.assertEqual(result, OUTPUT_TOO_LONG_FALLBACK)
        self.assertEqual(stub.calls, 1)
        self.assertNotIn("PRIVATE PARTIAL", result)

    async def test_tool_free_response_exhaustion_returns_short_fallback(self):
        from src.jade_runtime.responses_chat import OUTPUT_TOO_LONG_FALLBACK
        class FakeResponses:
            async def create(self, **kwargs):
                return NS(status="incomplete",
                          incomplete_details=NS(reason="max_output_tokens"),
                          output_text="PRIVATE PARTIAL")
        backend = ResponsesChat(NS(responses=FakeResponses()),
                                NS(model="test", max_completion_tokens=320,
                                   reasoning_effort="low"))
        self.assertEqual(await backend.complete([]), OUTPUT_TOO_LONG_FALLBACK)

    async def test_stream_incomplete_without_audio_yields_fallback(self):
        from src.jade_runtime.responses_chat import OUTPUT_TOO_LONG_FALLBACK
        class FakeStream:
            def __aiter__(self):
                return self
            async def __anext__(self):
                if getattr(self, "read", False):
                    raise StopAsyncIteration
                self.read = True
                return NS(type="response.incomplete", response=NS(
                    status="incomplete", incomplete_details=NS(reason="max_output_tokens")))
            async def aclose(self):
                self.closed = True
        class FakeResponses:
            async def create(self, **kwargs):
                return FakeStream()
        backend = ResponsesChat(NS(responses=FakeResponses()),
                                NS(model="test", max_completion_tokens=320,
                                   reasoning_effort="low"))
        pieces = [part async for part in backend.complete_stream_with_tools([], None)]
        self.assertEqual(pieces, [OUTPUT_TOO_LONG_FALLBACK])


if __name__ == "__main__":
    unittest.main()
