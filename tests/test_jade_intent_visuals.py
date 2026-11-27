"""Offline acceptance tests for Jade's shared two-reaction Live2D contract.

No Live2D SDK, real microphone, audio output, tokens or LLM services required.
"""
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from src.jade_runtime.avatar import Avatar
from src.jade_runtime.config import Settings
from src.jade_runtime.intent_engine import INTENTS
from src.jade_runtime.intent_visuals import (
    EXPRESSIONS, public_visual_contract, reaction_for_intent, visual_contract,
)
from src.jade_runtime.mobile_gateway import MobileGateway, WEB_ROOT


class VisualContractTests(unittest.TestCase):
    def test_every_intent_has_two_captions_and_supported_expression_fallbacks(self):
        contract = visual_contract()
        self.assertEqual(contract["version"], 1)
        self.assertEqual(set(contract["intents"]), INTENTS)
        first = set()
        captions = set()
        for intent in sorted(INTENTS):
            choices = contract["intents"][intent]
            self.assertEqual(len(choices), 2, intent)
            # The r21 has its own A/B face, acting and motion parameters. The
            # shared expression name is only a safe fallback: both sad variants
            # stay sad, and both angry variants stay angry.
            if intent not in {"sad", "angry"}:
                self.assertNotEqual(choices[0]["expression"], choices[1]["expression"])
            self.assertNotEqual(choices[0]["text"], choices[1]["text"])
            self.assertIn(choices[0]["expression"], EXPRESSIONS)
            first.add(choices[0]["expression"])
            for choice in choices:
                self.assertNotIn(choice["text"], captions)
                captions.add(choice["text"])
        self.assertEqual(first, EXPRESSIONS)
        self.assertEqual(len(captions), 18)
        self.assertEqual({v["expression"] for v in contract["intents"]["sad"]}, {"Sad"})
        self.assertEqual({v["expression"] for v in contract["intents"]["angry"]}, {"Angry"})

    def test_unknown_label_has_trusted_neutral_fallback(self):
        self.assertEqual(reaction_for_intent("untrusted data"), reaction_for_intent("neutral"))
        self.assertEqual(reaction_for_intent("playful", 2), reaction_for_intent("playful", 0))
        self.assertNotEqual(reaction_for_intent("playful", 1), reaction_for_intent("playful", 0))

    def test_visual_toggle_never_disables_voice_intent(self):
        with patch("src.jade_runtime.config.environ",
                   side_effect=lambda key, default="": "0" if key == "JADE_AVATAR_INTENT_ENABLED" else default):
            settings = Settings.load()
        self.assertFalse(settings.avatar_intent_enabled)
        self.assertIn("playful", INTENTS)
        self.assertFalse(public_visual_contract(False)["enabled"])
        self.assertTrue(public_visual_contract(True)["enabled"])

    def test_mobile_js_parses_and_avoids_double_intent_trigger(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable: JS syntax checked in browser recipe")
        for name in ("avatar.js", "app.js"):
            with self.subTest(name=name):
                result = subprocess.run(
                    [node, "--check", str(WEB_ROOT / name)],
                    text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
        app_source = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertEqual(app_source.count("avatar().setIntent("), 1)

    def test_mobile_adapter_reads_shared_palette_not_separate_expressions(self):
        source = (WEB_ROOT / "avatar.js").read_text(encoding="utf-8")
        self.assertIn("/assets/intent-visuals.json", source)
        self.assertNotIn('playful: "WinkR"', source)


class _Writer:
    def __init__(self):
        self.parts = []
    def write(self, data):
        self.parts.append(data)
    async def drain(self):
        pass


class MobileVisualContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_mobile_get_returns_toggle_and_two_variants_without_secrets(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                mobile = MobileGateway(object(), object(), token="x" * 40,
                                       avatar_intent_enabled=enabled)
                writer = _Writer()
                await mobile._static(writer, "/assets/intent-visuals.json")
                response = b"".join(writer.parts)
                self.assertIn(b"HTTP/1.1 200 OK", response)
                payload = json.loads(response.split(b"\r\n\r\n", 1)[1])
                self.assertEqual(payload["enabled"], enabled)
                self.assertEqual(payload["intents"], visual_contract()["intents"])
                self.assertNotIn(b"x" * 40, response)


class AvatarVisualTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.avatar = Avatar()
    async def asyncTearDown(self):
        if self.avatar._reset_task is not None:
            self.avatar._reset_task.cancel()
            await asyncio.gather(self.avatar._reset_task, return_exceptions=True)

    async def test_pc_alternates_reactions_for_successive_replies(self):
        self.avatar.set_intent("playful")
        self.assertEqual(self.avatar._pending_expression, "WinkR")
        self.avatar.set_intent("playful")
        self.assertEqual(self.avatar._pending_expression, "WinkL")
        self.avatar.set_intent("playful")
        self.assertEqual(self.avatar._pending_expression, "WinkR")

    async def test_mouth_levels_cannot_replace_pending_expression(self):
        self.avatar.set_intent("tender")
        self.avatar._queue_mouth(.1)
        self.avatar._queue_mouth(.6)
        self.assertEqual(self.avatar._pending_expression, "WinkL")
        self.assertEqual(self.avatar._pending_mouth, .6)

    async def test_disabled_toggle_never_sends_expression(self):
        self.avatar.intent_enabled = False
        self.avatar.set_intent("serious")
        self.assertIsNone(self.avatar._pending_expression)
        self.avatar._queue_mouth(.3)
        self.assertEqual(self.avatar._pending_mouth, .3)

    async def test_standalone_renderer_receives_both_message_types(self):
        class Stdin:
            def __init__(self):
                self.frames = []

            def write(self, data):
                self.frames.extend(json.loads(line) for line in data.decode().splitlines())

            async def drain(self):
                # End this synthetic renderer deterministically after its
                # first batch. The production loop stays long-lived; here we
                # verify both IPC frames and its broken-pipe recovery.
                raise BrokenPipeError("synthetic renderer finished")

        stdin = Stdin()
        self.avatar.process = type("FakeProcess", (), {"stdin": stdin})()
        self.avatar.set_intent("curious")
        self.avatar._queue_mouth(.4)
        # On Windows the old infinite writer/cancel fixture hung until the
        # eight-minute CI timeout. No tests are skipped or disabled.
        with self.assertLogs("jade.avatar", level="WARNING"):
            await asyncio.wait_for(self.avatar._write_loop(), timeout=2)
        self.assertIn({"type": "expression", "value": "Surprised"}, stdin.frames)
        self.assertIn({"type": "mouth", "value": .4}, stdin.frames)

    async def test_voice_end_returns_to_neutral(self):
        self.avatar.set_intent("excited")
        self.avatar.observer("discord")("pcm_start", None)
        self.avatar.observer("discord")("pcm_end", None)
        self.assertEqual(self.avatar._pending_expression, "Neutral")


if __name__ == "__main__":
    unittest.main()
