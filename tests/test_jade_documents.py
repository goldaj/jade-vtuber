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
