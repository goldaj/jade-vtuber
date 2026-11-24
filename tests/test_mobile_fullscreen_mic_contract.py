"""Regression contract for the single microphone in the immersive PWA."""
from pathlib import Path
import re
import unittest


WEB = Path(__file__).resolve().parents[1] / "src" / "jade_runtime" / "mobile_web"


class MobileFullscreenMicContract(unittest.TestCase):
    def test_immersive_dock_is_visible_and_interactive_in_every_view(self):
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        self.assertIn('.shell:not([data-view="home"]):not(.is-room-only) .room-bottom{display:none}', css)
        self.assertNotIn('.shell.is-room-only .room-bottom{display:none', css)
        dock = re.search(r"\.shell\.is-room-only \.room-bottom\{([^}]+)\}", css)
        self.assertIsNotNone(dock)
        self.assertIn("display:flex", dock.group(1))
        self.assertIn("justify-content:center", dock.group(1))
        self.assertIn("safe-area-inset-bottom", dock.group(1))
        button = re.search(r"\.shell\.is-room-only \.room-bottom #mic\{([^}]+)\}", css)
        self.assertIsNotNone(button)
        self.assertIn("pointer-events:auto", button.group(1))
        self.assertIn(".shell.is-room-only .room-bottom #mic.recording{", css)
        self.assertIn(".shell.is-room-only .conversation,.shell.is-room-only .app-nav{display:none!important}", css)

    def test_single_button_moves_without_resetting_audio_or_recording(self):
        js = (WEB / "app.js").read_text(encoding="utf-8")
        html = (WEB / "salon.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="mic"'), 1)
        placement = js.split("function syncMicPlacement() {", 1)[1].split("function showView(", 1)[0]
        self.assertIn('shell.dataset.view === "home" || shell.classList.contains("is-room-only")', placement)
        self.assertIn("dock.appendChild?.(mic)", placement)
        self.assertIn("form.insertBefore(mic, input)", placement)
        self.assertNotIn("soundEnabled", placement)
        self.assertNotIn("recording =", placement)
        self.assertIn("shell.dataset.view = view;\n    syncMicPlacement();", js)
        self.assertIn('shell.classList.toggle("is-room-only", active);\n    syncMicPlacement();', js)


if __name__ == "__main__":
    unittest.main()
