"""Offline contract tests for Jade's stateless Responses API migration.

No OpenAI credentials, network, Discord or audio dependencies are needed.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

import pytest

from src.jade_runtime.config import Settings
from src.jade_runtime.openai_services import OpenAIServices


def text_response(text="[INTENT:neutral] Bonjour", *, status="completed"):
    return NS(
        id="resp-text", status=status, output_text=text,
        output=[NS(type="message", content=[NS(type="output_text", text=text)])],
        usage=NS(input_tokens=123, output_tokens=19),
        incomplete_details=NS(reason="max_output_tokens") if status == "incomplete" else None,
    )


def tool_response(*, calls=None, status="completed"):
    calls = calls or [NS(type="function_call", call_id="call-1",
                         name="jade_save_memory", arguments='{"kind":"ordinary"}')]
    return NS(
        id="resp-tool", status=status, output_text="",
        output=[NS(type="reasoning", encrypted_content="encrypted-reasoning"), *calls],
        usage=NS(input_tokens=83, output_tokens=18),
        incomplete_details=None,
    )


def streaming_text(text="[INTENT:neutral] Bonjour"):
    async def generator():
        yield NS(type="response.created")
        yield NS(type="response.output_item.added", item=NS(type="message"))
        yield NS(type="response.output_text.delta", delta=text[:14])
        yield NS(type="response.output_text.delta", delta=text[14:])
        yield NS(type="response.completed", response=text_response(text))
    return generator()


class FakeResponses:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    async def create(self, **params):
        self.calls.append(params)
        if not self.results:
            raise AssertionError("Unplanned provider call")
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def service_with(*responses, model="gpt-6-luna", reasoning="low"):
    fake = FakeResponses(responses)
    client = NS(responses=fake)
    return OpenAIServices(Settings(model=model, reasoning_effort=reasoning), client=client), fake


async def no_tool(arguments):
    raise AssertionError("A local memory write was not requested")


def test_plain_text_preserves_original_low_and_never_uses_chat_completions():
    service, fake = service_with(text_response())
    result = asyncio.run(service.complete([{"role": "user", "content": "Bonjour"}]))
    assert "Bonjour" in result
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["model"] == "gpt-6-luna"
    assert call["reasoning"] == {"effort": "low"}
    assert call["store"] is False
    assert call["max_output_tokens"] == 320
    assert "tools" not in call
    assert "previous_response_id" not in call
    assert "conversation" not in call


def test_memory_available_but_unused_is_still_low():
    service, fake = service_with(text_response())
    result = asyncio.run(service.complete_with_tools(
        [{"role": "user", "content": "Bonjour"}], no_tool))
    assert result.endswith("Bonjour")
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["reasoning"] == {"effort": "low"}
    assert call["store"] is False
    assert call["tool_choice"] == "auto"
    assert call["parallel_tool_calls"] is False
    assert call["include"] == ["reasoning.encrypted_content"]
    schema = call["tools"][0]
    assert schema["type"] == "function"
    assert schema["name"] == "jade_save_memory"
    assert schema["strict"] is True
    assert schema["parameters"]["additionalProperties"] is False
    assert set(schema["parameters"]["required"]) == set(schema["parameters"]["properties"])
    assert "function" not in schema


def test_memory_call_is_local_and_continuation_replays_reasoning():
    first = tool_response()
    last = text_response("[INTENT:playful] Je m'en souviendrai.")
    service, fake = service_with(first, last)
    recorded = []

    async def action(arguments):
        recorded.append(arguments)
        return {"status": "enregistré", "level": 2}

    result = asyncio.run(service.complete_with_tools(
        [{"role": "system", "content": "Tu es Jade"},
         {"role": "user", "content": "Je commence le piano"}], action))
    assert "Je m'en souviendrai" in result
    assert recorded == ['{"kind":"ordinary"}']
    assert len(fake.calls) == 2
    first_call, second = fake.calls
    assert first_call["reasoning"]["effort"] == "low"
    assert second["reasoning"]["effort"] == "low"
    assert first_call["store"] is second["store"] is False
    assert "tools" not in second
    items = second["input"]
    assert items[0]["role"] == "system"
    assert items[1]["role"] == "user"
    assert items[2].type == "reasoning"
    assert items[2].encrypted_content == "encrypted-reasoning"
    assert items[3].type == "function_call"
    assert items[4]["type"] == "function_call_output"
    assert items[4]["call_id"] == "call-1"
    assert "enregistré" in items[4]["output"]


def test_unknown_tool_is_refused_and_never_executed():
    first = tool_response(calls=[NS(type="function_call", call_id="x",
                                    name="execute_shell", arguments='{"cmd":"rm"}')])
    service, fake = service_with(first, text_response())
    asyncio.run(service.complete_with_tools(
        [{"role": "user", "content": "hello"}], no_tool))
    assert '"refusé"' in fake.calls[1]["input"][-1]["output"]


def test_multiple_calls_allow_one_write_only():
    calls = [NS(type="function_call", call_id=f"call-{i}",
                name="jade_save_memory", arguments='{"kind":"ordinary"}')
             for i in range(3)]
    service, fake = service_with(tool_response(calls=calls), text_response())
    invoked = []

    async def action(arguments):
        invoked.append(arguments)
        return {"status": "enregistré"}

    asyncio.run(service.complete_with_tools(
        [{"role": "user", "content": "Bonjour"}], action))
    assert len(invoked) == 1
    outputs = fake.calls[1]["input"][-3:]
    assert [item["call_id"] for item in outputs] == ["call-0", "call-1", "call-2"]
    assert "refusé" in outputs[1]["output"]
    assert "refusé" in outputs[2]["output"]


def test_duplicate_call_ids_raise_before_writing():
    calls = [NS(type="function_call", call_id="same",
                name="jade_save_memory", arguments="{}")
             for _ in range(2)]
    service, fake = service_with(tool_response(calls=calls))
    with pytest.raises(ValueError, match="duplicate"):
        asyncio.run(service.complete_with_tools(
            [{"role": "user", "content": "Bonjour"}], no_tool))
    assert len(fake.calls) == 1


def test_incomplete_response_never_writes_memory():
    service, fake = service_with(tool_response(status="incomplete"))
    with pytest.raises(RuntimeError, match="not completed"):
        asyncio.run(service.complete_with_tools(
            [{"role": "user", "content": "Bonjour"}], no_tool))
    assert len(fake.calls) == 1


def test_regular_stream_yields_fragments_with_low_and_no_tools():
    stream = streaming_text()
    service, fake = service_with(stream)

    async def run():
        return [fragment async for fragment in service.complete_stream(
            [{"role": "user", "content": "Bonjour"}])]

    fragments = asyncio.run(run())
    assert len(fragments) == 2
    assert "".join(fragments) == "[INTENT:neutral] Bonjour"
    assert fake.calls[0]["stream"] is True
    assert fake.calls[0]["reasoning"]["effort"] == "low"
    assert fake.calls[0]["store"] is False


def test_stream_with_memory_available_does_not_speak_before_tool_result():
    service, fake = service_with(tool_response(), streaming_text())
    invoked = []

    async def action(arguments):
        invoked.append(arguments)
        return {"status": "enregistré"}

    async def run():
        return [part async for part in service.complete_stream_with_tools(
            [{"role": "user", "content": "Je commence le piano"}], action)]

    result = asyncio.run(run())
    assert "".join(result).endswith("Bonjour")
    assert len(invoked) == 1
    assert len(fake.calls) == 2
    assert fake.calls[0].get("stream") is None
    assert fake.calls[1]["stream"] is True
    assert fake.calls[0]["reasoning"]["effort"] == "low"
    assert fake.calls[1]["reasoning"]["effort"] == "low"
    assert fake.calls[0]["store"] is fake.calls[1]["store"] is False


def test_stream_with_unused_tool_remains_low_and_speaks_once():
    service, fake = service_with(text_response("[INTENT:neutral] Coucou"))

    async def run():
        return [part async for part in service.complete_stream_with_tools(
            [{"role": "user", "content": "Coucou"}], no_tool)]

    assert asyncio.run(run()) == ["[INTENT:neutral] Coucou"]
    assert fake.calls[0]["reasoning"]["effort"] == "low"
    assert len(fake.calls) == 1


def test_stream_missing_terminal_event_is_not_success():
    async def broken():
        yield NS(type="response.output_text.delta", delta="[INTENT:neutral] Bonjour")
    service, _ = service_with(broken())

    async def run():
        return [part async for part in service.complete_stream(
            [{"role": "user", "content": "Bonjour"}])]

    with pytest.raises(RuntimeError, match="without response.completed"):
        asyncio.run(run())


def test_stream_with_different_final_text_is_not_success():
    async def broken():
        yield NS(type="response.output_text.delta", delta="Wrong")
        yield NS(type="response.completed", response=text_response("Correct"))
    service, _ = service_with(broken())

    async def run():
        return [part async for part in service.complete_stream(
            [{"role": "user", "content": "Bonjour"}])]

    with pytest.raises(ValueError, match="differs"):
        asyncio.run(run())


def test_failed_write_returns_explicit_failure_to_model():
    service, fake = service_with(tool_response(), text_response())

    async def broken_action(arguments):
        raise RuntimeError("SQLite locked")

    asyncio.run(service.complete_with_tools(
        [{"role": "user", "content": "Je commence le piano"}], broken_action))
    assert '"échec"' in fake.calls[1]["input"][-1]["output"]


def test_provider_exception_propagates_without_retry():
    service, fake = service_with(RuntimeError("HTTP 429"))
    with pytest.raises(RuntimeError, match="429"):
        asyncio.run(service.complete_with_tools(
            [{"role": "user", "content": "Bonjour"}], no_tool))
    assert len(fake.calls) == 1
