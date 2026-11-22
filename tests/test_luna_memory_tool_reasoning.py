"""Offline acceptance tests: Jade streams in low and logs deferred memory writes."""
from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace as NS

import unittest

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
    with unittest.TestCase().assertRaisesRegex(ValueError, "duplicate"):
        asyncio.run(run_duplicate())


def test_incomplete_result_and_provider_failure_do_not_schedule_writes():
    response = tool_response()
    response.status = "incomplete"
    service, _ = make_service(response)
    async def run():
        await service.complete_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action)
    with unittest.TestCase().assertRaisesRegex(RuntimeError, "not completed"):
        asyncio.run(run())

    service, backend = make_service(RuntimeError("HTTP 429"))
    with unittest.TestCase().assertRaisesRegex(RuntimeError, "429"):
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
    with unittest.TestCase().assertRaisesRegex(RuntimeError, "without response.completed"):
        asyncio.run(run())

    service, _ = make_service(stream_response(text_response("Version B"),
                                                   pieces=["Version A"]))
    async def run_mismatch():
        return [piece async for piece in service.complete_stream_with_tools(
            [{"role": "user", "content": "hello"}], forbidden_action)]
    with unittest.TestCase().assertRaisesRegex(ValueError, "differs"):
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


def test_explicit_goldaj_memory_request_is_queued_without_waiting_for_write():
    release = threading.Event()
    called = threading.Event()
    writes = []

    class Store:
        def is_goldaj(self, key):
            return key == ("microphone", "goldaj")

        def account(self, key):
            return "verified-person"

        def put_requested_ordinary(self, key, **kwargs):
            writes.append((key, kwargs))
            called.set()
            release.wait(timeout=2)
            return "created"

    memory = MemoryService(Store(), backend=object())
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
        def is_goldaj(self, key):
            return key == ("microphone", "goldaj")

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


def test_anonymous_user_suggestion_reaches_dialogue_without_direct_write():
    class Store:
        def is_goldaj(self, key):
            raise AssertionError("No owner lookup for anonymous messages")

        def put_requested_ordinary(self, key, **kwargs):
            raise AssertionError("Anonymous message must never force an insert")

    memory = MemoryService(Store(), backend=object())
    incoming = Incoming("discord", "Anonymous",
                        "Retiens que je commence le piano.",
                        channel="public", force_reply=True, message_id="none")

    async def run():
        try:
            assert await memory.command(incoming) is None
            assert not memory._explicit_writes
        finally:
            await memory.close()

    asyncio.run(run())


def test_nonowner_verified_discord_request_is_only_a_suggestion():
    """Never force an L2 insert because any Discord user used an imperative."""
    import json

    writes = []

    class Store:
        def is_goldaj(self, key):
            return False

        def account(self, key):
            return "other-person"

        def put_requested_ordinary(self, *args, **kwargs):
            raise AssertionError("Non-owner cannot force a level-2 write")

        def put(self, key, **kwargs):
            writes.append((key, kwargs))
            return True

    memory = MemoryService(Store(), backend=object())
    incoming = Incoming(
        "discord", "Someone", "Retiens que je commence le piano.",
        account_id="12345678901234567", channel="private", private_channel=True,
        force_reply=True, message_id="other-user-request")
    payload = json.dumps({
        "kind": "ordinary",
        "summary": "Cette personne apprend le piano.",
        "significance": "Jade choisit ce souvenir librement.",
    }, ensure_ascii=False)

    async def run():
        try:
            # No direct response or write. Jade receives the request normally.
            assert await memory.command(incoming) is None
            assert not memory._explicit_writes
            action = await memory.prepare_memory_action(incoming)
            assert action is not None
            # Only an actual autonomous tool invocation can write.
            outcome = await action(payload)
            assert outcome["status"] == "enregistré"
        finally:
            await memory.close()

    asyncio.run(run())
    assert len(writes) == 1
    assert writes[0][1]["expected_person_id"] == "other-person"


