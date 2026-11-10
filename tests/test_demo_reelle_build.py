"""Packaging rejects private material and missing model assets, offline."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from demo.reelle import build_reelle as builder
    from demo.reelle.build_reelle import check_stage, copy_checked
except ModuleNotFoundError as exc:
    if exc.name not in {"demo", "demo.reelle", "demo.reelle.build_reelle"}:
        raise
    check_stage = copy_checked = None


@unittest.skipIf(check_stage is None, "demo omitted from this preview")
class DemoPackagingSafetyTests(unittest.TestCase):
    def test_license_selection_ignores_module_code(self):
        self.assertFalse(builder.source_is_notice(Path("packaging/licenses/_spdx.pyc")))
        self.assertFalse(builder.source_is_notice(Path("some/licenses/module.py")))
        self.assertTrue(builder.source_is_notice(Path("pkg.dist-info/licenses/LICENSE.txt")))

    def test_forbidden_name_and_empty_stage_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            with self.assertRaises(RuntimeError):
                check_stage(stage)
            (stage / ".env.private").write_text("fixture", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                check_stage(stage)

    def test_private_key_marker_across_chunk_boundary_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Synthetic marker only; no key material is present.
            path = Path(tmp) / "data.bin"
            path.write_bytes(b"x" * (1024 * 1024 - 12) +
                             b"-----BEGIN " + b"PRIVATE KEY-----" + b"fixture")
            with self.assertRaises(RuntimeError):
                check_stage(path.parent)

    def test_lfs_pointer_and_path_outside_root_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            source = root / "asset.bin"
            source.write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
            with self.assertRaises(RuntimeError):
                copy_checked(source, Path(tmp) / "copy.bin", root)
            outside = Path(tmp) / "outside.bin"
            outside.write_bytes(b"fixture")
            with self.assertRaises(RuntimeError):
                copy_checked(outside, Path(tmp) / "copy.bin", root)

    def test_persona_is_copied_but_a_secret_in_it_blocks_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "prompt_chat.txt"
            target = root / "assets" / "prompt_chat.txt"
            source.write_text("Jade est vive et espiègle.", encoding="utf-8")
            with patch.object(builder, "ROOT", root), patch.object(builder, "PROMPT", source):
                builder.copy_public_prompt(target)
                self.assertEqual(target.read_bytes(), source.read_bytes())
                source.write_text("OPENAI_API_KEY=" + "sk-" + "A" * 32, encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    builder.copy_public_prompt(target)


if __name__ == "__main__":
    unittest.main()
