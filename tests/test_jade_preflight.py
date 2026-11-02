"""Offline preflight must not contact any accounts or hardware."""
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.jade_runtime.config import Settings
from src.jade_runtime.diagnostics import inspect_environment


class DiagnosticsTests(unittest.TestCase):
    def test_plain_offline_preflight_requires_no_keys(self):
        result = inspect_environment(Settings())
        self.assertTrue(all(item.ok for item in result))
        self.assertEqual(len(result), 1)

    def test_services_require_explicit_live(self):
        result = inspect_environment(Settings(), mic=True)
        self.assertTrue(any(c.name == "Mode live" and not c.ok for c in result))

    def test_openai_key_never_written_to_diagnostic_output(self):
        secret = "super-private-test-key-000"
        with patch("src.jade_runtime.diagnostics._installed", return_value=True):
            items = inspect_environment(Settings(api_key=secret), live=True)
        self.assertTrue(all(item.ok for item in items))
        self.assertNotIn(secret, repr(items))

    def test_audio_ffplay_missing_is_detected_without_playback(self):
        with patch("src.jade_runtime.diagnostics.which", return_value=None):
            items = inspect_environment(Settings(api_key="test", audio_output="ffplay"),
                                        live=True, voice=True)
        self.assertTrue(any(c.name == "Lecture locale WAV" and not c.ok for c in items))

    def test_phone_http_is_not_marked_public_or_enabled_by_default(self):
        with patch("src.jade_runtime.diagnostics.which", return_value=None):
            items = inspect_environment(Settings(api_key="test"), live=True, http=True)
        self.assertTrue(any(c.name == "API web privée" and not c.ok for c in items))
        self.assertTrue(any(not c.required and not c.ok for c in items))

    def test_voice_discord_requires_ffmpeg(self):
        with patch("src.jade_runtime.diagnostics.which", return_value=None):
            items = inspect_environment(Settings(api_key="test"),
                                        live=True, discord=True, voice=True, discord_voice=True)
        self.assertTrue(any(c.name == "FFmpeg Discord" and not c.ok for c in items))

    def test_twitch_vts_discord_explicit_config_required(self):
        with patch("src.jade_runtime.diagnostics._installed", return_value=True):
            items = inspect_environment(Settings(api_key="test"),
                                        live=True, twitch=True, vts=True, discord=True)
        self.assertTrue(any(c.name == "Twitch activé" and not c.ok for c in items))
        self.assertTrue(any(c.name == "VTube Studio autorisé" and not c.ok for c in items))
        self.assertTrue(any(c.name == "Discord activé" and not c.ok for c in items))

    def test_cli_demo_preflight_never_needs_openai_account(self):
        # Fix both ends of the pipe: a UTF-8 test runner can spawn a child
        # that otherwise writes using the Windows legacy code page.
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run([sys.executable, "main.py", "--preflight"],
                                text=True, encoding="utf-8", env=env,
                                capture_output=True, check=False, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Aucun appel OpenAI", result.stdout)


if __name__ == "__main__":
    unittest.main()
