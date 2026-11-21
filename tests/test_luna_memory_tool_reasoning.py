"""Offline acceptance tests: Jade streams in low and logs deferred memory writes."""
from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace as NS

import pytest

from src.jade_runtime.config import Settings
from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.memory_service import MemoryService


def text_response(text="[INTENT:neutral] Bonjour", *, status="completed", calls=()):
    items = [NS(type="message", content=[NS(type="output_text", text=text)])] if text else []
    return NS(
        id="resp-text", status=status, output_text=text, output=[
            NS(type="reasoning", encrypted_content="sealed"), *items, *calls],
        usage=NS(input_tokens=123, output_tokens=19),
        incomplete_details="max_output_tokens" if status != "completed" else None,
    )


def tool_call(name="jade_save_memory", *, call_id="call-1", arguments='{"kind":"ordinary"}'):
    return NS(type="function_call", call_id=call_id,
              name=name, arguments=arguments)


def tool_response(*calls, text=""):
    if not calls:
        calls = (tool_call(),)
    return text_response(text, calls=calls)


def stream_response(response, *, pieces=None):
    async def events():
        yield NS(type="response.created")
        if pieces:
            for fragment in pieces:
                yield NS(type="response.output_text.delta", delta=fragment)
        yield NS(type="response.completed", response=response)
    return events()


class FakeResponses:
    def __init__(self, items):
        self.items = list(items)
        self.calls = []

    async def create(self, **arguments):
        self.calls.append(arguments)
        assert self.items, "Unplanned LLM call"
        result = self.items.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def make_service(*results):
    backend = FakeResponses(results)
    client = NS(responses=backend)
    return OpenAIServices(Settings(model="gpt-6-luna", reasoning_effort="low"),
                          client=client), backend


async def forbidden_action(arguments):
    raise AssertionError("No memory action should execute")


def test_simple_chat_preserves_low_and_local_history():
    service, backend = make_service(text_response())
    async def run():
        return await service.complete([{"role": "user", "content": "Bonjour"}])
    assert asyncio.run(run()).endswith("Bonjour")
    call = backend.calls[0]
    assert call["reasoning"] == {"effort": "low"}
    assert call["store"] is False
    assert call["input"][0]["role"] == "user"
    assert "tools" not in call


def test_tool_available_but_unused_still_keeps_low():
    service, backend = make_service(text_response())
    async def run():
        return await service.complete_with_tools(
            [{"role": "user", "content": "Bonjour"}], forbidden_action)
    assert asyncio.run(run()).endswith("Bonjour")
    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert call["reasoning"]["effort"] == "low"
    assert call["tool_choice"] == "auto"
    assert call["parallel_tool_calls"] is False
    assert call["store"] is False
    assert call["include"] == ["reasoning.encrypted_content"]
    schema = call["tools"][0]
    assert schema["name"] == "jade_save_memory"
    assert schema["strict"] is True
    assert schema["parameters"]["additionalProperties"] is False


def test_tool_only_reply_does_not_wait_for_sqlite_and_reasons_low_twice():
    service, backend = make_service(
        tool_response(), text_response("[INTENT:playful] Je m'en souviens."))
    started, release = asyncio.Event(), asyncio.Event()
    used = []

    async def write(arguments):
        used.append(arguments)
        started.set()
        await release.wait()
        return {"status": "enregistré", "level": 2}

    async def run():
        try:
            reply = await service.complete_with_tools(
                [{"role": "user", "content": "Je commence le piano"}], write)
            assert reply.endswith("Je m'en souviens.")
            assert not release.is_set()
            await asyncio.wait_for(started.wait(), timeout=1)
            assert used == ['{"kind":"ordinary"}']
            assert backend.calls[0]["reasoning"]["effort"] == "low"
            assert backend.calls[1]["reasoning"]["effort"] == "low"
            assert backend.calls[1]["store"] is False
            continuation = backend.calls[1]["input"]
            assert continuation[-2].type == "function_call"
            assert continuation[-1]["type"] == "function_call_output"
            assert continuation[-1]["call_id"] == "call-1"
            assert '"enregistré"' in continuation[-1]["output"]
        finally:
            release.set()
            await service._responses.close()

    asyncio.run(run())


def test_combined_text_and_memory_call_never_duplicates_reply():
    service, backend = make_service(tool_response(
        text="[INTENT:neutral] Je note cette information."))
    recorded = []

    async def action(arguments):
        recorded.append(arguments)
        return {"status": "enregistré", "level": 2}

    async def run():
        try:
            reply = await service.complete_with_tools(
                [{"role": "user", "content": "Info"}], action)
            assert reply.endswith("Je note cette information.")
        finally:
            await service._responses.close()

    asyncio.run(run())
    assert len(backend.calls) == 1
    assert recorded == ['{"kind":"ordinary"}']


def test_unknown_and_duplicate_tools_are_not_executed():
    service, backend = make_service(
        tool_response(tool_call("execute_shell")), text_response())
    async def run():
        await service.complete_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action)
    asyncio.run(run())
    assert '"refusé"' in backend.calls[1]["input"][-1]["output"]

    duplicate = tool_response(tool_call(call_id="same"), tool_call(call_id="same"))
    service, _ = make_service(duplicate)
    async def run_duplicate():
        await service.complete_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action)
    with pytest.raises(ValueError, match="duplicate"):
        asyncio.run(run_duplicate())


