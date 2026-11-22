"""Cross-platform global memory regression suite, no real connectors or paid calls."""
import json
from contextlib import closing
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


def request(query="", level="all", kind="all"):
    return json.dumps({
        "query": query, "level": level, "kind": kind,
        "cursor": 0, "limit": 15,
    })


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

    def mobile(self, text="Retrouve ce souvenir"):
        return Incoming("mobile", "Goldaj", text, channel="private")

    def discord(self, text="Retrouve ce souvenir", *, channel="server1"):
        return Incoming("discord", "Alice", text, channel=channel,
                        account_id=DISCORD[1])

    def twitch(self, text="Retrouve ce souvenir"):
        return Incoming("twitch", "Bob", text, channel="live",
                        account_id=TWITCH[1])

    async def browse(self, incoming, **filters):
        action = await self.service.prepare_memory_action(incoming)
        self.assertIsNotNone(action)
        return await action.search(request(**filters))

    async def test_unlinked_users_read_the_same_global_memory(self):
        self.store.put(OWNER, kind="ordinary", scope="person",
                       summary="Le roman s'appelle Les Ressuscités.")
        self.store.put(DISCORD, kind="core_relationship", scope="discord:server1",
                       summary="Il a terminé le chapitre sept.")
        for caller in (self.mobile(), self.discord(), self.twitch()):
            found = await self.browse(caller)
            self.assertEqual(len(found["items"]), 2)
            self.assertEqual({
                mem["source_account_id"] for mem in found["items"]
            }, {"goldaj", DISCORD[1]})
        # Linking accounts must not be a prerequisite for global read.
        self.assertNotEqual(self.store.account(OWNER), self.store.account(DISCORD))

    async def test_public_discord_recalls_other_servers_and_private_origins(self):
        self.store.put(OWNER, kind="ordinary", scope="person",
                       summary="Projet personnel du propriétaire.")
        self.store.put(DISCORD, kind="ordinary", scope="discord:server2",
                       summary="Une discussion dans un autre serveur.")
        self.store.put(TWITCH, kind="ordinary", scope="twitch:live",
                       summary="Un événement Twitch mémorable.")
        public = await self.browse(self.discord(), level="2")
        self.assertEqual(len(public["items"]), 3)
        self.assertEqual({x["scope"] for x in public["items"]}, {
            "person", "discord:server2", "twitch:live"})

    async def test_global_context_can_inject_public_memories(self):
        self.store.put(TWITCH, kind="ordinary", scope="twitch:live",
                       summary="Jade s'est souvenue d'un tournoi de curling Twitch.")
        # A relevant query in a public Discord channel can see this memory.
        text = await self.service.context_for(
            self.discord("Parle-moi du tournoi de curling Twitch"))
        self.assertIn("tournoi de curling Twitch", text)
        self.assertIn("interlocuteur=202", text)

    async def test_unlink_does_not_hide_saved_memories(self):
        self.store.put(OWNER, kind="ordinary", scope="person",
                       summary="Information spécifique au créateur.")
        token = self.store.begin_link(OWNER, target=DISCORD)
        self.assertTrue(self.store.complete_link(DISCORD, token))
        before = await self.browse(self.discord(), query="spécifique")
        self.assertEqual(len(before["items"]), 1)
        self.assertTrue(self.store.unlink(DISCORD))
        after = await self.browse(self.discord(), query="spécifique")
        self.assertEqual(len(after["items"]), 1)

    async def test_expired_and_deleted_memories_do_not_reappear(self):
        self.store.put(DISCORD, kind="ordinary", scope="discord:server1",
                       summary="Souvenir ordinaire expiré.")
        self.store.put(DISCORD, kind="core_relationship",
                       scope="discord:server1",
                       summary="Souvenir fondateur non expiré.")
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE memories SET expires_at='2000-01-01T00:00:00+00:00' "
                       "WHERE kind='ordinary'")
            db.commit()
        found = await self.browse(self.twitch())
        self.assertEqual(len(found["items"]), 1)
        memory_id = found["items"][0]["id"]
        self.assertTrue(self.store.delete_memory(DISCORD, memory_id))
        self.assertEqual((await self.browse(self.mobile()))["items"], [])

    async def test_raw_history_stays_session_local_but_is_globally_browsable(self):
        self.store.append_conversation_turn(
            DISCORD, "discord:server1", source_platform="discord",
            source_author_name="Alice", message_id="d-1",
            user_content="Alice: Contenu du serveur",
            assistant_content="Jade: Réponse du serveur")
        self.store.put_self_core(OWNER, summary="Jade a vécu un épisode personnel.")
        # Level-1 session reload remains restricted to the ongoing dialogue
        # to avoid merging separate conversations in the LLM's raw history.
        self.assertEqual(await self.service.history_for(self.mobile()), [])
        self.assertEqual(await self.service.history_for(self.discord(
            channel="server2")), [])
        for caller in (self.mobile(), self.twitch(), self.discord()):
            raw = await self.browse(caller, level="1")
            self.assertEqual(len(raw["items"]), 1)
            self.assertEqual(raw["items"][0]["source_author_name"], "Alice")
            core = await self.browse(caller, level="3", kind="core_self")
            self.assertEqual(len(core["items"]), 1)
            self.assertEqual(core["items"][0]["source_account_id"], "goldaj")


if __name__ == "__main__":
    unittest.main()
