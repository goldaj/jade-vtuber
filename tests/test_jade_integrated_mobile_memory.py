"""Regression contract across the four independent Jade PRs, offline only.

This test is deliberately kept on the integration review branch; it does not
change production branches or require Discord/Tailscale/OpenAI access.
"""
import asyncio
from pathlib import Path
import tempfile
import unittest

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore, identity_of
from src.jade_runtime.messages import Incoming
from src.jade_runtime.mobile_gateway import MobileGateway
from src.jade_runtime.orchestrator import Runtime

OWNER = ("microphone", "goldaj")


class DummyModel:
    def __init__(self):
        self.prompted = []

    async def complete(self, messages):
        self.prompted.append(messages)
        return "[INTENT:neutral] J'ai bien retrouvé le fil."


class Integration(unittest.IsolatedAsyncioTestCase):
    async def test_owner_core_recall_on_mobile_text_and_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "jade-memory.sqlite3")
            store.enable(OWNER)
            self.assertTrue(store.put_self_core(
                OWNER, summary="Jade a terminé un roman avec Goldaj.",
                significance="Une première expérience importante."))
            ai = DummyModel()
            memory = MemoryService(store, ai)
            mobile = None

            async def on_reply(reply):
                mobile.deliver(reply)

            runtime = Runtime(Dialogue(ai, "Tu es Jade."), on_reply,
                              memory_service=memory)
            mobile = MobileGateway(runtime, ai, token="t" * 40)
            self.assertEqual(identity_of(Incoming(
                "mobile", "Goldaj", "Salut")), OWNER)
            self.assertEqual(identity_of(Incoming(
                "microphone", "Goldaj", "Salut")), OWNER)
            await runtime.start()
            try:
                written = Incoming("mobile", "Goldaj", "Quel roman ?",
                                   message_id="m-1", channel="private",
                                   force_reply=True, input_modality="text")
                spoken = Incoming("mobile", "Goldaj", "Et ensuite ?",
                                  message_id="m-2", channel="private",
                                  force_reply=True, input_modality="voice")
                self.assertEqual((await mobile._conversation(written)).intent, "neutral")
                self.assertEqual((await mobile._conversation(spoken)).intent, "neutral")
                prompts = "\n".join(str(x) for x in ai.prompted)
                self.assertIn("Jade a terminé un roman avec Goldaj.", prompts)
                self.assertIn("Quel roman ?", str(ai.prompted[1]))
            finally:
                await runtime.stop()
                await memory.close()

    async def test_both_feature_flags_are_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Settings(memory_enabled=True, memory_curator_enabled=True,
                           memory_db_path=str(Path(tmp) / "jade-memory.sqlite3"),
                           mobile_enabled=True, mobile_token="t" * 40,
                           mobile_owner_login="owner@example.test",
                           mobile_public_origin="https://pc.ts.net")
            cfg.validate()
            self.assertTrue(cfg.memory_enabled)
            self.assertTrue(cfg.mobile_enabled)


if __name__ == "__main__":
    unittest.main()
