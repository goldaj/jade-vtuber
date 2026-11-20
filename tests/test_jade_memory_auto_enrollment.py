"""Regressions for default persistence and command-free Discord enrollment."""
import asyncio
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

    def test_erasure_optout_survives_reopening_db(self):
        account = ("discord", "123")
        self.assertTrue(self.store.auto_enable(account))
        self.assertTrue(self.store.put(
            account, kind="ordinary", scope="discord:789", summary="Fait de test"))
        self.assertTrue(self.store.forget_own_identity(account))
        self.store.block_auto_enrollment(account)
        reopened = MemoryStore(self.path)
        self.assertFalse(reopened.auto_enable(account))
        self.assertIsNone(reopened.account(account))
        self.assertEqual(reopened.list_for_account(account), [])
        reopened.enable(account)
        self.assertTrue(reopened.auto_enable(account))
        self.assertIsNotNone(reopened.account(account))

    def test_optout_blocks_first_enrollment_too(self):
        account = ("discord", "123")
        self.store.block_auto_enrollment(account)
        self.assertFalse(self.store.auto_enable(account))
        self.store.enable(account)
        self.assertTrue(self.store.auto_enable(account))

    def test_legacy_v3_sqlite_is_extended_without_reset(self):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA user_version=3")
        reopened = MemoryStore(self.path)
        self.assertTrue(reopened.auto_enable(("discord", "999")))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 3)

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

    async def test_server_discord_persists_and_forget_remains_effective(self):
        incoming = self.incoming()
        self.assertTrue(await self.service.ensure_auto_enrolled(incoming))
        self.assertTrue(await self.service.remember_turn(incoming, Reply(incoming, "Noté.")))
        self.assertEqual(len(await self.service.history_for(incoming)), 2)
        forgotten = self.incoming(text="!jade-memoire oublier")
        result = await self.service.command(forgotten)
        self.assertIn("désactivée", result.text)
        self.assertFalse(await self.service.ensure_auto_enrolled(incoming))
        self.assertIsNone(self.store.account(("discord", "123")))
        activated = await self.service.command(self.incoming(text="!jade-memoire activer"))
        self.assertIn("activée", activated.text)
        self.assertTrue(await self.service.ensure_auto_enrolled(incoming))

    async def test_private_discord_twitch_unknown_not_auto_enrolled(self):
        self.assertFalse(await self.service.ensure_auto_enrolled(self.incoming(private=True)))
        self.assertFalse(await self.service.ensure_auto_enrolled(
            self.incoming(platform="twitch")))
        self.assertFalse(await self.service.ensure_auto_enrolled(
            self.incoming(account="")))
        self.assertIsNone(self.store.account(("discord", "123")))

    async def test_discord_voice_verified_id_shares_text_profile(self):
        text = self.incoming()
        voice = self.incoming(platform="discord_voice", speaker_id=123)
        self.assertTrue(await self.service.ensure_auto_enrolled(text))
        self.assertTrue(await self.service.ensure_auto_enrolled(voice))
        self.assertEqual(self.store.account(("discord", "123")),
                         self.store.account(("discord", str(voice.speaker_id))))


if __name__ == "__main__":
    unittest.main()
