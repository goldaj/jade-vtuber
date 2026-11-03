"""Prepare a PRIVATE, unapproved snapshot with NO Git history.

Preview does not publish or authorize publication. By default excludes
jade-modeling/LFS, original personal prompts, internal docs and Git metadata.
One identified portrait may optionally be copied after SHA-256 verification.
Run after reviewing the tracked-file gate; credential rotation remains separate.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

if __package__:
    from .jade_publication_audit import ROOT, audit_worktree, scan_text, tracked_paths
else:
    from jade_publication_audit import ROOT, audit_worktree, scan_text, tracked_paths

PUBLIC_FILES = frozenset({
    "main.py", "pyproject.toml", "poetry.lock", ".env.example", ".gitignore",
    ".editorconfig", ".flake8", "mypy.ini",
})
PUBLIC_PREFIXES = ("src/", "tests/", "config/profiles/")
PUBLIC_TOOLS = frozenset({
    "tools/jade_publication_audit.py",
    "tools/jade_publication_export.py",
    "tools/jade_ci_preflight.py",
    "tools/jade_twitch_authorize.py",
})
PUBLIC_TEMPLATES = frozenset({
    "docs/publication/README_PUBLIC_TEMPLATE.md",
    "config/templates/prompt_chat.public.txt",
})
TEMPLATE_README = "docs/publication/README_PUBLIC_TEMPLATE.md"
TEMPLATE_PROMPT = "config/templates/prompt_chat.public.txt"
PORTRAIT_SOURCE = "jade-modeling/assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png"
PORTRAIT_SHA256 = "011b9d9c06190ce044120ba7640feb575a0a76a10f620575bd90f2a20cbb3275"
PORTRAIT_TARGET = "docs/images/jade.png"
NO_ART_TEXT = "Visuel et animation en cours ; aucun asset 2D n’est inclus dans cet aperçu de code"
WITH_PORTRAIT_TEXT = "Portrait de présentation inclus ; modèle et animation en cours"
WARNING = ("UNAPPROVED PRIVATE PREVIEW. NOT RELEASE-CLEARED.\n"
           "Keep credentials private; review every exported source.\n"
           "No license or release approval has been granted.\n")

def selected_paths(paths: list[str]) -> list[str]:
    """Explicit allowlist; the optional portrait is handled separately."""
    return sorted(p for p in paths if p in PUBLIC_FILES or p in PUBLIC_TOOLS or p in PUBLIC_TEMPLATES
                  or (p.startswith(PUBLIC_PREFIXES) and p.endswith(".py"))
                  or (p.startswith("config/profiles/") and p.endswith(".toml")))

def _verified_portrait(root: Path, paths: list[str]) -> bytes:
    if PORTRAIT_SOURCE not in paths:
        raise ValueError("Portrait is not tracked in the source checkout")
    source = root / PORTRAIT_SOURCE
    if not source.is_file() or not source.resolve().is_relative_to(root):
        raise ValueError("Portrait missing or outside checkout")
    if source.stat().st_size > 10_000_000:
        raise ValueError("Unexpected portrait size")
    image = source.read_bytes()
    if not image.startswith(b"\x89PNG\r\n\x1a\n") or hashlib.sha256(image).hexdigest() != PORTRAIT_SHA256:
        raise ValueError("Portrait digest does not match the approved source")
    return image


def create_preview(root: Path, dest: Path, paths: list[str], *, include_portrait: bool = False) -> int:
    root, dest = root.resolve(), dest.resolve()
    if root == dest or root in dest.parents or dest in root.parents:
        raise ValueError("Preview must live in a new directory outside source tree")
    if dest.exists():
        raise ValueError("Preview destination already exists; refusing overwrite")
    names = selected_paths(paths)
    if not names or "main.py" not in names or "pyproject.toml" not in names:
        raise ValueError("Required application source missing")
    substitutions = {
        "README.md": TEMPLATE_README,
        "prompt_chat.txt": TEMPLATE_PROMPT,
    }
    copyset = {p: p for p in names} | substitutions
    # Validate everything BEFORE creating output (avoid partial exports).
    for target, source in copyset.items():
        sourcefile = root / source
        if not sourcefile.is_file() or not sourcefile.resolve().is_relative_to(root):
            raise ValueError("Source for public preview missing or outside checkout")
        if sourcefile.stat().st_size > 2_000_000:
            raise ValueError("Oversized source excluded from public preview")
        if scan_text(sourcefile.read_text(encoding="utf-8")):
            raise ValueError("Potential credential in preview source")
    portrait = _verified_portrait(root, paths) if include_portrait else None
    readme = None
    if portrait is not None:
        readme = (root / TEMPLATE_README).read_text(encoding="utf-8")
        if NO_ART_TEXT not in readme or "\n" not in readme:
            raise ValueError("Portrait README template is not compatible")
        readme = readme.replace(NO_ART_TEXT, WITH_PORTRAIT_TEXT, 1)
        readme = readme.replace("\n", "\n\n![Portrait de Jade](docs/images/jade.png)\n", 1)
    dest.mkdir(parents=True)
    for target, source in copyset.items():
        output = dest / target
        output.parent.mkdir(parents=True, exist_ok=True)
        if target == "README.md" and readme is not None:
            output.write_text(readme, encoding="utf-8")
        else:
            shutil.copyfile(root / source, output)
    if portrait is not None:
        output = dest / PORTRAIT_TARGET
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(portrait)
    (dest / "PREVIEW_NOT_FOR_PUBLICATION.txt").write_text(WARNING, encoding="utf-8")
    return len(copyset) + (1 if portrait is not None else 0)

def main() -> int:
    parser = argparse.ArgumentParser(description="Create a private snapshot, optionally with a portrait; NOT public-ready")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--write", action="store_true", help="Write preview; default is dry-run")
    parser.add_argument("--include-portrait", action="store_true", help="Include one SHA-256 verified portrait in the private preview")
    args = parser.parse_args()
    findings = audit_worktree(ROOT)
    if findings:
        print("BLOCKED: tracked-file audit has", len(findings), "finding(s); no preview exported")
        return 1
    paths = tracked_paths(ROOT)
    names = selected_paths(paths)
    if not args.write:
        if args.include_portrait:
            try:
                _verified_portrait(ROOT.resolve(), paths)
            except (ValueError, OSError):
                print("BLOCKED: approved portrait missing or digest mismatch; no files copied")
                return 2
        print("Dry-run:", len(names), "allowlisted tracked sources; history excluded.")
        print("Portrait:", "verified and selected" if args.include_portrait else "excluded")
        print("No files copied, and NO PUBLICATION AUTHORIZATION.")
        return 0
    try:
        count = create_preview(ROOT, args.destination, paths, include_portrait=args.include_portrait)
    except (ValueError, OSError, UnicodeError):
        print("BLOCKED: cannot prepare safe private preview. No secret values displayed.")
        return 2
    print("Created PRIVATE, unapproved snapshot:", count, "files. NOT publication-cleared.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
