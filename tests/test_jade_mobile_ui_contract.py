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
        self.assertIn('const dock = document.querySelector?.(".room-bottom");', JS)
        self.assertIn("dock.appendChild?.(mic)", JS)
        self.assertIn("form.insertBefore(mic, input)", JS)
        self.assertIn('.shell[data-view="home"] .conversation{display:none}', CSS)
        self.assertNotIn("      input.focus();\n      openReminderFromHash();", JS)

    def test_notifications_move_into_profile(self):
        self.assertEqual(HTML.count('id="notifications-enabled"'), 1)
        self.assertLess(HTML.index('id="notifications-enabled"'), HTML.index('id="reminders-panel"'))
        self.assertIn('view === "profile" && token', JS)
        profile = HTML.split('id="profile-intro"', 1)[1].split('<div class="chat-heading">', 1)[0]
        self.assertIn('id="notifications-enabled"', profile)
        self.assertNotIn('id="notifications-on"', HTML)
        self.assertNotIn('id="notifications-off"', HTML)
        self.assertNotIn('<fieldset class="notification-choice"', HTML)

    def test_scenes_remain_undistorted_and_avatar_zooms_separately(self):
        self.assertNotIn("room-immersive-width", JS + CSS)
        self.assertIn(".room-plane,.bedroom-frame{", CSS)
        self.assertIn("width:max(100cqw,56.28cqh);height:max(177.6833cqw,100cqh);", CSS)
        self.assertIn("immersive ? 1.9 : 1.5", AVATAR)
        self.assertIn('window.JadeAvatar?.resize?.()', JS)
        self.assertIn('.shell:not([data-view="home"]),.shell[data-view="chat"]', CSS)
        self.assertIn('id="portrait-static-room" width="941" height="1672"', HTML)
        self.assertIn('<option value="living">Salon</option>', HTML)
        self.assertIn('.room:is([data-room="kitchen"],[data-room="living"])[data-avatar-model="next"]', CSS)
        self.assertIn('.room:is([data-room="bedroom"],[data-room="kitchen"],[data-room="living"])', CSS)
        self.assertNotIn("room-kitchen.webp", CSS + JS + HTML)
        self.assertNotIn("kitchen-effects", HTML)
        self.assertIn('["bedroom", "kitchen", "living"].includes(room?.dataset.room)', AVATAR)
        self.assertIn('.room[data-room="bedroom"] .room-art,.bedroom-frame,.portrait-seated-body{display:none}', CSS)


if __name__ == "__main__":
    unittest.main()
