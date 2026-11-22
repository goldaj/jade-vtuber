"""Delivery regression: failed Discord output cannot create durable memories."""
import asyncio
import unittest
from unittest.mock import ANY, patch

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime


class Backend:
    async def complete(self, messages):
        return "Une réponse simulée."


class MemorySpy:
    def __init__(self):
        self.writes = 0
        self.schedules = 0

    async def ensure_auto_enrolled(self, incoming):
        return True

    async def command(self, incoming):
        return None

    async def context_for(self, incoming):
        return ""

    async def history_for(self, incoming):
        return []

    async def remember_turn(self, incoming, reply):
        self.writes += 1
        return True

    def schedule(self, incoming, reply):
        self.schedules += 1
        return True


class DeliveryIsRequired(unittest.IsolatedAsyncioTestCase):
    async def test_delivery_proofs_require_a_matching_plan_and_callback_receipt(self):
        async def deliver(_reply):
            return {
                "transport_accepted": ("discord_text", "mobile_text"),
                "playback_completed": ("discord_voice",),
            }
        runtime = Runtime(
            Dialogue(Backend(), "Tu es Jade."), deliver,
            delivery_plan=lambda _reply: ("discord_text",))
        with patch("src.jade_runtime.orchestrator.record_delivery_evidence") as observed:
            await runtime.start()
            try:
                await runtime.submit(Incoming(
                    "discord", "Alice", "Bonjour Jade",
                    channel="42", account_id="41", message_id="m1",
                    private_channel=True, force_reply=True))
                await asyncio.wait_for(runtime.idle(), 2)
            finally:
                await runtime.stop()
        observed.assert_called_once_with(
            ANY, "transport_accepted", "discord_text", proof="discord_api")

    async def test_failed_delivery_does_not_mark_memories_as_delivered(self):
        memory = MemorySpy()

        async def reject(_reply):
            raise RuntimeError("Discord destination unavailable")

        runtime = Runtime(Dialogue(Backend(), "Tu es Jade."), reject,
                          memory_service=memory)
        await runtime.start()
        try:
            await runtime.submit(Incoming(
                "discord", "Alice", "Jade, je t'écris en privé.",
                channel="900", account_id="41", message_id="m1",
                private_channel=True, force_reply=True))
            await asyncio.wait_for(runtime.idle(), 2)
        finally:
            await runtime.stop()
        self.assertEqual(memory.writes, 0)
        self.assertEqual(memory.schedules, 0)
        self.assertGreaterEqual(runtime.errors, 1)


if __name__ == "__main__":
    unittest.main()
