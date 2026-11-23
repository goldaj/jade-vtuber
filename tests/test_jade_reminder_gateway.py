"""DEV-036: authenticated HTTP routes, independent of any real push provider."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from src.jade_runtime.mobile_gateway import MobileGateway
from src.jade_runtime.reminders import ReminderService


class MobileReminderHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        reminders = ReminderService(Path(self.folder.name) / "jade-reminders.sqlite3")
        self.mobile = MobileGateway(
            SimpleNamespace(document_service=None), None,
            token="k" * 40, reminder_service=reminders)
        self.server = await asyncio.start_server(
            self.mobile._accept, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        if self.mobile.connections:
            await asyncio.gather(*self.mobile.connections, return_exceptions=True)

    async def request(self, route, payload, *, authenticated=True, origin=None):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        data = json.dumps(payload).encode()
        fields = [
            f"POST {route} HTTP/1.1",
            f"Host: 127.0.0.1:{self.port}",
            f"Content-Length: {len(data)}",
            "Content-Type: application/json",
        ]
        if authenticated:
            fields.append("Authorization: Bearer " + "k" * 40)
        if origin:
            fields.append("Origin: " + origin)
        writer.write(("\r\n".join(fields) + "\r\n\r\n").encode() + data)
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), 4)
        writer.close()
        await writer.wait_closed()
        header, body = response.split(b"\r\n\r\n", 1)
        return int(header.split(b" ", 2)[1]), json.loads(body)

    async def test_owner_can_create_open_update_cancel_and_list(self):
        stamp = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        request = {"action": "create", "id": None, "title": "Un rappel privé",
                   "due_at": stamp}
        status, body = await self.request("/api/reminders", request,
                                          authenticated=False)
        self.assertEqual(status, 401)
        status, body = await self.request("/api/reminders", request,
                                          origin="https://evil.example")
        self.assertEqual(status, 403)
        status, body = await self.request("/api/reminders", request)
        self.assertEqual(status, 200)
        reminder_id = body["reminder"]["id"]
        self.assertEqual(len(reminder_id), 24)
        status, body = await self.request("/api/reminders",
                                          {"action": "list", "id": None,
                                           "title": None, "due_at": None})
        self.assertEqual(status, 200)
        self.assertEqual(len(body["items"]), 1)
        status, body = await self.request("/api/reminders",
                                          {"action": "get", "id": reminder_id})
        self.assertEqual(status, 200)
        self.assertEqual(body["reminder"]["title"], "Un rappel privé")
        status, body = await self.request("/api/reminders",
                                          {"action": "update", "id": reminder_id,
                                           "title": "Nouveau titre",
                                           "due_at": None})
        self.assertEqual(status, 200)
        self.assertEqual(body["reminder"]["title"], "Nouveau titre")
        status, body = await self.request("/api/reminders",
                                          {"action": "cancel", "id": reminder_id,
                                           "title": None, "due_at": None})
        self.assertEqual(status, 200)
        self.assertEqual(body["reminder"]["state"], "cancelled")
        status, _ = await self.request("/api/reminders",
                                       {"action": "get", "id": "f" * 24})
        self.assertEqual(status, 404)

    async def test_sent_reminder_requires_manual_ack_on_mobile(self):
        stamp = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        _, created = await self.request("/api/reminders", {
            "action": "create", "id": None, "title": "Lire le rappel",
            "due_at": stamp})
        reminder_id = created["reminder"]["id"]
        payload = {"action": "ack", "id": reminder_id, "title": None, "due_at": None}
        status, _ = await self.request("/api/reminders", payload,
                                       authenticated=False)
        self.assertEqual(status, 401)
        status, _ = await self.request("/api/reminders", payload)
        self.assertEqual(status, 400)
        store = self.mobile.reminders.store
        import sqlite3
        with sqlite3.connect(store.path) as db:
            db.execute("UPDATE reminders SET due_at=1 WHERE id=?", (reminder_id,))
        self.assertEqual(len(store.claim_due()), 1)
        store.complete(reminder_id, True)
        status, listed = await self.request("/api/reminders", {
            "action": "list", "id": None, "title": None, "due_at": None})
        self.assertEqual(status, 200)
        self.assertEqual([r["id"] for r in listed["items"]], [reminder_id])
        self.assertEqual(listed["items"][0]["state"], "sent")
        status, acknowledged = await self.request("/api/reminders", payload)
        self.assertEqual(status, 200)
        self.assertEqual(acknowledged["reminder"]["state"], "acknowledged")
        status, listed = await self.request("/api/reminders", {
            "action": "list", "id": None, "title": None, "due_at": None})
        self.assertEqual(status, 200)
        self.assertEqual(listed["items"], [])
        status, fetched = await self.request("/api/reminders",
                                              {"action": "get", "id": reminder_id})
        self.assertEqual(status, 200)
        self.assertEqual(fetched["reminder"]["state"], "acknowledged")

    async def test_push_requires_configuration_and_auth(self):
        status, body = await self.request("/api/push", {"action": "config"},
                                          authenticated=False)
        self.assertEqual(status, 401)
        status, body = await self.request("/api/push", {"action": "config"})
        self.assertEqual(status, 200)
        self.assertFalse(body["enabled"])
        status, body = await self.request("/api/push", {
            "action": "subscribe", "subscription": {"endpoint": "invalid"}})
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "push_not_configured")


if __name__ == "__main__":
    unittest.main()
