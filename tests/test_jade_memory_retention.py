"""Level 1/2/3 retention contracts (offline, synthetic SQLite only)."""
import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import (
    CONVERSATION_RELOAD_HOURS, CONVERSATION_RETENTION_DAYS,
    ORDINARY_RETENTION_DAYS, MemoryStore, SCHEMA_VERSION,
)
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime


OWNER = ("microphone", "goldaj")


class SQLiteRetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jade.sqlite3"
        self.store = MemoryStore(self.path)
        self.store.enable(OWNER)
        self.other = ("discord", "123")
        self.store.enable(self.other)

    def rows(self, sql, params=()):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute(sql, params).fetchall()

    def test_default_ttl_365_days_for_auto_and_direct_ordinary(self):
        self.assertEqual(CONVERSATION_RETENTION_DAYS, 7)
        self.assertEqual(CONVERSATION_RELOAD_HOURS, 24)
        self.assertEqual(ORDINARY_RETENTION_DAYS, 365)
        self.assertTrue(self.store.put(
            OWNER, kind="ordinary", scope="person", summary="Ordinaire choisi par Jade"))
        self.assertEqual(self.store.put_requested_ordinary(
            OWNER, scope="person", summary="Ordinaire demandé"), "created")
        rows = self.rows(
            "SELECT kind,created_at,expires_at FROM memories ORDER BY created_at")
        self.assertEqual(len(rows), 2)
        for kind, created, expires in rows:
            self.assertEqual(kind, "ordinary")
            self.assertEqual(
                datetime.fromisoformat(expires) - datetime.fromisoformat(created),
                timedelta(days=365),
            )
        self.assertTrue(self.store.put(
            OWNER, kind="core_relationship", scope="person", summary="Core choisie"))
        self.assertTrue(self.store.put_self_core(OWNER, summary="Core autobiographique"))
        self.assertEqual(self.rows(
            "SELECT expires_at FROM memories WHERE kind='core_relationship'"),
            [(None,)])
        self.assertEqual(len(self.store.recall_self_core(OWNER)), 1)

    def test_migration_v3_extends_old_ordinary_from_original_date(self):
        self.store.put(OWNER, kind="ordinary", scope="person", summary="Mémoire ancienne")
        self.store.put(OWNER, kind="core_relationship", scope="person",
                       summary="Souvenir profond de Jade")
        self.store.put_self_core(OWNER, summary="Souvenir autobiographique")
        now = datetime.now(timezone.utc)
        created = (now - timedelta(days=120)).isoformat()
        expires = (now - timedelta(days=30)).isoformat()  # 90-day legacy TTL
        with closing(sqlite3.connect(self.path)) as db:
            db.execute(
                "UPDATE memories SET created_at=?,expires_at=? WHERE kind='ordinary'",
                (created, expires),
            )
            db.execute("PRAGMA user_version=3")
            db.commit()
        migrated = MemoryStore(self.path)
        rows = self.rows(
            "SELECT created_at,expires_at FROM memories WHERE kind='ordinary'")
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            datetime.fromisoformat(rows[0][1]) - datetime.fromisoformat(rows[0][0]),
            timedelta(days=365),
        )
        self.assertEqual(self.rows("PRAGMA user_version"), [(SCHEMA_VERSION,)])
        self.assertEqual(
            len(migrated.recall(OWNER, "person")), 2)
        self.assertEqual(len(migrated.recall_self_core(OWNER)), 1)
        # Migrating again must not add 365 days to the just-migrated expiry.
        MemoryStore(self.path)
        self.assertEqual(
            self.rows("SELECT expires_at FROM memories WHERE kind='ordinary'"),
            [(rows[0][1],)],
        )

    def test_prune_seven_day_turns_and_expired_ordinary_only(self):
        now = datetime.now(timezone.utc)
        for n in range(4):
            self.assertTrue(self.store.append_conversation_turn(
                OWNER, "person", source_platform="microphone",
                message_id=f"turn-{n}", user_content=f"Demande {n}",
                assistant_content=f"Réponse {n}"))
        with closing(sqlite3.connect(self.path)) as db:
            for n, days in ((0, 8), (1, 7), (2, 6)):
                db.execute(
                    "UPDATE conversation_turns SET created_at=? WHERE source_message_id=?",
                    ((now - timedelta(days=days, seconds=10)).isoformat(), f"turn-{n}"),
                )
            db.commit()
        self.store.put(OWNER, kind="ordinary", scope="person",
                       summary="Souvenir ordinaire expiré")
        self.store.put(OWNER, kind="ordinary", scope="person",
                       summary="Souvenir ordinaire actif")
        self.store.put(OWNER, kind="core_relationship", scope="person",
                       summary="Core permanente")
        self.store.put_self_core(OWNER, summary="Core personnelle permanente")
        with closing(sqlite3.connect(self.path)) as db:
            db.execute(
                "UPDATE memories SET expires_at=? WHERE summary='Souvenir ordinaire expiré'",
                ((now - timedelta(seconds=5)).isoformat(),))
            db.commit()
        turns, ordinary = self.store.prune_expired()
        self.assertEqual((turns, ordinary), (2, 1))
        self.assertEqual(len(self.rows("SELECT id FROM conversation_turns")), 2)
        self.assertEqual(len(self.rows("SELECT id FROM memories")), 2)
        self.assertEqual(len(self.store.recall_self_core(OWNER)), 1)
        self.assertEqual(self.store.prune_expired(), (0, 0))
        # Same cleanup also runs automatically when reopening an existing DB.
        with closing(sqlite3.connect(self.path)) as db:
            db.execute(
                "UPDATE conversation_turns SET created_at=?",
                ((now - timedelta(days=9)).isoformat(),))
            db.commit()
        MemoryStore(self.path)
        self.assertEqual(self.rows("SELECT id FROM conversation_turns"), [])

    def test_24h_recovery_has_no_exchange_count_cap_and_is_scoped(self):
        now = datetime.now(timezone.utc)
        for n in range(140):
            self.assertTrue(self.store.append_conversation_turn(
                OWNER, "person", source_platform="microphone",
                message_id=f"owner-{n}", user_content=f"Question {n}",
                assistant_content=f"Réponse {n}"))
        for scope, owner, mid in (
            ("discord:99", OWNER, "other-channel"),
            ("person", self.other, "other-person"),
        ):
            self.store.append_conversation_turn(
                owner, scope, source_platform="discord",
                message_id=mid, user_content="Secret autre profil",
                assistant_content="Réponse isolée")
        self.store.append_conversation_turn(
            OWNER, "person", source_platform="mobile", message_id="old-25h",
            user_content="Dialogue vieux de 25 heures",
            assistant_content="Réponse ancienne")
        self.store.append_conversation_turn(
            OWNER, "person", source_platform="mobile", message_id="old-8d",
            user_content="Dialogue vieux de huit jours",
            assistant_content="Réponse périmée")
        with closing(sqlite3.connect(self.path)) as db:
            db.execute(
                "UPDATE conversation_turns SET created_at=? WHERE source_message_id='old-25h'",
                ((now - timedelta(hours=25)).isoformat(),))
            db.execute(
                "UPDATE conversation_turns SET created_at=? WHERE source_message_id='old-8d'",
                ((now - timedelta(days=8)).isoformat(),))
            db.commit()
        recent = self.store.recent_conversation_turns(OWNER, "person")
        self.assertEqual(len(recent), 280)
        self.assertEqual(recent[0]["content"], "Question 0")
        self.assertEqual(recent[-1]["content"], "Réponse 139")
        self.assertFalse(any("Secret" in v["content"] for v in recent))
        self.assertEqual(len(self.rows("SELECT id FROM conversation_turns")), 144)
        # The 25-hour-old message is still stored until the seven-day purge.
        self.assertEqual(self.store.prune_expired()[0], 1)
        self.assertEqual(len(self.rows("SELECT id FROM conversation_turns")), 143)


class FullHistoryRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self.cleanup)
        self.store = MemoryStore(Path(self.temp.name) / "jade.sqlite3")
        self.store.enable(OWNER)

    async def cleanup(self):
        self.temp.cleanup()

    async def test_runtime_reinjects_all_24h_turns_to_model(self):
        for n in range(80):
            self.store.append_conversation_turn(
                OWNER, "person", source_platform="microphone",
                message_id=f"history-{n}", user_content=f"Question {n}",
                assistant_content=f"Réponse {n}")

        class Backend:
            def __init__(self):
                self.inputs = None

            async def complete(self, messages):
                self.inputs = messages
                return "Nouvelle réponse Jade"

        backend = Backend()
        delivered = []

        async def output(reply):
            delivered.append(reply)

        service = MemoryService(self.store, backend, curator_enabled=False)
        dialogue = Dialogue(backend, "Tu es Jade", max_messages=4)
        runtime = Runtime(dialogue, output, memory_service=service)
        await runtime.start()
        try:
            incoming = Incoming(
                "microphone", "Goldaj", "Jade, peux-tu me répondre ?",
                force_reply=True, message_id="new")
            result = asyncio.get_running_loop().create_future()
            await runtime.submit(incoming, result=result)
            await asyncio.wait_for(runtime.idle(), timeout=5)
            self.assertEqual(result.result(), "Nouvelle réponse Jade")
            self.assertIsNotNone(backend.inputs)
            self.assertEqual(len(backend.inputs), 162)  # system + 160 + user
            self.assertIn("Question 0", backend.inputs[1]["content"])
            self.assertIn("Réponse 79", backend.inputs[-2]["content"])
            self.assertEqual(len(dialogue.history[incoming.history_key]), 162)
        finally:
            await runtime.stop()
            await service.close()


if __name__ == "__main__":
    unittest.main()
