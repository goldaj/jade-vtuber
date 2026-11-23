"""Offline layout contract for the simplified mobile app."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "src" / "jade_runtime" / "mobile_web"
HTML = (ROOT / "salon.html").read_text(encoding="utf-8")
CSS = (ROOT / "jade-theme.css").read_text(encoding="utf-8")
JS = (ROOT / "app.js").read_text(encoding="utf-8")
AVATAR = (ROOT / "avatar.js").read_text(encoding="utf-8")


class MobileUiLayoutContract(unittest.TestCase):
    def test_header_and_legacy_labels_removed(self):
        for fragment in (
            "Je suis là, avec toi", "header-notifications", "à tes côtés",
            "Jade gère les rappels depuis ton PC",
            "Les rappels envoyés restent visibles",
            "Ce réglage concerne les notifications Android",
            "Bienvenue chez nous", "Conversation avec Jade",
            "Paramètres, compte lié et informations techniques de Jade",
        ):
            self.assertNotIn(fragment, HTML)
        self.assertNotIn("Les rappels envoyés restent visibles", JS)

    def test_one_microphone_moves_between_accueil_and_chat(self):
        self.assertEqual(HTML.count('id="mic"'), 1)
        room_bottom = HTML.split('<div class="room-bottom">', 1)[1].split("</div>", 1)[0]
        self.assertIn('id="mic"', room_bottom)
        self.assertIn('document.querySelector(".room-bottom").appendChild(mic)', JS)
        self.assertIn("form.insertBefore(mic, input)", JS)
        self.assertIn('.shell[data-view="home"] .conversation{display:none}', CSS)
        self.assertNotIn("      input.focus();\n      openReminderFromHash();", JS)

    def test_notifications_move_into_profile(self):
        self.assertEqual(HTML.count('class="notification-choice"'), 1)
        self.assertLess(HTML.index('class="notification-choice"'), HTML.index('id="reminders-panel"'))
        self.assertIn(":not(.notification-choice)", CSS)
        self.assertIn('view === "profile" && token', JS)
        self.assertIn('id="notifications-on"', HTML)
        self.assertIn('id="notifications-off"', HTML)

    def test_scenes_remain_undistorted_and_avatar_zooms_separately(self):
        self.assertIn('roomPlane.getBoundingClientRect().width', JS)
        self.assertIn("var(--room-immersive-width,100%)", CSS)
        self.assertIn("immersive ? 1.9 : 1.5", AVATAR)
        self.assertIn('window.JadeAvatar?.resize?.()', JS)
        self.assertIn('.shell:not([data-view="home"]),.shell[data-view="chat"]', CSS)
        self.assertIn('.room-art[data-room="kitchen"]::before', CSS)


if __name__ == "__main__":
    unittest.main()
