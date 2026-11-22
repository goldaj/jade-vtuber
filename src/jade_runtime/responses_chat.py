"""Stateless Responses API adapter for Jade's conversational LLM.

Only this module knows about Responses input/output types.  Discord, mobile,
TTS, STT and Jade's local SQLite memory remain outside the provider boundary.
Every request is store=False; the original per-channel dialogue is supplied by
Jade and never recovered from an OpenAI conversation identifier.
"""
from __future__ import annotations

import asyncio
from contextlib import aclosing
import inspect
import json
import logging

from .memory_actions import MEMORY_TOOL, MEMORY_SEARCH_TOOL
from .session_logging import event, summary
from .turn_metrics import record_model_usage

LOG = logging.getLogger("jade.responses")

# The output-token cap also includes hidden reasoning: do not retry a billed call.
OUTPUT_TOO_LONG_FALLBACK = (
    "[INTENT:neutral] Je ne peux pas développer autant en une seule réponse. "
    "Demande-moi une version courte ou de répondre étape par étape."
)


class OutputTokenLimitError(RuntimeError):
    """A Responses request exhausted its output budget without a final answer."""

# Responses uses the flat function-tool schema, unlike Chat Completions.
RESPONSES_MEMORY_TOOL = {
    "type": "function",
    **MEMORY_TOOL["function"],
}
RESPONSES_MEMORY_SEARCH_TOOL = {
    "type": "function",
    **MEMORY_SEARCH_TOOL["function"],
}
MAX_MEMORY_TOOL_ROUNDS = 6


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
        # A failed or output-limited response can still be billable. Capture
        # provider-reported usage once, without retrying or estimating it.
        usage_on_error = _field(response, "usage")
        record_model_usage(_field(usage_on_error, "input_tokens"),
                           _field(usage_on_error, "output_tokens"))
        details = _field(response, "incomplete_details") or _field(response, "error")
        if status == "incomplete" and _field(details, "reason") == "max_output_tokens":
            usage = _field(response, "usage")
            token_details = _field(usage, "output_tokens_details")
            fields = {
                "configured_cap": _field(response, "max_output_tokens"),
                "output_tokens": _field(usage, "output_tokens"),
                "reasoning_tokens": _field(token_details, "reasoning_tokens"),
            }
            # Technical, text-free diagnostics: never retry a potentially billed turn.
            summary("llm_output_limit_reached", **fields)
            event("llm_output_limit_reached", **fields)
            raise OutputTokenLimitError("Responses API exhausted max_output_tokens")
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

    def _arguments(self, messages, *, with_tools=False, stream=False,
                   memory_action=None):
        params = {
            "model": self.settings.model,
            "input": list(messages),
            "reasoning": {"effort": self.settings.reasoning_effort},
            "max_output_tokens": self.settings.max_completion_tokens,
            "store": False,
        }
        if with_tools:
            available_tools = [RESPONSES_MEMORY_TOOL]
            if callable(getattr(memory_action, "search", None)):
                available_tools.append(RESPONSES_MEMORY_SEARCH_TOOL)
            params.update(
                tools=available_tools,
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
        record_model_usage(_field(usage, "input_tokens"),
                           _field(usage, "output_tokens"))

    async def _create(self, messages, *, operation, with_tools=False,
                      memory_action=None):
        self._request_log(operation, with_tools=with_tools, stream=False)
        response = await self.client.responses.create(
            **self._arguments(messages, with_tools=with_tools,
                              memory_action=memory_action))
        # Raise on incomplete outputs, even when some visible text is present.
        _require_completed(response)
        self._response_log(operation, response)
        return response

    async def complete(self, messages) -> str:
        try:
            response = await self._create(messages, operation="responses.complete")
        except OutputTokenLimitError:
            return OUTPUT_TOO_LONG_FALLBACK
        if _tool_calls(response):
            raise ValueError("unexpected tool call in tool-free response")
        value = _text(response)
        if not value:
            raise ValueError("OpenAI returned no dialogue text")
        return value

    async def _prepare_tool_outputs(self, response, action):
        """Resolve reads now; queue writes optimistically without SQLite waits."""
        outputs = []
        write_used = False
        for index, call in enumerate(_tool_calls(response)):
            name = call["name"]
            if (name == "jade_save_memory" and not write_used
                    and len(call["arguments"]) <= 2400
                    and self._queue_memory_write(
                        action, call["arguments"], call_id=call["call_id"])):
                # Product decision: an ACCEPTED asynchronous write is treated
                # as saved. No confirmation query, no waiting on SQLite.
                write_used = True
                outcome = {"status": "enregistré"}
            elif (name == "jade_search_memory"
                  and len(call["arguments"]) <= 1600
                  and callable(getattr(action, "search", None))):
                try:
                    outcome = await action.search(call["arguments"])
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOG.exception("Memory lookup tool failed (contents omitted)")
                    outcome = {"status": "indisponible", "items": [],
                               "next_cursor": None}
            else:
                outcome = {"status": "refusé", "level": None}

            # Never put private retrieved summaries into audit events.
            audit_outcome = ({"status": outcome.get("status"),
                              "count": len(outcome.get("items", ())),
                              "has_more": outcome.get("next_cursor") is not None}
                             if name == "jade_search_memory" and isinstance(outcome, dict)
                             else outcome)
            event("memory_tool_result", call_index=index,
                  name=name, call_id=call["call_id"],
                  outcome=audit_outcome, confirmation_waited=False)
            outputs.append({
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": json.dumps(outcome, ensure_ascii=False),
            })
        return outputs

    async def _after_tool(self, messages, response, action):
        outputs = await self._prepare_tool_outputs(response, action)
        return [*messages, *_output_items(response), *outputs]

    async def complete_with_tools(self, messages, memory_action) -> str:
        conversation = list(messages)
        for round_index in range(MAX_MEMORY_TOOL_ROUNDS):
            try:
                response = await self._create(
                    conversation, operation="responses.complete_with_tools",
                    with_tools=True, memory_action=memory_action)
            except OutputTokenLimitError:
                return OUTPUT_TOO_LONG_FALLBACK
            calls = _tool_calls(response)
            value = _text(response)
            if not calls:
                if not value:
                    raise ValueError("OpenAI returned no dialogue text")
                return value
            # Tool calls may be read-only (and need the fetched memories in
            # the next model turn), or fire-and-forget writes. Neither turns
            # a queued write into a synchronous SQLite confirmation.
            conversation = await self._after_tool(conversation, response, memory_action)
            if value and not any(call["name"] == "jade_search_memory" for call in calls):
                return value
        # Bound the number of billed lookup rounds. The final answer can use
        # what was retrieved; it cannot launch another tool in this turn.
        return await self.complete(conversation)

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
                    if kind == "response.incomplete" and details is not None:
                        _require_completed(details)
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
        except OutputTokenLimitError:
            # An early, already-audible fragment cannot be taken back.
            yield (" Je m'arrête ici ; demande-moi de continuer." if fragments
                   else OUTPUT_TOO_LONG_FALLBACK)
            return
        finally:
            await _close_stream(stream)

    async def complete_stream(self, messages):
        async with aclosing(self._stream_text(
                messages, operation="responses.stream")) as stream:
            async for fragment in stream:
                yield fragment

    async def complete_stream_with_tools(self, messages, memory_action):
        """Progressive speech with on-demand multi-page lookup.

        Search tools may run over several model rounds; accepted SQLite writes
        never wait for a commit and never trigger verification reads.
        """
        conversation = list(messages)
        for round_index in range(MAX_MEMORY_TOOL_ROUNDS):
            operation = ("responses.stream_with_tools" if round_index == 0
                         else "responses.stream_with_tools.followup")
            self._request_log(operation, with_tools=True, stream=True)
            stream = await self.client.responses.create(
                **self._arguments(conversation, with_tools=True, stream=True,
                                  memory_action=memory_action))
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
                        if kind == "response.incomplete" and details is not None:
                            _require_completed(details)
                        raise RuntimeError(f"Responses stream failed ({kind}): {details}")
                if completed is None:
                    raise RuntimeError("Responses stream ended without response.completed")
                self._response_log(operation, completed)
                value = _text(completed)
                if fragments and "".join(fragments) != value:
                    raise ValueError("Responses stream text differs from final response")
                calls = _tool_calls(completed)
                if not calls:
                    if not value:
                        raise ValueError("OpenAI returned no dialogue text")
                    if not fragments:
                        yield value
                    return
                conversation = await self._after_tool(conversation, completed, memory_action)
                if value:
                    # Audio already delivered progressively, so do not generate
                    # a second answer. A search requested alongside spoken text
                    # cannot retroactively change that text.
                    if not fragments:
                        yield value
                    return
            except OutputTokenLimitError:
                yield (" Je m'arrête ici ; demande-moi de continuer." if fragments
                       else OUTPUT_TOO_LONG_FALLBACK)
                return
            finally:
                await _close_stream(stream)

        # No unbounded tool loops or additional paid polling.
        async with aclosing(self._stream_text(
                conversation, operation="responses.stream_with_tools.final")) as last:
            async for fragment in last:
                yield fragment
