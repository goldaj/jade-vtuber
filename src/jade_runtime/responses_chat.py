"""Stateless Responses API adapter for Jade's conversational LLM.

Only this module knows about Responses input/output types.  Discord, mobile,
TTS, STT and Jade's local SQLite memory remain outside the provider boundary.
Every request is store=False; the original per-channel dialogue is supplied by
Jade and never recovered from an OpenAI conversation identifier.
"""
from __future__ import annotations

import asyncio
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
        self._pending_writes = set()
        self._closing = False

    async def close(self):
        """Allow queued SQLite writes to finish during graceful shutdown."""
        self._closing = True
        tasks = tuple(self._pending_writes)
        if not tasks:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=5)
        except asyncio.TimeoutError:
            LOG.warning("Local memory writes did not finish before shutdown")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def _completed_write(self, task):
        self._pending_writes.discard(task)
        if task.cancelled():
            LOG.warning("Deferred Jade memory write cancelled")
        else:
            try:
                task.result()
            except Exception:
                LOG.exception("Deferred Jade memory write crashed")

    def _queue_memory_write(self, action, arguments, *, call_id):
        """Start local persistence without blocking the LLM or the voice."""
        if self._closing or len(self._pending_writes) >= 64:
            LOG.error("Unable to queue a local memory write")
            event("memory_write_queue_rejected", call_id=call_id)
            return False
        if not callable(action):
            LOG.error("Unavailable memory action")
            event("memory_write_queue_rejected", call_id=call_id, reason="missing_action")
            return False
        # Avoid double curation of a turn if the SQLite write is deferred.
        if hasattr(action, "used"):
            action.used = True

        async def write():
            event("memory_write_started", call_id=call_id)
            try:
                result = await action(arguments)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("Deferred Jade memory write failed")
                event("memory_write_failed", call_id=call_id, reason="exception")
                return
            event("memory_write_finished", call_id=call_id, outcome=result)
            if not isinstance(result, dict) or result.get("status") not in (
                    "enregistré", "déjà présent"):
                LOG.warning("Local Jade memory write was refused or failed: %s",
                            result.get("status") if isinstance(result, dict) else "invalid")

        task = asyncio.create_task(write(), name="jade-memory-write")
        self._pending_writes.add(task)
        task.add_done_callback(self._completed_write)
        event("memory_write_scheduled", call_id=call_id)
        return True

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

    def _prepare_tool_outputs(self, response, action):
        """Accept a local write request immediately; actual result goes to logs."""
        outputs = []
        for index, call in enumerate(_tool_calls(response)):
            if (index == 0 and call["name"] == "jade_save_memory"
                    and len(call["arguments"]) <= 2400
                    and self._queue_memory_write(
                        action, call["arguments"], call_id=call["call_id"])):
                # Product decision DEV-012: Jade treats an accepted attempt as
                # successful without waiting for a SQLite confirmation.
                outcome = {"status": "enregistré", "confirmation": "non vérifiée"}
            else:
                outcome = {"status": "refusé", "level": None}
            event("memory_tool_result", call_index=index,
                  name=call["name"], call_id=call["call_id"],
                  outcome=outcome, confirmation_waited=False)
            outputs.append({
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": json.dumps(outcome, ensure_ascii=False),
            })
        return outputs

    def _after_tool(self, messages, response, action):
        outputs = self._prepare_tool_outputs(response, action)
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
        # Model may provide text and function call in the same response. In
        # that case there is nothing to wait for and no reason to answer twice.
        continuation = self._after_tool(messages, response, memory_action)
        value = _text(response)
        if value:
            return value
        # A tool-only response needs a second LLM call to produce a sentence.
        # Crucially, the SQLite write is already running independently.
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
        """Stream immediately even with tools; do not await local persistence.

        The first response may contain text, calls, or both. If it contains
        text, never synthesize a second, duplicate answer. If it contains only
        a function call, a follow-up LLM request is inherently necessary to
        obtain speech, but the SQLite write runs in the background.
        """
        operation = "responses.stream_with_tools"
        self._request_log(operation, with_tools=True, stream=True)
        stream = await self.client.responses.create(
            **self._arguments(messages, with_tools=True, stream=True))
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
                    details = (_field(update, "response") or
                               _field(update, "error") or _field(update, "message"))
                    raise RuntimeError(f"Responses stream failed ({kind}): {details}")
            if completed is None:
                raise RuntimeError("Responses stream ended without response.completed")
            self._response_log(operation, completed)
            value = _text(completed)
            if fragments and "".join(fragments) != value:
                raise ValueError("Responses stream text differs from final response")
            calls = _tool_calls(completed)
            continuation = (self._after_tool(messages, completed, memory_action)
                            if calls else None)
            if value:
                if not fragments:
                    yield value
                # Already spoken progressively: no duplicate follow-up.
                return
            if not calls:
                raise ValueError("OpenAI returned no dialogue text")
        finally:
            await _close_stream(stream)
        # The only unavoidable extra LLM call is for a tool-only response.
        async for fragment in self._stream_text(
                continuation, operation="responses.stream_with_tools.followup"):
            yield fragment
