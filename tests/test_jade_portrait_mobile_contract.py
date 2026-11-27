"""Portrait rooms and r21 layout contract (no network or WebGL)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "jade_runtime" / "mobile_web"


class PortraitMobileContract(unittest.TestCase):
    def test_bedroom_and_r21_use_separate_frames(self):
        html = (WEB / "salon.html").read_text(encoding="utf-8")
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="avatar-frame"'), 1)
        self.assertIn('<div class="bedroom-frame"', html)
        self.assertEqual(html.count('id="portrait-bedroom"'), 1)
        self.assertEqual(html.count('id="avatar-container"'), 1)
        self.assertLess(html.index('id="portrait-bedroom"'),
                        html.index('id="avatar-container"'))
        self.assertIn('aspect-ratio:941 / 1672', css)
        self.assertIn('width:max(100cqw,56.28cqh)', css)
        self.assertIn('container-type:size', css)
        self.assertIn('[data-avatar-model="next"] .avatar-frame', css)

    def test_windowed_bedroom_camera_keeps_r21_size(self):
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        self.assertIn('transform:translate(-50%,calc(-50% - var(--seated-home-lift))) scale(1.25);', css)
        self.assertIn('.bedroom-frame{', css)
        self.assertIn('.shell[data-view="home"]:not(.is-room-only)', css)
        # The portrait background gets the new camera transform, not Jade.
        self.assertIn('[data-avatar-model="next"]) #avatar-container,', css)
        self.assertIn('transform:translateY(calc(-1 * var(--seated-home-lift)));', css)
        self.assertIn('@media(max-width:819px) and (orientation:portrait)', css)

    def test_portrait_motion_has_its_own_layer_and_camera(self):
        html = (WEB / "salon.html").read_text(encoding="utf-8")
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        guard = (WEB / "login-guard.js").read_text(encoding="utf-8")
        self.assertLess(html.index('id="portrait-bedroom"'),
                        html.index('id="portrait-bedroom-motion"'))
        self.assertLess(html.index('id="portrait-bedroom-motion"'),
                        html.index('id="avatar-container"'))
        self.assertIn('z-index:1;pointer-events:none', css)
        self.assertIn('.portrait-bedroom-motion[hidden]{display:none!important}', css)
        self.assertIn('width:max(100cqw,56.28cqh);height:max(177.6833cqw,100cqh);', css)
        self.assertIn('src="/assets/room-bedroom-portrait.avif"', html)
        self.assertIn('"/assets/portrait-bedroom-motion.js"', guard)
        self.assertIn('id="portrait-motion-enabled" checked', html)
        self.assertNotIn('@media(prefers-reduced-motion:reduce){.portrait-bedroom-motion{display:none!important}}', css)

    def test_portrait_room_media_paths_are_whitelisted(self):
        gateway = (ROOT / "src" / "jade_runtime" / "mobile_gateway.py").read_text(
            encoding="utf-8")
        for path in ("/assets/portrait-bedroom-motion.js",
                     "/assets/room-bedroom-portrait.avif",
                     "/assets/room-kitchen-portrait.avif",
                     "/assets/room-living-portrait.avif"):
            self.assertIn(path, gateway)
        for path in ("/assets/room-spring.webp", "/assets/room-backdrop.webp", "/assets/room-curtain.webp"):
            self.assertNotIn(path, gateway)


if __name__ == "__main__":
    unittest.main()
