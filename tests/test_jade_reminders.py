"""DEV-036: private persistence and push scheduler, no network or billed LLM."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

from src.jade_runtime.reminders import (
    ReminderAction, ReminderService, ReminderStore, _valid_due, _valid_subscription,
)


def future(minutes=10):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


class TestReminderStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "jade-reminders.sqlite3"
        self.store = ReminderStore(self.path)

    def test_create_persists_and_recovers_across_restart(self):
        created = self.store.create("Rendez-vous", future(), "mobile")
        self.assertEqual(created["state"], "pending")
        rows = ReminderStore(self.path).list()
        self.assertEqual(rows[0]["id"], created["id"])
        self.assertEqual(rows[0]["title"], "Rendez-vous")
        self.assertEqual(ReminderStore(self.path).get(created["id"])["title"], "Rendez-vous")
        self.assertIsNone(self.store.get("0" * 24))

    def test_timezone_required_and_future_only(self):
        with self.assertRaises(ValueError):
            _valid_due("2026-11-22T18:30:00")
        with self.assertRaises(ValueError):
            _valid_due("1990-01-01T00:00:00+00:00")
        self.assertGreater(_valid_due(future()), 0)

    def test_update_cancel_and_no_double_claim(self):
        created = self.store.create("Relire", future(), "mobile")
        changed = self.store.change(created["id"], title="Relire le chapitre")
        self.assertEqual(changed["title"], "Relire le chapitre")
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE reminders SET due_at=1 WHERE id=?", (created["id"],))
        self.assertEqual(len(self.store.claim_due()), 1)
        self.assertEqual(self.store.claim_due(), [])
        self.store.complete(created["id"], True)
        self.assertEqual(self.store.get(created["id"])["state"], "sent")
        self.assertEqual(self.store.claim_due(), [])
        self.store.change(created["id"], due_at=future())
        self.assertEqual(self.store.get(created["id"])["state"], "pending")
        self.store.change(created["id"], cancel=True)
        self.assertEqual(self.store.get(created["id"])["state"], "cancelled")

    def test_expired_push_subscription_and_allowlisted_https_only(self):
        fake = {"endpoint": "https://fcm.googleapis.com/fcm/send/" + "x" * 40,
                "keys": {"p256dh": "y" * 87, "auth": "z" * 22}}
        _valid_subscription(fake)
        self.store.subscribe(fake)
        self.assertEqual(len(self.store.subscriptions()), 1)
        self.store.unsubscribe(fake["endpoint"])
        self.assertEqual(self.store.subscriptions(), [])
        fake["endpoint"] = "https://127.0.0.1/attacker"
        with self.assertRaises(ValueError):
            self.store.subscribe(fake)
        fake["endpoint"] = "http://fcm.googleapis.com/send/test"
        with self.assertRaises(ValueError):
            self.store.subscribe(fake)


class TestReminderAction(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = ReminderService(Path(self.tmp.name) / "reminders.sqlite3")

    async def test_owner_mobile_create_list_update_cancel(self):
        action = ReminderAction(self.service, "mobile", "")
        created = await action.manage_reminder(json.dumps({
            "action": "create", "title": "Examen", "due_at": future(), "id": None}))
        self.assertEqual(created["status"], "ok")
        item_id = created["reminder"]["id"]
        listed = await action.manage_reminder(
            json.dumps({"action": "list", "title": None, "due_at": None, "id": None}))
        self.assertEqual(listed["items"][0]["id"], item_id)
        updated = await action.manage_reminder(json.dumps({
            "action": "update", "title": "Examen déplacé", "due_at": future(12),
            "id": item_id}))
        self.assertEqual(updated["reminder"]["title"], "Examen déplacé")
        cancelled = await action.manage_reminder(json.dumps({
            "action": "cancel", "title": None, "due_at": None, "id": item_id}))
        self.assertEqual(cancelled["reminder"]["state"], "cancelled")

    async def test_no_owner_action_for_unknown_discord(self):
        class Incoming:
            platform = "discord"
            account_id = "123456789123456789"
            channel = "123456789123456789"
        self.assertIsNone(await self.service.for_turn(Incoming()))

    async def test_push_dispatch_is_independent_of_phone_page_and_llm(self):
        created = self.service.store.create("Ce soir", future(), "mobile")
        fake = {"endpoint": "https://fcm.googleapis.com/fcm/send/" + "x" * 40,
                "keys": {"p256dh": "y" * 87, "auth": "z" * 22}}
        self.service.store.subscribe(fake)
        self.service.push.send = Mock(return_value=True)
        with sqlite3.connect(self.service.store.path) as db:
            db.execute("UPDATE reminders SET due_at=1 WHERE id=?", (created["id"],))
        task = asyncio.create_task(self.service.run_forever())
        try:
            await asyncio.wait_for(self._sent(created["id"]), timeout=2)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(self.service.get_state(created["id"]), "sent") if hasattr(
            self.service, "get_state") else self.assertEqual(
                self.service.store.get(created["id"])["state"], "sent")
        self.service.push.send.assert_called_once()

    async def _sent(self, reminder_id):
        while self.service.store.get(reminder_id)["state"] != "sent":
            await asyncio.sleep(0.02)


if __name__ == "__main__":
    unittest.main()
