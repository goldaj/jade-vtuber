"""Check Jade's branch documentation contract without creating nine-file churn.

A technical PR must update one durable entry in docs/operations/CHANGELOG.md.
Domain-specific manuals are reviewed and edited only when affected. Changes
exclusively to tests and documentation do not force the changelog.
Runs with the standard library; PR checkout must use fetch-depth: 0.
"""
from __future__ import annotations

import os
import re
from urllib.parse import unquote
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "AGENTS.md",
    "docs/README.md",
    "docs/handbook/README.md",
    "docs/handbook/INSTALLATION.md",
    "docs/handbook/DEMO.md",
    "docs/handbook/USER_GUIDE.md",
    "docs/handbook/TECHNICAL.md",
    "docs/handbook/AI_HANDOFF.md",
    "docs/handbook/BRANCH_STATE.md",
    "docs/handbook/BRANCH_MAINTENANCE.md",
    "docs/operations/README.md",
    "docs/operations/AGENT_COORDINATION.md",
    "docs/operations/CHANGELOG.md",
    "docs/operations/handoffs/README.md",
    "docs/backlog/README.md",
    "docs/backlog/DEFINITION_OF_DONE.md",
    "docs/backlog/01-DEVELOPPEMENT.md",
    "docs/backlog/02-RECETTE.md",
    "docs/backlog/03-INSTALLATION-OPS.md",
    "docs/backlog/04-PRODUCTION-2D.md",
)
CHANGELOG = "docs/operations/CHANGELOG.md"
TECHNICAL_PREFIXES = (
    "src/", "scripts/", "demo/", "config/", "jade-modeling/",
    "assets/", "tools/", ".github/",
)
TECHNICAL_FILES = {
    "main.py", "pyproject.toml", "poetry.lock", ".env.example",
    ".gitignore", ".gitattributes", ".editorconfig", ".flake8",
    "mypy.ini", "prompt_chat.txt",
    "Installer-Demo-Express.cmd", "Lancer-Demo-Express.cmd",
    "Installer-Launcher-Jade.cmd",
}


def requires_changelog(path: str) -> bool:
    """Affects runtime, assets, tooling, deployment or configuration.

    Deliberately excludes tests/, docs/ and the agent instruction files.
    Updating a unit test or archiving an old document should not require
    editing unrelated current manuals.
    """
    return path in TECHNICAL_FILES or path.startswith(TECHNICAL_PREFIXES)


def changed_files(base_ref: str) -> set[str]:
    result = subprocess.run(
        ["git", "merge-base", f"origin/{base_ref}", "HEAD"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Cannot locate merge-base with origin/{base_ref}; checkout fetch-depth must be 0"
        )
    comparison = subprocess.run(
        ["git", "diff", "--name-only", result.stdout.strip(), "HEAD"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    return set(comparison.stdout.splitlines())



def broken_local_markdown_links() -> list[str]:
    """Check relative links in active manuals, excluding historical transcripts."""
    active_files = {ROOT / path for path in REQUIRED}
    active_files.add(ROOT / "README.md")
    for directory in (
        "docs/ameliorations", "docs/architecture", "docs/backlog",
        "docs/operations", "docs/publication",
    ):
        active_files.update((ROOT / directory).rglob("*.md"))
    pattern = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
    root = ROOT.resolve()
    missing = []
    for file in sorted(active_files):
        if not file.is_file():
            continue
        content = file.read_text(encoding="utf-8")
        for match in pattern.finditer(content):
            href = match.group(1).strip().split(' "', 1)[0]
            if not href or href.startswith("#") or re.match(
                r"^(https?:|mailto:|tel:|data:|//)", href, re.IGNORECASE
            ):
                continue
            destination = unquote(href.split("#", 1)[0].split("?", 1)[0])
            target = (file.parent / destination).resolve()
            if not target.is_relative_to(root) or not target.exists():
                missing.append(f"{file.relative_to(ROOT)} -> {href}")
    return missing


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        print("Required documentation missing: " + ", ".join(missing), file=sys.stderr)
        return 1
    for path in REQUIRED:
        if not (ROOT / path).read_text(encoding="utf-8").strip():
            print("Empty documentation: " + path, file=sys.stderr)
            return 1

    links = broken_local_markdown_links()
    if links:
        print("Broken current Markdown links:", file=sys.stderr)
        for item in links[:30]:
            print("  " + item, file=sys.stderr)
        return 1

    base = os.environ.get("GITHUB_BASE_REF", "").strip()
    if base:
        try:
            changed = changed_files(base)
        except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
            print(f"Documentation comparison failed: {error}", file=sys.stderr)
            return 1
        technical = sorted(path for path in changed if requires_changelog(path))
        if technical and CHANGELOG not in changed:
            print("Technical files changed: " + ", ".join(technical[:20]), file=sys.stderr)
            print(
                "Update only docs/operations/CHANGELOG.md as a required minimum; "
                "also update affected domain manuals and diagrams.",
                file=sys.stderr,
            )
            return 1

    print("Jade documentation: canonical files present and change contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
