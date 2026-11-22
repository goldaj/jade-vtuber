"""Mobile botanical redesign regression: preserve the real Live2D bedroom and all routes."""
from pathlib import Path
import json
import unittest

from src.jade_runtime.mobile_gateway import WEB_FILES
from src.jade_runtime.mobile_icons import icon_png

ROOT = Path(__file__).resolve().parents[1] / "src/jade_runtime/mobile_web"


class BotanicalUIContract(unittest.TestCase):
    def test_home_reminders_and_views_keep_the_live_room(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for fragment in ('id="avatar-container"', 'class="room"', 'room-spring.webp',
                         'id="home-reminder-list"', 'id="reminders-panel"',
                         'id="messages"', 'id="composer"', 'id="mic"',
                         'id="auth-modal"', 'id="auth-token"'):
            self.assertIn(fragment, html)
        for view in ("home", "reminders", "chat", "activities", "profile"):
            self.assertIn('data-view-target="' + view + '"', html)
        self.assertIn("/assets/jade-theme.css", WEB_FILES)
        css = (ROOT / "jade-theme.css").read_text(encoding="utf-8")
        self.assertIn('.shell[data-view="home"]', css)
        self.assertIn('#c8dcc7', css.lower())
        self.assertIn('#2f5d45', css.lower())
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("renderHomeReminders", app)
        self.assertIn('showView("chat")', app)
        self.assertIn('showView("reminders")', app)

    def test_manifest_flower_palette_and_png_contract(self):
        manifest = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["theme_color"].lower(), "#2f5d45")
        self.assertEqual(manifest["background_color"].lower(), "#fffdf7")
        self.assertTrue(any(x["src"] == "/icon-192.png" for x in manifest["icons"]))
        for size in (192, 512):
            png = icon_png(size)
            self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(int.from_bytes(png[16:20], "big"), size)
            self.assertEqual(int.from_bytes(png[20:24], "big"), size)


if __name__ == "__main__":
    unittest.main()
