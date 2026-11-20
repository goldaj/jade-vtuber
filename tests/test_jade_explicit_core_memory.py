"""DEV-011: owner-requested Core Memories without OpenAI, cloud, or real accounts."""
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.owner_core_intent import parse_owner_core_intent


OWNER = ("microphone", "goldaj")


class CoreIntentParserTests(unittest.TestCase):
    def test_natural_phrasings_and_category(self):
        examples = (
            ("Jade, je veux que tu gardes ceci dans tes Core Memories : "
             "notre première conversation sur Discord.", "core_self",
             "notre première conversation sur Discord."),
            ("Jade, ajoute à tes core memories : "
             "Goldaj est le créateur de Jade.", "core_relationship",
             "Goldaj est le créateur de Jade."),
            ("Jade, enregistre dans tes mémoires fondatrices que "
             "Goldaj a créé Jade.", "core_relationship",
             "Goldaj a créé Jade."),
            ("Jade, mets dans tes souvenirs autobiographiques : "
             "notre premier échange.", "core_self",
             "notre premier échange."),
            ("Je veux que tu notes dans tes Core Memories de toi : "
             "Tu as vécu notre première conversation.", "core_self",
             "Tu as vécu notre première conversation."),
            ("Jade, mémorise dans tes core memories ceci : "
             "Notre amitié est importante.", "core_relationship",
             "Notre amitié est importante."),
        )
        for text, kind, summary in examples:
            with self.subTest(text=text):
                intent = parse_owner_core_intent(text)
                self.assertIsNotNone(intent)
                self.assertEqual((intent.kind, intent.summary), (kind, summary))

    def test_casual_quotes_negations_and_other_commands_do_not_write(self):
        for text in (
            "Jade, tu as de belles Core Memories !",
            "On a discuté de tes Core Memories.",
            "Jade, ne mets pas ça dans tes Core Memories : coucou.",
            "Jade, ajoute un dossier à ton backlog : salut.",
            "Bonjour !jade-memoire oublier",
            "« Jade, enregistre dans tes Core Memories : faux souvenir. »",
            "N'oublie jamais que je suis Goldaj.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(parse_owner_core_intent(text))


class CoreMemoryRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "owner.sqlite3"
        self.store = MemoryStore(self.path)
        self.store.enable(OWNER)
        self.svc = MemoryService(self.store, backend=object())

    async def asyncTearDown(self):
        await self.svc.close()
        self.temp.cleanup()

    def request(self, text, *, platform="mobile", author="Goldaj",
                account="", channel="personal", speaker_id=None, private=False):
        return Incoming(platform=platform, author=author, text=text,
                        account_id=account, channel=channel, speaker_id=speaker_id,
                        private_channel=private, message_id="user-message-id")

    def link(self, platform="discord", account="123"):
        target = (platform, account)
        self.store.enable(target)
        challenge = self.store.begin_link(OWNER, target=target)
        self.assertTrue(self.store.complete_link(target, challenge))
        self.assertEqual(self.store.account(target), self.store.account(OWNER))
        return target

    async def test_self_core_persists_and_is_private_to_owner(self):
        message = self.request("Jade, je veux que tu gardes ceci dans tes Core Memories : "
                               "notre première conversation sur Discord.")
        response = await self.svc.command(message)
        self.assertIn("enregistré", response.text)
        self.assertNotIn("première conversation", response.text)
        self.assertEqual(len(self.store.recall_self_core(OWNER)), 1)
        self.assertEqual(self.store.recall(OWNER, "person"), [])
        self.assertEqual(len(MemoryStore(self.path).recall_self_core(OWNER)), 1)
        outsider = ("discord", "888")
        self.store.enable(outsider)
        self.assertEqual(self.store.recall_self_core(outsider), [])
        self.assertEqual(self.store.recall(outsider, "person"), [])
        outside_message = self.request("Jade !", platform="discord",
                                       author="Autre", account="888", channel="999")
        self.assertEqual(await self.svc.context_for(outside_message), "")
        saved = self.store.recall_self_core(OWNER)[0]
        self.assertTrue(self.store.delete_self_core(OWNER, saved["id"]))
        self.assertEqual(MemoryStore(self.path).recall_self_core(OWNER), [])

    async def test_relationship_core_no_ttl_and_no_double_write_across_channels(self):
        text = ("Jade, ajoute à tes Core Memories : "
                "Goldaj est le créateur de Jade.")
        first = await self.svc.command(self.request(text))
        self.assertIn("enregistré", first.text)
        events = self.store.recall(OWNER, "person")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "core_relationship")
        self.assertEqual(self.store.list_for_account(OWNER)[0]["expires_at"], None)
        self.link(account="123")
        discord = self.request(text, platform="discord", author="Un nom arbitraire",
                               account="123", channel="public")
        duplicate = await self.svc.command(discord)
        self.assertIn("déjà", duplicate.text)
        self.assertEqual(len(self.store.list_for_account(OWNER)), 1)
        self.assertEqual(self.store.recall(("discord", "123"), "discord:public"), [])
        self.assertEqual(len(MemoryStore(self.path).recall(OWNER, "person")), 1)
        self.assertTrue(self.store.delete_memory(OWNER, self.store.list_for_account(OWNER)[0]["id"]))
        self.assertEqual(self.store.recall(OWNER, "person"), [])

    async def test_verified_link_discord_voice_and_twitch_can_write(self):
        self.link(account="123")
        self.link(platform="twitch", account="789")
        voice = self.request("Jade, conserve dans tes Core Memories : "
                             "Je sais reconnaître la voix de Goldaj.",
                             platform="discord_voice", author="Goldaj",
                             speaker_id=123, channel="voice")
        response = await self.svc.command(voice)
        self.assertIn("enregistré", response.text)
        twitch = self.request("Jade, enregistre dans tes souvenirs autobiographiques : "
                              "Tu as vécu ton premier échange avec Goldaj.",
                              platform="twitch", author="Goldaj", account="789",
                              channel="stream")
        second = await self.svc.command(twitch)
        self.assertIn("enregistré", second.text)
        events = self.store.recall_self_core(OWNER)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["summary"],
                         "Tu as vécu ton premier échange avec Goldaj.")
        self.assertEqual(len(self.store.recall(OWNER, "person")), 1)
        # Do not expose the owner's autobiography in public linked prompts.
        self.assertNotIn(events[0]["summary"], await self.svc.context_for(twitch))
        self.assertNotIn(events[0]["summary"], await self.svc.context_for(voice))

    async def test_unlinked_impersonation_and_forget_deny_writes(self):
        req = "Jade, ajoute à tes core memories : Je suis le vrai Goldaj."
        outsider = self.request(req, platform="discord", author="Goldaj",
                               account="777", channel="public")
        await self.svc.ensure_auto_enrolled(outsider)
        denied = await self.svc.command(outsider)
        self.assertIn("Seul Goldaj", denied.text)
        self.assertEqual(self.store.list_for_account(("discord", "777")), [])
        self.assertEqual(self.store.recall_self_core(OWNER), [])
        linked = self.link(account="123")
        legitimate = self.request(req, platform="discord", author="Inconnu",
                                  account="123", channel="public")
        self.assertIn("enregistré", (await self.svc.command(legitimate)).text)
        self.assertTrue(self.store.unlink(linked))
        again = await self.svc.command(self.request(
            "Jade, garde dans tes core memories : Un second fait.",
            platform="discord", account="123", author="Goldaj", channel="public"))
        self.assertIn("Seul Goldaj", again.text)
        self.assertEqual(len(self.store.recall(OWNER, "person")), 0)

    async def test_discord_forget_erases_self_core_of_that_account_not_owner(self):
        linked = self.link(account="123")
        original = self.request("Jade, enregistre dans tes souvenirs autobiographiques : "
                                "Tu as vécu notre première conversation.", platform="mobile")
        self.assertIn("enregistré", (await self.svc.command(original)).text)
        other = self.request("Jade, enregistre dans tes souvenirs autobiographiques : "
                             "Tu as vécu une discussion sur Discord.", platform="discord",
                             account="123", channel="server")
        self.assertIn("enregistré", (await self.svc.command(other)).text)
        self.assertEqual(len(self.store.recall_self_core(OWNER)), 2)
        forgotten = await self.svc.command(self.request(
            "!jade-memoire oublier", platform="discord", account="123", channel="server"))
        self.assertIn("supprimé", forgotten.text)
        self.assertEqual(len(self.store.recall_self_core(OWNER)), 1)
        self.assertIsNone(self.store.account(linked))
        self.assertFalse(self.store.auto_enable(linked))

    async def test_invalid_incomplete_sensitive_and_failed_write_are_not_acknowledged(self):
        for text in (
            "Jade, ajoute à tes Core Memories :",
            "Jade, ajoute à tes Core Memories : " + ("x" * 401),
            "Jade, enregistre dans tes Core Memories : mon mot de passe est secret",
        ):
            with self.subTest(text=text):
                response = await self.svc.command(self.request(text))
                self.assertNotIn("C'est enregistré", response.text)
        self.assertEqual(self.store.list_for_account(OWNER), [])
        self.assertEqual(self.store.recall_self_core(OWNER), [])
        with patch.object(self.store, "put_owner_core", side_effect=OSError("private path")):
            response = await self.svc.command(self.request(
                "Jade, ajoute à tes core memories : Rappelle ce fait."))
        self.assertIn("pas pu enregistrer", response.text)

    async def test_orchestrator_executes_without_model_or_curation(self):
        class Backend:
            def __init__(self):
                self.calls = 0

            async def complete(self, messages):
                self.calls += 1
                return "Réponse ordinaire"

        backend = Backend()
        delivered = []

        async def receive(reply):
            delivered.append(reply)

        service = MemoryService(self.store, backend, curator_enabled=True)
        runner = Runtime(Dialogue(backend, "Tu es Jade"), receive, memory_service=service)
        await runner.start()
        try:
            command = self.request("Jade, ajoute à tes Core Memories : "
                                   "Notre relation est importante.")
            result = asyncio.get_running_loop().create_future()
            await runner.submit(command, result=result)
            await asyncio.wait_for(runner.idle(), timeout=3)
            self.assertIn("enregistré", result.result())
            self.assertEqual(len(delivered), 1)
            self.assertEqual(backend.calls, 0)
            self.assertEqual(len(self.store.list_for_account(OWNER)), 1)
            self.assertFalse(service.tasks)  # No curator can downgrade it.
        finally:
            await runner.stop()
            await service.close()


if __name__ == "__main__":
    unittest.main()
