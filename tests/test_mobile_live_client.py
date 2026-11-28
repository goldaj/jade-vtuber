"""Offline behavioural checks for Live mobile. No hardware or provider calls."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "jade_runtime" / "mobile_web"


class MobileLiveClientTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is required for browser doubles")
    def test_client_worklet_and_app_behaviour(self):
        for filename in (
            "mobile_live_audio_worklet_test.js", "mobile_live_client_test.js",
            "mobile_live_app_test.js", "mobile_preferences_test.js", "mobile_config_app_test.js",
        ):
            with self.subTest(script=filename):
                result = subprocess.run(
                    [shutil.which("node"), str(ROOT / "tests" / filename)],
                    cwd=ROOT, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_private_single_microphone_and_safe_profile_control(self):
        html = (WEB / "salon.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="mic"'), 1)
        self.assertEqual(html.count('id="live-mode-toggle"'), 1)
        profile = html.split('id="profile-intro"', 1)[1].split('</section>', 1)[0]
        self.assertIn('id="live-mode-toggle"', profile)
        live_input = re.search(r'<input\b[^>]*id="live-mode-toggle"[^>]*>', profile)
        self.assertIsNotNone(live_input)
        self.assertIn('type="checkbox"', live_input.group(0))
        self.assertNotIn("aria-pressed", live_input.group(0))
        for filename in ("live-client.js", "live-audio-worklet.js"):
            source = (WEB / filename).read_text(encoding="utf-8")
            for forbidden in ("localStorage.", "sessionStorage.", "indexedDB.", "OPENAI_API_KEY", "navigator.sendBeacon"):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
