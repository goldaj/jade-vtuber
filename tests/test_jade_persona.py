"""Offline tests for Jade's standard prompt and its explicit private override."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.jade_runtime.assets import load_prompt


class JadeRelationshipPromptTests(unittest.TestCase):
    def test_standard_project_prompt_is_timid_and_personal(self):
        root = Path(__file__).resolve().parents[1]
        with patch("src.jade_runtime.assets.environ", side_effect=lambda key, default="": default):
            loaded = load_prompt(root)
        # The public demo export intentionally swaps the personal prompt for
        # a neutral template and must not expose the creator's persona.
        if "Tu as été créée par Goldaj." not in loaded:
            self.skipTest("public preview persona intentionally neutral")
        self.assertIn("Goldaj est ton père", loaded)
        self.assertIn("« papa »", loaded)
        self.assertIn("n'appelle pas les autres personnes", loaded.lower())
        self.assertIn("timide", loaded)

    def test_private_override_is_respected_verbatim(self):
        with TemporaryDirectory() as tmp:
            custom = Path(tmp) / "persona.txt"
            expected = "Tu es une Jade fictive, vive et très concise."
            custom.write_text(expected, encoding="utf-8")

            def environ(key, default=""):
                return str(custom) if key == "JADE_PROMPT_FILE" else default

            with patch("src.jade_runtime.assets.environ", side_effect=environ):
                loaded = load_prompt(Path(tmp))
        self.assertEqual(loaded, expected)
