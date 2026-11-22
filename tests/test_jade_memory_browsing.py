"""Offline regression tests for explicit L2/L3 browsing through trusted channels."""
import asyncio
import json
import sqlite3
from contextlib import closing

from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming

ALICE = ("discord", "1234512345")
BOB = ("discord", "5432154321")
OWNER = ("microphone", "goldaj")
CHANNEL = "555000111"
OTHER = "999000111"


def _setup(tmp_path):
    store = MemoryStore(tmp_path / "memory-search.sqlite3")
    for key in (ALICE, BOB, OWNER):
        store.enable(key)
    return store


def _voice(key, *, channel=CHANNEL):
    return Incoming(
        "discord_voice", "Same-visible-nickname", "Te souviens-tu de cette date ?",
        channel=channel, speaker_id=int(key[1]), voice_session_id="a" * 32,
        force_reply=True, input_modality="voice")


def _request(*, query="", kind="all", scope="current", cursor=0, limit=15):
    return json.dumps({
        "query": query, "kind": kind, "scope": scope,
        "cursor": cursor, "limit": limit,
    }, ensure_ascii=False)


def test_discord_voice_can_retrieve_all_same_speaker_same_channel_l2(tmp_path):
    store = _setup(tmp_path)
    for i in range(39):
        assert store.put(
            ALICE, kind="ordinary", scope=f"discord:{CHANNEL}",
            summary=f"Souvenir important numéro {i:03d} écrit dans le même salon.")
    store.put(BOB, kind="ordinary", scope=f"discord:{CHANNEL}",
              summary="Souvenir privé de Bob.")
    store.put(ALICE, kind="ordinary", scope=f"discord:{OTHER}",
              summary="Information d'un autre salon.")
    with closing(sqlite3.connect(store.path)) as db:
        db.execute(
            "UPDATE memories SET expires_at='2000-01-01T00:00:00+00:00' "
            "WHERE summary=?", ("Souvenir important numéro 005 écrit dans le même salon.",))

    service = MemoryService(store, object())
    async def run():
        try:
            # Context remains private-by-default in public voice, but Jade
            # can actively explore ALL current-channel memories on demand.
            assert await service.context_for(_voice(ALICE)) == ""
            action = await service.prepare_memory_action(_voice(ALICE))
            assert callable(action.search)
            collected, cursor = [], 0
            while True:
                page = await action.search(_request(cursor=cursor))
                assert page["status"] == "ok"
                assert page["scope_applied"] == "current"
                collected.extend(page["items"])
                if page["next_cursor"] is None:
                    break
                cursor = page["next_cursor"]
            assert len(collected) == 38
            assert len({item["id"] for item in collected}) == 38
            assert all(item["kind"] == "ordinary" for item in collected)
            assert all("Souvenir important" in item["summary"] for item in collected)
            searched = await action.search(_request(query="numéro 037"))
            assert any("037" in item["summary"] for item in searched["items"])
            assert action.used is False  # Browsing does not suppress curation.
        finally:
            await service.close()
    asyncio.run(run())