def test_incomplete_result_and_provider_failure_do_not_schedule_writes():
    response = tool_response()
    response.status = "incomplete"
    service, _ = make_service(response)
    async def run():
        await service.complete_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action)
    with pytest.raises(RuntimeError, match="not completed"):
        asyncio.run(run())

    service, backend = make_service(RuntimeError("HTTP 429"))
    with pytest.raises(RuntimeError, match="429"):
        asyncio.run(service.complete_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action))
    assert len(backend.calls) == 1


def test_first_voice_fragment_arrives_before_model_completion():
    gate = asyncio.Event()
    first_sent = asyncio.Event()

    async def events():
        first_sent.set()
        yield NS(type="response.output_text.delta", delta="[INTENT:neutral] Bonjour.")
        await gate.wait()
        yield NS(type="response.completed", response=text_response(
            "[INTENT:neutral] Bonjour."))

    service, backend = make_service(events())

    async def run():
        stream = service.complete_stream_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action)
        try:
            first = await asyncio.wait_for(anext(stream), timeout=1)
            assert first == "[INTENT:neutral] Bonjour."
            assert first_sent.is_set()
            assert not gate.is_set()  # Text was NOT buffered until completion.
        finally:
            gate.set()
        rest = [piece async for piece in stream]
        assert rest == []

    asyncio.run(run())
    assert len(backend.calls) == 1
    assert backend.calls[0]["stream"] is True
    assert backend.calls[0]["reasoning"]["effort"] == "low"


def test_voice_stream_tool_only_never_waits_for_sqlite():
    service, backend = make_service(
        stream_response(tool_response()),
        stream_response(text_response("[INTENT:neutral] Je note."), pieces=[
            "[INTENT:neutral] ", "Je note."]))
    started, release = asyncio.Event(), asyncio.Event()

    async def action(arguments):
        started.set()
        await release.wait()
        return {"status": "enregistré"}

    async def run():
        try:
            result = [chunk async for chunk in service.complete_stream_with_tools(
                [{"role": "user", "content": "Je commence le piano"}], action)]
            assert "".join(result) == "[INTENT:neutral] Je note."
            assert not release.is_set()
            await asyncio.wait_for(started.wait(), timeout=1)
        finally:
            release.set()
            await service._responses.close()

    asyncio.run(run())
    assert len(backend.calls) == 2
    assert backend.calls[0]["stream"] is True
    assert backend.calls[1]["stream"] is True
    assert backend.calls[0]["store"] is backend.calls[1]["store"] is False


def test_voice_stream_combined_text_and_tool_has_one_reply_and_deferred_write():
    service, backend = make_service(
        stream_response(tool_response(text="[INTENT:neutral] Je retiens."),
                        pieces=["[INTENT:neutral] ", "Je retiens."]))
    used = []

    async def action(arguments):
        used.append(arguments)
        return {"status": "enregistré"}

    async def run():
        try:
            fragments = [fragment async for fragment in
                         service.complete_stream_with_tools(
                             [{"role": "user", "content": "Bonjour"}], action)]
            assert "".join(fragments) == "[INTENT:neutral] Je retiens."
        finally:
            await service._responses.close()

    asyncio.run(run())
    assert len(backend.calls) == 1
    assert used == ['{"kind":"ordinary"}']


def test_stream_incomplete_and_text_mismatch_are_errors():
    async def broken():
        yield NS(type="response.output_text.delta", delta="Texte incomplet")
    service, _ = make_service(broken())
    async def run():
        return [piece async for piece in service.complete_stream_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action)]
    with pytest.raises(RuntimeError, match="without response.completed"):
        asyncio.run(run())

    service, _ = make_service(stream_response(text_response("Version B"),
                                                   pieces=["Version A"]))
    async def run_mismatch():
        return [piece async for piece in service.complete_stream_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action)]
    with pytest.raises(ValueError, match="differs"):
        asyncio.run(run_mismatch())


def test_dialogue_preserves_intent_with_asynchronous_tool():
    service, _ = make_service(
        tool_response(), text_response("[INTENT:playful] Je retiens cette information."))
    seen = []

    async def action(arguments):
        seen.append(arguments)
        return {"status": "enregistré"}

    async def run():
        try:
            incoming = Incoming("mobile", "Goldaj", "Je commence le piano.",
                                force_reply=True, message_id="mobile01")
            reply = await Dialogue(service, "Tu es Jade.").respond(
                incoming, memory_action=action)
            assert reply.intent == "playful"
            assert reply.text == "Je retiens cette information."
        finally:
            await service._responses.close()

    asyncio.run(run())
    assert seen == ['{"kind":"ordinary"}']


