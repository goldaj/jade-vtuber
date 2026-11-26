"""Mobile botanical redesign regression: preserve the real Live2D bedroom and all routes."""
from pathlib import Path
import json
import unittest

from src.jade_runtime.mobile_gateway import WEB_FILES
from src.jade_runtime.mobile_icons import icon_png

ROOT = Path(__file__).resolve().parents[1] / "src/jade_runtime/mobile_web"


class BotanicalUIContract(unittest.TestCase):
    def test_navigation_and_immersive_room_keep_the_live_room(self):
        login = (ROOT / "index.html").read_text(encoding="utf-8")
        html = (ROOT / "salon.html").read_text(encoding="utf-8")
        for fragment in ('id="avatar-container"', 'class="room"', 'room-bedroom-portrait.avif',
                         'id="reminders-panel"', 'id="reminders-list"',
                         'id="messages"', 'id="composer"', 'id="mic"'):
            self.assertIn(fragment, html)
        for view in ("home", "reminders", "chat", "profile"):
            self.assertIn('data-view-target="' + view + '"', html)
        self.assertIn("/assets/jade-theme.css", WEB_FILES)
        self.assertIn("/assets/splash-jade.png", WEB_FILES)
        self.assertIn("/assets/splash.js", WEB_FILES)
        self.assertIn('id="jade-launch-splash"', login)
        self.assertIn('src="/assets/splash-jade.png"', login)
        self.assertIn('src="/assets/splash.js"', login)
        self.assertIn('src="/assets/login-guard.js"', login)
        self.assertNotIn('src="/assets/app.js"', login)
        self.assertNotIn('src="/vendor/', login)
        self.assertNotIn('href="/assets/styles.css"', login)
        self.assertNotIn('class="room"', login)
        self.assertIn('href="/assets/login.css"', login)
        self.assertIn("/assets/salon.html", WEB_FILES)
        self.assertIn("/assets/login.css", WEB_FILES)
        self.assertIn("/assets/login-guard.js", WEB_FILES)
        self.assertIn("object-fit:cover", (ROOT / "jade-theme.css").read_text(encoding="utf-8"))
        splash_js = (ROOT / "splash.js").read_text(encoding="utf-8")
        self.assertNotIn('addEventListener("load", dismissSplash', splash_js)
        self.assertIn("  dismissSplash();", splash_js)
        css = (ROOT / "jade-theme.css").read_text(encoding="utf-8")
        self.assertIn('.shell[data-view="home"]', css)
        self.assertIn('#c8dcc7', css.lower())
        self.assertIn('#2f5d45', css.lower())
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertNotIn('id="home-reminder-list"', html)
        self.assertNotIn('id="activities-overview"', html)
        self.assertNotIn('data-view-target="activities"', html)
        self.assertLess(html.index('id="reminders-list"'), html.index('id="reminder-create-panel"'))
        self.assertIn('<details id="reminder-create-panel"', html)
        self.assertIn('type="radio" id="notifications-on"', html)
        self.assertIn('type="radio" id="notifications-off"', html)
        self.assertIn('src="/icon.svg" width="40"', html)
        self.assertIn('class="deployment-actions"', html)
        self.assertIn('showView("reminders")', app)
        self.assertIn("refreshNotificationChoice()", app)
        self.assertIn("setRoomFullscreen(true)", app)
        self.assertNotIn("renderHomeReminders", app)
        self.assertIn('.shell.is-room-only .room{', css)

    def test_login_card_is_minimal_and_sharp_splash_is_preserved(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        auth = html.split('<div id="auth-modal"', 1)[1].split("</form>", 1)[0]
        for fragment in ('class="auth-heading"', 'src="/icon.svg" width="44"',
                         '>Espace privé de Jade</h1>', ">Jeton d'accès</label>",
                         'id="auth-token" type="password"', '>Entrer dans le salon</button>'):
            self.assertIn(fragment, auth)
        self.assertIn('id="auth-feedback"', auth)
        self.assertIn("novalidate", auth)
        self.assertIn('"/api/auth"', (ROOT / "login-guard.js").read_text(encoding="utf-8"))
        self.assertNotIn("<p>", auth)
        self.assertNotIn("<small>", auth)
        self.assertNotIn("Tailscale", auth)
        self.assertNotIn("placeholder=", auth)
        css = (ROOT / "login.css").read_text(encoding="utf-8")
        auth_layer = css.split(".auth-layer{", 1)[1].split("}", 1)[0]
        self.assertIn('url("/assets/splash-jade.png")', auth_layer)
        # The initial splash used to mask the modal until window.load fired.
        self.assertIn("z-index:100000", auth_layer)
        self.assertIn("z-index:99999", css.split(".jade-launch-splash{", 1)[1].split("}", 1)[0])
        self.assertIn("backdrop-filter:none", auth_layer)
        self.assertIn("cover no-repeat", auth_layer)
        self.assertIn("transform:translateY(clamp(", css)
        self.assertIn("@media(max-height:520px)", css)
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('modal.classList.add("hidden")', js)
        self.assertIn('modal.classList.remove("hidden")', js)

    def test_manifest_flower_palette_and_png_contract(self):
        manifest = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["theme_color"].lower(), "#2f5d45")
        self.assertEqual(manifest["background_color"].lower(), "#fffdf7")
        self.assertTrue(any(x["src"] == "/icon.svg" and x["sizes"] == "any" for x in manifest["icons"]))
        image = (ROOT / "splash-jade.png").read_bytes()
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(any(x["src"] == "/icon-192.png" for x in manifest["icons"]))
        for size in (192, 512):
            png = icon_png(size)
            self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(int.from_bytes(png[16:20], "big"), size)
            self.assertEqual(int.from_bytes(png[20:24], "big"), size)


if __name__ == "__main__":
    unittest.main()
