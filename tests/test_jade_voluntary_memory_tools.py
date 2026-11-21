"""DEV-012: verify autonomous conversation tools without real API requests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.orchestrator import Runtime


OWNER = ("microphone", "goldaj")


def incoming(platform="mobile", **kwargs):
    return Incoming(platform, "Goldaj",
                    "Nous avons terminé notre premier roman ensemble.",
                    message_id="dev012", force_reply=True, **kwargs)


def arguments(kind="ordinary", evidence="terminé notre premier roman",
              summary="Nous avons terminé un roman ensemble."):
    return json.dumps({
        "kind": kind,
        "summary": summary,
        "significance": "Une réussite importante pour Jade.",
        "evidence": evidence,
    })


class VoluntaryMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "memory.sqlite3"
        self.store = MemoryStore(self.path)
        self.store.enable(OWNER)
        self.service = MemoryService(self.store, backend=object(), curator_enabled=True)

    async def asyncTearDown(self):
        await self.service.close()

    async def test_actual_levels_persist_duplicates_and_reopen(self):
        action = await self.service.prepare_memory_action(incoming())
        self.assertIsNotNone(action)
        self.assertFalse(action.used)
        self.assertEqual(await action(arguments()), {
            "status": "enregistré", "level": 2, "kind": "ordinary"})
        self.assertTrue(action.used)
        self.assertEqual((await action(arguments()))["status"], "déjà présent")
        self.assertEqual((await action(arguments(kind="core_self")))["level"], 3)
        self.assertEqual((await action(arguments(kind="core_relationship")))["level"], 3)
        reopened = MemoryStore(self.path)
        memories = reopened.list_for_account(OWNER)
        self.assertEqual({m["kind"] for m in memories}, {"ordinary", "core_relationship"})
        self.assertIsNotNone(next(m for m in memories
                                 if m["kind"] == "ordinary")["expires_at"])
        self.assertIsNone(next(m for m in memories
                               if m["kind"] == "core_relationship")["expires_at"])
        self.assertEqual(len(reopened.recall_self_core(OWNER)), 1)

    async def test_no_verified_identity_no_tool_and_no_external_autobiography(self):
        self.assertIsNone(await self.service.prepare_memory_action(
            incoming("discord", account_id="", channel="room")))
        key = ("discord", "123")
        self.store.enable(key)
        source = incoming("discord", account_id="123", channel="77")
        action = await self.service.prepare_memory_action(source)
        self.assertEqual((await action(arguments("core_self")))["status"], "refusé")
        self.assertEqual((await action(arguments()))["status"], "enregistré")
        self.assertEqual(self.store.recall(key, "discord:99"), [])
        self.assertEqual(len(self.store.recall(key, "discord:77")), 1)
        self.assertEqual(self.store.recall_self_core(OWNER), [])

    async def test_human_core_request_does_not_force_a_core(self):
        request = Incoming(
            "mobile", "Goldaj",
            "Jade, garde dans tes Core Memories : nous avons fini le roman.",
            message_id="request")
        reply = await self.service.command(request)
        self.assertIn("mémoire ordinaire", reply.text)
        self.assertEqual(self.store.recall_self_core(OWNER), [])
        # Even when a caller somehow supplies this same raw request to a tool,
        # it must never upgrade the human instruction.
        action = await self.service.prepare_memory_action(request)
        candidate = arguments(kind="core_self", evidence="nous avons fini le roman")
        self.assertEqual((await action(candidate))["status"], "refusé")

    async def test_unfounded_or_sensitive_content_is_refused(self):
        action = await self.service.prepare_memory_action(incoming())
        invalid = [
            arguments(evidence="phrase non présente dans le message"),
            arguments(summary="Mot de passe sk-secret123"),
            arguments(evidence="terminé notre premier roman", summary=""),
            '{"kind":"ordinary","summary":"x"}',
            "{" * 3000,
        ]
        for payload in invalid:
            self.assertEqual((await action(payload))["status"], "refusé")
        self.assertEqual(self.store.list_for_account(OWNER), [])

    async def test_erasure_reactivation_and_sqlite_error(self):
        action = await self.service.prepare_memory_action(incoming())
        old_id = self.store.account(OWNER)
        self.store.forget(OWNER)
        self.store.enable(OWNER)
        self.assertNotEqual(old_id, self.store.account(OWNER))
        self.assertEqual((await action(arguments()))["status"], "refusé")
        another = await self.service.prepare_memory_action(incoming())
        with patch.object(self.store, "put", side_effect=OSError("disk read only")):
            self.assertEqual((await another(arguments()))["status"], "échec")
        self.assertEqual(self.store.list_for_account(OWNER), [])

    async def test_disabled_account_cannot_write(self):
        self.store.forget(OWNER)
        self.assertIsNone(await self.service.prepare_memory_action(incoming()))

    async def test_runtime_exposes_tool_to_model_and_no_second_curator(self):
        class Model:
            calls = 0

            async def complete_with_tools(self, messages, action):
                self.calls += 1
                self_prompt = messages[0]["content"]
                assert "jade_save_memory" in self_prompt
                outcome = await action(arguments())
                assert outcome["status"] == "enregistré"
                return "J'ai pris soin de mémoriser ce moment."

        received = []
        async def publish(reply):
            received.append(reply.text)
        backend = Model()
        runtime = Runtime(Dialogue(backend, "Tu es Jade"), publish,
                          memory_service=self.service)
        await runtime.start()
        try:
            await runtime.submit(incoming())
            await runtime.idle()
        finally:
            await runtime.stop()
        self.assertEqual(backend.calls, 1)
        self.assertEqual(received, ["J'ai pris soin de mémoriser ce moment."])
        self.assertEqual(len(self.store.list_for_account(OWNER)), 1)
        self.assertFalse(self.service.tasks)


if __name__ == "__main__":
    unittest.main()
