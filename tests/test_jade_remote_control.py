"""Offline coverage for the private PyCharm Run control plane."""
import asyncio
from pathlib import Path
import tempfile
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.jade_runtime import remote_pycharm
from src.jade_runtime.remote_control import ControlService


class GitUpdateTests(unittest.TestCase):
    def test_refuse_other_branch(self):
        with patch.object(remote_pycharm, "git", return_value="main") as git:
            with self.assertRaisesRegex(remote_pycharm.GitRefusal, "wrong_branch"):
                remote_pycharm.plan_develop_update(Path("."))
        self.assertEqual(git.call_count, 1)

    def test_reject_divergent_remote_head(self):
        with patch.object(remote_pycharm, "git",
                          side_effect=["develop", "old-sha", "", "new-sha"]), \
             patch.object(remote_pycharm.subprocess, "run",
                          return_value=SimpleNamespace(returncode=1)):
            with self.assertRaisesRegex(remote_pycharm.GitRefusal, "not_fast_forward"):
                remote_pycharm.plan_develop_update(Path("."))

    def test_accept_fast_forward_only(self):
        with patch.object(remote_pycharm, "git",
                          side_effect=["develop", "old-sha", "", "new-sha"]) as git, \
             patch.object(remote_pycharm.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0)):
            self.assertEqual(remote_pycharm.plan_develop_update(Path(".")),
                             ("old-sha", "new-sha"))
        self.assertEqual(git.call_args_list[2].args[1:], ("fetch", "origin", "+refs/heads/develop:refs/remotes/origin/develop"))