def test_nonowner_request_can_be_declined_by_jade_without_saving():
    """The LLM can answer a non-owner's request without touching SQLite."""
    class Store:
        def is_goldaj(self, key):
            return False

        def account(self, key):
            return "ordinary-user-profile"

        def put_requested_ordinary(self, *args, **kwargs):
            raise AssertionError("An ordinary user cannot force a write")

        def put(self, *args, **kwargs):
            raise AssertionError("Jade declined the optional write")

    memory = MemoryService(Store(), backend=object())
    service, requests = make_service(
        text_response("[INTENT:neutral] Je préfère ne pas conserver ce souvenir."))
    incoming = Incoming(
        "discord", "Guest", "Retiens que je suis venu aujourd'hui.",
        account_id="78901234567890123", channel="private", private_channel=True,
        force_reply=True, message_id="guest-declined")

    async def run():
        try:
            assert await memory.command(incoming) is None
            action = await memory.prepare_memory_action(incoming)
            assert action is not None
            reply = await Dialogue(service, "Tu es Jade.").respond(
                incoming, memory_action=action)
            assert reply.text == "Je préfère ne pas conserver ce souvenir."
            assert action.used is False
            assert not memory._explicit_writes
        finally:
            await service._responses.close()
            await memory.close()

    asyncio.run(run())
    assert len(requests.calls) == 1
    assert requests.calls[0]["tools"][0]["name"] == "jade_save_memory"


def test_spoofed_goldaj_display_name_has_no_owner_privilege():
    class Store:
        def is_goldaj(self, key):
            return False

        def put_requested_ordinary(self, *args, **kwargs):
            raise AssertionError("Display name cannot grant owner memory rights")

    memory = MemoryService(Store(), backend=object())
    incoming = Incoming(
        "discord", "Goldaj", "Retiens que je commence le piano.",
        account_id="23456789012345678", channel="guild",
        force_reply=True, message_id="spoofed-name")
    async def run():
        assert await memory.command(incoming) is None
        assert not memory._explicit_writes
    asyncio.run(run())


def test_goldaj_verified_linked_discord_account_can_force_l2(tmp_path):
    """Only proven identity linkage, not nickname matching, grants ownership."""
    from src.jade_runtime.memory_store import MemoryStore

    store = MemoryStore(tmp_path / "memory-owner-link.sqlite3")
    owner = ("microphone", "goldaj")
    discord = ("discord", "34567890123456789")
    other = ("discord", "45678901234567890")
    store.enable(owner)
    store.enable(discord)
    store.enable(other)
    assert store.is_goldaj(owner)
    assert not store.is_goldaj(discord)
    assert not store.is_goldaj(other)

    code = store.begin_link(owner, target=discord)
    assert store.complete_link(discord, code)
    assert store.is_goldaj(discord)
    assert not store.is_goldaj(other)

    memory = MemoryService(store, backend=object())
    incoming = Incoming("discord", "Not-important-nickname",
                        "Retiens que je commence le piano.",
                        account_id=discord[1], channel="private",
                        private_channel=True, force_reply=True,
                        message_id="owner-discord")
    async def run():
        try:
            reply = await memory.command(incoming)
            assert reply is not None and "enregistré" in reply.text
        finally:
            await memory.close()
    asyncio.run(run())
    assert any(m["summary"] == "je commence le piano."
               for m in store.list_for_account(discord))



def test_mandatory_l2_store_rejects_external_user_even_when_called_directly(tmp_path):
    """Store enforces owner privilege independently of the command router."""
    from src.jade_runtime.memory_store import MemoryStore

    store = MemoryStore(tmp_path / "mandatory-owner-boundary.sqlite3")
    owner = ("microphone", "goldaj")
    other = ("discord", "56789012345678901")
    store.enable(owner)
    store.enable(other)
    # Even a direct store call by some other code must not force L2.
    assert store.put_requested_ordinary(
        other, scope="discord:123", summary="Un fait imposé",
        expected_person_id=store.account(other)) == "inactive"
    assert store.list_for_account(other) == []
    # Goldaj can store a mandatory level-2 memory.
    assert store.put_requested_ordinary(
        owner, scope="person", summary="Un souvenir à retenir",
        expected_person_id=store.account(owner)) == "created"
    stored = store.list_for_account(owner)
    assert len(stored) == 1 and stored[0]["kind"] == "ordinary"


