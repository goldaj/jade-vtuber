"""DEV-011 (revised): natural requests write ordinary memory only.

No OpenAI, real microphone, Discord connection or private user data.
"""
import asyncio
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

    async def test_owner_core_request_is_always_ordinary_and_persistent(self):
        msg = self.request(
            "Jade, je veux que tu gardes ceci dans tes Core Memories : "
            "notre première conversation sur Discord.")
        result = await self.svc.command(msg)
        self.assertIn("mémoire ordinaire", result.text)
        self.assertIn("mon choix", result.text)
        self.assertNotIn("première conversation", result.text)
        memories = MemoryStore(self.path).list_for_account(OWNER)
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["kind"], "ordinary")
        self.assertEqual(memories[0]["scope"], "person")
        self.assertIsNotNone(memories[0]["expires_at"])
        self.assertEqual(MemoryStore(self.path).recall_self_core(OWNER), [])
        self.assertIn("première conversation", await self.svc.context_for(msg))
        self.assertFalse(self.svc.schedule(msg, Reply(msg, "Réponse.")))
        self.assertFalse(hasattr(self.store, "put_owner_core"))

    async def test_natural_voice_from_micro_and_mobile_deduplicates(self):
        phrase = "Jade, retiens que nous avons finalisé le prototype."
        mobile = self.request(phrase, platform="mobile")
        mic = self.request(phrase, platform="microphone")
        self.assertIn("enregistré", (await self.svc.command(mobile)).text)
        self.assertIn("déjà", (await self.svc.command(mic)).text)
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
        first = await self.svc.command(one)
        self.assertIn("mémoire ordinaire", first.text)
        self.assertIn("mon choix", first.text)
        self.assertIn("enregistré", (await self.svc.command(two)).text)
        self.assertEqual(len(self.store.list_for_account(("discord", "123"))), 1)
        self.assertEqual(len(self.store.list_for_account(("discord", "456"))), 1)
        self.assertEqual(self.store.recall_self_core(OWNER), [])
        other_channel = self.request("Jade, bonjour", platform="discord",
                                     account="123", author="Alice", channel="999")
        self.assertEqual(await self.svc.context_for(other_channel), "")
        self.assertNotIn("Alice", await self.svc.context_for(two))
        self.assertEqual(len(self.store.recall(("discord", "123"), "discord:100")), 1)
        self.assertEqual(len(self.store.recall(("discord", "456"), "discord:100")), 1)

    async def test_voice_and_text_share_verified_discord_scope(self):
        text = self.request("Jade, retiens que ce canal est notre atelier.",
                            platform="discord", account="123", channel="789")
        voice = self.request("Jade, retiens que ce canal est notre atelier.",
                             platform="discord_voice", speaker_id=123, channel="789")
        self.assertTrue(await self.svc.ensure_auto_enrolled(text))
        self.assertIn("enregistré", (await self.svc.command(voice)).text)
        self.assertIn("déjà", (await self.svc.command(text)).text)
        self.assertEqual(len(self.store.list_for_account(("discord", "123"))), 1)

    async def test_dm_auto_enrolled_but_twitch_remains_manual_opt_in(self):
        dm = self.request("Jade, mémorise que je viens de me connecter.",
                          platform="discord", account="123", channel="dm", private=True)
        twitch = self.request("Jade, retiens que je suis en ligne.",
                              platform="twitch", account="456", channel="stream")
        self.assertTrue(await self.svc.ensure_auto_enrolled(dm))
        self.assertFalse(await self.svc.ensure_auto_enrolled(twitch))
        self.assertIn("enregistré", (await self.svc.command(dm)).text)
        self.assertIn("n'est pas active", (await self.svc.command(twitch)).text)
        self.assertEqual(len(self.store.list_for_account(("discord", "123"))), 1)
        self.assertEqual(self.store.list_for_account(("twitch", "456")), [])
        self.store.enable(("twitch", "456"))
        self.assertIn("enregistré", (await self.svc.command(twitch)).text)

    async def test_profile_changes_revoke_pending_write(self):
        key = ("discord", "123")
        old_id = self.store.enable(key)
        self.assertTrue(self.store.forget_own_identity(key))
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
        self.assertIn("pas pu enregistrer", result.text)
        self.assertEqual(self.store.recall_self_core(OWNER), [])

    async def test_account_forget_removes_ordinary_without_touching_owner(self):
        outsider = ("discord", "123")
        self.store.enable(outsider)
        request = self.request("Jade, retiens que ma couleur est verte.",
                               platform="discord", author="Goldaj", account="123")
        self.assertIn("enregistré", (await self.svc.command(request)).text)
        self.assertEqual(self.store.recall(OWNER, "person"), [])
        self.assertTrue(self.store.forget_own_identity(outsider))
        self.assertEqual(self.store.list_for_account(outsider), [])
        self.assertEqual(self.store.recall_self_core(OWNER), [])

    async def test_orchestrator_routes_request_without_llm_or_core_curator(self):
        class Backend:
            calls = 0

            async def complete(self, messages):
                self.calls += 1
                raise AssertionError("Direct memory requests must not call the model")

        backend = Backend()
        delivered = []

        async def receive(reply):
            delivered.append(reply)

        service = MemoryService(self.store, backend, curator_enabled=True)
        runner = Runtime(Dialogue(backend, "Tu es Jade"), receive, memory_service=service)
        await runner.start()
        try:
            msg = self.request("Jade, ajoute à tes Core Memories : "
                               "ce moment passé avec Goldaj.")
            result = asyncio.get_running_loop().create_future()
            await runner.submit(msg, result=result)
            await asyncio.wait_for(runner.idle(), 3)
            self.assertIn("ordinaire", result.result())
            self.assertEqual(backend.calls, 0)
            self.assertEqual(len(delivered), 1)
            self.assertEqual(self.store.list_for_account(OWNER)[0]["kind"], "ordinary")
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
