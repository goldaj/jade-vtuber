"""DEV-012: OpenAI native tool protocol and streaming tests without paid calls."""
from types import SimpleNamespace as NS
import unittest

from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.memory_actions import MEMORY_TOOL


def choice(message=None, finish="stop", delta=None):
    return NS(choices=[NS(index=0, message=message, finish_reason=finish,
                          delta=delta)])


class FakeStream:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.chunks:
            raise StopAsyncIteration
        return self.chunks.pop(0)

    async def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = NS(completions=NS(create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.replies.pop(0)


def stub_service(replies):
    service = OpenAIServices.__new__(OpenAIServices)
    service.settings = NS(model="test", max_completion_tokens=500,
                          reasoning_effort="low")
    service.client = FakeClient(replies)
    return service


class OpenAIToolProtocol(unittest.IsolatedAsyncioTestCase):
    async def test_abstain_uses_one_request(self):
        service = stub_service([
            choice(NS(content="[INTENT:neutral] Bonjour.")),
        ])
        async def unexpected(_):
            raise AssertionError("the model did not request a tool")
        output = await service.complete_with_tools(
            [{"role": "user", "content": "Bonjour"}], unexpected)
        self.assertIn("Bonjour", output)
        self.assertEqual(len(service.client.calls), 1)
        self.assertEqual(service.client.calls[0]["tool_choice"], "auto")
        self.assertEqual(MEMORY_TOOL["function"]["name"], "jade_save_memory")

    async def test_tool_call_and_continuation_receive_result(self):
        called = NS(id="call_1", function=NS(
            name="jade_save_memory", arguments='{"kind":"ordinary"}'))
        service = stub_service([
            choice(NS(content=None, tool_calls=[called]), "tool_calls"),
            choice(NS(content="Je viens de mémoriser ce fait.")),
        ])
        seen = []
        async def execute(raw):
            seen.append(raw)
            return {"status": "enregistré", "level": 2}
        result = await service.complete_with_tools(
            [{"role": "user", "content": "un fait"}], execute)
        self.assertIn("mémoriser", result)
        self.assertEqual(seen, ['{"kind":"ordinary"}'])
        self.assertEqual(len(service.client.calls), 2)
        followup = service.client.calls[1]["messages"]
        self.assertEqual(followup[-1]["role"], "tool")
        self.assertIn("enregistré", followup[-1]["content"])
        self.assertNotIn("tools", service.client.calls[1])

    async def test_streamed_arguments_never_reach_voice_and_continue_normally(self):
        def delta(*, content=None, tool_calls=None):
            return NS(content=content, tool_calls=tool_calls)

        before = FakeStream([
            choice(finish=None, delta=delta(tool_calls=[
                NS(index=0, id="call_", function=NS(
                    name="jade_save_", arguments='{"kind":'))])),
            choice(finish=None, delta=delta(tool_calls=[
                NS(index=0, id="2", function=NS(
                    name="memory", arguments='"ordinary"}'))])),
            choice(finish="tool_calls", delta=delta()),
        ])
        after = FakeStream([
            choice(finish=None, delta=delta(content="[INTENT:neutral] C'est noté.")),
            choice(finish="stop", delta=delta()),
        ])
        service = stub_service([before, after])
        seen = []
        async def execute(raw):
            seen.append(raw)
            return {"status": "échec", "level": 2}
        output = []
        async for text in service.complete_stream_with_tools(
                [{"role": "user", "content": "message"}], execute):
            output.append(text)
        self.assertEqual(output, ["[INTENT:neutral] C'est noté."])
        self.assertEqual(seen, ['{"kind":"ordinary"}'])
        self.assertEqual(len(service.client.calls), 2)
        self.assertTrue(before.closed)
        self.assertTrue(after.closed)

    async def test_streaming_abstains_without_followup(self):
        stream = FakeStream([
            choice(finish=None, delta=NS(content="Salut.", tool_calls=None)),
            choice(finish="stop", delta=NS(content=None, tool_calls=None)),
        ])
        service = stub_service([stream])
        async def unexpected(_):
            raise AssertionError("no tool was called")
        output = []
        async for token in service.complete_stream_with_tools([], unexpected):
            output.append(token)
        self.assertEqual(output, ["Salut."])
        self.assertEqual(len(service.client.calls), 1)


if __name__ == "__main__":
    unittest.main()