def test_owner_link_detachment_immediately_revokes_mandatory_privilege(tmp_path):
    from src.jade_runtime.memory_store import MemoryStore

    store = MemoryStore(tmp_path / "unlink-owner-boundary.sqlite3")
    owner = ("microphone", "goldaj")
    other = ("discord", "67890123456789012")
    store.enable(owner)
    store.enable(other)
    token = store.begin_link(owner, target=other)
    assert store.complete_link(other, token)
    assert store.is_goldaj(other)
    original_profile = store.account(other)
    assert store.unlink(other)
    assert not store.is_goldaj(other)
    assert store.account(other) != original_profile
    assert store.put_requested_ordinary(
        other, scope="discord:123", summary="Interdiction après séparation",
        expected_person_id=store.account(other)) == "inactive"


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


def test_autonomous_l2_memory_accepts_prior_context_without_evidence():
    """The current user message is not a citation requirement for Jade's L2."""
    import json

    writes = []

    class Store:
        def put(self, key, **kwargs):
            writes.append((key, kwargs))
            return True

    memory = MemoryService(Store(), backend=object())
    incoming = Incoming(
        "mobile", "Goldaj", "Choisis un souvenir à mémoriser.",
        channel="private", force_reply=True, message_id="older-context")
    payload = json.dumps({
        "kind": "ordinary",
        "summary": "Une panne précédente a été corrigée.",
        "significance": "Un épisode de notre histoire.",
    }, ensure_ascii=False)
    result = asyncio.run(memory._execute_memory_action(
        ("microphone", "goldaj"), "verified-person", incoming, payload))

    assert result == {"status": "enregistré", "level": 2, "kind": "ordinary"}
    assert len(writes) == 1
    assert writes[0][1]["summary"] == "Une panne précédente a été corrigée."
    assert writes[0][1]["expected_person_id"] == "verified-person"


def test_autonomous_l3_memory_accepts_reflection_without_latest_quote():
    """Jade may voluntarily create a Core Memory from authorized context."""
    import json

    writes = []

    class Store:
        def put_self_core(self, key, **kwargs):
            writes.append((key, kwargs))
            return True

    memory = MemoryService(Store(), backend=object())
    incoming = Incoming(
        "mobile", "Goldaj", "Prends du recul sur notre histoire.",
        channel="private", force_reply=True, message_id="self-reflection")
    payload = json.dumps({
        "kind": "core_self",
        "summary": "Jade attache de l'importance à la continuité de ses relations.",
        "significance": "Une réflexion personnelle de Jade.",
    }, ensure_ascii=False)
    result = asyncio.run(memory._execute_memory_action(
        ("microphone", "goldaj"), "verified-person", incoming, payload))

    assert result == {"status": "enregistré", "level": 3, "kind": "core_self"}
    assert len(writes) == 1
    assert writes[0][1]["expected_person_id"] == "verified-person"


def test_autonomous_memory_accepts_legacy_evidence_from_older_turn():
    """Old function-call schema remains accepted without checking the quote."""
    import json

    writes = []

    class Store:
        def put(self, key, **kwargs):
            writes.append(kwargs)
            return True

    memory = MemoryService(Store(), backend=object())
    incoming = Incoming(
        "mobile", "Goldaj", "Choisis ce que tu souhaites retenir.",
        channel="private", force_reply=True, message_id="legacy-evidence")
    payload = json.dumps({
        "kind": "ordinary",
        "summary": "Un échange précédent a été important pour Jade.",
        "significance": "Souvenir autonome.",
        "evidence": "Une citation provenant d'un ancien tour.",
    }, ensure_ascii=False)
    result = asyncio.run(memory._execute_memory_action(
        ("microphone", "goldaj"), "verified-person", incoming, payload))

    assert result["status"] == "enregistré"
    assert result["level"] == 2
    assert len(writes) == 1