@unittest.skipUnless(shutil.which("git"), "Git required for local integration tests")
class RealGitUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.origin, self.checkout = root / "origin", root / "checkout"
        self.origin.mkdir()
        self.run_git(self.origin, "init", "-b", "develop")
        self.run_git(self.origin, "config", "user.email", "test@example.invalid")
        self.run_git(self.origin, "config", "user.name", "Test")
        for name in ("runtime.txt", "local.txt"):
            (self.origin / name).write_text("old\n", encoding="utf-8")
        self.run_git(self.origin, "add", ".")
        self.run_git(self.origin, "commit", "-m", "initial")
        self.run_git(root, "clone", str(self.origin), str(self.checkout))
        (self.origin / "runtime.txt").write_text("new\n", encoding="utf-8")
        self.run_git(self.origin, "commit", "-am", "update")

    def run_git(self, root, *args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_preserves_unrelated_tracked_and_untracked_files(self):
        (self.checkout / "local.txt").write_text("mine\n", encoding="utf-8")
        (self.checkout / "private.txt").write_text("private\n", encoding="utf-8")
        old, target = remote_pycharm.plan_develop_update(self.checkout)
        remote_pycharm.apply_develop_update(self.checkout, old, target)
        self.assertEqual(self.run_git(self.checkout, "rev-parse", "HEAD"), target)
        self.assertEqual((self.checkout / "local.txt").read_text(), "mine\n")
        self.assertEqual((self.checkout / "private.txt").read_text(), "private\n")
        self.assertEqual((self.checkout / "runtime.txt").read_text(), "new\n")

    def test_conflicting_local_change_is_not_overwritten(self):
        (self.checkout / "runtime.txt").write_text("mine\n", encoding="utf-8")
        old, target = remote_pycharm.plan_develop_update(self.checkout)
        with self.assertRaisesRegex(remote_pycharm.GitRefusal, "git_merge_failed"):
            remote_pycharm.apply_develop_update(self.checkout, old, target)
        self.assertEqual(self.run_git(self.checkout, "rev-parse", "HEAD"), old)
        self.assertEqual((self.checkout / "runtime.txt").read_text(), "mine\n")

    def test_git_error_is_reported_without_remote_credentials(self):
        with patch.object(remote_pycharm.subprocess, "run", return_value=SimpleNamespace(
                returncode=1, stderr="fatal: authentication failed https://user:secret@example.invalid/repo")):
            with self.assertRaisesRegex(remote_pycharm.GitRefusal, "authentication failed") as error:
                remote_pycharm.git(self.checkout, "fetch", "origin")
        self.assertNotIn("secret", str(error.exception))


class CustomRunOptionsTests(unittest.TestCase):
    def test_manager_starts_child_with_exact_pycharm_flags(self):
        expected = ("--live", "--discord", "--discord-voice", "--voice", "--mobile")
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(remote_pycharm, "_WindowsJob") as job, \
             patch.object(remote_pycharm, "git", side_effect=["abc123", "develop"]), \
             patch.object(remote_pycharm.subprocess, "Popen") as popen:
            child = popen.return_value
            child.pid = 12345
            child.stdout = None
            manager = remote_pycharm.PycharmManager(
                Path(folder), "x" * 40, log_dir=Path(folder), flags=expected)
            try:
                manager._start_child()
                self.assertEqual(popen.call_args.args[0][-len(expected):], list(expected))
                self.assertNotIn("--avatar", popen.call_args.args[0])
                self.assertEqual(manager.status()["pid"], 12345)
                job.return_value.assign.assert_called_once_with(child)
            finally:
                manager.file_handler.close()
                manager.job.close()

    def test_manager_rejects_unexpected_flags(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                remote_pycharm.PycharmManager(
                    Path(folder), "x" * 40, log_dir=Path(folder),
                    flags=("--discord", "--arbitrary-command"))


class RuntimeStopTests(unittest.TestCase):
    def test_pycharms_stop_flag_is_not_a_global_runtime_setting(self):
        # A separate process only reacts when its own private flag is present.
        with tempfile.TemporaryDirectory() as folder:
            flag = Path(folder) / "stop.flag"
            flag.touch()
            from main import _watch_runner_stop, _RunnerStopRequested
            with self.assertRaises(_RunnerStopRequested):
                asyncio.run(_watch_runner_stop(str(flag)))

    def test_manager_does_not_create_another_jade_without_pycharm_run(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(remote_pycharm, "git", return_value="abc123"):
                manager = remote_pycharm.PycharmManager(
                    Path(folder), "x" * 40, log_dir=Path(folder))
            try:
                status = manager.status()
                self.assertFalse(status["running"])
                self.assertTrue(status["pycharm_run"])
                self.assertEqual(status["branch"], "develop")
            finally:
                manager.file_handler.close()
                manager.job.close()


class ControlTests(unittest.TestCase):
    def test_controller_rejects_wrong_credentials_and_non_tailscale_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                ControlService(Path(folder), owner="owner@example.com",
                               origin="http://example.com", mobile_token="x"*40,
                               ipc_token="y"*40, log_dir=Path(folder))

    def test_when_pycharm_is_closed_the_controller_reports_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            service = ControlService(Path(folder), owner="owner@example.com",
                origin="https://jade.example.ts.net", mobile_token="x"*40,
                ipc_token="y"*40, log_dir=Path(folder))
            with patch.object(service, "runner_request",
                              return_value=(503, {"error":"pycharm_run_not_available"})):
                snapshot = service.status()
            self.assertFalse(snapshot["pycharm_run"])
            self.assertFalse(snapshot["running"])
            self.assertEqual(snapshot["branch"], "develop")

    def test_logs_are_bounded_and_not_arbitrary_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = ControlService(root, owner="owner@example.com",
                origin="https://jade.example.ts.net", mobile_token="x"*40,
                ipc_token="y"*40, log_dir=root)
            (root / "jade-pycharm-console.log").write_text(
                "INFO hello\nERROR failure\n", encoding="utf-8")
            self.assertIn("ERROR failure", service.logs())
            self.assertNotIn("password=", service.logs())


if __name__ == "__main__":
    unittest.main()
