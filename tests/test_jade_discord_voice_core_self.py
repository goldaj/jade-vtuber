"""Regression: linked Discord voice can store Jade's owner-private autobiography.

These are offline tests. They do not call Discord, OpenAI, or TTS.
"""
import asyncio
import json

from src.jade_runtime.memory_batch import MemoryBatcher
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming, Reply


OWNER = ("microphone", "goldaj")
DISCORD_OWNER = ("discord", "34567890123456789")
STRANGER = ("discord", "45678901234567890")
FACT = "Jade a choisi le 1er février 2025 comme date de naissance."


def _voice(account, *, author="Goldaj"):
    return Incoming(
        platform="discord_voice", author=author,
        text="Que souhaites-tu retenir de notre histoire ?",
        channel="1340781874594709613", message_id="voice-core",
        speaker_id=int(account[1]), voice_session_id="a" * 32,
        force_reply=True, input_modality="voice",
    )


def _candidate(kind="core_self"):
    return json.dumps({
        "kind": kind,
        "summary": FACT,
        "significance": "Date importante pour l'histoire personnelle de Jade.",
    }, ensure_ascii=False)


def _store(tmp_path):
    store = MemoryStore(tmp_path / "jade-voice-core.sqlite3")
    for account in (OWNER, DISCORD_OWNER, STRANGER):
        store.enable(account)
    return store


def _link_owner(store):
    token = store.begin_link(OWNER, target=DISCORD_OWNER)
    assert store.complete_link(DISCORD_OWNER, token)
    assert store.is_goldaj(DISCORD_OWNER)


def test_linked_owner_voice_persists_self_core_without_public_recall(tmp_path):
    store = _store(tmp_path)
    _link_owner(store)
    service = MemoryService(store, backend=object())

    async def run():
        try:
            incoming = _voice(DISCORD_OWNER, author="Un pseudo quelconque")
            action = await service.prepare_memory_action(incoming)
            assert action is not None
            result = await action(_candidate())
            assert result == {
                "status": "enregistré", "level": 3, "kind": "core_self"
            }
            # Public voice must not inject private owner memories into prompts.
            assert await service.context_for(incoming) == ""
            assert len(store.recall_self_core(OWNER)) == 1
            assert store.recall_self_core(DISCORD_OWNER) == []
            # A second attempt is an idempotent duplicate, not a second Core.
            assert (await action(_candidate()))["status"] == "déjà présent"
            assert len(store.recall_self_core(OWNER)) == 1
        finally:
            await service.close()

    asyncio.run(run())


def test_unlinked_discord_voice_cannot_write_owner_autobiography(tmp_path):
    store = _store(tmp_path)
    service = MemoryService(store, backend=object())

    async def run():
        try:
            incoming = _voice(STRANGER, author="Goldaj")
            action = await service.prepare_memory_action(incoming)
            assert action is not None
            assert (await action(_candidate()))["status"] == "refusé"
            # The database must enforce this too if bypassing service policy.
            assert not store.put_self_core(
                STRANGER, summary=FACT, expected_person_id=store.account(STRANGER))
            assert store.recall_self_core(OWNER) == []
            # Third-party relationship memories still behave as before.
            result = await action(_candidate("core_relationship"))
            assert result["status"] == "enregistré"
            assert len(store.list_for_account(STRANGER)) == 1
            assert store.recall_self_core(OWNER) == []
        finally:
            await service.close()

    asyncio.run(run())


def test_unlinked_before_deferred_voice_write_revokes_self_core(tmp_path):
    store = _store(tmp_path)
    _link_owner(store)
    service = MemoryService(store, backend=object())

    async def run():
        try:
            action = await service.prepare_memory_action(_voice(DISCORD_OWNER))
            assert action is not None
            assert store.unlink(DISCORD_OWNER)
            assert not store.is_goldaj(DISCORD_OWNER)
            assert (await action(_candidate()))["status"] == "refusé"
            assert store.recall_self_core(OWNER) == []
        finally:
            await service.close()

    asyncio.run(run())


def test_batch_curator_accepts_linked_owner_discord_voice_core_self(tmp_path):
    """The default batched curator follows the same verified owner policy."""
    store = _store(tmp_path)
    _link_owner(store)

    class Model:
        async def complete(self, messages):
            incoming_text = "Que souhaites-tu retenir de notre histoire ?"
            return json.dumps([{
                "index": 0, "kind": "core_self", "summary": FACT,
                "significance": "Épisode fondateur de Jade.",
                "evidence": incoming_text,
            }], ensure_ascii=False)

    async def run():
        batch = MemoryBatcher(store, Model(), batch_size=1, delay_seconds=0.01)
        try:
            incoming = _voice(DISCORD_OWNER)
            assert batch.schedule(
                DISCORD_OWNER, f"discord:{incoming.channel}", incoming,
                Reply(incoming, "J'ai choisi de retenir cette date.")
            )
            await asyncio.wait_for(asyncio.gather(*tuple(batch.tasks)), timeout=3)
            assert len(store.recall_self_core(OWNER)) == 1
        finally:
            await batch.close()

    asyncio.run(run())
