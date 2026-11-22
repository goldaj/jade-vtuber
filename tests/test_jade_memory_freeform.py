"""Offline acceptance tests: Jade owns L2/L3 wording and needs no transcript quote."""
import asyncio
import json

import pytest

from src.jade_runtime.memory_batch import MemoryBatcher
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming, Reply

SPEAKER = ("discord", "12345678901234567")


def incoming(message="Jade, veux-tu garder un souvenir de notre soirée ?"):
    return Incoming(
        "discord_voice", "Goldaj", message,
        channel="1340781874594709613", speaker_id=int(SPEAKER[1]),
        voice_session_id="a" * 32, input_modality="voice",
        force_reply=True, message_id="original-voice-message")


@pytest.mark.parametrize("kind,level", [
    ("ordinary", "2"),
    ("core_self", "3"),
    ("core_relationship", "3"),
])
@pytest.mark.parametrize("legacy_evidence", [False, True])
def test_discord_can_store_any_l2_l3_in_jades_own_words(
        tmp_path, kind, level, legacy_evidence):
    store = MemoryStore(tmp_path / "freeform.sqlite3")
    service = MemoryService(store, backend=object())

    async def run():
        try:
            message = incoming()
            action = await service.prepare_memory_action(message)
            assert action is not None and action.write_enabled
            payload = {
                "kind": kind,
                "summary": "Jade invente librement sa propre formulation d'un jalon.",
                "significance": "Ce souvenir mérite de compter dans son histoire.",
            }
            # An old untrusted payload may have a non-exact quotation or even
            # a null value. Neither may veto Jade's freely chosen summary.
            if legacy_evidence:
                payload["evidence"] = None
            result = await action(json.dumps(payload, ensure_ascii=False))
            assert result == {
                "status": "enregistré", "level": int(level), "kind": kind}
            stored = store.search_global(level=level, kind=kind)["items"]
            assert len(stored) == 1
            assert stored[0]["summary"] == payload["summary"]
            assert stored[0]["source_account_id"] == SPEAKER[1]
        finally:
            await service.close()

    asyncio.run(run())


def test_single_curator_can_write_reformulated_core_without_evidence(tmp_path):
    store = MemoryStore(tmp_path / "single.sqlite3")
    store.enable(SPEAKER)

    class Model:
        async def complete(self, messages):
            return json.dumps({
                "kind": "core_relationship",
                "summary": "Jade a découvert une nouvelle complicité durable.",
                "significance": "Un tournant dans sa relation au monde.",
            }, ensure_ascii=False)

    service = MemoryService(
        store, Model(), curator_enabled=True, curation_mode="single")

    async def run():
        try:
            message = incoming("Nous avons vécu un moment important aujourd'hui.")
            reply = Reply(message, "Je suis contente de cette discussion.")
            assert service.schedule(message, reply)
            await asyncio.wait_for(
                asyncio.gather(*tuple(service.tasks)), timeout=3)
            items = store.search_global(level="3", kind="core_relationship")["items"]
            assert len(items) == 1
            assert "nouvelle complicité" in items[0]["summary"]
        finally:
            await service.close()

    asyncio.run(run())


@pytest.mark.parametrize("kind,level", [
    ("ordinary", "2"),
    ("core_self", "3"),
])
def test_batch_curator_can_write_reformulated_memory_without_evidence(
        tmp_path, kind, level):
    store = MemoryStore(tmp_path / "batch.sqlite3")
    store.enable(SPEAKER)

    class Model:
        async def complete(self, messages):
            return json.dumps([{
                "index": 0,
                "kind": kind,
                "summary": "Jade reformule un événement absent du texte littéral.",
                "significance": "Elle juge son importance toute seule.",
            }], ensure_ascii=False)

    batch = MemoryBatcher(store, Model(), batch_size=1, delay_seconds=0.01)

    async def run():
        try:
            message = incoming("Un évènement suffisamment significatif s'est produit.")
            assert batch.schedule(
                SPEAKER, f"discord:{message.channel}", message,
                Reply(message, "Je retiens que cet échange était important."))
            await asyncio.wait_for(asyncio.gather(*tuple(batch.tasks)), timeout=3)
            result = store.search_global(level=level, kind=kind)["items"]
            assert len(result) == 1
            assert "reformule un événement" in result[0]["summary"]
        finally:
            await batch.close()

    asyncio.run(run())


def test_jade_does_not_need_to_copy_or_quote_keyword_to_store(tmp_path):
    store = MemoryStore(tmp_path / "keywords.sqlite3")
    service = MemoryService(store, backend=object())

    async def run():
        try:
            action = await service.prepare_memory_action(incoming())
            payload = {
                "kind": "core_self",
                "summary": "Dans un récit fictif, Jade utilise le mot token.",
                "significance": "Un détail fictif qu'elle a choisi d'immortaliser.",
                "evidence": "Cette phrase n'apparaît nulle part dans le dialogue.",
            }
            result = await action(json.dumps(payload, ensure_ascii=False))
            assert result["status"] == "enregistré"
            assert len(store.search_global(level="3")["items"]) == 1
        finally:
            await service.close()

    asyncio.run(run())
