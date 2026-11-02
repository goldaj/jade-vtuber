"""Dependency-free preflight: safe source review and deterministic failures."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from src.utility.public_profile import ALLOWED_PROFILE_KEYS
from tools.jade_ci_preflight import ALLOWED, validate

class OfflinePreflightTests(unittest.TestCase):
    def test_public_profile_whitelist_matches_independent_preflight(self):
        self.assertEqual(ALLOWED_PROFILE_KEYS, ALLOWED)

    def test_standalone_cli_help_free_of_provider_dependencies(self):
        proc = subprocess.run([sys.executable, "tools/jade_ci_preflight.py"],
                              capture_output=True, text=True, timeout=20)
        # This runs in the actual repository: status may be BLOCKED on existing
        # tracked data. In either case the scanner must terminate safely.
        self.assertIn(proc.returncode, (0, 1))
        self.assertIn("preflight", proc.stdout.lower())

    def test_synthetic_valid_and_invalid_python_toml(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / "src").mkdir()
            (root / "config" / "profiles").mkdir(parents=True)
            (root / "src" / "demo.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname = 'synthetic'\n", encoding="utf-8")
            profile = root / "config" / "profiles" / "offline.toml"
            profile.write_text("[settings]\nJADE_QUEUE_LIMIT = 64\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
            count, errors = validate(root)
            self.assertEqual(count, 3)
            self.assertEqual(errors, [])
            profile.write_text("[settings]\nOPENAI_API_KEY = 'test'\n", encoding="utf-8")
            self.assertIn("INVALID_TOML_OR_PUBLIC_PROFILE", validate(root)[1])
            profile.write_text("[settings]\nJADE_QUEUE_LIMIT = 64\n", encoding="utf-8")
            (root / "src" / "demo.py").write_text("def bad(: pass\n", encoding="utf-8")
            self.assertIn("INVALID_PYTHON_SOURCE", validate(root)[1])
