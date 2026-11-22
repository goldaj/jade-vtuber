"""Offline regression tests for budgeted history and private memory batches."""
import asyncio
from contextlib import closing
import sqlite3
import json
from pathlib import Path
import tempfile
import unittest

from src.jade_runtime.context_selection import select_context
from src.jade_runtime.memory_batch import MemoryBatcher
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming, Reply


class ContextBudgetTests(unittest.TestCase):
    def test_preserves_storage_and_selects_old_relevant_exchange(self):
        history = []
        for i in range(40):
            topic = "papillon azure" if i == 5 else "discussion ordinaire"
            history += [{"role": "user", "content": f"Message {i} {topic}"},
                        {"role": "assistant", "content": f"Réponse {i}"}]
        selected = select_context(history, "Tu te souviens du papillon azure ?",
                                  max_chars=1000, recent_pairs=3, older_pairs=2)
        self.assertEqual(len(history), 80)
        content = " ".join(m["content"] for m in selected)
        self.assertIn("papillon azure", content)
        self.assertIn("Message 39", content)
        self.assertNotIn("Message 10 discussion", content)

    def test_unpaired_passive_discord_message_keeps_turn_order(self):
        history = [
            {"role": "user", "content": "un premier texte sans réponse"},
            {"role": "user", "content": "une question posée à Jade"},
            {"role": "assistant", "content": "la réponse à la question"},
            {"role": "user", "content": "nouvelle question"},
            {"role": "assistant", "content": "nouvelle réponse"},
        ]
        self.assertEqual(select_context(history, "question",
                                        max_chars=1000, recent_pairs=4), history)

    def test_bounded_inactive_context(self):
        history = [{"role": "user", "content": "a" * 800},
                   {"role": "assistant", "content": "b" * 800}] * 30
        selected = select_context(history, "Question", max_chars=3500)
        self.assertLessEqual(sum(len(m["content"]) for m in selected), 3500)


class BatchMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = MemoryStore(Path(self.temp.name) / "mem.sqlite3")
        self.key = ("discord", "123")
        self.store.enable(self.key)

    async def test_batch_one_paid_call_for_three_events(self):
        class Model:
            def __init__(self):
                self.calls = 0

            async def complete(self, messages):
                self.calls += 1
                data = json.loads(messages[1]["content"])
                return json.dumps([{"index": 1, "kind": "ordinary",
                    "summary": "Alice a terminé son projet de jardin.",
                    "significance": "Réussite partagée avec Jade.",
                    "evidence": data[1]["text"]}])
        model = Model()
        batch = MemoryBatcher(self.store, model, batch_size=3, delay_seconds=10)
        try:
            for i in range(3):
                source = Incoming("discord", "Alice",
                    f"Nous avons terminé ce projet ensemble numéro {i}.",
                    account_id="123", channel="77", message_id=f"b{i}")
                self.assertTrue(batch.schedule(self.key, "discord:77", source,
                                                Reply(source, "Bravo !")))
            await asyncio.wait_for(asyncio.gather(*list(batch.tasks)), 2)
            self.assertEqual(model.calls, 1)
            self.assertEqual(len(self.store.list_for_account(self.key)), 1)
        finally:
            await batch.close()

    async def test_stale_profile_before_batch_must_not_write(self):
        class Model:
            def __init__(self):
                self.entered = asyncio.Event()
                self.release = asyncio.Event()

            async def complete(self, messages):
                self.entered.set()
                await self.release.wait()
                text = json.loads(messages[1]["content"])[0]["text"]
                return json.dumps([{"index": 0, "kind": "core_relationship",
                    "summary": "Alice et Jade ont partagé une victoire.",
                    "significance": "Événement marquant.", "evidence": text}])
        model = Model()
        batch = MemoryBatcher(self.store, model, batch_size=1, delay_seconds=.01)
        source = Incoming("discord", "Alice",
            "Nous avons terminé ce projet ensemble et partagé une victoire.",
            account_id="123", channel="77", message_id="race")
        try:
            self.assertTrue(batch.schedule(self.key, "discord:77", source,
                                            Reply(source, "Bravo !")))
            await asyncio.wait_for(model.entered.wait(), 2)
            with closing(sqlite3.connect(self.store.path)) as db:
                db.execute('PRAGMA foreign_keys=ON')
                db.execute('DELETE FROM persons WHERE id=?', (self.store.account(self.key),))
                db.commit()
            self.store.enable(self.key)
            model.release.set()
            await asyncio.wait_for(asyncio.gather(*list(batch.tasks)), 2)
            self.assertEqual(self.store.list_for_account(self.key), [])
        finally:
            await batch.close()

    async def test_third_party_core_self_is_autobiographical_not_person_memory(self):
        class Model:
            async def complete(self, messages):
                text = json.loads(messages[1]["content"])[0]["text"]
                return json.dumps([{"index": 0, "kind": "core_self",
                    "summary": "Jade a découvert sa vocation de coautrice.",
                    "significance": "Épisode personnel de Jade.",
                    "evidence": text}])
        batch = MemoryBatcher(self.store, Model(), batch_size=1)
        incoming = Incoming("discord", "Alice",
            "Nous avons partagé une discussion importante sur ton avenir.",
            account_id="123", channel="77", message_id="foreign-self")
        try:
            self.assertTrue(batch.schedule(
                self.key, "discord:77", incoming, Reply(incoming, "Je comprends.")))
            await asyncio.wait_for(asyncio.gather(*list(batch.tasks)), 3)
            self.assertEqual(self.store.list_for_account(self.key), [])
            # Jade's self Core is global autobiography, not Alice's relational memory.
            with closing(sqlite3.connect(self.store.path)) as db:
                self.assertEqual(db.execute(
                    "SELECT COUNT(*) FROM jade_self_core").fetchone()[0], 1)
        finally:
            await batch.close()

    async def test_local_prefilter_rejects_empty_pleasantries_and_duplicates(self):
        class Model:
            def __init__(self):
                self.calls = 0

            async def complete(self, messages):
                self.calls += 1
                return "[]"
        model = Model()
        batch = MemoryBatcher(self.store, model, batch_size=2, delay_seconds=0.1)
        trivial = Incoming("discord", "Alice", "Merci beaucoup pour ton aide !",
                           account_id="123", channel="77", message_id="thanks")
        useful = Incoming("discord", "Alice",
                          "J'ai terminé une formation importante cette semaine.",
                          account_id="123", channel="77", message_id="useful")
        repeat = Incoming("discord", "Alice",
                          "  j'ai terminé   une formation importante cette semaine. ",
                          account_id="123", channel="77", message_id="dup")
        try:
            self.assertFalse(batch.schedule(self.key, "discord:77", trivial,
                                            Reply(trivial, "De rien")))
            self.assertTrue(batch.schedule(self.key, "discord:77", useful,
                                           Reply(useful, "Félicitations")))
            self.assertFalse(batch.schedule(self.key, "discord:77", repeat,
                                            Reply(repeat, "Bien")))
            await asyncio.wait_for(asyncio.gather(*list(batch.tasks)), 2)
            self.assertEqual(model.calls, 1)
        finally:
            await batch.close()

    async def test_short_greetings_do_not_bill(self):
        class Model:
            async def complete(self, messages):
                raise AssertionError("No API call expected")
        batch = MemoryBatcher(self.store, Model())
        source = Incoming("discord", "Alice", "Salut Jade",
                          account_id="123", channel="77")
        self.assertFalse(batch.schedule(self.key, "discord:77",
                                        source, Reply(source, "Salut")))
        await batch.close()


if __name__ == "__main__":
    unittest.main()
