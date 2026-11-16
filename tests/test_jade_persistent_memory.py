"""Offline SQLite memory tests. No paid API calls or real user data."""
import asyncio
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.jade_runtime.discord_text import parse_discord_message
from src.jade_runtime.twitch_irc import parse_message
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore, identity_of
from src.jade_runtime.memory_transfer import export_memory, import_memory
from src.jade_runtime.orchestrator import Runtime


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jade.sqlite3"
        self.store = MemoryStore(self.path)
        self.alice = ("discord", "101")
        self.bob = ("discord", "102")

    def test_trusted_ids_not_names_and_local_owner(self):
        self.assertEqual(identity_of(Incoming("discord", "Alice", "Salut",
                                               account_id="101")), self.alice)
        self.assertEqual(identity_of(Incoming("discord_voice", "Alice", "Salut",
                                               speaker_id=101)), self.alice)
        self.assertIsNone(identity_of(Incoming("discord", "Alice", "Salut")))
        self.assertEqual(identity_of(Incoming("microphone", "Goldaj", "Salut")),
                         ("microphone", "goldaj"))
        self.assertEqual(identity_of(Incoming("mobile", "Goldaj", "Salut")),
                         ("microphone", "goldaj"))
        self.assertIsNone(identity_of(Incoming("discord", "Goldaj", "Salut")))
        self.assertIsNone(identity_of(Incoming("twitch", "Goldaj", "Je suis Goldaj")))

    def test_connector_parsers_expose_account_ids_without_spoofing_names(self):
        discord = SimpleNamespace(
            id=42, content="Bonjour Jade",
            author=SimpleNamespace(id=101, display_name="Alice"),
            channel=SimpleNamespace(id=10),
        )
        from_discord = parse_discord_message(discord)
        self.assertEqual(from_discord.account_id, "101")
        self.assertEqual(identity_of(from_discord), self.alice)
        from_twitch = parse_message(
            "@id=msg-3;user-id=6001 :alias!alias@alias.tmi.twitch.tv PRIVMSG #live :Bonjour Jade"
        )
        self.assertEqual(from_twitch.account_id, "6001")
        self.assertEqual(identity_of(from_twitch), ("twitch", "6001"))
        unknown = parse_message(
            ":alias!alias@alias.tmi.twitch.tv PRIVMSG #live :Bonjour Jade"
        )
        self.assertIsNone(identity_of(unknown))

    def test_opt_in_core_never_expires_and_isolated_per_channel(self):
        self.assertIsNone(self.store.account(self.alice))
        self.assertFalse(self.store.put(
            self.alice, kind="core_relationship", scope="discord:10",
            summary="Nous avons achevé un jeu."))
        self.store.enable(self.alice)
        self.store.enable(self.bob)
        self.assertTrue(self.store.put(self.alice, kind="core_relationship",
                                       scope="discord:10", summary="Nous avons achevé un jeu.",
                                       significance="Moment fondateur"))
        self.assertTrue(self.store.put(self.alice, kind="ordinary",
                                       scope="discord:10", summary="Un devoir est en cours."))
        self.assertEqual(len(self.store.recall(self.alice, "discord:10")), 2)
        self.assertEqual(self.store.recall(self.alice, "discord:11"), [])
        self.assertEqual(self.store.recall(self.bob, "discord:10"), [])
        self.assertFalse(self.store.put(self.alice, kind="core_relationship",
                                        scope="discord:10", summary="Nous avons achevé un jeu."))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertIsNone(db.execute(
                "SELECT expires_at FROM memories WHERE kind='core_relationship'").fetchone()[0])
            db.execute("UPDATE memories SET expires_at='2000-01-01' WHERE kind='ordinary'")
            db.commit()
        self.assertEqual(self.store.prune_ordinary(), 1)
        self.assertEqual(len(self.store.recall(self.alice, "discord:10")), 1)
        self.assertEqual(len(MemoryStore(self.path).recall(self.alice, "discord:10")), 1)

    def test_owner_memory_is_shared_between_local_mic_and_mobile(self):
        local = identity_of(Incoming("microphone", "Goldaj", "Salut"))
        mobile = identity_of(Incoming("mobile", "Goldaj", "Salut"))
        self.assertEqual(local, mobile)
        self.store.enable(local)
        self.assertTrue(self.store.put(
            local, kind="core_relationship", scope="person",
            summary="Goldaj a terminé son projet avec Jade."))
        self.assertEqual(len(self.store.recall(mobile, "person")), 1)
        self.assertEqual(len(self.store.list_for_account(mobile)), 1)

    def test_target_bound_link_preserves_complete_history_on_link_and_unlink(self):
        twitch = ("twitch", "6001")
        other = ("twitch", "6002")
        for key in (self.alice, twitch, other):
            self.store.enable(key)
        self.assertTrue(self.store.append_conversation_turn(
            self.alice, "discord:10", source_platform="discord",
            message_id="discord-1", user_content="Salut Discord",
            assistant_content="Salut Alice"))
        self.assertTrue(self.store.append_conversation_turn(
            twitch, "twitch:live", source_platform="twitch",
            message_id="twitch-1", user_content="Salut Twitch",
            assistant_content="Salut Twitch"))
        code = self.store.begin_link(self.alice, target=twitch)
        self.assertTrue(code.startswith("v1.twitch.6001."))
        self.assertFalse(self.store.complete_link(other, code))
        self.assertTrue(self.store.complete_link(twitch, code))
        self.assertFalse(self.store.complete_link(twitch, code))
        # Both scopes survive deleting the previous person (ON DELETE CASCADE).
        self.assertEqual(len(self.store.recent_conversation_turns(
            self.alice, "twitch:live")), 2)
        self.assertEqual(len(self.store.recent_conversation_turns(
            twitch, "discord:10")), 2)
        self.assertTrue(self.store.unlink(twitch))
        self.assertEqual(len(self.store.recent_conversation_turns(
            twitch, "twitch:live")), 2)
        self.assertEqual(self.store.recent_conversation_turns(
            self.alice, "twitch:live"), [])
        self.assertEqual(len(self.store.recent_conversation_turns(
            self.alice, "discord:10")), 2)

    def test_unlink_owner_keeps_mobile_and_microphone_history_private(self):
        owner, twitch = ("microphone", "goldaj"), ("twitch", "6001")
        self.store.enable(owner)
        self.store.enable(twitch)
        for source in ("mobile", "microphone"):
            self.assertTrue(self.store.append_conversation_turn(
                owner, "person", source_platform=source,
                message_id=source + "-01", user_content="Journal " + source,
                assistant_content="Reçu"))
        code = self.store.begin_link(owner, target=twitch)
        self.assertTrue(self.store.complete_link(twitch, code))
        self.assertEqual(len(self.store.recent_conversation_turns(twitch, "person")), 4)
        self.assertTrue(self.store.unlink(owner))
        self.assertEqual(len(self.store.recent_conversation_turns(owner, "person")), 4)
        self.assertEqual(self.store.recent_conversation_turns(twitch, "person"), [])

    def test_unlink_discord_preserves_voice_and_text_conversations(self):
        twitch = ("twitch", "6001")
        self.store.enable(self.alice)
        self.store.enable(twitch)
        for platform in ("discord", "discord_voice"):
            self.assertTrue(self.store.append_conversation_turn(
                self.alice, "discord:45", source_platform=platform,
                message_id=platform + "-01", user_content="Hello " + platform,
                assistant_content="Bonjour"))
        code = self.store.begin_link(twitch, target=self.alice)
        self.assertTrue(self.store.complete_link(self.alice, code))
        self.assertEqual(len(self.store.recent_conversation_turns(
            twitch, "discord:45")), 4)
        self.assertTrue(self.store.unlink(self.alice))
        self.assertEqual(len(self.store.recent_conversation_turns(
            self.alice, "discord:45")), 4)
        self.assertEqual(self.store.recent_conversation_turns(twitch, "discord:45"), [])

    def test_new_link_challenge_invalidates_previous_code(self):
        twitch = ("twitch", "6001")
        self.store.enable(self.alice)
        self.store.enable(twitch)
        first = self.store.begin_link(self.alice, target=twitch)
        second = self.store.begin_link(self.alice, target=twitch)
        self.assertNotEqual(first, second)
        self.assertFalse(self.store.complete_link(twitch, first))
        self.assertTrue(self.store.complete_link(twitch, second))

    def test_public_forget_erases_only_target_account_in_linked_profile(self):
        owner, twitch = ("microphone", "goldaj"), ("twitch", "6001")
        self.store.enable(owner)
        self.store.enable(twitch)
        self.store.put(owner, kind="core_relationship", scope="person",
                       summary="Private Goldaj owner note")
        self.store.put(twitch, kind="core_relationship", scope="twitch:live",
                       summary="Twitch participant note")
        self.store.put_self_core(owner, summary="Jade has remembered a family moment")
        self.assertTrue(self.store.append_conversation_turn(
            owner, "person", source_platform="mobile", message_id="m-1",
            user_content="Private mobile note", assistant_content="Private response"))
        self.assertTrue(self.store.append_conversation_turn(
            twitch, "twitch:live", source_platform="twitch", message_id="t-1",
            user_content="Public Twitch note", assistant_content="Public response"))
        code = self.store.begin_link(owner, target=twitch)
        self.assertTrue(self.store.complete_link(twitch, code))
        self.assertTrue(self.store.forget_own_identity(twitch))
        self.assertIsNone(self.store.account(twitch))
        self.assertIsNotNone(self.store.account(owner))
        self.assertEqual(len(self.store.list_for_account(owner)), 1)
        self.assertEqual(len(self.store.recall_self_core(owner)), 1)
        self.assertEqual(len(self.store.recent_conversation_turns(owner, "person")), 2)
        self.assertEqual(self.store.recent_conversation_turns(owner, "twitch:live"), [])

    def test_public_forget_owner_preserves_linked_external_account(self):
        owner, twitch = ("microphone", "goldaj"), ("twitch", "6001")
        self.store.enable(owner)
        self.store.enable(twitch)
        self.store.put(owner, kind="core_relationship", scope="person",
                       summary="Private Goldaj owner note")
        self.store.put(twitch, kind="core_relationship", scope="twitch:live",
                       summary="Twitch participant note")
        self.store.put_self_core(owner, summary="Jade has remembered a family moment")
        code = self.store.begin_link(owner, target=twitch)
        self.assertTrue(self.store.complete_link(twitch, code))
        self.assertTrue(self.store.forget_own_identity(owner))
        self.assertIsNone(self.store.account(owner))
        self.assertEqual(len(self.store.list_for_account(twitch)), 1)
        self.assertEqual(len(self.store.recall_self_core(owner)), 0)

    def test_cross_platform_link_unlink_and_explicit_erasure(self):
        twitch = ("twitch", "6001")
        self.store.enable(self.alice)
        self.store.enable(twitch)
        self.store.put(self.alice, kind="core_relationship",
                       scope="discord:10", summary="Premier succès Discord.")
        self.store.put(twitch, kind="core_relationship",
                       scope="twitch:live", summary="Premier succès Twitch.")
        code = self.store.begin_link(self.alice)
        self.assertFalse(self.store.complete_link(self.alice, code))
        self.assertTrue(self.store.complete_link(twitch, code))
        self.assertFalse(self.store.complete_link(twitch, code))
        self.assertEqual(self.store.account(twitch), self.store.account(self.alice))
        self.assertEqual(len(self.store.list_for_account(twitch)), 2)
        self.assertTrue(self.store.unlink(twitch))
        self.assertNotEqual(self.store.account(twitch), self.store.account(self.alice))
        self.assertEqual(len(self.store.list_for_account(twitch)), 1)
        self.assertEqual(len(self.store.list_for_account(self.alice)), 1)
        self.assertTrue(self.store.forget(self.alice))
        self.assertEqual(self.store.list_for_account(self.alice), [])
        self.assertEqual(len(self.store.list_for_account(twitch)), 1)
        self.assertTrue(self.store.forget(twitch))
        self.assertEqual(self.store.list_for_account(twitch), [])

    def test_owner_only_deletion_and_migration(self):
        self.store.enable(self.alice)
        self.store.enable(self.bob)
        self.store.put(self.alice, kind="core_self", scope="discord:10",
                       summary="Jade a terminé son premier récit avec Alice.")
        mid = self.store.list_for_account(self.alice)[0]["id"]
        self.assertFalse(self.store.delete_memory(self.bob, mid))
        snapshot = Path(self.tmp.name) / "jade-memory-backup.zip"
        export_memory(self.path, snapshot)
        restored = Path(self.tmp.name) / "restored.sqlite3"
        import_memory(snapshot, restored)
        self.assertEqual(len(MemoryStore(restored).list_for_account(self.alice)), 1)
        self.assertFalse(self.store.delete_memory(self.bob, mid))
        self.assertTrue(self.store.delete_memory(self.alice, mid))
        self.assertEqual(self.store.list_for_account(self.alice), [])
        with self.assertRaises(FileExistsError):
            import_memory(snapshot, restored)
        with self.assertRaises(FileExistsError):
            export_memory(self.path, snapshot)

    def test_tampered_export_is_rejected_and_existing_db_preserved(self):
        import zipfile
        source = Path(self.tmp.name) / "backup.zip"
        export_memory(self.path, source)
        bad = Path(self.tmp.name) / "bad.zip"
        with zipfile.ZipFile(source) as original:
            manifest = original.read("manifest.json")
            data = bytearray(original.read("jade-memory.sqlite3"))
        data[-1] ^= 1
        with zipfile.ZipFile(bad, "w") as rewritten:
            rewritten.writestr("jade-memory.sqlite3", data)
            rewritten.writestr("manifest.json", manifest)
        target = Path(self.tmp.name) / "reject.sqlite3"
        with self.assertRaises(ValueError):
            import_memory(bad, target)
        self.assertFalse(target.exists())


class MemoryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = MemoryStore(Path(self.tmp.name) / "jade.sqlite3")

    async def test_opt_in_and_runtime_recall_after_restart(self):
        key = ("discord", "101")
        model = AsyncMock()
        model.complete.return_value = "[INTENT:playful] Salut, Alice."
        svc = MemoryService(self.store, model)
        source = Incoming("discord", "Alice", "Jade, bonjour",
                          channel="99", message_id="a", force_reply=True,
                          account_id="101")
        self.assertEqual(await svc.context_for(source), "")
        self.assertIn("activée", (await svc.command(Incoming(
            "discord", "Alice", "!jade-memoire activer", account_id="101"))).text)
        self.store.put(key, kind="core_relationship", scope="discord:99",
                       summary="Alice et Jade ont achevé un roman.")
        delivered = []
        async def output(reply):
            delivered.append(reply)
        runtime = Runtime(Dialogue(model, "Jade"), output, memory_service=svc)
        await runtime.start()
        await runtime.submit(source)
        await asyncio.wait_for(runtime.idle(), 2)
        await runtime.stop()
        self.assertEqual(delivered[0].intent, "playful")
        self.assertEqual(delivered[0].text, "Salut, Alice.")
        self.assertIn("Alice et Jade ont achevé un roman.",
                      str(model.complete.await_args.args[0]))
        await svc.close()
        self.assertTrue(self.store.list_for_account(key))

    async def test_curator_selects_core_autonomously_then_forgets(self):
        key = ("microphone", "goldaj")
        self.store.enable(key)
        mock = AsyncMock()
        mock.complete.return_value = json.dumps({
            "kind": "core_self",
            "summary": "Jade et Goldaj ont achevé leur premier jeu.",
            "significance": "Un accomplissement partagé.",
            "evidence": "Nous avons terminé notre jeu ensemble.",
        })
        svc = MemoryService(self.store, mock, curator_enabled=True)
        source = Incoming("microphone", "Goldaj",
                          "Nous avons terminé notre jeu ensemble.",
                          channel="mic", force_reply=True)
        self.assertTrue(svc.schedule(source, Reply(source, "Merci, papa !")))
        await asyncio.wait_for(asyncio.gather(*list(svc.tasks)), 2)
        self.assertEqual(len(self.store.list_for_account(key)), 0)
        self.assertEqual(len(self.store.recall_self_core(key)), 1)
        self.assertEqual(self.store.recall_self_core(key)[0]["summary"],
                         "Jade et Goldaj ont achevé leur premier jeu.")
        await svc.close()
        self.assertTrue(self.store.forget(key))
        self.assertEqual(self.store.list_for_account(key), [])
        self.assertEqual(self.store.recall_self_core(key), [])

    async def test_unknown_account_and_curator_disabled_no_model_call(self):
        source = Incoming("twitch", "User", "Bonjour Jade", channel="live")
        backend = AsyncMock()
        svc = MemoryService(self.store, backend, curator_enabled=False)
        self.assertFalse(svc.schedule(source, Reply(source, "Salut")))
        self.assertEqual(await svc.context_for(source), "")
        self.assertIn("compte vérifié", (await svc.command(Incoming(
            "twitch", "User", "!jade-memoire activer"))).text)
        backend.complete.assert_not_awaited()
        await svc.close()


if __name__ == "__main__":
    unittest.main()
