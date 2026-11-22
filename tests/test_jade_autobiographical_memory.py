"""Tests for Jade's global autobiography, source attribution, migration and erasure."""
import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock

from src.jade_runtime.memory_store import MemoryStore, SCHEMA_VERSION
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_transfer import export_memory, import_memory
from src.jade_runtime.messages import Incoming, Reply

OWNER = ("microphone", "goldaj")
ALICE = ("discord", "101")


class Autobiography(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jade.sqlite3"
        self.store = MemoryStore(self.path)

    async def test_global_core_from_consented_speakers_and_duplicate_control(self):
        self.store.enable(ALICE)
        self.assertTrue(self.store.put_self_core(ALICE, summary="Jade a appris un secret."))
        self.assertFalse(self.store.put_self_core(OWNER, summary="Jade a fini un projet."))
        self.store.enable(OWNER)
        self.assertTrue(self.store.put_self_core(
            OWNER, summary="Jade a terminé son premier roman interactif.",
            significance="C'était une expérience importante.", message_id="test-1"))
        self.assertFalse(self.store.put_self_core(
            OWNER, summary="Jade a terminé son premier roman interactif."))
        self.assertEqual(self.store.recall_self_core(ALICE), [])
        self.assertEqual(self.store.recall(ALICE, "discord:22"), [])
        self.assertEqual(self.store.list_for_account(OWNER), [])
        owner = self.store.recall_self_core(OWNER)
        self.assertEqual(len(owner), 2)
        self.assertTrue(all(m["visibility"] == "owner_only" for m in owner))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM jade_self_core").fetchone()[0], 2)
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    async def test_all_dialogues_read_global_self_core_with_owner_only_deletion(self):
        self.store.enable(OWNER)
        self.store.enable(ALICE)
        self.store.put_self_core(
            OWNER, summary="Jade a terminé son premier roman interactif.",
            significance="Elle a appris à coécrire.")
        svc = MemoryService(self.store, AsyncMock())
        text = await svc.context_for(Incoming("microphone", "Goldaj", "Salut"))
        self.assertIn("premier roman", text)
        text_mobile = await svc.context_for(Incoming("mobile", "Goldaj", "Salut"))
        self.assertIn("premier roman", text_mobile)
        text_public = await svc.context_for(Incoming(
            "discord", "Goldaj", "Salut", account_id="101", channel="99"))
        self.assertIn("premier roman", text_public)
        self.assertIn("premier roman", (await svc.command(
            Incoming("discord", "Alice", "!jade-memoire autobiographie",
                     account_id="101"))).text)
        await svc.close()

    async def test_manual_list_and_targeted_delete(self):
        self.store.enable(OWNER)
        self.store.put_self_core(OWNER, summary="Jade a fini son premier récit.")
        svc = MemoryService(self.store, AsyncMock())
        msg = Incoming("microphone", "Goldaj", "!jade-memoire autobiographie")
        response = await svc.command(msg)
        memory_id = self.store.recall_self_core(OWNER)[0]["id"]
        self.assertIn(memory_id, response.text)
        result = await svc.command(Incoming(
            "microphone", "Goldaj", "!jade-memoire supprimer-self " + memory_id))
        self.assertIn("supprimé", result.text)
        self.assertEqual(self.store.recall_self_core(OWNER), [])
        self.store.put_self_core(OWNER, summary="Jade a repris le projet.")
        self.assertIsNone(await svc.command(Incoming(
            "microphone", "Goldaj", "!jade-memoire oublier")))
        self.assertEqual(len(self.store.recall_self_core(OWNER)), 1)
        active_id = self.store.recall_self_core(OWNER)[0]["id"]
        self.assertTrue(self.store.delete_self_core(OWNER, active_id))
        self.assertEqual(self.store.recall_self_core(OWNER), [])
        await svc.close()

    async def test_v1_upgrade_and_portable_current_backup(self):
        self.store.enable(OWNER)
        # Simulate the exact pre-autobiography SQLite layout and user_version.
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("DROP TABLE jade_self_core")
            db.execute("PRAGMA user_version=1")
            db.commit()
        old_archive = Path(self.temp.name) / "v1.zip"
        export_memory(self.path, old_archive)
        restored_v1 = Path(self.temp.name) / "restored_v1.sqlite3"
        import_memory(old_archive, restored_v1)
        migrated = MemoryStore(restored_v1)
        self.assertTrue(migrated.put_self_core(
            OWNER, summary="Jade a migré sa mémoire vers le nouveau PC."))
        archive = Path(self.temp.name) / "current.zip"
        export_memory(restored_v1, archive)
        restored_v2 = Path(self.temp.name) / "restored_current.sqlite3"
        import_memory(archive, restored_v2)
        self.assertEqual(len(MemoryStore(restored_v2).recall_self_core(OWNER)), 1)

    async def test_queued_core_self_does_not_resurface_after_profile_replacement(self):
        self.store.enable(OWNER)
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(_messages):
            entered.set()
            await release.wait()
            return json.dumps({
                "kind": "core_self",
                "summary": "Jade a terminé sa première histoire.",
                "significance": "Un événement fondateur.",
                "evidence": "Nous avons terminé le dernier chapitre.",
            })

        model = AsyncMock()
        model.complete.side_effect = delayed
        svc = MemoryService(self.store, model, curator_enabled=True)
        source = Incoming("microphone", "Goldaj",
                          "Nous avons terminé le dernier chapitre.",
                          message_id="delayed-core", force_reply=True)
        try:
            self.assertTrue(svc.schedule(source, Reply(source, "Fin du récit.")))
            await asyncio.wait_for(entered.wait(), 2)
            before = self.store.account(OWNER)
            with closing(sqlite3.connect(self.path)) as db:
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("DELETE FROM persons WHERE id=?", (before,))
                db.commit()
            self.assertNotEqual(self.store.enable(OWNER), before)
            release.set()
            await asyncio.wait_for(asyncio.gather(*list(svc.tasks)), 2)
            self.assertEqual(self.store.recall_self_core(OWNER), [])
        finally:
            await svc.close()

    async def test_curator_keeps_core_self_out_of_personal_table(self):
        self.store.enable(OWNER)
        backend = AsyncMock()
        backend.complete.return_value = json.dumps({
            "kind": "core_self",
            "summary": "Jade a aidé à conclure sa première aventure.",
            "significance": "Première aventure coécrite.",
            "evidence": "Nous avons achevé le dernier chapitre.",
        })
        svc = MemoryService(self.store, backend, curator_enabled=True)
        source = Incoming("microphone", "Goldaj",
                          "Nous avons achevé le dernier chapitre.",
                          message_id="test2", force_reply=True)
        self.assertTrue(svc.schedule(source, Reply(source, "J'en suis heureuse.")))
        await asyncio.wait_for(asyncio.gather(*list(svc.tasks)), timeout=2)
        self.assertEqual(len(self.store.recall_self_core(OWNER)), 1)
        self.assertEqual(self.store.list_for_account(OWNER), [])
        await svc.close()


if __name__ == "__main__":
    unittest.main()
