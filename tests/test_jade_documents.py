"""DEV-032: local document generation and verified authorization."""
import asyncio
import json
import time
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from io import BytesIO

from src.jade_runtime.documents import DocumentService, DocumentStore, TTL_SECONDS
from src.jade_runtime.memory_store import MemoryStore
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
