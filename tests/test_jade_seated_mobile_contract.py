"""Hybrid seated Jade: layout and fallback contract (no network or WebGL)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "jade_runtime" / "mobile_web"


class SeatedMobileContract(unittest.TestCase):
    def test_separate_layers_share_one_frame(self):
        html = (WEB / "salon.html").read_text(encoding="utf-8")
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="avatar-frame"'), 1)
        self.assertEqual(html.count('id="portrait-bedroom"'), 1)
        self.assertEqual(html.count('id="portrait-seated-body"'), 1)
        self.assertEqual(html.count('id="avatar-container"'), 1)
        self.assertLess(html.index('id="portrait-seated-body"'),
                        html.index('id="avatar-container"'))
        self.assertIn('aspect-ratio:941 / 1672', css)
        self.assertIn('width:max(100cqw,56.28cqh)', css)
        self.assertIn('top:40.6699%;width:71.2009%;height:56.2201%', css)
        self.assertIn('clip-path:polygon(', css)

    def test_feature_only_activates_with_both_images(self):
        scene = (WEB / "seated-scene.js").read_text(encoding="utf-8")
        guard = (WEB / "login-guard.js").read_text(encoding="utf-8")
        room = (WEB / "room-motion.js").read_text(encoding="utf-8")
        self.assertIn('Promise.all([preload(ASSETS.room), preload(ASSETS.body)])', scene)
        self.assertIn('room.dataset.seatedReady = "true"', scene)
        self.assertIn('room.dataset.seatedReady = "false"', scene)
        self.assertIn('"/assets/seated-scene.js"', guard)
        self.assertIn('room?.dataset.seatedReady !== "true"', room)
        self.assertIn('if (room) room.dataset.room = next', room)

    def test_animated_head_not_scaled_independently_by_phone(self):
        avatar = (WEB / "avatar.js").read_text(encoding="utf-8")
        self.assertIn('const headScale = 1.30', avatar)
        self.assertIn('model.position.set(width * .50, height * .61)', avatar)
        self.assertIn('const seated = room?.dataset.room === "bedroom"', avatar)
        self.assertNotIn("Redmi", avatar)

    def test_new_media_paths_are_whitelisted(self):
        gateway = (ROOT / "src" / "jade_runtime" / "mobile_gateway.py").read_text(
            encoding="utf-8")
        for path in ("/assets/seated-scene.js",
                     "/assets/room-bedroom-portrait.avif",
                     "/assets/jade-seated-body.avif"):
            self.assertIn(path, gateway)


if __name__ == "__main__":
    unittest.main()
