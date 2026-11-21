"""Regression coverage for the Chat Completions tool/reasoning incompatibility."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.jade_runtime.config import Settings
from src.jade_runtime.openai_services import OpenAIServices


class _Completions:
    def __init__(self, *, use_memory_tool=False):
        self.calls = []
        self.use_memory_tool = use_memory_tool

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            async def chunks():
                yield SimpleNamespace(choices=[SimpleNamespace(
                    index=0, finish_reason=None,
                    delta=SimpleNamespace(content="[INTENT:neutral] Bonjour", tool_calls=None))])
                yield SimpleNamespace(choices=[SimpleNamespace(
                    index=0, finish_reason="stop",
                    delta=SimpleNamespace(content=None, tool_calls=None))])
            return chunks()
        if kwargs.get("tools") and self.use_memory_tool:
            tool = SimpleNamespace(id="call-1", function=SimpleNamespace(
                name="jade_save_memory",
                arguments='{"kind":"ordinary","summary":"Un fait","significance":"Important","evidence":"Un fait exact"}'))
            return SimpleNamespace(id="test-1", choices=[SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(content=None, tool_calls=[tool]))])
        return SimpleNamespace(id="test-2", choices=[SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content="[INTENT:neutral] Bonjour", tool_calls=[]))])


def _service(model="gpt-6-luna", *, use_memory_tool=False):
    completions = _Completions(use_memory_tool=use_memory_tool)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    service = OpenAIServices(Settings(model=model, reasoning_effort="low"), client=client)
    return service, completions


def test_tool_completion_uses_none_for_luna():
    service, completions = _service()
    async def memory_action(arguments):
        raise AssertionError("No tool was called")
    response = asyncio.run(service.complete_with_tools(
        [{"role": "user", "content": "Bonjour"}], memory_action))
    assert "Bonjour" in response
    assert completions.calls[0]["reasoning_effort"] == "none"
    assert completions.calls[0]["tools"][0]["function"]["name"] == "jade_save_memory"


def test_tool_stream_uses_none_for_luna():
    service, completions = _service()
    async def memory_action(arguments):
        raise AssertionError("No tool was called")

    async def collect():
        return [chunk async for chunk in service.complete_stream_with_tools(
            [{"role": "user", "content": "Bonjour"}], memory_action)]

    assert "Bonjour" in "".join(asyncio.run(collect()))
    assert completions.calls[0]["reasoning_effort"] == "none"
    assert completions.calls[0]["stream"] is True


def test_regular_completion_preserves_configured_reasoning():
    service, completions = _service()
    asyncio.run(service.complete([{"role": "user", "content": "Bonjour"}]))
    assert completions.calls[0]["reasoning_effort"] == "low"
    assert "tools" not in completions.calls[0]


def test_other_models_preserve_configured_reasoning_with_tools():
    service, completions = _service(model="gpt-5.6")
    async def memory_action(arguments):
        raise AssertionError("No tool was called")
    asyncio.run(service.complete_with_tools(
        [{"role": "user", "content": "Bonjour"}], memory_action))
    assert completions.calls[0]["reasoning_effort"] == "low"


def test_memory_tool_followup_remains_supported():
    service, completions = _service(use_memory_tool=True)
    received = []

    async def memory_action(arguments):
        received.append(arguments)
        return {"status": "enregistré", "level": 2}

    result = asyncio.run(service.complete_with_tools(
        [{"role": "user", "content": "Garde ce souvenir"}], memory_action))
    assert "Bonjour" in result
    assert len(received) == 1
    assert len(completions.calls) == 2
    assert completions.calls[0]["reasoning_effort"] == "none"
    # The follow-up no longer offers tools and retains the configured effort.
    assert completions.calls[1]["reasoning_effort"] == "low"
    assert "tools" not in completions.calls[1]
    assert any(message["role"] == "tool" for message in completions.calls[1]["messages"])
