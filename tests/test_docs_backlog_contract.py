"""Offline regression tests for the operational backlog integrity gate."""
import tempfile
import unittest
from pathlib import Path

# The minimal public preview copies tests but intentionally omits scripts/.
# Validate the real backlog only when its controller is included in the bundle.
if (Path(__file__).resolve().parents[1] / "scripts/check_docs.py").is_file():
    from scripts.check_docs import backlog_integrity_errors
else:
    backlog_integrity_errors = None


@unittest.skipIf(backlog_integrity_errors is None,
                 "portable preview does not include the operational backlog")
class BacklogIntegrityTests(unittest.TestCase):
    def test_current_backlog_is_consistent(self):
        self.assertEqual(backlog_integrity_errors(), [])

    def test_missing_dependency_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "docs/backlog"
            folder.mkdir(parents=True)
            for name in ("01-DEVELOPPEMENT.md", "02-RECETTE.md",
                         "03-INSTALLATION-OPS.md", "04-PRODUCTION-2D.md"):
                (folder / name).write_text("# Backlog\n", encoding="utf-8")
            (folder / "01-DEVELOPPEMENT.md").write_text(
                "| **DEV-001** | P0 | A | **À faire** | État | Tâche | Résultat | REC-999 |\n",
                encoding="utf-8")
            (folder / "README.md").write_text(
                "### P0 · 1 tâches\n"
                "| 1 | DEV-001 | A | Tâche | [DEV](01-DEVELOPPEMENT.md) |\n",
                encoding="utf-8")
            self.assertTrue(any("REC-999" in error
                                for error in backlog_integrity_errors(root)))


if __name__ == "__main__":
    unittest.main()
