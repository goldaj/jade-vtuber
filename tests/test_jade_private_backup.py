"""Synthetic private-backup tests: no real credentials or network."""
import base64
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from src.jade_runtime import private_backup as backup


def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class FakeGitHub:
    def __init__(self, data):
        self.data = data
        self.private = True
        self.repo_id = 12345
        self.puts = []
        self.fail_after_put = False
        self.fail_before_put = False

    def __call__(self, method, endpoint, body=None):
        if endpoint == "repos/owner/private-backup":
            return {"id": self.repo_id, "full_name": "owner/private-backup",
                    "private": self.private, "default_branch": "main"}
        if endpoint.startswith("repos/owner/private-backup/contents/"):
            if method == "PUT":
                self.puts.append(body)
                if self.fail_before_put or body["sha"] != blob_sha(self.data):
                    raise backup.PrivateBackupError("synthetic")
                self.data = base64.b64decode(body["content"])
                if self.fail_after_put:
                    raise backup.PrivateBackupError("synthetic")
                return {}
            return {"type": "file", "encoding": "base64", "sha": blob_sha(self.data),
                    "content": base64.b64encode(self.data).decode()}
        raise AssertionError("unexpected synthetic endpoint")


class PrivateBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "active.env"
        self.path.write_text(
            "JADE_BACKUP_REPOSITORY=owner/private-backup\n"
            "JADE_BACKUP_REPOSITORY_ID=12345\n"
            "JADE_BACKUP_FILE=active.env\n"
            "TWITCH_TOKEN=" + "synthetic-" + "x" * 32 + "\n", encoding="utf-8")
        self.env = patch.dict(os.environ, {"JADE_SECRETS_FILE": str(self.path)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.github_original = backup._github
        self.fake = FakeGitHub(self.path.read_bytes())
        self.client = patch.object(backup, "_github", self.fake)
        self.client.start()
        self.addCleanup(self.client.stop)

    def test_bootstrap_update_and_idempotent_retry(self):
        backup.sync_private_backup(self.path)
        self.assertEqual(self.fake.puts, [])
        before = self.fake.data
        self.path.write_bytes(before + b"NEW_VALUE=synthetic\n")
        backup.sync_private_backup(self.path)
        self.assertEqual(len(self.fake.puts), 1)
        self.assertEqual(self.fake.puts[0]["sha"], blob_sha(before))
        self.assertEqual(self.fake.data, self.path.read_bytes())
        backup.sync_private_backup(self.path)
        self.assertEqual(len(self.fake.puts), 1)

    def test_no_state_never_overwrites_existing_remote(self):
        self.fake.data += b"external change\n"
        with self.assertRaises(backup.PrivateBackupError):
            backup.sync_private_backup(self.path)
        self.assertEqual(self.fake.puts, [])

    def test_remote_conflict_never_overwrites(self):
        backup.sync_private_backup(self.path)
        self.fake.data += b"other device\n"
        self.path.write_bytes(self.path.read_bytes() + b"rotated\n")
        with self.assertRaises(backup.PrivateBackupError):
            backup.sync_private_backup(self.path)
        self.assertEqual(self.fake.puts, [])

    def test_public_or_wrong_repository_never_receives_contents(self):
        for kind in ("public", "wrong_id"):
            self.fake.private = kind != "public"
            self.fake.repo_id = 99 if kind == "wrong_id" else 12345
            with self.assertRaises(backup.PrivateBackupError):
                backup.sync_private_backup(self.path)
            self.assertEqual(self.fake.puts, [])

    def test_ambiguous_put_is_verified_without_a_second_put(self):
        backup.sync_private_backup(self.path)
        self.path.write_bytes(self.path.read_bytes() + b"rotated\n")
        self.fake.fail_after_put = True
        backup.sync_private_backup(self.path)
        self.assertEqual(len(self.fake.puts), 1)
        self.assertEqual(self.fake.data, self.path.read_bytes())

    def test_failed_put_remains_pending_without_retry(self):
        backup.sync_private_backup(self.path)
        self.path.write_bytes(self.path.read_bytes() + b"rotated\n")
        self.fake.fail_before_put = True
        with self.assertRaises(backup.PrivateBackupError):
            backup.sync_private_backup(self.path)
        self.assertEqual(len(self.fake.puts), 1)

    def test_target_path_cannot_escape_or_select_other_file(self):
        self.path.write_text(self.path.read_text().replace("JADE_BACKUP_FILE=active.env",
                                                          "JADE_BACKUP_FILE=../leak.env"))
        with self.assertRaises(backup.PrivateBackupError):
            backup.sync_private_backup(self.path)
        self.assertEqual(self.fake.puts, [])

    def test_repository_path_traversal_is_rejected_before_network(self):
        self.path.write_text(self.path.read_text().replace("owner/private-backup", "owner/.."))
        with self.assertRaises(backup.PrivateBackupError):
            backup.sync_private_backup(self.path)
        self.assertEqual(self.fake.puts, [])

    def test_github_body_uses_stdin_and_failures_do_not_echo(self):
        secret = "synthetic-" + "z" * 40
        with patch.object(backup.subprocess, "run", return_value=SimpleNamespace(
                returncode=1, stdout=b"", stderr=secret.encode())) as run:
            with self.assertRaises(backup.PrivateBackupError) as error:
                self.github_original("PUT", "repos/owner/private-backup/contents/active.env",
                                     {"content": base64.b64encode(secret.encode()).decode()})
        args, kwargs = run.call_args
        self.assertNotIn(secret, repr(args))
        self.assertIn("--input", args[0])
        self.assertNotIn(secret, str(error.exception))
        self.assertIsInstance(kwargs["input"], bytes)


if __name__ == "__main__":
    unittest.main()