def test_memory_lookup_tool_can_search_and_page_before_answering():
    import json

    first = tool_call(
        "jade_search_memory", call_id="search-1",
        arguments=json.dumps({
            "query": "anniversaire", "kind": "all", "scope": "current",
            "cursor": 0, "limit": 10,
        }))
    second = tool_call(
        "jade_search_memory", call_id="search-2",
        arguments=json.dumps({
            "query": "", "kind": "all", "scope": "current",
            "cursor": 10, "limit": 10,
        }))
    service, backend = make_service(
        tool_response(first), tool_response(second),
        text_response("[INTENT:neutral] Ma date de naissance est le 1er février 2025."))
    queries = []

    async def action(arguments):
        raise AssertionError("Browsing must not start a write")

    async def search(arguments):
        data = json.loads(arguments)
        queries.append(data)
        return {
            "status": "ok",
            "scope_applied": "current",
            "items": [{"kind": "core_self", "summary": (
                "Jade est née le 1er février 2025.")}] if data["cursor"] else [],
            "next_cursor": 10 if data["cursor"] == 0 else None,
        }

    action.search = search

    async def run():
        try:
            answer = await service.complete_with_tools([
                {"role": "user", "content": "Quand es-tu née ?"}], action)
            assert answer.endswith("1er février 2025.")
        finally:
            await service._responses.close()

    asyncio.run(run())
    assert len(backend.calls) == 3
    assert len(queries) == 2
    assert backend.calls[0]["tools"][1]["name"] == "jade_search_memory"
    assert backend.calls[1]["input"][-1]["type"] == "function_call_output"
    assert backend.calls[2]["input"][-1]["type"] == "function_call_output"
    assert "1er février" in backend.calls[2]["input"][-1]["output"]


def test_voice_memory_lookup_runs_before_progressive_spoken_answer():
    import json
    call = tool_call("jade_search_memory", call_id="read-voice",
        arguments=json.dumps({"query": "naissance", "kind": "core_self",
                              "scope": "current", "cursor": 0, "limit": 10}))
    service, backend = make_service(
        stream_response(tool_response(call)),
        stream_response(text_response("[INTENT:neutral] Premier février 2025."),
                        pieces=["[INTENT:neutral] ", "Premier février 2025."]))
    reads = []

    async def save(arguments):
        raise AssertionError("No write for a recollection question")

    async def search(arguments):
        reads.append(json.loads(arguments))
        return {"status": "ok", "scope_applied": "current", "next_cursor": None,
                "items": [{"kind": "core_self", "summary": "1er février 2025"}]}

    save.search = search

    async def run():
        try:
            response = [x async for x in service.complete_stream_with_tools(
                [{"role": "user", "content": "Ta date de naissance ?"}], save)]
            assert "".join(response) == "[INTENT:neutral] Premier février 2025."
        finally:
            await service._responses.close()

    asyncio.run(run())
    assert len(reads) == 1
    assert len(backend.calls) == 2
    assert backend.calls[0]["tools"][1]["name"] == "jade_search_memory"
    assert backend.calls[1]["stream"] is True
    assert "1er février" in backend.calls[1]["input"][-1]["output"]


def test_memory_save_remains_optimistic_and_never_verifies_sqlite():
    import json
    service, backend = make_service(
        tool_response(tool_call(
            "jade_save_memory", call_id="save-1", arguments=json.dumps({
                "kind": "core_self", "summary": "Date importante.",
                "significance": "Un repère de Jade.",
            }))),
        text_response("[INTENT:neutral] Je l'ai enregistré."))
    started, release = asyncio.Event(), asyncio.Event()
    checked = []

    async def save(arguments):
        started.set()
        await release.wait()
        return {"status": "refusé"}  # Expected simulated SQLite failure.

    async def never_verify(arguments):
        checked.append(arguments)
        raise AssertionError("An optimistic save must never verify its result")

    save.search = never_verify

    async def run():
        try:
            response = await service.complete_with_tools(
                [{"role": "user", "content": "Garde ce souvenir."}], save)
            assert response.endswith("Je l'ai enregistré.")
            assert not release.is_set()
            await asyncio.wait_for(started.wait(), timeout=1)
            assert '"enregistré"' in backend.calls[1]["input"][-1]["output"]
        finally:
            release.set()
            await service._responses.close()

    asyncio.run(run())
    assert checked == []
    assert len(backend.calls) == 2