def test_explicit_human_memory_request_is_queued_without_waiting_for_write():
    release = threading.Event()
    called = threading.Event()
    writes = []

    class Store:
        def account(self, key):
            return "verified-person"

        def put_requested_ordinary(self, key, **kwargs):
            writes.append((key, kwargs))
            called.set()
            release.wait(timeout=2)
            return "created"

    store = Store()
    memory = MemoryService(store, backend=object())
    incoming = Incoming("mobile", "Goldaj",
                        "Retiens que je commence le piano.",
                        channel="private", force_reply=True,
                        message_id="explicit01")

    async def run():
        try:
            reply = await memory.command(incoming)
            assert reply is not None
            assert "enregistré" in reply.text
            assert not release.is_set()
            await asyncio.wait_for(asyncio.to_thread(called.wait), timeout=1)
            assert not release.is_set()
        finally:
            release.set()
            await memory.close()

    asyncio.run(run())
    assert len(writes) == 1
    assert writes[0][1]["expected_person_id"] == "verified-person"



def test_goldaj_cannot_force_core_even_with_async_memory():
    writes = []

    class Store:
        def account(self, key):
            return "owner-profile"

        def put_requested_ordinary(self, key, **kwargs):
            writes.append(kwargs)
            return "created"

    memory = MemoryService(Store(), backend=object())
    incoming = Incoming(
        "mobile", "Goldaj",
        "Jade, enregistre dans tes core memories que je commence le piano.",
        channel="private", force_reply=True, message_id="core-request")

    async def run():
        try:
            reply = await memory.command(incoming)
            assert "pas dans mes Core Memories" in reply.text
        finally:
            await memory.close()

    asyncio.run(run())
    assert len(writes) == 1
    assert writes[0]["expected_person_id"] == "owner-profile"


def test_anonymous_user_cannot_queue_personal_memory():
    class Store:
        def account(self, key):
            return None

        def put_requested_ordinary(self, key, **kwargs):
            raise AssertionError("No write without active identity")

    memory = MemoryService(Store(), backend=object())
    incoming = Incoming("discord", "Anonymous",
                        "Retiens que je commence le piano.",
                        channel="public", force_reply=True, message_id="none")

    async def run():
        try:
            reply = await memory.command(incoming)
            assert "ne peux mémoriser" in reply.text or "inactive" in reply.text
            assert not memory._explicit_writes
        finally:
            await memory.close()

    asyncio.run(run())



def test_log_event_accepts_tool_name_without_crashing(monkeypatch):
    """Regression: the previous event(name, **fields) broke each memory call."""
    import json
    from src.jade_runtime import session_logging
    logged = []
    monkeypatch.setattr(
        session_logging._AUDIT, "info",
        lambda fmt, payload: logged.append(json.loads(payload)))
    session_logging.event("memory_tool_result", call_index=0,
                          name="jade_save_memory", call_id="call-01",
                          outcome={"status": "enregistré"},
                          confirmation_waited=False)
    assert logged == [{
        "event": "memory_tool_result", "call_index": 0,
        "name": "jade_save_memory", "call_id": "call-01",
        "outcome": {"status": "enregistré"},
        "confirmation_waited": False,
    }]


def test_memory_tool_only_continuation_survives_audit_with_name_field():
    """One call to write, then a normal Jade reply, without a TypeError."""
    service, backend = make_service(
        tool_response(), text_response("[INTENT:neutral] C'est noté."))
    stored = []

    async def write(arguments):
        stored.append(arguments)
        return {"status": "enregistré", "level": 2}

    async def run():
        try:
            result = await service.complete_with_tools(
                [{"role": "user", "content": "Je commence le piano"}], write)
            assert "C'est noté" in result
        finally:
            await service._responses.close()

    asyncio.run(run())
    assert stored == ['{"kind":"ordinary"}']
    assert len(backend.calls) == 2
    assert backend.calls[0]["reasoning"]["effort"] == "low"
    assert backend.calls[1]["reasoning"]["effort"] == "low"


def test_memory_rejection_explains_wrong_evidence_without_storing(monkeypatch):
    """A historical quote fails the current-message policy, not SQLite."""
    import json
    from src.jade_runtime import memory_service as module
    rejected = []
    monkeypatch.setattr(
        module, "event",
        lambda event_type, **details: rejected.append((event_type, details)))

    class Store:
        def put(self, *args, **kwargs):
            raise AssertionError("Rejected candidate must never touch SQLite")

        def put_self_core(self, *args, **kwargs):
            raise AssertionError("Rejected candidate must never touch SQLite")

    service = MemoryService(Store(), backend=object())
    incoming = Incoming(
        "mobile", "Goldaj", "Choisis un souvenir à mémoriser.",
        channel="private", force_reply=True, message_id="stale-evidence-test")
    payload = json.dumps({
        "kind": "ordinary",
        "summary": "Une panne précédente est corrigée.",
        "significance": "Épisode important.",
        "evidence": "Une phrase prononcée au tour précédent.",
    }, ensure_ascii=False)
    result = asyncio.run(service._execute_memory_action(
        ("microphone", "goldaj"), "verified-person", incoming, payload))
    assert result["status"] == "refusé"
    assert rejected == [(
        "memory_write_rejected",
        {"reason": "evidence_not_in_current_message", "scope": "person"},
    )]
