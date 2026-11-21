"""Cross-platform memory regressions without real connectors or paid calls."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming

OWNER = ("microphone", "goldaj")
DISCORD = ("discord", "101")
TWITCH = ("twitch", "202")


class CrossChannelMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jade.sqlite3"
        self.store = MemoryStore(self.path)
        self.service = MemoryService(self.store, object(), curator_enabled=False)
        for account in (OWNER, DISCORD, TWITCH):
            self.store.enable(account)

    async def asyncTearDown(self):
        await self.service.close()

    def mobile(self):
        return Incoming("mobile", "Goldaj", "Tu te souviens ?", channel="private")

    def dm(self):
        return Incoming("discord", "Goldaj", "Tu te souviens ?", channel="dm101",
                        account_id="101", private_channel=True)

    def server(self):
        return Incoming("discord", "Goldaj", "Tu te souviens ?", channel="server1",
                        account_id="101")

    def link(self, target=DISCORD):
        code = self.store.begin_link(OWNER, target=target)
        self.assertTrue(self.store.complete_link(target, code))

    async def test_both_directions_only_after_link(self):
        self.store.put(OWNER, kind="ordinary", scope="person",
                       summary="Son roman s'appelle Les Ressuscités.")
        self.store.put(DISCORD, kind="core_relationship", scope="discord:server1",
                       summary="Il a terminé le chapitre sept.")
        self.assertNotIn("chapitre sept", await self.service.context_for(self.mobile()))
        self.assertNotIn("Les Ressuscités", await self.service.context_for(self.dm()))
        self.link()
        self.assertIn("chapitre sept", await self.service.context_for(self.mobile()))
        self.assertIn("autre canal: discord", await self.service.context_for(self.mobile()))
        self.assertIn("Les Ressuscités", await self.service.context_for(self.dm()))

    async def test_public_cannot_read_private_or_other_server_memories(self):
        self.store.put(OWNER, kind="ordinary", scope="person",
                       summary="Confidentiel : projet non public.")
        self.store.put(DISCORD, kind="ordinary", scope="discord:server2",
                       summary="Une conversation dans un autre serveur.")
        self.store.put(DISCORD, kind="ordinary", scope="discord:server1",
                       summary="Ce salon a son information locale.")
        self.link()
        public = await self.service.context_for(self.server())
        self.assertIn("information locale", public)
        self.assertNotIn("Confidentiel", public)
        self.assertNotIn("autre serveur", public)
        self.assertIn("Confidentiel", await self.service.context_for(self.dm()))

    async def test_twitch_public_memory_recalled_on_mobile_only(self):
        self.store.put(TWITCH, kind="ordinary", scope="twitch:live",
                       summary="Souvenir d'une discussion Twitch.")
        self.link(TWITCH)
        self.assertIn("discussion Twitch", await self.service.context_for(self.mobile()))
        public = Incoming("twitch", "Goldaj", "Tu sais ?", channel="live",
                          account_id="202")
        self.assertIn("discussion Twitch", await self.service.context_for(public))
        self.assertNotIn("discussion Twitch", await self.service.context_for(self.server()))

    async def test_unlinked_person_and_unlink_are_isolated(self):
        self.store.put(OWNER, kind="ordinary", scope="person",
                       summary="Information spécifique au créateur.")
        self.store.enable(("discord", "303"))
        self.link()
        stranger = Incoming("discord", "Goldaj", "Tu sais ?", channel="dm303",
                            account_id="303", private_channel=True)
        self.assertNotIn("spécifique", await self.service.context_for(stranger))
        self.assertIn("spécifique", await self.service.context_for(self.dm()))
        self.assertTrue(self.store.unlink(DISCORD))
        self.assertNotIn("spécifique", await self.service.context_for(self.dm()))
        self.assertIn("spécifique", await self.service.context_for(self.mobile()))

    async def test_expired_memories_and_erased_account_are_excluded(self):
        self.store.put(DISCORD, kind="ordinary", scope="discord:server1",
                       summary="Souvenir ordinaire expiré.")
        self.store.put(DISCORD, kind="core_relationship", scope="discord:server1",
                       summary="Souvenir fondateur non expiré.")
        self.link()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE memories SET expires_at='2000-01-01T00:00:00+00:00' "
                       "WHERE kind='ordinary' AND source_platform='discord'")
            db.commit()
        context = await self.service.context_for(self.mobile())
        self.assertNotIn("ordinaire expiré", context)
        self.assertIn("fondateur non expiré", context)
        self.assertTrue(self.store.forget_own_identity(DISCORD))
        self.store.block_auto_enrollment(DISCORD)
        self.assertNotIn("fondateur non expiré", await self.service.context_for(self.mobile()))
        self.assertFalse(self.store.auto_enable(DISCORD))

    async def test_raw_turns_and_jade_autobiography_do_not_cross(self):
        self.store.append_conversation_turn(
            DISCORD, "discord:server1", source_platform="discord",
            message_id="d-1", user_content="Contenu du serveur",
            assistant_content="Réponse du serveur")
        self.store.put_self_core(OWNER, summary="Jade a vécu un épisode personnel.")
        self.link()
        self.assertEqual(await self.service.history_for(self.mobile()), [])
        self.assertEqual(await self.service.history_for(self.dm()), [])
        self.assertEqual(len(self.store.recent_conversation_turns(
            DISCORD, "discord:server1")), 2)
        self.assertIn("épisode personnel", await self.service.context_for(self.mobile()))
        self.assertNotIn("épisode personnel", await self.service.context_for(self.dm()))


if __name__ == "__main__":
    unittest.main()
