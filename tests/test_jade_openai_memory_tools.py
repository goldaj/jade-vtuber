"""DEV-012: Responses API memory tools and streaming, with offline synthetic clients."""
import unittest
from types import SimpleNamespace as NS

from src.jade_runtime.config import Settings
from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.memory_actions import MEMORY_TOOL


def response(text="", *, calls=()):
    items = ([NS(type="message", content=[NS(type="output_text", text=text)])]
             if text else [])
    return NS(status="completed", output_text=text, output=[*items, *calls])


def tool_call(arguments='{"kind":"ordinary"}'):
    return NS(type="function_call", call_id="call_1",
              name="jade_save_memory", arguments=arguments)


class FakeStream:
    def __init__(self, events):
        self.events = list(events)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.events:
            raise StopAsyncIteration
        return self.events.pop(0)

    async def aclose(self):
        self.closed = True


class FakeResponses:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.replies:
            raise AssertionError("Unexpected extra LLM request")
        return self.replies.pop(0)


class FakeClient:
    def __init__(self, replies):
        self.responses = FakeResponses(replies)


def stub_service(replies):
    client = FakeClient(replies)
    return OpenAIServices(Settings(), client=client), client.responses


class OpenAIToolProtocol(unittest.IsolatedAsyncioTestCase):
    async def test_abstain_uses_one_request(self):
        service, provider = stub_service([response("[INTENT:neutral] Bonjour.")])
        async def unexpected(_):
            raise AssertionError("the model did not request a tool")
        output = await service.complete_with_tools(
            [{"role": "user", "content": "Bonjour"}], unexpected)
        self.assertIn("Bonjour", output)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0]["tool_choice"], "auto")
        self.assertFalse(provider.calls[0]["store"])
        self.assertEqual(MEMORY_TOOL["function"]["name"], "jade_save_memory")

    async def test_tool_call_and_continuation_receive_result(self):
        service, provider = stub_service([
            response(calls=[tool_call()]),
            response("Je viens de mémoriser ce fait."),
        ])
        seen = []
        async def execute(raw):
            seen.append(raw)
            return {"status": "enregistré", "level": 2}
        result = await service.complete_with_tools(
            [{"role": "user", "content": "un fait"}], execute)
        await service._responses.close()
        self.assertIn("mémoriser", result)
        self.assertEqual(seen, ['{"kind":"ordinary"}'])
        self.assertEqual(len(provider.calls), 2)
        followup = provider.calls[1]["input"]
        self.assertEqual(followup[-1]["type"], "function_call_output")
        self.assertIn("enregistré", followup[-1]["output"])
        # Jade can elect another voluntary action after seeing the first result.
        self.assertIn("tools", provider.calls[1])
        self.assertTrue(any(tool.get("name") == "jade_save_memory"
                            for tool in provider.calls[1]["tools"]))

    async def test_streamed_arguments_never_reach_voice_and_continue_normally(self):
        called = tool_call()
        before = FakeStream([
            NS(type="response.function_call_arguments.delta", delta='{"kind":'),
            NS(type="response.function_call_arguments.delta", delta='"ordinary"}'),
            NS(type="response.completed", response=response(calls=[called])),
        ])
        spoken = "[INTENT:neutral] C'est noté."
        after = FakeStream([
            NS(type="response.output_text.delta", delta=spoken),
            NS(type="response.completed", response=response(spoken)),
        ])
        service, provider = stub_service([before, after])
        seen = []
        async def execute(raw):
            seen.append(raw)
            return {"status": "échec", "level": 2}
        output = [text async for text in service.complete_stream_with_tools(
            [{"role": "user", "content": "message"}], execute)]
        await service._responses.close()
        self.assertEqual(output, [spoken])
        self.assertEqual(seen, ['{"kind":"ordinary"}'])
        self.assertEqual(len(provider.calls), 2)
        self.assertTrue(before.closed)
        self.assertTrue(after.closed)

    async def test_streaming_abstains_without_followup(self):
        spoken = "Salut."
        stream = FakeStream([
            NS(type="response.output_text.delta", delta=spoken),
            NS(type="response.completed", response=response(spoken)),
        ])
        service, provider = stub_service([stream])
        async def unexpected(_):
            raise AssertionError("no tool was called")
        output = [token async for token in service.complete_stream_with_tools(
            [], unexpected)]
        self.assertEqual(output, [spoken])
        self.assertEqual(len(provider.calls), 1)
        self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
