"""Character prompt validation without API calls or private assets."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.jade_runtime.assets import load_prompt


class JadeRelationshipPromptTests(unittest.TestCase):
    def test_default_character_prompt_mentions_goldaj_with_restraint(self):
        root = Path(__file__).resolve().parents[1]
        with patch("src.jade_runtime.assets.environ", side_effect=lambda key, default="": default):
            loaded = load_prompt(root)
        self.assertIn("Goldaj est ton père", loaded)
        self.assertIn("« papa »", loaded)
        self.assertIn("pas les autres", loaded.lower())

    def test_private_override_retains_relationship_without_replacing_persona(self):
        with TemporaryDirectory() as tmp:
            custom = Path(tmp) / "persona.txt"
            custom.write_text("Tu es une Jade fictive, vive et très concise.", encoding="utf-8")

            def environ(key, default=""):
                return str(custom) if key == "JADE_PROMPT_FILE" else default

            with patch("src.jade_runtime.assets.environ", side_effect=environ):
                loaded = load_prompt(Path(tmp))
        self.assertTrue(loaded.startswith("Tu es une Jade fictive"))
        self.assertIn("Goldaj est ton père", loaded)
        self.assertIn("papa", loaded)
        self.assertIn("N'appelle jamais les autres", loaded)
