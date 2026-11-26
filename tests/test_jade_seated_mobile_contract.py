"""Hybrid seated Jade: layout and fallback contract (no network or WebGL)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "jade_runtime" / "mobile_web"


class SeatedMobileContract(unittest.TestCase):
    def test_bedroom_and_body_use_separate_frames(self):
        html = (WEB / "salon.html").read_text(encoding="utf-8")
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="avatar-frame"'), 1)
        self.assertIn('<div class="bedroom-frame"', html)
        self.assertEqual(html.count('id="portrait-bedroom"'), 1)
        self.assertEqual(html.count('id="portrait-seated-body"'), 1)
        self.assertEqual(html.count('id="avatar-container"'), 1)
        self.assertLess(html.index('id="portrait-seated-body"'),
                        html.index('id="avatar-container"'))
        self.assertIn('aspect-ratio:941 / 1672', css)
        self.assertIn('width:max(100cqw,56.28cqh)', css)
        self.assertIn('top:var(--seated-body-top,40.6699%);width:71.2009%;height:var(--seated-body-height,56.2201%)', css)
        self.assertIn('clip-path:none', css)
        self.assertIn('container-type:size', css)
        self.assertIn('[data-seated-compositor="true"] .portrait-seated-body{display:none}', css)

    def test_windowed_bedroom_camera_keeps_jade_size(self):
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        self.assertIn('transform:translate(-50%,calc(-50% - var(--seated-home-lift))) scale(1.25);', css)
        self.assertIn('.bedroom-frame{', css)
        self.assertIn('.shell[data-view="home"]:not(.is-room-only)', css)
        # The portrait background gets the new camera transform, not Jade.
        self.assertIn('[data-avatar-model="next"]) #avatar-container,', css)
        self.assertIn('transform:translateY(calc(-1 * var(--seated-home-lift)));', css)
        self.assertIn('@media(max-width:819px) and (orientation:portrait)', css)

    def test_seated_body_lifecycle_is_independent_of_bedroom(self):
        scene = (WEB / "seated-scene.js").read_text(encoding="utf-8")
        guard = (WEB / "login-guard.js").read_text(encoding="utf-8")
        room = (WEB / "room-motion.js").read_text(encoding="utf-8")
        self.assertNotIn("portrait-bedroom", scene)
        self.assertIn("const bodyImage = await pending.promise", scene)
        self.assertIn('room.dataset.seatedReady = "true"', scene)
        self.assertIn('avatar.canIsolateHead', scene)
        self.assertIn('room.dataset.seatedCompositor = layered ? "true" : "false"', scene)
        self.assertIn('prepareSeatedComposition(bodyImage)', scene)
        self.assertIn('[940, 956].includes(bodyImage.naturalHeight)', scene)
        self.assertIn('body.style.setProperty("--seated-body-top"', scene)
        self.assertIn('body.style.setProperty("--seated-body-height"', scene)
        self.assertIn('room.dataset.seatedReady = "false"', scene)
        self.assertIn('"/assets/seated-scene.js"', guard)
        self.assertIn('room.dataset.room = next', room)

    def test_animated_head_not_scaled_independently_by_phone(self):
        avatar = (WEB / "avatar.js").read_text(encoding="utf-8")
        self.assertIn('const headScale = 1.30', avatar)
        # Owner-adjusted seated head alignment, 2026-11-24.
        self.assertIn('placeModel(Math.max(.05, scale * headScale), width * .555, cameraViewportHeight * .584', avatar)
        self.assertIn('renderPass(renderer, "rear")', avatar)
        self.assertIn('renderPass(renderer, "front")', avatar)
        self.assertIn('PIXI.Sprite.from(image)', avatar)
        self.assertIn('room?.dataset.seatedCompositor === "true"', avatar)
        self.assertIn('const seated = isSeated()', avatar)
        self.assertIn('room?.dataset.room === "bedroom"', avatar)
        # The seated posture must survive a missing Pixi depth compositor.
        self.assertIn('room?.dataset.seatedReady === "true";', avatar)
        self.assertIn("const sprite = seatedComposition?.body", avatar)
        self.assertIn("window.JadeSeatedScene?.layout", avatar)
        self.assertIn("height * layout.top", avatar)
        self.assertIn("height * layout.height", avatar)
        self.assertNotIn("new PIXI.Graphics()", avatar)
        self.assertNotIn("seatedComposition.neck", avatar)
        self.assertNotIn("Redmi", avatar)

    def test_corrected_avif_has_no_runtime_graphics_neck(self):
        avatar = (WEB / "avatar.js").read_text(encoding="utf-8")
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        self.assertNotIn("neck = new PIXI.Graphics()", avatar)
        self.assertNotIn("seatedComposition.neck", avatar)
        self.assertNotIn('data-seated-compositor="false"] .avatar-frame::before', css)
        self.assertIn('clip-path:none', css)

    def test_portrait_motion_has_its_own_layer_and_camera(self):
        html = (WEB / "salon.html").read_text(encoding="utf-8")
        css = (WEB / "jade-theme.css").read_text(encoding="utf-8")
        guard = (WEB / "login-guard.js").read_text(encoding="utf-8")
        self.assertLess(html.index('id="portrait-bedroom"'),
                        html.index('id="portrait-bedroom-motion"'))
        self.assertLess(html.index('id="portrait-bedroom-motion"'),
                        html.index('id="portrait-seated-body"'))
        self.assertIn('z-index:1;pointer-events:none', css)
        self.assertIn('.portrait-bedroom-motion[hidden]{display:none!important}', css)
        self.assertIn('width:max(100cqw,56.28cqh);height:max(177.6833cqw,100cqh);', css)
        self.assertIn('src="/assets/room-bedroom-portrait.avif"', html)
        self.assertIn('"/assets/portrait-bedroom-motion.js"', guard)
        self.assertIn('id="portrait-motion-enabled" checked', html)
        self.assertNotIn('@media(prefers-reduced-motion:reduce){.portrait-bedroom-motion{display:none!important}}', css)

    def test_new_media_paths_are_whitelisted(self):
        gateway = (ROOT / "src" / "jade_runtime" / "mobile_gateway.py").read_text(
            encoding="utf-8")
        for path in ("/assets/seated-scene.js",
                     "/assets/portrait-bedroom-motion.js",
                     "/assets/room-bedroom-portrait.avif",
                     "/assets/jade-seated-body.avif"):
            self.assertIn(path, gateway)
        for path in ("/assets/room-spring.webp", "/assets/room-backdrop.webp", "/assets/room-curtain.webp"):
            self.assertNotIn(path, gateway)


if __name__ == "__main__":
    unittest.main()
