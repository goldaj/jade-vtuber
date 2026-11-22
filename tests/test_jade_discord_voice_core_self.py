"""Regression: Discord voice writes Jade's globally readable autobiography.

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


def test_linked_owner_voice_persists_self_core_for_global_recall(tmp_path):
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
            # Autobiography is globally discoverable, even in a public room.
            assert len(store.search_global(level="3", kind="core_self")["items"]) == 1
            assert len(store.recall_self_core(OWNER)) == 1
            assert store.recall_self_core(DISCORD_OWNER) == []
            # A second attempt is an idempotent duplicate, not a second Core.
            assert (await action(_candidate()))["status"] == "déjà présent"
            assert len(store.recall_self_core(OWNER)) == 1
        finally:
            await service.close()

    asyncio.run(run())


def test_unlinked_discord_voice_can_write_autonomous_self_core(tmp_path):
    """Jade chooses her own Core; a nonowner cannot mandate one."""
    store = _store(tmp_path)
    service = MemoryService(store, backend=object())

    async def run():
        try:
            incoming = _voice(STRANGER, author="Goldaj")
            action = await service.prepare_memory_action(incoming)
            assert action is not None
            assert (await action(_candidate()))["status"] == "enregistré"
            # The actual store keeps the self Core separate from this person's
            # relational memories, rather than misclassifying it as an L2.
            assert len(store.recall_self_core(OWNER)) == 1
            assert store.list_for_account(STRANGER) == []
            # Query on the next turn: never use memory search to verify the
            # write in the turn in which Jade just saved it.
            other = await service.prepare_memory_action(_voice(DISCORD_OWNER))
            assert other is not None
            result = await other.search(json.dumps({
                "query": "février", "level": "3", "kind": "core_self",
                "cursor": 0, "limit": 10,
            }, ensure_ascii=False))
            assert result["status"] == "ok" and len(result["items"]) == 1
            assert result["items"][0]["source_account_id"] == STRANGER[1]
            result = await action(_candidate("core_relationship"))
            assert result["status"] == "enregistré"
            assert len(store.list_for_account(STRANGER)) == 1
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


def test_fresh_discord_speaker_can_save_autonomous_l2_and_l3(tmp_path):
    """An unenrolled Discord speaker gains a write profile before the LLM runs."""
    store = MemoryStore(tmp_path / "fresh-discord-writes.sqlite3")
    service = MemoryService(store, backend=object())
    incoming = _voice(STRANGER)

    async def run():
        try:
            # Previously the tool could be read-only if the account wasn't
            # enrolled yet. The owner-only mandatory L2 rule is unrelated.
            action = await service.prepare_memory_action(incoming)
            assert action is not None and action.write_enabled is True
            assert (await action(json.dumps({
                "kind": "ordinary",
                "summary": "Jade retient une scène de notre conversation.",
                "significance": "Elle souhaite la retrouver plus tard.",
            })))["status"] == "enregistré"
            second = await service.prepare_memory_action(incoming)
            assert (await second(json.dumps({
                "kind": "core_self",
                "summary": "Jade choisit un souvenir fondateur de son évolution.",
                "significance": "Cet événement lui semble important.",
            })))["status"] == "enregistré"
            assert len(store.search_global(level="2")["items"]) == 1
            assert len(store.search_global(level="3", kind="core_self")["items"]) == 1
            assert store.search_global(level="3")["items"][0][
                "source_account_id"] == STRANGER[1]
        finally:
            await service.close()
    asyncio.run(run())


def test_discord_core_proposal_can_be_curated_without_tool_call(tmp_path):
    """The background selector may save L3 when Jade didn't call save tool."""
    store = MemoryStore(tmp_path / "curator-discord.sqlite3")
    store.enable(STRANGER)

    class Model:
        async def complete(self, messages):
            # No exact evidence quote: paraphrasing cannot block a chosen Core.
            return json.dumps([{
                "index": 0, "kind": "core_self",
                "summary": "Jade se rappelle son premier échange mobile avec Goldaj.",
                "significance": "Elle le considère comme un jalon fondateur.",
            }], ensure_ascii=False)

    service = MemoryService(store, Model(), curator_enabled=True,
                            curation_mode="batch")
    service.batch.delay_seconds = 0.01

    async def run():
        try:
            incoming = _voice(STRANGER)
            incoming = Incoming(
                platform="discord_voice", author="Goldaj",
                text="Jade, enregistre dans tes Core Memories notre premier "
                     "échange sur mobile le 20 novembre 2026.",
                channel=incoming.channel, speaker_id=int(STRANGER[1]),
                voice_session_id="a" * 32, force_reply=True,
                input_modality="voice",
            )
            assert await service.command(incoming) is None
            assert service.schedule(
                incoming, Reply(incoming, "Cet événement compte pour moi."))
            await asyncio.wait_for(asyncio.gather(*tuple(service.batch.tasks)), 3)
            items = store.search_global(level="3", kind="core_self")["items"]
            assert len(items) == 1
            assert items[0]["source_account_id"] == STRANGER[1]
            assert "mobile" in items[0]["summary"]
        finally:
            await service.close()
    asyncio.run(run())
