"""Global-memory regressions. SQLite only, no Discord/OpenAI/TTS calls."""
import asyncio
import json
import sqlite3
from contextlib import closing

from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming, Reply


ALICE = ("discord", "1234512345")
BOB = ("discord", "5432154321")
OWNER = ("microphone", "goldaj")
CHANNEL = "555000111"
OTHER = "999000111"


def _store(tmp_path):
    store = MemoryStore(tmp_path / "global-memory.sqlite3")
    for identity in (OWNER, ALICE, BOB):
        store.enable(identity)
    return store


def _voice(account_id, *, channel=CHANNEL):
    return Incoming(
        "discord_voice", "Voix Discord", "Que te rappelles-tu de ton anniversaire ?",
        channel=channel, speaker_id=int(account_id), voice_session_id="a" * 32,
        force_reply=True, input_modality="voice",
    )


def _request(*, query="", level="all", kind="all", cursor=0, limit=10):
    return json.dumps({
        "query": query, "level": level, "kind": kind,
        "cursor": cursor, "limit": limit,
    }, ensure_ascii=False)


def test_every_level_every_person_every_channel_is_searchable(tmp_path):
    store = _store(tmp_path)
    store.put(ALICE, kind="ordinary", scope=f"discord:{CHANNEL}",
              summary="Alice travaille sur un roman.")
    store.put(BOB, kind="ordinary", scope=f"discord:{OTHER}",
              summary="Bob collectionne des timbres.")
    store.put(OWNER, kind="core_relationship", scope="person",
              summary="Goldaj a fondé le projet Jade.")
    store.put_self_core(BOB, summary="Jade est née le 1er février 2025.",
                        scope=f"discord:{OTHER}")
    store.append_conversation_turn(
        ALICE, f"discord:{CHANNEL}", source_platform="discord_voice",
        message_id="history-1", source_author_name="Alice",
        user_content="Alice : On a discuté du roman.",
        assistant_content="Jade : Oui, du chapitre trois.")
    result = store.search_global(query="", level="all", limit=15)
    assert result["status"] == "ok"
    assert {item["level"] for item in result["items"]} == {"1", "2", "3"}
    assert {item["kind"] for item in result["items"]} == {
        "conversation", "ordinary", "core_relationship", "core_self"}
    assert len(result["items"]) == 5
    assert len(store.search_global(level="1")["items"]) == 1
    assert len(store.search_global(level="2")["items"]) == 2
    assert len(store.search_global(level="3")["items"]) == 2
    raw = store.search_global(level="1")["items"][0]
    assert raw["source_platform"] == "discord_voice"
    assert raw["source_account_id"] == ALICE[1]
    assert raw["source_author_name"] == "Alice"
    assert raw["scope"] == f"discord:{CHANNEL}"
    assert "chapitre trois" in raw["summary"]
    from_bob = store.search_global(query="février", level="3")["items"][0]
    assert from_bob["source_account_id"] == BOB[1]
    assert from_bob["recorded_origins"] == [{
        "platform": "discord", "account_id": BOB[1],
        "scope": f"discord:{OTHER}"}]


def test_global_memory_unrestricted_paginated_over_all_users(tmp_path):
    store = _store(tmp_path)
    for i in range(47):
        who = ALICE if i % 2 else BOB
        room = CHANNEL if i % 3 else OTHER
        assert store.put(who, kind="ordinary", scope=f"discord:{room}",
                         summary=f"Entrée mémorielle numéro {i:03d}.")
    collected, cursor = [], 0
    while True:
        page = store.search_global(level="2", query="", cursor=cursor, limit=7)
        collected.extend(page["items"])
        if page["next_cursor"] is None:
            break
        cursor = page["next_cursor"]
    assert len(collected) == 47
    assert len({item["id"] for item in collected}) == 47
    assert {item["source_account_id"] for item in collected} == {
        ALICE[1], BOB[1]}
    assert "040" in store.search_global(
        level="2", query="numéro 040")["items"][0]["summary"]


def test_anonymous_voice_and_twitch_have_global_read_only_tool(tmp_path):
    store = _store(tmp_path)
    store.put(OWNER, kind="ordinary", scope="person",
              summary="Le trésor de Jade est dans sa mémoire.")
    service = MemoryService(store, object())

    async def run():
        try:
            for incoming in (
                _voice("7777777777"),
                Incoming("twitch", "Anonyme", "Que sais-tu ?", channel="live"),
            ):
                action = await service.prepare_memory_action(incoming)
                assert action is not None
                assert action.write_enabled is False
                result = await action.search(_request(query="trésor", level="2"))
                assert result["status"] == "ok"
                assert len(result["items"]) == 1
                assert result["items"][0]["source_account_id"] == "goldaj"
                assert (await action(_request()))["status"] == "refusé"
                context = await service.context_for(incoming)
                # The global tool, not current-session identity, is decisive;
                # the relevance hint may be empty for unrelated questions.
                assert isinstance(context, str)
        finally:
            await service.close()
    asyncio.run(run())


