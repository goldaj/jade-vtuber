"""Regressions for default persistence and command-free Discord enrollment."""
import asyncio
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.jade_runtime.config import Settings
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.messages import Incoming, Reply


class MemoryDefaultTests(unittest.TestCase):
    def test_memory_defaults_are_live_ready_without_creating_database(self):
        settings = Settings()
        self.assertTrue(settings.memory_enabled)
        self.assertTrue(settings.memory_curator_enabled)
        self.assertTrue(Path(settings.memory_db_path).is_absolute())
        self.assertTrue(settings.memory_db_path.endswith(".sqlite3"))


class AutoEnrollmentStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "jade.sqlite3"
        self.store = MemoryStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_discord_enrolls_without_command_but_twitch_does_not(self):
        self.assertTrue(self.store.auto_enable(("discord", "123")))
        self.assertTrue(self.store.account(("discord", "123")))
        self.assertFalse(self.store.auto_enable(("twitch", "456")))
        self.assertIsNone(self.store.account(("twitch", "456")))
        self.assertTrue(self.store.auto_enable(("discord", "123")))
        self.assertEqual(len(self.store.list_for_account(("discord", "123"))), 0)

    def test_legacy_v3_sqlite_is_extended_without_reset(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA user_version=3")
            db.commit()
        reopened = MemoryStore(self.path)
        self.assertTrue(reopened.auto_enable(("discord", "999")))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 5)

    def test_v4_legacy_block_table_migrates_without_losing_memories(self):
        account = ("discord", "123")
        self.store.enable(account)
        self.store.put(account, kind="ordinary", scope="discord:789",
                       summary="Souvenir conservé pendant migration")
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TABLE memory_auto_enrollment_blocks "
                       "(platform TEXT NOT NULL, account_id TEXT NOT NULL, "
                       "created_at TEXT NOT NULL, PRIMARY KEY(platform, account_id))")
            db.execute("INSERT INTO memory_auto_enrollment_blocks VALUES "
                       "('discord', '456', '2026-11-20T00:00:00+00:00')")
            db.execute("PRAGMA user_version=4")
            db.commit()
        reopened = MemoryStore(self.path)
        self.assertTrue(reopened.auto_enable(("discord", "456")))
        self.assertEqual(len(reopened.list_for_account(account)), 1)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 5)
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='memory_auto_enrollment_blocks'").fetchone())

    def test_discord_accounts_remain_separate(self):
        one = ("discord", "123")
        two = ("discord", "456")
        self.assertTrue(self.store.auto_enable(one))
        self.assertTrue(self.store.auto_enable(two))
        self.assertTrue(self.store.put(one, kind="ordinary", scope="discord:789",
                                       summary="Un secret personnel"))
        self.assertEqual(self.store.recall(two, "discord:789"), [])
        self.assertEqual(len(self.store.recall(one, "discord:789")), 1)


class AutoEnrollmentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "jade.sqlite3")
        self.service = MemoryService(self.store, object())

    async def asyncTearDown(self):
        await self.service.close()
        self.temp.cleanup()

    def incoming(self, *, platform="discord", private=False, account="123",
                 text="Un souvenir utile", speaker_id=None):
        return Incoming(platform=platform, author="Personne", text=text,
                        account_id=account, channel="789",
                        private_channel=private, speaker_id=speaker_id)

    async def test_discord_history_persists_and_old_forget_command_is_unsupported(self):
        incoming = self.incoming()
        self.assertTrue(await self.service.ensure_auto_enrolled(incoming))
        self.assertTrue(await self.service.remember_turn(incoming, Reply(incoming, "Noté.")))
        self.assertEqual(len(await self.service.history_for(incoming)), 2)
        self.assertIsNone(await self.service.command(
            self.incoming(text="!jade-memoire oublier")))
        self.assertTrue(await self.service.ensure_auto_enrolled(incoming))
        self.assertEqual(len(await self.service.history_for(incoming)), 2)

    async def test_private_discord_auto_enrolled_but_twitch_unknown_not(self):
        self.assertTrue(await self.service.ensure_auto_enrolled(self.incoming(private=True)))
        self.assertIsNotNone(self.store.account(("discord", "123")))
        self.assertFalse(await self.service.ensure_auto_enrolled(
            self.incoming(platform="twitch")))
        self.assertFalse(await self.service.ensure_auto_enrolled(
            self.incoming(account="")))
        self.assertIsNone(self.store.account(("twitch", "123")))

    async def test_private_discord_can_confirm_mobile_link_without_manual_activation(self):
        owner = ("microphone", "goldaj")
        self.store.enable(owner)
        challenge = self.store.begin_link(owner, target=("discord", "123"))
        confirmation = self.incoming(
            private=True, text="!jade-memoire confirmer " + challenge)
        self.assertTrue(await self.service.ensure_auto_enrolled(confirmation))
        result = await self.service.command(confirmation)
        self.assertIn("Comptes associés", result.text)
        self.assertEqual(self.store.account(owner), self.store.account(("discord", "123")))
        self.assertFalse(self.store.complete_link(("discord", "123"), challenge))

    async def test_dm_and_server_history_stay_separate_after_auto_enrollment(self):
        private = Incoming("discord", "Personne", "Secret du MP", channel="111",
                           account_id="123", private_channel=True)
        server = self.incoming(text="Message du serveur")
        self.assertTrue(await self.service.ensure_auto_enrolled(private))
        self.assertTrue(await self.service.remember_turn(
            private, Reply(private, "Réponse privée.")))
        self.assertEqual(len(await self.service.history_for(private)), 2)
        self.assertEqual(await self.service.history_for(server), [])

    async def test_discord_voice_verified_id_shares_text_profile(self):
        text = self.incoming()
        voice = self.incoming(platform="discord_voice", speaker_id=123)
        self.assertTrue(await self.service.ensure_auto_enrolled(text))
        self.assertTrue(await self.service.ensure_auto_enrolled(voice))
        self.assertEqual(self.store.account(("discord", "123")),
                         self.store.account(("discord", str(voice.speaker_id))))


if __name__ == "__main__":
    unittest.main()
