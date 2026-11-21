"""Stateless Responses API adapter for Jade's conversational LLM.

Only this module knows about Responses input/output types.  Discord, mobile,
TTS, STT and Jade's local SQLite memory remain outside the provider boundary.
Every request is store=False; the original per-channel dialogue is supplied by
Jade and never recovered from an OpenAI conversation identifier.
"""
from __future__ import annotations

import inspect
import json
import logging

from .memory_actions import MEMORY_TOOL
from .session_logging import event

LOG = logging.getLogger("jade.responses")

# Responses uses the flat function-tool schema, unlike Chat Completions.
RESPONSES_MEMORY_TOOL = {
    "type": "function",
    **MEMORY_TOOL["function"],
}


def _field(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _output_items(response) -> list:
    output = _field(response, "output", None)
    if output is None or not isinstance(output, (list, tuple)):
        raise ValueError("Responses API returned no output items")
    return list(output)


def _text(response) -> str:
    """Read final visible text without confusing reasoning/tools with speech."""
    # Python SDK exposes a convenient output_text property.
    value = _field(response, "output_text")
    if isinstance(value, str) and value:
        return value
    parts = []
    for item in _output_items(response):
        if _field(item, "type") != "message":
            continue
        for part in (_field(item, "content", ()) or ()):
            if _field(part, "type") == "output_text":
                text = _field(part, "text")
                if isinstance(text, str):
                    parts.append(text)
    return "".join(parts)


def _tool_calls(response) -> list[dict[str, str]]:
    calls = []
    for item in _output_items(response):
        if _field(item, "type") != "function_call":
            continue
        calls.append({
            "call_id": _field(item, "call_id"),
            "name": _field(item, "name"),
            "arguments": _field(item, "arguments"),
        })
    if len(calls) > 4:
        raise ValueError("too many memory tool calls")
    if any(not isinstance(call["call_id"], str) or not call["call_id"]
           or not isinstance(call["name"], str) or not call["name"]
           or not isinstance(call["arguments"], str)
           for call in calls):
        raise ValueError("malformed Responses function call")
    if len({call["call_id"] for call in calls}) != len(calls):
        raise ValueError("duplicate Responses function call ID")
    return calls


def _require_completed(response) -> None:
    status = _field(response, "status")
    if status != "completed":
        details = _field(response, "incomplete_details") or _field(response, "error")
        raise RuntimeError(f"Responses API not completed (status={status}, details={details})")


async def _close_stream(stream) -> None:
    close = getattr(stream, "aclose", None)
    if not callable(close):
        close = getattr(stream, "close", None)
    if callable(close):
        result = close()
        if inspect.isawaitable(result):
            await result


class ResponsesChat:
    """Minimal Responses bridge compatible with Jade's four chat methods."""

    def __init__(self, client, settings):
        self.client = client
        self.settings = settings

    def _arguments(self, messages, *, with_tools=False, stream=False):
        params = {
            "model": self.settings.model,
            "input": list(messages),
            "reasoning": {"effort": self.settings.reasoning_effort},
            "max_output_tokens": self.settings.max_completion_tokens,
            "store": False,
        }
        if with_tools:
            params.update(
                tools=[RESPONSES_MEMORY_TOOL],
                tool_choice="auto",
                parallel_tool_calls=False,
                include=["reasoning.encrypted_content"],
            )
        if stream:
            params["stream"] = True
        return params

    def _request_log(self, operation, *, with_tools, stream):
        event("openai_request", operation=operation, endpoint="/v1/responses",
              model=self.settings.model, tools_enabled=with_tools,
              streaming=stream, effective_reasoning_effort=self.settings.reasoning_effort,
              provider_storage=False)

    def _response_log(self, operation, response):
        output = _output_items(response)
        calls = _tool_calls(response)
        usage = _field(response, "usage")
        event("openai_response", operation=operation,
              response_id=_field(response, "id"), status=_field(response, "status"),
              output_types=[_field(item, "type") for item in output],
              raw_output=_text(response),
              tool_calls=[{"name": c["name"], "arguments": c["arguments"]}
                          for c in calls],
              input_tokens=_field(usage, "input_tokens"),
              output_tokens=_field(usage, "output_tokens"))

    async def _create(self, messages, *, operation, with_tools=False):
        self._request_log(operation, with_tools=with_tools, stream=False)
        response = await self.client.responses.create(
            **self._arguments(messages, with_tools=with_tools))
        # Raise on incomplete outputs, even when some visible text is present.
        _require_completed(response)
        self._response_log(operation, response)
        return response

    async def complete(self, messages) -> str:
        response = await self._create(messages, operation="responses.complete")
        if _tool_calls(response):
            raise ValueError("unexpected tool call in tool-free response")
        value = _text(response)
        if not value:
            raise ValueError("OpenAI returned no dialogue text")
        return value

    @staticmethod
    async def _execute_tools(response, action) -> list[dict]:
        """One authorized local memory write at most, plus refused call outputs."""
        calls = _tool_calls(response)
        results = []
        for index, call in enumerate(calls):
            if (index == 0 and call["name"] == "jade_save_memory"
                    and len(call["arguments"]) <= 2400):
                try:
                    result = await action(call["arguments"])
                except Exception:
                    LOG.exception("Local memory action failed")
                    result = {"status": "échec", "level": None}
            else:
                result = {"status": "refusé", "level": None}
            event("memory_tool_result", call_index=index, name=call["name"],
                  call_id=call["call_id"], outcome=result)
            results.append({
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": json.dumps(result, ensure_ascii=False),
            })
        return results

    async def _after_tool(self, messages, response, action) -> list:
        outputs = await self._execute_tools(response, action)
        # Stateless continuation: replay the complete output (including
        # encrypted reasoning items) and matched function_call_output items.
        # This is NEVER a shared provider-side conversation or stored session.
        return [*messages, *_output_items(response), *outputs]

    async def complete_with_tools(self, messages, memory_action) -> str:
        response = await self._create(
            messages, operation="responses.complete_with_tools", with_tools=True)
        calls = _tool_calls(response)
        if not calls:
            value = _text(response)
            if not value:
                raise ValueError("OpenAI returned no dialogue text")
            return value
        continuation = await self._after_tool(messages, response, memory_action)
        # The continuation cannot use tools again, preventing loops and repeat
        # writes. It still has the original 'low' reasoning configuration.
        return await self.complete(continuation)

    async def _stream_text(self, messages, *, operation):
        self._request_log(operation, with_tools=False, stream=True)
        stream = await self.client.responses.create(
            **self._arguments(messages, stream=True))
        completed = None
        fragments = []
        try:
            async for update in stream:
                kind = _field(update, "type")
                if kind == "response.output_text.delta":
                    fragment = _field(update, "delta")
                    if isinstance(fragment, str) and fragment:
                        fragments.append(fragment)
                        yield fragment
                elif kind == "response.completed":
                    completed = _field(update, "response")
                    _require_completed(completed)
                elif kind in ("response.failed", "response.incomplete", "error"):
                    details = _field(update, "response") or _field(update, "error") or _field(update, "message")
                    raise RuntimeError(f"Responses stream failed ({kind}): {details}")
            if completed is None:
                raise RuntimeError("Responses stream ended without response.completed")
            self._response_log(operation, completed)
            if _tool_calls(completed):
                raise ValueError("unexpected tool call in tool-free stream")
            visible = _text(completed)
            if not visible:
                raise ValueError("OpenAI returned no dialogue text")
            if not fragments:
                yield visible
            elif "".join(fragments) != visible:
                # Never speak an unverified extra suffix after fragments that
                # the listener may already have heard.
                raise ValueError("Responses stream text differs from final response")
        finally:
            await _close_stream(stream)

    async def complete_stream(self, messages):
        async for fragment in self._stream_text(
                messages, operation="responses.stream"):
            yield fragment

    async def complete_stream_with_tools(self, messages, memory_action):
        # Deliberate safety boundary: no text is spoken before we know whether
        # the model requested a local write. Otherwise a mixed text/tool
        # response could announce a memory commit BEFORE SQLite confirms it.
        # Most Jade voice calls do not use early streaming; this impacts only
        # first-token latency when streaming is explicitly enabled.
        response = await self._create(
            messages, operation="responses.stream_with_tools.prepare", with_tools=True)
        calls = _tool_calls(response)
        if not calls:
            value = _text(response)
            if not value:
                raise ValueError("OpenAI returned no dialogue text")
            yield value
            return
        continuation = await self._after_tool(messages, response, memory_action)
        async for fragment in self._stream_text(
                continuation, operation="responses.stream_with_tools.followup"):
            yield fragment
