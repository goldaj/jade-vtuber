"""DEV-032: local document generation and verified authorization."""
import asyncio
import json
import time
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile
from io import BytesIO

from src.jade_runtime.documents import DocumentService, DocumentStore, TTL_SECONDS
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.discord_text import DiscordText
from src.jade_runtime.messages import Incoming


class LinkedIdentities:
    def is_goldaj(self, key):
        return key == ("discord", "123456")


class DocumentTests(unittest.TestCase):
    def test_text_and_opaque_link(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            file = store.create("exemple.py", "print('salut')\n")
            self.assertEqual(store.read(file.id)[1], b"print('salut')\n")
            self.assertEqual(file.public()["url"], "/api/documents/" + file.id)
            self.assertEqual(TTL_SECONDS, 86400)

    def test_formatted_office_and_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            for name, content, expected in (
                ("exemple.pdf", "Bonjour", b"%PDF-1.4"),
                ("exemple.docx", "Bonjour\nMonde", b"PK"),
                ("exemple.xlsx", "nom;age\nJade;1", b"PK"),
            ):
                with self.subTest(name=name):
                    item = store.create(name, content)
                    actual = store.read(item.id)[1]
                    self.assertTrue(actual.startswith(expected))
                    if name.endswith((".docx", ".xlsx")):
                        with ZipFile(BytesIO(actual)) as archive:
                            self.assertTrue(archive.testzip() is None)

    def test_site_zip_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            site = store.create("site.zip", json.dumps({
                "index.html": "<h1>Jade</h1>", "css/site.css": "body{}"}))
            with ZipFile(BytesIO(store.read(site.id)[1])) as archive:
                self.assertEqual(sorted(archive.namelist()), ["css/site.css", "index.html"])
            with self.assertRaises(ValueError):
                store.create("bad.zip", json.dumps({"../secret": "no"}))

    def test_expire_and_track_discord(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            item = store.create("a.txt", "contenu")
            store.mark_discord((item,), "100", 200)
            store.prune(now=item.expires_at + 1)
            self.assertFalse((Path(directory) / (item.id + ".bin")).exists())
            self.assertEqual(store.expired_discord(), [])  # expiry based on real clock
            # Use artificially expired metadata to exercise a restart sweep.
            record = store._load(item.id)
            record["expires_at"] = time.time() - 1
            store._write_metadata(record)
            self.assertEqual(len(store.expired_discord()), 1)
            store.ack_discord(item.id, "100", 200)
            self.assertIsNone(store._load(item.id))

    def test_bad_filename_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            for name in ("../test.py", "a/b.txt", "x", "a.txt\r\n"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    store.create(name, "hello")


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_mobile_and_linked_discord_only(self):
        with tempfile.TemporaryDirectory() as directory:
            service = DocumentService(directory, memory_store=LinkedIdentities())
            for incoming, expected in (
                (Incoming("mobile", "Goldaj", "Crée un PDF"), True),
                (Incoming("discord", "alias", "Crée un PDF", account_id="123456"), True),
                (Incoming("discord_voice", "alias", "Crée un PDF", speaker_id=123456), True),
                (Incoming("discord", "Goldaj", "Crée un PDF", account_id="2222"), False),
                (Incoming("discord_voice", "Goldaj", "Crée un PDF", speaker_id=2222), False),
            ):
                with self.subTest(origin=incoming.platform, id=incoming.account_id):
                    action = await service.for_turn(incoming)
                    self.assertEqual(action.allowed, expected)
            action = await service.for_turn(
                Incoming("discord", "inconnu", "Fais un fichier", account_id="2222"))
            self.assertEqual((await action.create_document(json.dumps({
                "filename": "test.txt", "content": "interdit"})))["status"], "refusé")

    async def test_future_access_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            inc = Incoming("discord", "autre", "Crée un fichier", account_id="987")
            whitelist = DocumentService(directory, access_mode="allowlist",
                                        allowed_discord_ids=(987,))
            any_user = DocumentService(directory, access_mode="all")
            self.assertTrue((await whitelist.for_turn(inc)).allowed)
            self.assertTrue((await any_user.for_turn(inc)).allowed)



class LinkedDiscordRegressionTests(unittest.IsolatedAsyncioTestCase):
    """A real SQLite link must work in DM, public text and voice.

    In particular the link remains usable if memory processing is disabled:
    ownership is not a memory feature toggle.
    """
    async def test_existing_link_is_authorized_in_all_discord_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "jade-memories.sqlite3"
            store = MemoryStore(db)
            owner_key = ("microphone", "goldaj")
            discord_key = ("discord", "123456789012345678")
            other_key = ("discord", "234567890123456789")
            store.enable(owner_key)
            store.enable(discord_key)
            store.enable(other_key)
            token = store.begin_link(owner_key, target=discord_key)
            self.assertTrue(store.complete_link(discord_key, token))
            incoming_messages = (
                Incoming("discord", "Goldaj", "Crée un txt", channel="dm",
                         account_id=discord_key[1], private_channel=True),
                Incoming("discord", "Autre pseudo", "Crée un txt", channel="public",
                         account_id=discord_key[1]),
                Incoming("discord_voice", "Autre pseudo", "Crée un txt",
                         channel="vocal", speaker_id=int(discord_key[1])),
            )
            for memory in (store, None):
                with self.subTest(memory_enabled=memory is not None):
                    service = DocumentService(Path(directory) / "documents",
                                              memory_store=memory, identity_db_path=db)
                    for incoming in incoming_messages:
                        action = await service.for_turn(incoming)
                        self.assertTrue(action.allowed, incoming.platform)
                        self.assertTrue(action.owner_verified)
                        outcome = await action.create_document(json.dumps({
                            "filename": "test.txt", "content": "bonjour"}))
                        self.assertEqual(outcome["status"], "created")
                        self.assertEqual(len(action.attachments), 1)
                    attacker = Incoming("discord", "Goldaj", "Crée un txt",
                                        account_id=other_key[1])
                    self.assertFalse((await service.for_turn(attacker)).allowed)
                    disguised = Incoming("discord", "Goldaj", "Crée un txt")
                    self.assertFalse((await service.for_turn(disguised)).allowed)


class DiscordAttachmentDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_attachment_sent_in_private_public_and_voice_text_chats(self):
        """The same native Discord file path works for all three destinations."""
        class FakeFile:
            def __init__(self, path, *, filename):
                self.name = filename
                self.data = Path(path).read_bytes()
                self.closed = False

            def close(self):
                self.closed = True

        class FakeAllowedMentions:
            @staticmethod
            def none():
                return None

        class FakeChannel:
            def __init__(self, channel_id):
                self.id = channel_id
                self.sent = []

            async def send(self, text, *, files=None, allowed_mentions=None):
                self.sent.append((text, [(f.name, f.data) for f in (files or [])]))
                return SimpleNamespace(id=1000 + len(self.sent))

        class FakeClient:
            def __init__(self, channels):
                self.channels = channels

            def get_channel(self, channel_id):
                # Public text and voice rooms are cached by the connected bot.
                # DM channel is known only through the verified inbound message.
                return self.channels.get(channel_id) if channel_id != 11 else None

        with tempfile.TemporaryDirectory() as directory:
            store = DocumentStore(Path(directory))
            attachment = store.create("document.txt", "texte à télécharger")
            channels = {id: FakeChannel(id) for id in (10, 11, 12)}
            discord = DiscordText("fake-token", lambda message: None,
                                  send_enabled=True, document_store=store)
            discord.client = FakeClient(channels)
            discord._dm_channels["11"] = channels[11]
            with patch.dict("sys.modules", {
                "discord": SimpleNamespace(File=FakeFile,
                                           AllowedMentions=FakeAllowedMentions)}):
                for channel_id in (10, 11, 12):
                    with self.subTest(channel=channel_id):
                        sent = await discord.send_chat(
                            str(channel_id), "Voici le fichier",
                            source_message_id="123", attachments=(attachment,))
                        self.assertTrue(sent)
                        self.assertEqual(channels[channel_id].sent,
                            [("Voici le fichier", [("document.txt",
                                                   "texte à télécharger".encode())])])
            metadata = store._load(attachment.id)
            self.assertEqual(
                sorted(item["channel"] for item in metadata["discord"]),
                ["10", "11", "12"])


class DiscordPromptRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_linked_discord_owner_has_document_tool_without_mobile_channel(self):
        from src.jade_runtime.dialogue import Dialogue
        class FakeBackend:
            def __init__(self):
                self.instructions = ""

            async def complete_with_tools(self, messages, action):
                self.instructions = messages[0]["content"]
                assert callable(action.create_document)
                result = await action.create_document(json.dumps({
                    "filename": "jadesite.html", "content": "<p>Jade</p>"}))
                assert result["status"] == "created"
                return "[INTENT:neutral] Voilà ton fichier."

            async def complete(self, messages):
                raise AssertionError("Should not fall back to tool-free reply")

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "memory.sqlite3"
            memory = MemoryStore(db)
            memory.enable(("microphone", "goldaj"))
            discord_key = ("discord", "123456789123456789")
            memory.enable(discord_key)
            code = memory.begin_link(("microphone", "goldaj"), target=discord_key)
            self.assertTrue(memory.complete_link(discord_key, code))
            documents = DocumentService(Path(directory) / "documents",
                                        identity_db_path=db)
            action = await documents.for_turn(Incoming(
                "discord", "N'importe quel pseudo", "Crée un HTML",
                account_id=discord_key[1], channel="salon"))
            backend = FakeBackend()
            incoming = Incoming("discord", "N'importe quel pseudo", "Crée un HTML",
                                account_id=discord_key[1],
                                channel="salon", force_reply=True)
            reply = await Dialogue(backend, "Jade est une assistante.").respond(
                incoming, document_action=action)
            self.assertEqual(reply.attachments[0].name, "jadesite.html")
            self.assertIn("identité Goldaj vérifiée", backend.instructions)
            self.assertIn("Outil jade_create_document disponible", backend.instructions)
