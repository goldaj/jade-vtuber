"""Curator consent/revocation race and significance-content regressions.

No provider calls, real user content or persistent disk outside TemporaryDirectory.
"""
import asyncio
from contextlib import closing
import sqlite3
import json
from pathlib import Path
import tempfile
import unittest

from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming, Reply


class DelayedModel:
    def __init__(self, significance="Étape importante pour Jade."):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.significance = significance

    async def complete(self, messages):
        self.entered.set()
        await self.release.wait()
        return json.dumps({
            "kind": "ordinary",
            "summary": "Alice et Jade ont terminé un projet.",
            "significance": self.significance,
            "evidence": "Nous avons terminé ce projet ensemble.",
        })


class CuratorRevocation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = MemoryStore(Path(self.tmp.name) / "jade.sqlite3")
        self.key = ("discord", "101")
        self.store.enable(self.key)
        self.source = Incoming(
            "discord", "Alice", "Nous avons terminé ce projet ensemble.",
            account_id="101", channel="77", message_id="m-1")
        self.reply = Reply(self.source, "Bravo, mission accomplie.")

    async def _run_model(self, backend, *, forget_and_reenable=False):
        svc = MemoryService(self.store, backend, curator_enabled=True)
        try:
            self.assertTrue(svc.schedule(self.source, self.reply))
            await asyncio.wait_for(backend.entered.wait(), 2)
            if forget_and_reenable:
                with closing(sqlite3.connect(self.store.path)) as db:
                    db.execute("PRAGMA foreign_keys=ON")
                    db.execute("DELETE FROM persons WHERE id=?", (self.store.account(self.key),))
                    db.commit()
                self.store.enable(self.key)
            backend.release.set()
            await asyncio.wait_for(asyncio.gather(*list(svc.tasks)), 2)
        finally:
            await svc.close()

    async def test_replaced_profile_cannot_persist_queued_memory(self):
        backend = DelayedModel()
        await self._run_model(backend, forget_and_reenable=True)
        self.assertEqual(self.store.list_for_account(self.key), [])

    async def test_secret_in_significance_is_not_persisted(self):
        backend = DelayedModel(significance="Contient un mot de passe, à ne pas retenir.")
        await self._run_model(backend)
        self.assertEqual(self.store.list_for_account(self.key), [])


if __name__ == "__main__":
    unittest.main()