def test_public_scope_is_clamped_and_private_linked_account_can_browse_all(tmp_path):
    store = _setup(tmp_path)
    assert store.put(ALICE, kind="ordinary", scope=f"discord:{CHANNEL}",
                     summary="Cadeau découvert au salon courant.")
    assert store.put(ALICE, kind="ordinary", scope=f"discord:{OTHER}",
                     summary="Projet évoqué dans un autre salon.")
    token = store.begin_link(OWNER, target=ALICE)
    assert store.complete_link(ALICE, token)
    assert store.put(OWNER, kind="core_relationship", scope="person",
                     summary="Souvenir privé du microphone local.")
    assert store.put(BOB, kind="ordinary", scope=f"discord:{CHANNEL}",
                     summary="Ce souvenir n'appartient qu'à Bob.")
    service = MemoryService(store, object())

    async def run():
        try:
            public = await service.prepare_memory_action(_voice(ALICE))
            clamped = await public.search(_request(scope="all", limit=15))
            assert clamped["scope_applied"] == "current"
            assert len(clamped["items"]) == 1
            assert "Cadeau" in clamped["items"][0]["summary"]
            dm = Incoming("discord", "Alice", "Je veux tous mes souvenirs.",
                          account_id=ALICE[1], channel="dm", private_channel=True)
            private = await service.prepare_memory_action(dm)
            everything = await private.search(_request(scope="all"))
            assert everything["scope_applied"] == "all"
            assert len(everything["items"]) == 3
            assert all("Bob" not in m["summary"] for m in everything["items"])
            third_party = await service.prepare_memory_action(_voice(BOB))
            bobs_page = await third_party.search(_request())
            assert len(bobs_page["items"]) == 1
            assert "Bob" in bobs_page["items"][0]["summary"]
        finally:
            await service.close()
    asyncio.run(run())


def test_self_core_from_other_discord_speaker_is_not_returned_publicly(tmp_path):
    store = _setup(tmp_path)
    assert store.put_self_core(ALICE, summary="Jade s'est fixé une date d'anniversaire.",
                               expected_person_id=store.account(ALICE))
    service = MemoryService(store, object())

    async def run():
        try:
            alice = await service.prepare_memory_action(_voice(ALICE))
            bob = await service.prepare_memory_action(_voice(BOB))
            assert len((await alice.search(
                _request(kind="core_self", query="anniversaire")))["items"]) == 1
            assert (await bob.search(
                _request(kind="core_self", query="anniversaire")))["items"] == []
            # Only a trusted private owner identity can see Jade's full
            # autobiography, including events from another speaker.
            owner = await service.prepare_memory_action(Incoming(
                "mobile", "Goldaj", "Consulte tes souvenirs.", channel="private"))
            page = await owner.search(_request(scope="all", kind="core_self"))
            assert len(page["items"]) == 1
        finally:
            await service.close()
    asyncio.run(run())


def test_malformed_search_and_stale_profile_cannot_retrieve_memories(tmp_path):
    store = _setup(tmp_path)
    store.put(ALICE, kind="ordinary", scope=f"discord:{CHANNEL}",
              summary="Souvenir qui ne doit pas fuiter.")
    service = MemoryService(store, object())

    async def run():
        try:
            action = await service.prepare_memory_action(_voice(ALICE))
            assert (await action.search('{"query": "x"}'))["status"] == "refusé"
            assert (await action.search(_request(limit=0)))["status"] == "refusé"
            assert (await action.search(_request(cursor=True)))["status"] == "refusé"
            # A profile replaced after tool preparation invalidates its read
            # authority; no lookup on another person through a stale closure.
            original = store.account(ALICE)
            with closing(sqlite3.connect(store.path)) as db:
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("DELETE FROM persons WHERE id=?", (original,))
            store.enable(ALICE)
            assert (await action.search(_request()))["status"] == "indisponible"
        finally:
            await service.close()
    asyncio.run(run())


def test_same_turn_optimistic_write_cannot_trigger_verification_lookup(tmp_path):
    store = _setup(tmp_path)
    service = MemoryService(store, object())
    async def run():
        try:
            action = await service.prepare_memory_action(_voice(ALICE))
            assert action is not None
            # This flag is set by the Responses adapter upon accepting the
            # queued write. The lookup must not inspect persistence afterward.
            action.used = True
            forbidden = await action.search(_request(query="anniversaire"))
            assert forbidden["status"] == "refusé"
            assert forbidden["reason"] == "write_accepted_this_turn"
            next_turn = await service.prepare_memory_action(_voice(ALICE))
            allowed = await next_turn.search(_request(query="anniversaire"))
            assert allowed["status"] == "ok"
        finally:
            await service.close()
    asyncio.run(run())
