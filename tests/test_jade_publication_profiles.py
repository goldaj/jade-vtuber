"""No provider calls, no hardware and no actual credentials."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.jade_runtime.assets import load_prompt
from src.jade_runtime.config import Settings
from src.utility.private_config import environ
from src.utility.public_profile import load_profile, selected_profile

class PublicProfilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.private = self.root / "private.env"
        self.profile = self.root / "settings.toml"
        self.private.write_text("JADE_LLM_MODEL=private-model\nOPENAI_API_KEY=private-fixture\n", encoding="utf-8")
        self.profile.write_text('[settings]\nJADE_LLM_MODEL="profile-model"\nJADE_QUEUE_LIMIT=17\n', encoding="utf-8")
        clean = patch.dict(os.environ, {"JADE_SECRETS_FILE": str(self.private),
                                     "JADE_PROFILE_FILE": str(self.profile)}, clear=True)
        clean.start()
        self.addCleanup(clean.stop)

    def test_layering_and_settings(self):
        self.assertEqual(environ("JADE_LLM_MODEL"), "private-model")
        self.assertEqual(environ("JADE_QUEUE_LIMIT"), "17")
        self.assertEqual(Settings.load().max_queue, 17)
        self.assertEqual(environ("OPENAI_API_KEY"), "private-fixture")
        os.environ["JADE_LLM_MODEL"] = "process-model"
        self.assertEqual(environ("JADE_LLM_MODEL"), "process-model")

    def test_speed_profile_and_process_override(self):
        self.profile.write_text('[settings]\nJADE_TTS_SPEED=1.25\n', encoding="utf-8")
        self.assertEqual(Settings.load().tts_speed, 1.25)
        os.environ["JADE_TTS_SPEED"] = "1.0"
        self.assertEqual(Settings.load().tts_speed, 1.0)
        os.environ["JADE_TTS_SPEED"] = "1.6"
        with self.assertRaises(ValueError):
            Settings.load()

    def test_pitch_profile_loading_and_private_override(self):
        self.profile.write_text('[settings]\\nJADE_TTS_PITCH_SEMITONES=2.0\\n', encoding="utf-8")
        self.assertEqual(Settings.load().tts_pitch_semitones, 2.0)
        os.environ["JADE_TTS_PITCH_SEMITONES"] = "0"
        self.assertEqual(Settings.load().tts_pitch_semitones, 0.0)
        os.environ["JADE_TTS_PITCH_SEMITONES"] = "7"
        with self.assertRaises(ValueError):
            Settings.load()

    def test_shipped_fast_openai_profile_accepts_new_pitch(self):
        from src.utility.public_profile import PROFILE_ROOT
        os.environ["JADE_PROFILE_FILE"] = str(PROFILE_ROOT / "fast-openai.toml")
        loaded = load_profile()
        self.assertEqual(loaded["JADE_TTS_VOICE"], "shimmer")
        self.assertEqual(loaded["JADE_TTS_PITCH_SEMITONES"], "2.0")
        self.assertEqual(Settings.load().tts_pitch_semitones, 2.0)

    def test_secrets_and_identity_must_not_be_in_public_profile(self):
        for key in ("OPENAI_API_KEY", "TWITCH_TOKEN", "DISCORD_TOKEN",
                    "JADE_VTS_TOKEN", "BOT_NAME", "TWITCH_CHANNEL"):
            self.profile.write_text('[settings]\n' + key + '="redacted"\n', encoding="utf-8")
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "forbidden"):
                load_profile()

    def test_bad_profile_name_and_missing_profile_fail_closed(self):
        del os.environ["JADE_PROFILE_FILE"]
        os.environ["JADE_PROFILE"] = "../private"
        with self.assertRaises(ValueError):
            selected_profile()
        del os.environ["JADE_PROFILE"]
        os.environ["JADE_PROFILE_FILE"] = str(self.root / "missing.toml")
        with self.assertRaises(ValueError):
            load_profile()

    def test_private_prompt_file_and_asset_root(self):
        fallback = self.root / "prompt_chat.txt"
        fallback.write_text("public sample", encoding="utf-8")
        self.assertEqual(load_prompt(self.root), "public sample")
        p = self.root / "private-prompt.txt"
        p.write_text("private sample", encoding="utf-8")
        os.environ["JADE_PROMPT_FILE"] = str(p)
        self.assertEqual(load_prompt(self.root), "private sample")
        p.unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            load_prompt(self.root)
        del os.environ["JADE_PROMPT_FILE"]
        assetroot = self.root / "asset-root"
        (assetroot / "prompts").mkdir(parents=True)
        (assetroot / "prompts" / "chat.txt").write_text("from assets", encoding="utf-8")
        os.environ["JADE_ASSETS_ROOT"] = str(assetroot)
        self.assertEqual(load_prompt(self.root), "from assets")

if __name__ == "__main__":
    unittest.main()
