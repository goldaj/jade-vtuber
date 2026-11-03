"""Synthetic rotation tests: no real credentials, provider or private backup."""
import asyncio
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

from src.jade_runtime.twitch_rotation import (
    BackupPending, RotationError, RotationUncertain, TwitchTokenManager, _lock, _refresh,
    watch_twitch_token,
)
from src.jade_runtime.twitch_token import TwitchIdentity, TwitchTokenError, TwitchTokenExpired


OLD = "TWITCH_TOKEN='synthetic-old-access'\nTWITCH_REFRESH_TOKEN='synthetic-old-refresh'\nTWITCH_CLIENT_ID='synthetic-client'\nOTHER='preserved'\n"
NEW_ACCESS = "synthetic-new-access"
NEW_REFRESH = "synthetic-new-refresh"
ENV_KEYS = {"TWITCH_TOKEN", "TWITCH_REFRESH_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"}


class TwitchRotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "private.env"
        self.path.write_text(OLD, encoding="utf-8")
        self.environ = patch.dict(os.environ, {k: v for k, v in os.environ.items() if k not in ENV_KEYS}, clear=True)
        self.environ.start()
        self.addCleanup(self.environ.stop)
        self.addCleanup(self.tmp.cleanup)

    def manager(self, validate, refresh, backup):
        return TwitchTokenManager(self.path, sync_backup=backup, validate=validate, refresh=refresh)

    @staticmethod
    def invalid_then_valid():
        calls = [0]
        def validate(token, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                raise TwitchTokenExpired("expired")
            return TwitchIdentity(login="testbot")
        return validate

    def test_rotation_preserves_old_file_and_backs_up_pair(self):
        backups = []
        manager = self.manager(self.invalid_then_valid(), lambda *args: (NEW_ACCESS, NEW_REFRESH),
                               lambda p: backups.append(p.read_text(encoding="utf-8")))
        state = manager.check()
        self.assertTrue(state.rotated)
        self.assertFalse(state.backup_pending)
        self.assertEqual(len(backups), 2)
        self.assertEqual(backups[0], OLD)
        self.assertIn(NEW_ACCESS, backups[1])
        self.assertIn(NEW_REFRESH, backups[1])
        self.assertIn("OTHER='preserved'", backups[1])
        snapshots = list(self.path.parent.glob("*.before-twitch-*"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_text(encoding="utf-8"), OLD)
        self.assertNotIn(NEW_ACCESS, repr(state))

    def test_backup_precheck_failure_never_consumes_refresh(self):
        refresh = lambda *args: self.fail("refresh called")
        def bad_backup(path): raise RuntimeError("private provider content")
        manager = self.manager(lambda *a, **k: (_ for _ in ()).throw(TwitchTokenExpired("expired")), refresh, bad_backup)
        with self.assertRaises(BackupPending) as caught: manager.check()
        self.assertNotIn("private provider content", str(caught.exception))
        self.assertEqual(self.path.read_text(encoding="utf-8"), OLD)
        self.assertFalse(manager.pending.exists())

    def test_uncertain_outcome_never_retries(self):
        count = [0]
        def refresh(*args):
            count[0] += 1
            raise RotationUncertain("network timeout")
        manager = self.manager(lambda *a, **k: (_ for _ in ()).throw(TwitchTokenExpired("expired")), refresh, lambda p: None)
        with self.assertRaises(RotationUncertain): manager.check()
        with self.assertRaises(RotationUncertain): manager.check()
        self.assertEqual(count[0], 1)
        self.assertTrue(manager.pending.exists())
        self.assertEqual(self.path.read_text(encoding="utf-8"), OLD)

    def test_conflict_preserves_new_pair_for_private_recovery(self):
        def refresh(*args):
            self.path.write_text(OLD + "OTHER_CHANGE='preserved'\n", encoding="utf-8")
            return NEW_ACCESS, NEW_REFRESH
        manager = self.manager(self.invalid_then_valid(), refresh, lambda p: None)
        with self.assertRaises(RotationUncertain): manager.check()
        self.assertIn("OTHER_CHANGE", self.path.read_text(encoding="utf-8"))
        recovery = list(self.path.parent.glob("*.twitch-recovery-*"))
        self.assertEqual(len(recovery), 1)
        self.assertIn(NEW_REFRESH, recovery[0].read_text(encoding="utf-8"))
        self.assertTrue(manager.pending.exists())

    def test_change_during_precheck_does_not_consume_refresh(self):
        def backup(path): path.write_text(OLD + "USER_CHANGE=1\n", encoding="utf-8")
        manager = self.manager(lambda *a, **k: (_ for _ in ()).throw(TwitchTokenExpired("expired")),
                               lambda *a: self.fail("refresh called"), backup)
        with self.assertRaises(RotationError): manager.check()
        self.assertFalse(manager.pending.exists())
        self.assertIn("USER_CHANGE", self.path.read_text(encoding="utf-8"))

    def test_backup_failure_retries_backup_not_refresh(self):
        backups, refreshes = [0], [0]
        def backup(path):
            backups[0] += 1
            if backups[0] == 2: raise RuntimeError("simulated private provider failure")
        def refresh(*args):
            refreshes[0] += 1
            return NEW_ACCESS, NEW_REFRESH
        manager = self.manager(self.invalid_then_valid(), refresh, backup)
        state = manager.check()
        self.assertTrue(state.backup_pending)
        self.assertTrue(manager.backup_pending.exists())
        state = manager.check()
        self.assertFalse(state.backup_pending)
        self.assertEqual(refreshes[0], 1)
        self.assertFalse(manager.backup_pending.exists())

    def test_bad_scope_never_refreshes_and_environment_override_fails_closed(self):
        def invalid(*args, **kwargs): raise TwitchTokenError("scope")
        manager = self.manager(invalid, lambda *a: self.fail("refresh called"), lambda p: None)
        with self.assertRaises(TwitchTokenError): manager.check()
        with patch.dict(os.environ, {"TWITCH_TOKEN": "synthetic-external"}):
            with self.assertRaises(RotationError): manager.check()

    def test_lock_rejects_concurrent_rotation(self):
        path = self.path.with_name("test-lock")
        with _lock(path):
            with self.assertRaises(RotationError):
                with _lock(path): pass

    def test_http_failures_are_classified_without_sensitive_response(self):
        with patch("src.jade_runtime.twitch_rotation.build_opener") as opener:
            opener.return_value.open.side_effect = HTTPError("https://example.invalid", 401,
                "synthetic-secret", {}, io.BytesIO(b"synthetic-secret"))
            with self.assertRaises(RotationError) as caught:
                _refresh("synthetic-refresh", "synthetic-client", "synthetic-secret")
            self.assertNotIsInstance(caught.exception, RotationUncertain)
            self.assertNotIn("synthetic-secret", str(caught.exception))
            opener.return_value.open.side_effect = URLError("synthetic-secret")
            with self.assertRaises(RotationUncertain) as caught:
                _refresh("synthetic-refresh", "synthetic-client", "synthetic-secret")
            self.assertNotIn("synthetic-secret", str(caught.exception))

    def test_http_encodes_restricted_refresh_characters_and_keeps_new_pair(self):
        response = b'{"access_token":"synthetic-access+test", "refresh_token":"synthetic-refresh%3Dtest="}'
        fake = io.BytesIO(response)
        with patch("src.jade_runtime.twitch_rotation.build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value = fake
            access, refresh = _refresh("synthetic+refresh/old=", "synthetic-client", "synthetic-secret")
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(parse_qs(request.data.decode())["refresh_token"], ["synthetic+refresh/old="])
            self.assertNotIn("synthetic", request.full_url)
            self.assertEqual((access, refresh), ("synthetic-access+test", "synthetic-refresh%3Dtest="))


class TwitchWatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_hourly_watcher_routes_rotation_and_pending_backup(self):
        state = type("State", (), {"rotated": True, "backup_pending": True})()
        manager = type("Manager", (), {"check": lambda self: state})()
        on_rotation, on_pending = AsyncMock(), AsyncMock()
        with patch("src.jade_runtime.twitch_rotation.asyncio.sleep", new=AsyncMock()) as sleep:
            async def stop(value): raise asyncio.CancelledError()
            on_rotation.side_effect = stop
            with self.assertRaises(asyncio.CancelledError):
                await watch_twitch_token(manager, on_rotation, on_pending, interval=3600)
            sleep.assert_awaited_once_with(3600)
            on_pending.assert_awaited_once()
            on_rotation.assert_awaited_once_with(state)

    async def test_interval_over_one_hour_is_rejected(self):
        with self.assertRaises(ValueError):
            await watch_twitch_token(None, None, None, interval=3601)


if __name__ == "__main__":
    unittest.main()
