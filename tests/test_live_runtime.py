"""Offline end-to-end Live wiring with real Runtime, budgets and local tools."""
import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import sqlite3

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.documents import DocumentService
from src.jade_runtime.live_config import LiveConfig
from src.jade_runtime.live_sessions import LiveSessionError
from src.jade_runtime.live_runtime import create_mobile_live
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.turn_metrics import record_model_usage


SDP = "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=fingerprint:sha-256 00:11\r\na=ice-ufrag:test\r\n"
OWNER = ("microphone", "goldaj")


class FakeChannel:
    def __init__(self):
        self.events = asyncio.Queue()
        self.sent = []
        self.sequence = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.events.get()

    async def send(self, event):
        self.sent.append(event)
        self.sequence += 1
        if event["type"] == "session.close":
            await self.events.put({"type": "session.closed", "event_id": "closed-" + str(self.sequence),
                "reason": "client_request", "usage": {"seconds": 3, "active_seconds": 3, "paused_seconds": 0}})
        elif event["type"] == "session.commentary.append":
            # Simulated native provider rendering, not a second Jade TTS path.
            await self.events.put({"type": "session.commentary.appended", "event_id": "ack-" + str(self.sequence),
                                   "client_event_id": event["event_id"]})
            await self.events.put({"type": "session.output_transcript.delta",
                "event_id": "output-" + str(self.sequence), "delta": event["content"],
                "start_ms": 1200 + self.sequence * 200, "end_ms": 1400 + self.sequence * 200})

    async def close(self):
        pass


class FakeProvider:
    def __init__(self):
        self.created = []
        self.channels = {}

    async def create_session(self, sdp, session_config):
        self.created.append(session_config)
        ident = "provider_session_" + str(len(self.created))
        self.channels[ident] = FakeChannel()
        return {"session_id": ident, "sdp": SDP, "expires_at": None}

    @asynccontextmanager
    async def attach(self, session_id):
        channel = self.channels[session_id]
        await channel.events.put({"type": "session.started", "event_id": "started-" + session_id})
        try:
            yield channel
        finally:
            await channel.close()


class Model:
    def __init__(self):
        self.requests = []

    async def complete(self, messages):
        self.requests.append(messages)
        record_model_usage(150, 30)
        return "[INTENT:curious] Je peux reprendre notre projet."

    async def complete_with_tools(self, messages, action):
        if "Prépare les notes" not in messages[-1]["content"]:
            return await self.complete(messages)
        self.requests.append(messages)
        record_model_usage(180, 40)
        await action.create_document(json.dumps({"filename": "projet.txt", "content": "Notre monde se nomme Sora."}))
        action.used = True
        await action(json.dumps({"kind": "ordinary", "summary": "Le monde du projet se nomme Sora.",
                                 "significance": "Repère choisi par Jade."}))
        return "[INTENT:excited] Les notes du monde Sora sont prêtes."


async def eventually(predicate, timeout=2):
    async def wait():
        while not predicate():
            await asyncio.sleep(.002)
    await asyncio.wait_for(wait(), timeout)


class LiveRuntimeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.model = Model()
        self.store = MemoryStore(root / "memory.sqlite3")
        self.store.enable(OWNER)
        self.memory = MemoryService(self.store, self.model)
        self.documents = DocumentService(root / "documents", memory_store=self.store, access_mode="owner")
        self.classic = []

        async def on_reply(reply):
            self.classic.append(reply)

        self.runtime = Runtime(Dialogue(self.model, "Tu es Jade."), on_reply,
                               memory_service=self.memory, document_service=self.documents)
        await self.runtime.start()
        config = LiveConfig(enabled=True, max_session_seconds=30,
            budget_db_path=str(root / "budget.sqlite3"), session_db_path=str(root / "sessions.sqlite3"),
            daily_usd=Decimal("10"), monthly_usd=Decimal("100"),
            backend_reservation_usd=Decimal(".10"), close_timeout_seconds=1)
        self.provider = FakeProvider()
        self.manager = await create_mobile_live(self.runtime,
            SimpleNamespace(live=config, api_key="offline-test-key"), provider=self.provider)
        self.ledger = self.manager.budget
        self.bridge = self.manager.bridge
        self.bridge.fragment_wait_seconds = 0
        await self.manager.set_mode("Goldaj", "live", 0)
        self.client, self.thread = "client_live_0001", "thread_live_0001"
        armed = await self.manager.arm("Goldaj", self.client, self.thread)
        self.lease = armed["lease_id"]
        self.subscription, self.control = await self.manager.subscribe("Goldaj", self.client, self.lease)
        self.opened = await self.manager.create_session("Goldaj", self.client, self.thread,
            self.lease, "request_live_0001", SDP)
        self.handle = self.opened["session_id"]
        self.channel = self.provider.channels["provider_session_1"]
        await eventually(lambda: self.manager._sessions[self.handle].started.is_set())

    async def asyncTearDown(self):
        await self.manager.stop()
        await self.bridge.close()
        await self.runtime.stop(graceful=False, timeout=1)
        await self.memory.close()
        await self.documents.close()
        self.temp.cleanup()

    async def test_provider_to_tools_to_chat_and_memory_then_classic(self):
        transcript = {"type": "session.input_transcript.delta", "event_id": "input-1",
            "delta": "Prépare les notes de notre monde Sora.", "start_ms": 0, "end_ms": 1000}
        delegation = {"type": "session.delegation.created", "event_id": "delegation-event-1", "offset_ms": 1000,
            "delegation": {"id": "delegate1", "type": "delegation", "target": "client"}}
        await self.channel.events.put(transcript)
        await self.channel.events.put(delegation)
        await self.channel.events.put(delegation)  # Replayed sideband event.
        await eventually(lambda: any(e["type"] == "session.commentary.append" for e in self.channel.sent))
        await eventually(lambda: not self.manager._sessions[self.handle].pending_delegations)
        await eventually(lambda: any(len(state.chunks) > 1 for state in self.bridge.sessions.values()))
        self.assertEqual(self.classic, [])
        self.assertEqual(len(self.model.requests), 1)
        self.assertEqual(len(self.store.list_for_account(OWNER)), 1)
        self.assertEqual(len(list(self.documents.store.directory.glob("*.bin"))), 1)
        projected = []
        while not self.control.empty():
            projected.append(self.control.get_nowait())
        attachments = [event for event in projected if event["type"] == "attachments"]
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["session_id"], self.handle)
        self.assertTrue(any(e["type"] == "transcript" for e in projected))
        self.assertNotIn("provider_session_1", str(projected))
        snapshot = self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot["daily"]["backend_usd"]), Decimal(".10"))
        self.assertGreaterEqual(Decimal(snapshot["daily"]["estimated_usd"]), Decimal(".10"))

        await self.manager.close("Goldaj", self.client, self.lease, reason="text_selected")
        await eventually(lambda: self.manager._sessions[self.handle].closed.is_set())
        if self.bridge._flush_tasks:
            await asyncio.gather(*self.bridge._flush_tasks)
        history = self.store.recent_conversation_turns(OWNER, "person")
        self.assertIn("Prépare les notes", str(history))
        self.assertIn("Les notes du monde Sora", str(history))
        self.assertIn("interrompue", str(history))
        incoming = Incoming("mobile", "Goldaj", "Résume notre projet.", channel=self.thread,
                            message_id="classic-after-live", force_reply=True)
        reply = asyncio.get_running_loop().create_future()
        await self.runtime.submit(incoming, result=reply)
        await reply
        await self.runtime.idle()
        self.assertEqual(len(self.classic), 1)
        self.assertIn("Les notes du monde Sora", str(self.model.requests[-1]))
        self.assertEqual(self.manager.snapshot("Goldaj")["lease_state"], "closed")
        self.assertEqual(sum(e["type"] == "session.close" for e in self.channel.sent), 1)

    async def test_old_session_projection_cannot_reach_new_thread(self):
        context = self.manager._context(self.manager._sessions[self.handle])
        await self.manager.close("Goldaj", self.client, self.lease, reason="new_thread")
        await eventually(lambda: self.manager._sessions[self.handle].closed.is_set())
        new = await self.manager.arm("Goldaj", self.client, "thread_live_0002")
        _token, new_queue = await self.manager.subscribe("Goldaj", self.client, new["lease_id"])
        await self.manager.publish(context, {"type": "live_delegation", "intent": "excited", "attachments": []})
        await self.manager.publish(context, {"type": "live_transcript", "segments": []})
        self.assertTrue(new_queue.empty())
        with self.assertRaises(LiveSessionError):
            await self.manager.observe_playback("Goldaj", self.client, new["lease_id"],
                {"session_id": self.handle, "state": "drained"})


class LiveRuntimeFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_optional_live_sqlite_failures_preserve_classic_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = Model()
            delivered = []

            async def on_reply(reply):
                delivered.append(reply)

            runtime = Runtime(Dialogue(model, "Tu es Jade."), on_reply)
            await runtime.start()
            try:
                for index, component in enumerate(("LiveBudgetLedger", "LiveSessionManager", "LiveConversationBridge")):
                    with self.subTest(component=component):
                        config = LiveConfig(enabled=True, budget_db_path=str(root / str(index) / "budget.sqlite3"),
                            session_db_path=str(root / str(index) / "sessions.sqlite3"),
                            daily_usd=Decimal("10"), monthly_usd=Decimal("100"))
                        provider = FakeProvider()
                        with patch("src.jade_runtime.live_runtime." + component,
                                   side_effect=sqlite3.OperationalError("simulated unavailable storage")):
                            manager = await create_mobile_live(runtime,
                                SimpleNamespace(live=config, api_key="offline-test-key"), provider=provider)
                        try:
                            if manager is not None:
                                self.assertFalse((await manager.capabilities("Goldaj"))["available"])
                            result = asyncio.get_running_loop().create_future()
                            await runtime.submit(Incoming("mobile", "Goldaj", "Toujours disponible ?",
                                channel="classic-fallback", message_id="fallback-" + str(index), force_reply=True),
                                result=result)
                            await result
                            await runtime.idle()
                            self.assertEqual(len(delivered), index + 1)
                            self.assertEqual(provider.created, [])
                        finally:
                            if manager is not None:
                                await manager.stop()
                                if manager.bridge is not None:
                                    await manager.bridge.close()
            finally:
                await runtime.stop(graceful=False, timeout=1)


if __name__ == "__main__":
    unittest.main()
