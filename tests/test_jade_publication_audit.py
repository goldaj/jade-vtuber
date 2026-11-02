"""Only synthetic patterns, no real credentials."""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from tools import jade_publication_audit as audit

class ScanTests(unittest.TestCase):
    def test_suspicious_names(self):
        for path in (".env", "settings/.env.prod", "server.key", "service-account.json"):
            self.assertTrue(audit.suspect_filename(path))
        self.assertFalse(audit.suspect_filename(".env.example"))

    def test_patterns_no_echo(self):
        self.assertIn("TOKEN_PATTERN", audit.scan_text("key=" + "sk-" + "A"*32))
        self.assertIn("SENSITIVE_ASSIGNMENT", audit.scan_text("OPENAI_API_KEY=" + "B"*32))
        self.assertEqual(audit.scan_text("OPENAI_API_KEY=example\nTWITCH_TOKEN=example"), set())
        self.assertEqual(audit.scan_text('TWITCH_TOKEN = str(environ("TWITCH_TOKEN", ""))'), set())

    def test_current_tree_and_output_never_print_values(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / ".env").write_text("SYNTHETIC=private-fixture", encoding="utf-8")
            with patch.object(audit, "tracked_paths", return_value=[".env"]):
                findings = audit.audit_worktree(root)
            self.assertTrue(any(code=="TRACKED_PRIVATE_PATH" for code,_ in findings))
            self.assertNotIn("private-fixture", repr(findings))
        with patch.object(audit, "audit_worktree", return_value=[("TOKEN_PATTERN", "private/sensitive")]), patch("sys.argv", ["tool","--working-tree"]):
            with io.StringIO() as output, redirect_stdout(output):
                self.assertEqual(audit.main(), 1)
                self.assertNotIn("private/sensitive", output.getvalue())

if __name__ == "__main__":
    unittest.main()