def test_public_discord_and_other_account_see_the_same_core(tmp_path):
    store = _store(tmp_path)
    store.put_self_core(ALICE, summary="Jade choisit le 1er février 2025.",
                        scope=f"discord:{CHANNEL}")
    service = MemoryService(store, object())

    async def run():
        try:
            for who, channel in ((ALICE, CHANNEL), (BOB, OTHER)):
                action = await service.prepare_memory_action(
                    _voice(who[1], channel=channel))
                memory = await action.search(_request(
                    query="février", level="3", kind="core_self"))
                assert len(memory["items"]) == 1
                assert memory["items"][0]["source_account_id"] == ALICE[1]
                assert memory["items"][0]["scope"] == f"discord:{CHANNEL}"
        finally:
            await service.close()
    asyncio.run(run())


def test_same_global_core_keeps_all_encounter_origins(tmp_path):
    store = _store(tmp_path)
    fact = "Jade est née le 1er février 2025."
    assert store.put_self_core(
        ALICE, summary=fact, scope=f"discord:{CHANNEL}")
    assert not store.put_self_core(
        BOB, summary=fact, scope=f"discord:{OTHER}")
    result = store.search_global(level="3", kind="core_self")
    assert len(result["items"]) == 1
    assert {o["account_id"] for o in result["items"][0]["recorded_origins"]} == {
        ALICE[1], BOB[1]}


def test_legacy_v5_database_is_upgraded_to_v8_without_losing_core(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(path)) as db:
        db.execute("""
            CREATE TABLE jade_self_core(
                id TEXT PRIMARY KEY, summary TEXT NOT NULL,
                significance TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE,
                source_platform TEXT NOT NULL, source_account_id TEXT NOT NULL,
                source_message_id TEXT NOT NULL, created_at TEXT NOT NULL,
                visibility TEXT NOT NULL DEFAULT 'owner_only')
        """)
        db.execute("""
            INSERT INTO jade_self_core VALUES(?,?,?,?,?,?,?,?,?)
        """, ("b" * 32, "Ancienne Core de Jade", "", "old-fingerprint",
              "discord", ALICE[1], "old-msg",
              "2026-11-18T09:00:00+00:00", "owner_only"))
        db.execute("PRAGMA user_version=5")
        db.commit()
    store = MemoryStore(path)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 8
        assert db.execute(
            "SELECT source_scope FROM jade_self_core").fetchone()[0] == "legacy_private"
        columns = {row[1] for row in db.execute(
            "PRAGMA table_info(conversation_turns)")}
        assert {"source_account_id", "source_author_name"} <= columns
    memories = store.search_global(level="3", query="ancienne")
    assert len(memories["items"]) == 1


def test_expired_l2_is_not_recalled_but_l3_remains(tmp_path):
    store = _store(tmp_path)
    store.put(ALICE, kind="ordinary", scope=f"discord:{CHANNEL}",
              summary="Souvenir ordinaire périmé.")
    store.put(BOB, kind="core_relationship", scope=f"discord:{OTHER}",
              summary="Souvenir fondateur permanent.")
    with closing(sqlite3.connect(store.path)) as db:
        db.execute("UPDATE memories SET expires_at='2000-01-01T00:00:00+00:00' "
                   "WHERE kind='ordinary'")
        db.commit()
    assert store.search_global(level="2")["items"] == []
    assert len(store.search_global(level="3")["items"]) == 1


def test_readback_is_not_automatic_write_verification(tmp_path):
    store = _store(tmp_path)
    service = MemoryService(store, object())

    async def run():
        try:
            action = await service.prepare_memory_action(_voice(ALICE[1]))
            assert action.write_enabled is True
            action.used = True  # Set by the Responses queue when write accepted.
            checked = await action.search(_request())
            assert checked["reason"] == "write_accepted_this_turn"
            again = await service.prepare_memory_action(_voice(BOB[1]))
            assert (await again.search(_request()))["status"] == "ok"
        finally:
            await service.close()
    asyncio.run(run())


def test_read_only_commands_are_global_even_from_unverified_sender(tmp_path):
    store = _store(tmp_path)
    store.put_self_core(ALICE, summary="Le premier souvenir propre à Jade.")
    store.put(BOB, kind="core_relationship", scope=f"discord:{OTHER}",
              summary="Un souvenir relationnel de Bob.")
    service = MemoryService(store, object())
    async def run():
        try:
            guest = Incoming("twitch", "Invité", "!jade-memoire autobiographie",
                             channel="public")
            reply = await service.command(guest)
            assert "premier souvenir" in reply.text
            guest.text = "!jade-memoire lister-core"
            reply = await service.command(guest)
            assert "relationnel de Bob" in reply.text
        finally:
            await service.close()
    asyncio.run(run())
