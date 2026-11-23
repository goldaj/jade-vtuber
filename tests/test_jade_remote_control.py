"""Offline coverage for the private PyCharm Run control plane."""
import asyncio
from pathlib import Path
import tempfile
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

    def test_dirty_checkout_does_not_fetch(self):
        with patch.object(remote_pycharm, "git", side_effect=["develop", " M main.py"]) as git:
            with self.assertRaisesRegex(remote_pycharm.GitRefusal, "not_clean"):
                remote_pycharm.plan_develop_update(Path("."))
        self.assertEqual(git.call_count, 2)

    def test_reject_divergent_remote_head(self):
        with patch.object(remote_pycharm, "git",
                          side_effect=["develop", "", "old-sha", "", "new-sha"]), \
             patch.object(remote_pycharm.subprocess, "run",
                          return_value=SimpleNamespace(returncode=1)):
            with self.assertRaisesRegex(remote_pycharm.GitRefusal, "not_fast_forward"):
                remote_pycharm.plan_develop_update(Path("."))

    def test_accept_fast_forward_only(self):
        with patch.object(remote_pycharm, "git",
                          side_effect=["develop", "", "old-sha", "", "new-sha"]) as git, \
             patch.object(remote_pycharm.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0)):
            self.assertEqual(remote_pycharm.plan_develop_update(Path(".")),
                             ("old-sha", "new-sha"))
        self.assertEqual(git.call_args_list[3].args[1:], ("fetch", "origin", "develop"))


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
