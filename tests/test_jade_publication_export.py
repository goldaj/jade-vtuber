"""Preview is offline and uses synthetic fixtures; never publishes anything."""
import os
import base64
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import jade_publication_export as exporter
from tools.jade_publication_export import create_preview, selected_paths, tracked_paths

class ExportTests(unittest.TestCase):
    def test_strict_allowlist_drops_art_and_private_persona(self):
        paths = ["main.py", "pyproject.toml", "src/jade_runtime/config.py",
                 "jade-modeling/runtime-installed/Jade.moc3", "prompt_chat.txt",
                 "private/token.env", "docs/PRIVATE_CONFIGURATION.md",
                 "config/profiles/offline.toml", "tests/test_jade_core.py"]
        chosen = selected_paths(paths)
        self.assertEqual(chosen, ["config/profiles/offline.toml", "main.py",
                                  "pyproject.toml", "src/jade_runtime/config.py",
                                  "tests/test_jade_core.py"])

    def test_preview_uses_public_templates_and_never_copies_original_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private-repo"
            dest = Path(directory) / "release-preview"
            (root / "docs" / "publication").mkdir(parents=True)
            (root / "config" / "templates").mkdir(parents=True)
            (root / "main.py").write_text("print('demo')", encoding="utf-8")
            (root / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
            (root / "prompt_chat.txt").write_text("personal-private-persona", encoding="utf-8")
            (root / "docs/publication/README_PUBLIC_TEMPLATE.md").write_text("# Public Jade", encoding="utf-8")
            (root / "config/templates/prompt_chat.public.txt").write_text("generic-persona", encoding="utf-8")
            count = create_preview(root, dest, ["main.py", "pyproject.toml", "prompt_chat.txt"])
            self.assertEqual(count, 4)
            self.assertEqual((dest / "prompt_chat.txt").read_text(), "generic-persona")
            self.assertNotIn("personal-private-persona", (dest / "prompt_chat.txt").read_text())
            self.assertFalse((dest / ".git").exists())
            self.assertFalse((dest / "docs/images/jade.png").exists())
            self.assertTrue((dest / "PREVIEW_NOT_FOR_PUBLICATION.txt").exists())
            with self.assertRaises(ValueError):
                create_preview(root, dest, ["main.py", "pyproject.toml"])


    def test_cli_imports_both_as_module_and_as_script(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "tools/jade_publication_export.py", "--help"],
            text=True, capture_output=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--write", result.stdout)
        self.assertIn("--include-portrait", result.stdout)

    def test_optional_portrait_is_verified_and_copied_without_modification(self):
        image = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL2cAAAAASUVORK5CYII=")
        with tempfile.TemporaryDirectory() as directory:
            root, dest = Path(directory) / "source", Path(directory) / "preview"
            (root / "docs/publication").mkdir(parents=True)
            (root / "config/templates").mkdir(parents=True)
            (root / "assets").mkdir()
            (root / "main.py").write_text("print('demo')", encoding="utf-8")
            (root / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
            (root / exporter.TEMPLATE_README).write_text("# Jade\n" + exporter.NO_ART_TEXT, encoding="utf-8")
            (root / exporter.TEMPLATE_PROMPT).write_text("generic", encoding="utf-8")
            (root / "assets/portrait.png").write_bytes(image)
            with patch.object(exporter, "PORTRAIT_SOURCE", "assets/portrait.png"), \
                 patch.object(exporter, "PORTRAIT_SHA256", hashlib.sha256(image).hexdigest()):
                count = create_preview(root, dest, ["main.py", "pyproject.toml", "assets/portrait.png"], include_portrait=True)
            self.assertEqual(count, 5)
            self.assertEqual((dest / "docs/images/jade.png").read_bytes(), image)
            readme = (dest / "README.md").read_text(encoding="utf-8")
            self.assertIn("![Portrait de Jade](docs/images/jade.png)", readme)
            self.assertNotIn(exporter.NO_ART_TEXT, readme)

    def test_portrait_rejects_digest_mismatch_and_escape_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            parent, root = Path(directory), Path(directory) / "source"
            (root / "docs/publication").mkdir(parents=True)
            (root / "config/templates").mkdir(parents=True)
            (root / "assets").mkdir()
            (root / "main.py").write_text("print('demo')", encoding="utf-8")
            (root / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
            (root / exporter.TEMPLATE_README).write_text("# Jade\n" + exporter.NO_ART_TEXT, encoding="utf-8")
            (root / exporter.TEMPLATE_PROMPT).write_text("generic", encoding="utf-8")
            image = b"\x89PNG\r\n\x1a\n" + b"synthetic"
            (root / "assets/portrait.png").write_bytes(image)
            outside = parent / "outside.png"
            outside.write_bytes(image)
            for source, digest, tracked in [("assets/portrait.png", "0" * 64, True),
                                            (str(outside), hashlib.sha256(image).hexdigest(), True),
                                            ("assets/portrait.png", hashlib.sha256(image).hexdigest(), False)]:
                dest = parent / "preview"
                with patch.object(exporter, "PORTRAIT_SOURCE", source), \
                     patch.object(exporter, "PORTRAIT_SHA256", digest):
                    with self.assertRaises(ValueError):
                        paths = ["main.py", "pyproject.toml"] + ([source] if tracked else [])
                        create_preview(root, dest, paths, include_portrait=True)
                self.assertFalse(dest.exists())

    def test_cannot_export_inside_source_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                create_preview(root, root / "export", ["main.py"])

    @unittest.skipIf(os.environ.get("JADE_PREVIEW_CLOSURE_INNER") == "1",
                     "avoid recursively rebuilding the preview")
    def test_real_preview_runs_its_own_offline_suite(self):
        root = Path(__file__).resolve().parents[1]
        if not (root / ".git").exists():
            self.skipTest("closure check requires a Git checkout")
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "preview"
            create_preview(root, dest, tracked_paths(root))
            self.assertTrue((dest / "poetry.lock").is_file())
            self.assertTrue((dest / "tools/jade_ci_preflight.py").is_file())
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("JADE_", "OPENAI_", "TWITCH_", "DISCORD_", "ELEVENLABS_"))
                   and k != "BOT_NAME"}
            env["JADE_SECRETS_FILE"] = str(Path(directory) / "nonexistent-private.env")
            env["JADE_PREVIEW_CLOSURE_INNER"] = "1"
            env.pop("PYTHONPATH", None)
            # -I ignores PYTHONPATH; remove editable-install source paths too.
            # Assert both app and tool modules resolve from the exported copy.
            bootstrap = '''
import pathlib, sys, unittest
source = pathlib.Path(sys.argv[1]).resolve()
root = pathlib.Path.cwd().resolve()
sys.path[:] = [str(root)] + [p for p in sys.path if p and not pathlib.Path(p).resolve().is_relative_to(source)]
import src, tools.jade_ci_preflight as preflight
assert pathlib.Path(src.__file__).resolve().is_relative_to(root)
assert pathlib.Path(preflight.__file__).resolve().is_relative_to(root)
result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests'))
raise SystemExit(not result.wasSuccessful() or result.testsRun == 0)
'''
            proc = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", bootstrap, str(root)],
                                  cwd=dest, env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=180)
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-6000:])
            # Once the preview becomes a standalone repository, its retained
            # templates and tools must also support its own export command.
            for command in (["git", "init", "-q"], ["git", "add", "."]):
                subprocess.run(command, cwd=dest, env=env, check=True, capture_output=True)
            second = Path(directory) / "second-preview"
            proc = subprocess.run([sys.executable, "-X", "utf8", "tools/jade_publication_export.py",
                                   "--destination", str(second), "--write"],
                                  cwd=dest, env=env, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue((second / "poetry.lock").is_file())

if __name__ == "__main__":
    unittest.main()
