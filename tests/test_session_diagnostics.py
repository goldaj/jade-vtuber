"""Offline regression tests for Jade's session diagnostics."""
from __future__ import annotations

import asyncio
import logging

from src.jade_runtime import session_logging, turn_logging
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming, Reply


def test_private_session_file_and_compact_console(tmp_path, capsys, monkeypatch):
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    monkeypatch.setattr(session_logging, "_SESSION_FILE", None)
    try:
        path = session_logging.start_session_logging(tmp_path)
        assert path.exists()
        assert path == session_logging.start_session_logging(tmp_path)
        source = Incoming(
            "mobile", "Goldaj", "Jade, ceci contient sk-abcdefghijklmnopqrstuvwxyz",
            channel="private", force_reply=True)
        token = session_logging.bind_turn(17, source)
        try:
            turn_logging.record_input(17, source)
            session_logging.event("llm_raw", raw_output="[INTENT:playful] Salut Jade.")
            turn_logging.record_reply(17, Reply(source, "Bonjour", intent="playful"),
                                      ("mobile_text",))
            turn_logging.record_delivery(17, "handoff_completed",
                                         destinations=("mobile_text",))
        finally:
            session_logging.reset_turn(token)
        for handler in root.handlers:
            handler.flush()
        text = path.read_text(encoding="utf-8")
        stderr = capsys.readouterr().err
        assert "input_selected" in text
        assert "llm_raw" in text
        assert "reply_planned" in text
        assert "delivery_outcome" in text
        assert "abcdefghijklmnopqrstuvwxyz" not in text
        assert "[SECRET MASQUÉ]" in text
        assert "input_selected" in stderr
        assert "llm_raw" not in stderr
        assert "ceci contient" not in stderr
    finally:
        for handler in list(root.handlers):
            if handler not in previous_handlers:
                root.removeHandler(handler)
                handler.close()
        root.setLevel(previous_level)


def test_sqlite_commits_are_traced_without_sql_or_values(tmp_path, monkeypatch):
    from src.jade_runtime import memory_store
    events = []
    monkeypatch.setattr(memory_store, "event",
                        lambda name, **fields: events.append((name, fields)))
    store = MemoryStore(tmp_path / "jade-memory.sqlite3")
    store.enable(("microphone", "goldaj"))
    commits = [fields for name, fields in events if name == "sqlite_commit"]
    assert commits
    assert any(field["changed_rows"] >= 2 for field in commits)
    assert any(item["table"] == "identities"
               for field in commits for item in field["statements"])
    assert all("goldaj" not in str(field) for field in commits)


def test_raw_llm_text_is_recorded_before_intent_cleanup(monkeypatch):
    from src.jade_runtime import dialogue as dialogue_module
    events = []
    monkeypatch.setattr(dialogue_module, "event",
                        lambda name, **fields: events.append((name, fields)))

    class FakeBackend:
        async def complete(self, messages):
            return "[INTENT:playful] Bonjour à tous."

    source = Incoming("mobile", "Goldaj", "Jade, bonjour", force_reply=True)
    response = asyncio.run(Dialogue(FakeBackend(), "Prompt système").respond(source))
    assert response.text == "Bonjour à tous."
    assert any(name == "llm_raw" and "[INTENT:playful]" in fields["raw_output"]
               for name, fields in events)


def test_raw_stream_is_recorded_even_when_it_raises(monkeypatch):
    from src.jade_runtime import dialogue as dialogue_module
    events = []
    monkeypatch.setattr(dialogue_module, "event",
                        lambda name, **fields: events.append((name, fields)))

    class BrokenBackend:
        async def complete_stream(self, messages):
            yield "[INTENT:playful] Début."
            raise RuntimeError("transmission interrompue")

    async def deliver(sentence):
        return None

    source = Incoming("discord_voice", "Speaker", "Salut Jade",
                      force_reply=True)
    async def scenario():
        try:
            await Dialogue(BrokenBackend(), "Prompt système").respond(
                source, on_sentence=deliver)
        except RuntimeError:
            return
        raise AssertionError("A broken stream must propagate")

    asyncio.run(scenario())
    assert any(name == "llm_raw" and "[INTENT:playful]" in fields["raw_output"]
               for name, fields in events)
