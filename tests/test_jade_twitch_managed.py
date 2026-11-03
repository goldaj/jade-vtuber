"""Tests of Twitch connection lifecycle; no accounts or network involved."""
import asyncio
import threading
import time
import unittest
from types import SimpleNamespace

from src.jade_runtime.twitch_managed import run_managed_twitch


class Writer:
    def __init__(self):
        self.closed = asyncio.Event()

    def close(self):
        self.closed.set()


def state(token, *, pending=False, rotated=False):
    return SimpleNamespace(access_token=token, backup_pending=pending, rotated=rotated)


class ManagedTwitchTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_connection_uses_supplied_token_and_cancels_cleanly(self):
        started, finished = asyncio.Event(), asyncio.Event()
        class Client:
            token = "old-token"
            writer = None
            async def connect_forever(self):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    finished.set()
        class Manager:
            def check(self):
                raise AssertionError("Initial check belongs to the caller")
        task = asyncio.create_task(run_managed_twitch(Client(), Manager()))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(finished.is_set())

    async def test_periodic_rotation_swaps_token_and_closes_socket(self):
        writer = Writer()
        class Client:
            token = "old-token"
            async def connect_forever(self):
                await asyncio.Event().wait()
        client = Client()
        client.writer = writer
        manager = SimpleNamespace(check=lambda: state("oauth:new-token", rotated=True))
        task = asyncio.create_task(run_managed_twitch(client, manager, interval=0.01))
        await asyncio.wait_for(writer.closed.wait(), 1)
        self.assertEqual(client.token, "new-token")
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_auth_rejection_renews_then_reconnects(self):
        connected = asyncio.Event()
        class Client:
            token = "old-token"
            writer = None
            calls = 0
            async def connect_forever(self):
                self.calls += 1
                if self.calls == 1:
                    raise PermissionError("rejected")
                connected.set()
                await asyncio.Event().wait()
        client = Client()
        manager = SimpleNamespace(check=lambda: state("new-token", rotated=True))
        task = asyncio.create_task(run_managed_twitch(client, manager))
        await asyncio.wait_for(connected.wait(), 1)
        self.assertEqual(client.token, "new-token")
        self.assertEqual(client.calls, 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_auth_rejection_with_unchanged_token_is_not_retried(self):
        class Client:
            token = "old-token"
            writer = None
            async def connect_forever(self):
                raise PermissionError("rejected")
        manager = SimpleNamespace(check=lambda: state("old-token"))
        with self.assertRaises(PermissionError):
            await asyncio.wait_for(run_managed_twitch(Client(), manager), 1)

    async def test_backup_warning_never_logs_token(self):
        writer = Writer()
        class Client:
            token = "old-token"
            async def connect_forever(self):
                await asyncio.Event().wait()
        client = Client()
        client.writer = writer
        manager = SimpleNamespace(check=lambda: state("private-synthetic-value", pending=True))
        with self.assertLogs("jade.twitch.managed", level="WARNING") as logs:
            task = asyncio.create_task(run_managed_twitch(client, manager, interval=0.01))
            await asyncio.wait_for(writer.closed.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertNotIn("private-synthetic-value", " ".join(logs.output))

    async def test_validation_failure_cancels_connection(self):
        cleaned = asyncio.Event()
        class Client:
            token = "old-token"
            writer = None
            async def connect_forever(self):
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()
        def fail():
            raise RuntimeError("synthetic failure")
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            await asyncio.wait_for(run_managed_twitch(Client(), SimpleNamespace(check=fail), interval=0.01), 1)
        self.assertTrue(cleaned.is_set())

    async def test_simultaneous_checks_are_serialized(self):
        active, peak = [0], [0]
        guard = threading.Lock()
        connected = asyncio.Event()
        class Client:
            token = "old-token"
            writer = None
            calls = 0
            async def connect_forever(self):
                self.calls += 1
                if self.calls == 1:
                    raise PermissionError("rejected")
                connected.set()
                await asyncio.Event().wait()
        def check():
            with guard:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.04)
            with guard:
                active[0] -= 1
            return state("new-token", rotated=True)
        task = asyncio.create_task(run_managed_twitch(Client(), SimpleNamespace(check=check), interval=0.005))
        await asyncio.wait_for(connected.wait(), 1)
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(peak[0], 1)

    async def test_validation_interval_is_bounded(self):
        with self.assertRaises(ValueError):
            await run_managed_twitch(None, None, interval=3601)

    async def test_shutdown_waits_for_inflight_credential_check(self):
        entered, release = threading.Event(), threading.Event()
        class Client:
            token = "old-token"
            writer = None
            async def connect_forever(self):
                await asyncio.Event().wait()
        def check():
            entered.set()
            if not release.wait(2):
                raise RuntimeError("synthetic timeout")
            return state("old-token")
        task = asyncio.create_task(run_managed_twitch(Client(), SimpleNamespace(check=check), interval=0.01))
        await asyncio.wait_for(asyncio.to_thread(entered.wait), 1)
        task.cancel()
        await asyncio.sleep(0.02)
        self.assertFalse(task.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)


if __name__ == "__main__":
    unittest.main()
