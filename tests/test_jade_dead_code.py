"""No accidental resurrection of a non-OpenAI speech dependency."""
from pathlib import Path
import tomllib
import unittest


class DeadCodeAudit(unittest.TestCase):
    def test_no_non_openai_voice_provider_in_active_runtime(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / "src" / "jade_runtime").glob("*.py"):
            code = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("from elevenlabs", code)
            self.assertNotIn("import elevenlabs", code)
            self.assertNotIn("google.cloud.texttospeech", code)
            self.assertNotIn("import whisper", code)
        with (root / "pyproject.toml").open("rb") as f:
            deps = tomllib.load(f)["tool"]["poetry"]["dependencies"]
        for name in ("elevenlabs", "google-cloud-texttospeech", "nltk",
                     "speechrecognition", "twitchio", "py-cord", "discord-py-self"):
            self.assertNotIn(name, deps)

    def test_historical_voice_module_is_no_longer_in_current_tree(self):
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "src" / "texttospeech_elevenlabs.py").exists())
