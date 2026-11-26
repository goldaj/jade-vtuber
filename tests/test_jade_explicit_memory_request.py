"""Owner ordinary L2 requests are mandatory; Core proposals are voluntary.

No OpenAI, real microphone, Discord connection or private user data.
"""
import asyncio
from contextlib import closing
import sqlite3
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.explicit_memory_intent import parse_explicit_memory_intent
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.orchestrator import Runtime


OWNER = ("microphone", "goldaj")


class ExplicitMemoryParserTests(unittest.TestCase):
    def test_spoken_and_written_phrases(self):
        samples = (
            ("Jade, retiens que nous avons discuté de ce projet.",
             "nous avons discuté de ce projet.", False),
            ("Jade, mémorise que ce rendez-vous est demain.",
             "ce rendez-vous est demain.", False),
            ("Jade, souviens-toi que nous avons fait une randonnée.",
             "nous avons fait une randonnée.", False),
            ("Jade, garde ce souvenir : nous avons fait une randonnée.",
             "nous avons fait une randonnée.", False),
            ("Jade, enregistre dans ta mémoire que nous avons parlé ensemble.",
             "nous avons parlé ensemble.", False),
            ("Jade, je veux que tu gardes ceci dans tes Core Memories : "
             "notre première conversation sur Discord.",
             "notre première conversation sur Discord.", True),
            ("Jade, ajoute à tes Core Memories : Goldaj est ton créateur.",
             "Goldaj est ton créateur.", True),
            ("Jade, enregistre dans tes souvenirs autobiographiques : "
             "Tu as vécu cette discussion.",
             "Tu as vécu cette discussion.", True),
            ("Jade, enregistre un souvenir : nous avons trouvé une idée.",
             "nous avons trouvé une idée.", False),
            ("Jade, retiens bien que j'aime les projets d'IA.",
             "j'aime les projets d'IA.", False),
        )
        for phrase, summary, core in samples:
            with self.subTest(phrase=phrase):
                intent = parse_explicit_memory_intent(phrase)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.summary, summary)
                self.assertEqual(intent.requested_core, core)

    def test_no_implicit_writes_from_quotes_negation_or_unrelated_verbs(self):
        for phrase in (
            "Jade, tu as de belles Core Memories !",
            "On a discuté de tes Core Memories.",
            "Jade, ne mets pas cela dans tes Core Memories : coucou.",
            "Jade, ajoute pas à tes Core Memories : coucou.",
            "Jade, ajoute une carte dans le backlog.",
            "Jade, enregistre le son du microphone.",
            "« Jade, enregistre dans tes Core Memories : faux souvenir. »",
            "Jade, je te parle de tes Core Memories.",
            "!jade-memoire oublier",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse_explicit_memory_intent(phrase))


class ExplicitMemoryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "jade.sqlite3"
        self.store = MemoryStore(self.path)
        self.store.enable(OWNER)
        self.svc = MemoryService(self.store, backend=object(), curator_enabled=True)

    async def asyncTearDown(self):
        await self.svc.close()
        self.temp.cleanup()

    def request(self, text, *, platform="mobile", author="Goldaj",
                account="", channel="private", speaker_id=None, private=False):
        return Incoming(platform=platform, author=author, text=text,
                        account_id=account, channel=channel,
                        speaker_id=speaker_id, private_channel=private,
                        message_id="test-id")

    async def flush_explicit_writes(self, service=None):
        pending = tuple((service or self.svc)._explicit_writes)
        if pending:
            await asyncio.wait_for(asyncio.gather(*pending), timeout=3)

    async def jade_chooses_memory(self, source, summary):
        action = await self.svc.prepare_memory_action(source)
        self.assertIsNotNone(action)
        return await action(json.dumps({
            "kind": "ordinary", "summary": summary,
            "significance": "Décision volontaire de Jade dans le test.",
        }, ensure_ascii=False))

    async def test_owner_core_proposal_is_not_forced_to_l2_or_l3(self):
        # An owner's explicit Core suggestion is conversational input.
        # Unlike an ordinary L2 imperative, it cannot force any write.
        msg = self.request(
            "Jade, je veux que tu gardes ceci dans tes Core Memories : "
            "notre première conversation sur Discord.")
        self.assertIsNone(await self.svc.command(msg))
        await self.flush_explicit_writes()
        self.assertEqual(MemoryStore(self.path).list_for_account(OWNER), [])
        self.assertEqual(MemoryStore(self.path).recall_self_core(OWNER), [])
        # The optional Jade-selected memory tool is tested separately.
        self.assertFalse(hasattr(self.store, "put_owner_core"))

    async def test_natural_voice_from_micro_and_mobile_deduplicates(self):
        phrase = "Jade, retiens que nous avons finalisé le prototype."
        mobile = self.request(phrase, platform="mobile")
        mic = self.request(phrase, platform="microphone")
        self.assertIn("enregistré", (await self.svc.command(mobile)).text)
        self.assertIn("enregistré", (await self.svc.command(mic)).text)
        # Both calls merely acknowledge scheduling, not SQLite completion.
        await self.flush_explicit_writes()
        memories = self.store.list_for_account(OWNER)
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["kind"], "ordinary")
        self.assertEqual(self.store.recall_self_core(OWNER), [])
        self.assertEqual(len(self.store.recall(OWNER, "person")), 1)
    async def test_discord_users_keep_own_ordinary_memories_per_channel(self):
        one = self.request("Jade, ajoute à tes Core Memories : souvenir de Alice.",
                           platform="discord", account="123", author="Alice", channel="100")
        two = self.request("Jade, retiens que je préfère les plantes.",
                           platform="discord", account="456", author="Bob", channel="100")
        self.assertTrue(await self.svc.ensure_auto_enrolled(one))
        self.assertTrue(await self.svc.ensure_auto_enrolled(two))
        # Neither non-owner can compel an L2 or L3 write.
        self.assertIsNone(await self.svc.command(one))
        self.assertIsNone(await self.svc.command(two))
        self.assertEqual(self.store.list_for_account(("discord", "123")), [])
        self.assertEqual(self.store.list_for_account(("discord", "456")), [])
        # Jade may voluntarily accept each suggestion through her own tool.
        self.assertEqual((await self.jade_chooses_memory(
            one, "Alice a partagé un souvenir."))["status"], "enregistré")
        self.assertEqual((await self.jade_chooses_memory(
            two, "Bob préfère les plantes."))["status"], "enregistré")
        self.assertEqual(len(self.store.list_for_account(("discord", "123"))), 1)
        self.assertEqual(len(self.store.list_for_account(("discord", "456"))), 1)
        self.assertEqual(self.store.recall_self_core(OWNER), [])
        other_channel = self.request("Jade, bonjour", platform="discord",
                                     account="123", author="Alice", channel="999")
        # Context hints rank by the current turn, so they need not contain
        # all globally readable memories. The explicit search tool can.
        reader = await self.svc.prepare_memory_action(other_channel)
        query = json.dumps({"query": "Alice", "level": "2", "kind": "ordinary",
                            "cursor": 0, "limit": 10})
        visible = await reader.search(query)
        self.assertEqual(visible["status"], "ok")
        self.assertTrue(any("Alice" in item["summary"] for item in visible["items"]))
        self.assertIn("Bob préfère les plantes", await self.svc.context_for(two))
        self.assertEqual(len(self.store.recall(("discord", "123"), "discord:100")), 1)
        self.assertEqual(len(self.store.recall(("discord", "456"), "discord:100")), 1)
    async def test_voice_and_text_share_verified_discord_scope(self):
        text = self.request("Jade, retiens que ce canal est notre atelier.",
                            platform="discord", account="123", channel="789")
        voice = self.request("Jade, retiens que ce canal est notre atelier.",
                             platform="discord_voice", speaker_id=123, channel="789")
        self.assertTrue(await self.svc.ensure_auto_enrolled(text))
        self.assertIsNone(await self.svc.command(voice))
        self.assertIsNone(await self.svc.command(text))
        self.assertEqual((await self.jade_chooses_memory(
            voice, "Ce canal est notre atelier."))["status"], "enregistré")
        self.assertEqual((await self.jade_chooses_memory(
            text, "Ce canal est notre atelier."))["status"], "déjà présent")
        self.assertEqual(len(self.store.list_for_account(("discord", "123"))), 1)
    async def test_dm_auto_enrolled_but_twitch_remains_manual_opt_in(self):
        dm = self.request("Jade, mémorise que je viens de me connecter.",
                          platform="discord", account="123", channel="dm", private=True)
        twitch = self.request("Jade, retiens que je suis en ligne.",
                              platform="twitch", account="456", channel="stream")
        self.assertTrue(await self.svc.ensure_auto_enrolled(dm))
        self.assertFalse(await self.svc.ensure_auto_enrolled(twitch))
        self.assertIsNone(await self.svc.command(dm))
        self.assertEqual((await self.jade_chooses_memory(
            dm, "Cet utilisateur vient de se connecter."))["status"], "enregistré")
        self.assertIsNone(await self.svc.command(twitch))
        self.assertFalse((await self.svc.prepare_memory_action(twitch)).write_enabled)
        self.assertEqual(len(self.store.list_for_account(("discord", "123"))), 1)
        self.assertEqual(self.store.list_for_account(("twitch", "456")), [])
        self.store.enable(("twitch", "456"))
        # Even after opt-in Twitch remains a suggestion, not a forced command.
        self.assertIsNone(await self.svc.command(twitch))
        self.assertEqual((await self.jade_chooses_memory(
            twitch, "Cet utilisateur est en ligne."))["status"], "enregistré")
    async def test_profile_changes_revoke_pending_write(self):
        key = ("discord", "123")
        old_id = self.store.enable(key)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("DELETE FROM persons WHERE id=?", (old_id,))
            db.commit()
        self.store.enable(key)
        self.assertNotEqual(self.store.account(key), old_id)
        result = self.store.put_requested_ordinary(
            key, scope="discord:10", summary="Ancienne demande.",
            expected_person_id=old_id)
        self.assertEqual(result, "inactive")
        self.assertEqual(self.store.list_for_account(key), [])

    async def test_sensitive_long_empty_and_failed_sql_never_acknowledged(self):
        phrases = (
            "Jade, mémorise que",
            "Jade, retiens que " + "x" * 401,
            "Jade, garde en mémoire que mon mot de passe est secret.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase[:50]):
                result = await self.svc.command(self.request(phrase))
                self.assertNotIn("C'est enregistré", result.text)
        self.assertEqual(self.store.list_for_account(OWNER), [])
        with patch.object(self.store, "put_requested_ordinary",
                          side_effect=OSError("simulated path error")):
            result = await self.svc.command(self.request(
                "Jade, retiens que notre projet est en cours."))
            # Product contract: Jade acknowledges queue admission, not commit.
            self.assertIn("enregistré", result.text)
            await self.flush_explicit_writes()
        self.assertEqual(self.store.list_for_account(OWNER), [])
        self.assertEqual(self.store.recall_self_core(OWNER), [])
    async def test_targeted_deletion_keeps_owner_memory_isolated(self):
        outsider = ("discord", "123")
        self.store.enable(outsider)
        request = self.request("Jade, retiens que ma couleur est verte.",
                               platform="discord", author="Goldaj", account="123")
        # Display-name spoofing does not grant owner permission.
        self.assertIsNone(await self.svc.command(request))
        self.assertEqual((await self.jade_chooses_memory(
            request, "Cette personne aime le vert."))["status"], "enregistré")
        self.assertEqual(self.store.recall(OWNER, "person"), [])
        memory_id = self.store.list_for_account(outsider)[0]["id"]
        self.assertTrue(self.store.delete_memory(outsider, memory_id))
        self.assertEqual(self.store.list_for_account(outsider), [])
        self.assertEqual(self.store.recall_self_core(OWNER), [])
    async def test_orchestrator_routes_core_proposal_to_model_without_forced_write(self):
        class Backend:
            calls = 0

            async def complete(self, messages):
                self.calls += 1
                return "Je décide librement de ne pas le retenir."

        backend = Backend()
        delivered = []

        async def receive(reply):
            delivered.append(reply)

        service = MemoryService(self.store, backend, curator_enabled=False)
        # This test exercises Core-proposal routing only, not the separate
        # asynchronous curator (covered by its own tests).
        runner = Runtime(Dialogue(backend, "Tu es Jade"), receive, memory_service=service)
        await runner.start()
        try:
            msg = self.request("Jade, ajoute à tes Core Memories : "
                               "ce moment passé avec Goldaj.")
            result = asyncio.get_running_loop().create_future()
            await runner.submit(msg, result=result)
            await asyncio.wait_for(runner.idle(), 3)
            self.assertIn("librement", result.result())
            self.assertEqual(backend.calls, 1)
            self.assertEqual(len(delivered), 1)
            await self.flush_explicit_writes(service)
            self.assertEqual(self.store.list_for_account(OWNER), [])
            self.assertEqual(self.store.recall_self_core(OWNER), [])
            self.assertFalse(service.tasks)
        finally:
            await runner.stop()
            await service.close()

    async def test_jade_can_still_choose_core_autonomously_on_normal_dialogue(self):
        class AutonomousCurator:
            async def complete(self, messages):
                return json.dumps({
                    "kind": "core_self",
                    "summary": "Jade et Goldaj ont achevé leur premier prototype.",
                    "significance": "Étape importante vécue par Jade.",
                    "evidence": "Nous avons achevé notre premier prototype ensemble.",
                })

        source = self.request("Nous avons achevé notre premier prototype ensemble.",
                              platform="microphone")
        service = MemoryService(self.store, AutonomousCurator(), curator_enabled=True)
        try:
            self.assertTrue(service.schedule(source, Reply(source, "Je suis heureuse de notre avancée.")))
            await asyncio.wait_for(asyncio.gather(*list(service.tasks)), 3)
            found = self.store.recall_self_core(OWNER)
            self.assertEqual(len(found), 1)
            self.assertIn("premier prototype", found[0]["summary"])
        finally:
            await service.close()


if __name__ == "__main__":
    unittest.main()
