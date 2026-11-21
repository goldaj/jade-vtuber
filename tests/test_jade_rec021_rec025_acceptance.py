"""REC-021 / REC-025 automated acceptance checks, isolated and offline."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

from src.jade_runtime.memory_store import (
    CONVERSATION_RETENTION_DAYS, CONVERSATION_RELOAD_HOURS,
    ORDINARY_RETENTION_DAYS, MemoryStore,
)
from src.jade_runtime.memory_transfer import export_memory, import_memory

OWNER = ("microphone", "goldaj")  # Synthetic identity, no audio hardware used.
ALICE = ("discord", "20121")
BOB = ("discord", "20122")


class MemoryAcceptance(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "test.sqlite3"
        self.store = MemoryStore(self.path)

    def query(self, statement, args=()):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute(statement, args).fetchall()

    def test_rec021_consent_scope_core_and_restart(self):
        self.assertFalse(self.store.put(ALICE, kind="ordinary",
            scope="discord:10", summary="Not enrolled"))
        self.assertFalse(self.store.append_conversation_turn(ALICE, "discord:10",
            source_platform="discord", message_id="no-consent",
            user_content="Not saved", assistant_content="Not saved"))
        for key in (ALICE, BOB, OWNER):
            self.store.enable(key)
        self.assertTrue(self.store.put(ALICE, kind="ordinary",
            scope="discord:10", summary="Alice private draft"))
        self.assertTrue(self.store.put(ALICE, kind="core_relationship",
            scope="discord:10", summary="Alice relationship memory"))
        self.assertTrue(self.store.put(BOB, kind="ordinary",
            scope="discord:10", summary="Bob private draft"))
        self.assertTrue(self.store.put_self_core(OWNER,
            summary="Jade autobiographical moment"))
        self.assertFalse(self.store.put_self_core(ALICE,
            summary="Alice cannot write autobiography"))
        fresh = MemoryStore(self.path)
        self.assertEqual({m["kind"] for m in fresh.recall(ALICE, "discord:10")},
                         {"ordinary", "core_relationship"})
        self.assertEqual(fresh.recall(ALICE, "discord:11"), [])
        self.assertEqual(len(fresh.recall(BOB, "discord:10")), 1)
        self.assertNotIn("Alice", str(fresh.recall(BOB, "discord:10")))
        self.assertEqual(fresh.recall_self_core(ALICE), [])
        self.assertEqual(len(fresh.recall_self_core(OWNER)), 1)

    def test_rec021_retention_and_unlimited_24h_recovery(self):
        self.assertEqual((CONVERSATION_RETENTION_DAYS, CONVERSATION_RELOAD_HOURS,
                          ORDINARY_RETENTION_DAYS), (7, 24, 365))
        self.store.enable(OWNER)
        for n in range(45):
            self.assertTrue(self.store.append_conversation_turn(OWNER, "person",
                source_platform="mobile", message_id=f"new-{n}",
                user_content=f"Question {n}", assistant_content=f"Answer {n}"))
        for name, delta in (("old-25h", timedelta(hours=25)),
                            ("old-8d", timedelta(days=8))):
            self.assertTrue(self.store.append_conversation_turn(OWNER, "person",
                source_platform="mobile", message_id=name,
                user_content=name, assistant_content="Old reply"))
            with closing(sqlite3.connect(self.path)) as db:
                db.execute("UPDATE conversation_turns SET created_at=? "
                           "WHERE source_message_id=?",
                           ((datetime.now(timezone.utc)-delta).isoformat(), name))
                db.commit()
        self.assertTrue(self.store.put(OWNER, kind="ordinary",
            scope="person", summary="Expired ordinary"))
        self.assertTrue(self.store.put(OWNER, kind="ordinary",
            scope="person", summary="Active ordinary"))
        self.assertTrue(self.store.put(OWNER, kind="core_relationship",
            scope="person", summary="Permanent relationship"))
        self.assertTrue(self.store.put_self_core(OWNER,
            summary="Permanent autobiography"))
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE memories SET expires_at=? WHERE summary=?",
                ((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),
                 "Expired ordinary"))
            db.commit()
        self.assertEqual(len(self.store.recent_conversation_turns(OWNER, "person")), 90)
        self.assertEqual(self.store.prune_expired(), (1, 1))
        self.assertEqual(len(self.query("SELECT id FROM conversation_turns")), 46)
        self.assertEqual(len(self.store.recall(OWNER, "person")), 2)
        self.assertEqual(len(self.store.recall_self_core(OWNER)), 1)
        created, expires = self.query(
            "SELECT created_at,expires_at FROM memories WHERE kind='ordinary'")[0]
        self.assertEqual(datetime.fromisoformat(expires) -
                         datetime.fromisoformat(created), timedelta(days=365))

    def test_rec021_targeted_deletion_preserves_other_account(self):
        self.assertTrue(self.store.auto_enable(ALICE))
        self.store.enable(BOB)
        self.store.put(ALICE, kind="ordinary", scope="discord:10",
                       summary="Alice can delete her memory")
        self.store.put(BOB, kind="ordinary", scope="discord:10",
                       summary="Bob should survive")
        memory_id = self.store.list_for_account(ALICE)[0]["id"]
        self.assertTrue(self.store.delete_memory(ALICE, memory_id))
        fresh = MemoryStore(self.path)
        self.assertTrue(fresh.auto_enable(ALICE))
        self.assertEqual(fresh.recall(ALICE, "discord:10"), [])
        self.assertEqual(len(fresh.recall(BOB, "discord:10")), 1)

    def test_rec025_wal_backup_restore_and_scoped_deletion(self):
        for key in (ALICE, BOB, OWNER):
            self.store.enable(key)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode=WAL").fetchone()[0],
                             "wal")
        self.store.put(ALICE, kind="ordinary", scope="discord:10",
                       summary="Synthetic Alice backup")
        self.store.put(BOB, kind="core_relationship", scope="discord:10",
                       summary="Synthetic Bob backup")
        self.store.put_self_core(OWNER, summary="Synthetic Jade core")
        self.store.append_conversation_turn(ALICE, "discord:10",
            source_platform="discord", message_id="backup-1",
            user_content="Snapshot question", assistant_content="Snapshot reply")
        archive = self.root / "snapshot.zip"
        target = self.root / "restored.sqlite3"
        export_memory(self.path, archive)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(set(z.namelist()),
                             {"jade-memory.sqlite3", "manifest.json"})
            self.assertEqual(hashlib.sha256(z.read("jade-memory.sqlite3")).hexdigest(),
                             json.loads(z.read("manifest.json"))["sha256"])
        import_memory(archive, target)
        restored = MemoryStore(target)
        self.assertEqual(len(restored.recall(ALICE, "discord:10")), 1)
        self.assertEqual(len(restored.recall(BOB, "discord:10")), 1)
        self.assertEqual(len(restored.recall_self_core(OWNER)), 1)
        self.assertEqual(len(restored.recent_conversation_turns(
            ALICE, "discord:10")), 2)
        restored_id = restored.list_for_account(ALICE)[0]["id"]
        self.assertTrue(restored.delete_memory(ALICE, restored_id))
        self.assertEqual(restored.recall(ALICE, "discord:10"), [])
        self.assertEqual(len(restored.recent_conversation_turns(
            ALICE, "discord:10")), 2)
        self.assertEqual(len(restored.recall(BOB, "discord:10")), 1)
        self.assertEqual(len(restored.recall_self_core(OWNER)), 1)
        self.assertEqual(len(self.store.recall(ALICE, "discord:10")), 1,
                         "Restoring must not alter the original database")

    def test_rec025_rejects_tampering_and_existing_destinations(self):
        self.store.enable(ALICE)
        self.store.put(ALICE, kind="ordinary", scope="discord:10",
                       summary="Synthetic archived event")
        archive = self.root / "clean.zip"
        export_memory(self.path, archive)
        invalid = self.root / "tampered.zip"
        with zipfile.ZipFile(archive) as zipped:
            raw = bytearray(zipped.read("jade-memory.sqlite3"))
            manifest = zipped.read("manifest.json")
        raw[-1] ^= 1
        with zipfile.ZipFile(invalid, "w") as zipped:
            zipped.writestr("jade-memory.sqlite3", raw)
            zipped.writestr("manifest.json", manifest)
        target = self.root / "import.sqlite3"
        with self.assertRaises(ValueError):
            import_memory(invalid, target)
        self.assertFalse(target.exists())
        import_memory(archive, target)
        with self.assertRaises(FileExistsError):
            import_memory(archive, target)
        with self.assertRaises(FileExistsError):
            export_memory(self.path, archive)


if __name__ == "__main__":
    unittest.main()
