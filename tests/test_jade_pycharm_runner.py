"""Offline checks of the IDE launch profile; no Jade runtime is started."""
from contextlib import nullcontext
import json
import logging
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tools import jade_pycharm_runner as runner


class SelectedRunModeTests(unittest.TestCase):
    def test_existing_test_configuration_keeps_its_legacy_flags(self):
        self.assertEqual(runner.selected_modes([]), (False, runner.MODES))
        self.assertEqual(runner.selected_modes(["--preflight-only"]), (True, runner.MODES))

    def test_custom_discord_mobile_configuration_is_preserved(self):
        requested = ["--live", "--discord", "--discord-voice", "--voice", "--mobile"]
        self.assertEqual(runner.selected_modes(requested), (False, tuple(requested)))
        self.assertNotIn("--avatar", runner.selected_modes(requested)[1])

    def test_custom_configuration_rejects_unrecognized_flags(self):
        with self.assertRaises(SystemExit):
            runner.selected_modes(["--discord", "--invalid"])

    def test_custom_configuration_is_forwarded_to_preflight_and_manager(self):
        requested = ["--live", "--discord", "--discord-voice", "--voice", "--mobile"]
        with patch.object(runner.sys, "argv", ["runner", *requested]), \
             patch.object(runner, "check_develop"), \
             patch.object(runner, "single_instance", return_value=nullcontext()), \
             patch.object(runner, "check_other_runtime"), \
             patch.object(runner, "load_environment"), \
             patch.object(runner.os, "chdir"), \
             patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as preflight, \
             patch("src.utility.private_config.environ", return_value="x" * 40), \
             patch("src.jade_runtime.remote_pycharm.PycharmManager") as manager:
            self.assertEqual(runner.main(), 0)
        self.assertEqual(preflight.call_args.args[0][-len(requested):], requested)
        self.assertEqual(manager.call_args.kwargs["flags"], tuple(requested))
        self.assertTrue(runner.load_environment.call_args.kwargs["preserve_runtime"])


class EnvironmentTests(unittest.TestCase):
    def test_private_files_are_loaded_only_into_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            (private / "develop-mobile.json").write_text(
                json.dumps({"origin": "https://example.invalid", "owner": "example-owner"}), encoding="utf-8")
            (private / "develop-mobile.token").write_text("dummy-token", encoding="utf-8")
            (private / "config.env").write_text("", encoding="utf-8")
            env = {"JADE_PYCHARM_PRIVATE_DIR": str(private),
                   "JADE_SECRETS_FILE": str(private / "config.env"), "PATH": "old-path"}
            runner.load_environment(env)
            self.assertEqual(env["JADE_MOBILE_TOKEN"], "dummy-token")
            self.assertEqual(env["JADE_MOBILE_ENABLED"], "1")
            self.assertEqual(env["JADE_AUDIO_OUTPUT"], "none")
            self.assertTrue(env["PATH"].endswith(os.pathsep + "old-path"))

    def test_invalid_private_config_raises_generic_message(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            (private / "develop-mobile.json").write_text('sensitive-invalid-json', encoding="utf-8")
            (private / "develop-mobile.token").write_text("dummy-token", encoding="utf-8")
            with self.assertRaises(runner.LaunchError) as error:
                runner.load_environment({"JADE_PYCHARM_PRIVATE_DIR": str(private)})
            self.assertNotIn("dummy-token", str(error.exception))
            self.assertNotIn("sensitive-invalid-json", str(error.exception))

    def test_preflight_mode_does_not_run_the_live_runtime(self):
        with patch.object(runner.sys, "argv", ["runner", "--preflight-only"]), \
             patch.object(runner, "check_develop"), patch.object(runner, "single_instance", return_value=nullcontext()), \
             patch.object(runner, "check_other_runtime"), patch.object(runner, "load_environment"), \
             patch.object(runner.os, "chdir"), \
             patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as preflight, \
             patch("src.jade_runtime.remote_pycharm.PycharmManager") as manager:
            self.assertEqual(runner.main(), 0)
        self.assertIn("--preflight", preflight.call_args.args[0])
        manager.assert_not_called()

    def test_previous_legacy_runtime_is_rejected_without_exposing_command_line(self):
        with patch.object(runner.subprocess, "run", return_value=SimpleNamespace(stdout="123\n")), \
             patch.object(runner.os, "getpid", return_value=456):
            with self.assertRaises(runner.LaunchError):
                runner.check_other_runtime()

    def test_technical_file_excludes_conversation_logger(self):
        with tempfile.TemporaryDirectory() as directory:
            with runner.technical_log(Path(directory)):
                logging.getLogger("jade.test").warning("diagnostic-synthetic")
                logging.getLogger("jade.discord").info("Discord voice reconnected")
                logging.getLogger("jade.conversation").warning("conversation-synthetic")
            contents = (Path(directory) / "jade-pycharm-diagnostics.log").read_text(encoding="utf-8")
        self.assertIn("diagnostic-synthetic", contents)
        self.assertIn("Discord voice reconnected", contents)
        self.assertNotIn("conversation-synthetic", contents)

    def test_shared_run_configurations_reference_only_the_launcher(self):
        # The safe publication preview intentionally excludes private IDE profiles.
        if not (runner.ROOT / ".run").is_dir():
            self.skipTest("PyCharm profiles are excluded from the publication preview")
        for name in ("Jade - Discord mobile (test).run.xml",
                     "Jade - verification locale (sans connexion).run.xml"):
            root = ET.parse(runner.ROOT / ".run" / name).getroot()
            options = {option.get("name"): option.get("value") for option in root.findall(".//option")}
            self.assertEqual(options["SCRIPT_NAME"], "$PROJECT_DIR$/tools/jade_pycharm_runner.py")
            self.assertEqual(options["WORKING_DIRECTORY"], "$PROJECT_DIR$")


if __name__ == "__main__":
    unittest.main()
