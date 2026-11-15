"""Verify the branch documentation contract, including PR code/doc coupling.

Runs with only Python stdlib. In CI the checkout must have fetch-depth: 0.
"""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "docs/handbook/README.md",
    "docs/handbook/INSTALLATION.md",
    "docs/handbook/DEMO.md",
    "docs/handbook/USER_GUIDE.md",
    "docs/handbook/TECHNICAL.md",
    "docs/handbook/AI_HANDOFF.md",
    "docs/handbook/BRANCH_STATE.md",
    "docs/handbook/BRANCH_MAINTENANCE.md",
    "AGENTS.md",
)
SOURCE_PREFIXES = ("src/", "scripts/", "demo/", "tests/", "config/", "jade-modeling/", ".github/")
SOURCE_FILES = {"main.py", "pyproject.toml", "poetry.lock",
                "Installer-Demo-Express.cmd", "Lancer-Demo-Express.cmd",
                "Installer-Launcher-Jade.cmd"}

def changed_files(base_ref: str):
    result = subprocess.run(
        ["git", "merge-base", f"origin/{base_ref}", "HEAD"],
        cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Cannot locate merge-base with origin/{base_ref}; checkout fetch-depth must be 0")
    comparison = subprocess.run(
        ["git", "diff", "--name-only", result.stdout.strip(), "HEAD"],
        cwd=ROOT, text=True, capture_output=True, check=True)
    return set(comparison.stdout.splitlines())

def main() -> int:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        print("Documentation files missing: " + ", ".join(missing), file=sys.stderr)
        return 1
    for name in REQUIRED:
        if not (ROOT / name).read_text(encoding="utf-8").strip():
            print("Empty documentation: " + name, file=sys.stderr)
            return 1
    base = os.environ.get("GITHUB_BASE_REF", "").strip()
    if base:
        try:
            changed = changed_files(base)
        except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
            print(f"Documentation comparison failed: {error}", file=sys.stderr)
            return 1
        code_changes = sorted(p for p in changed if
            p.startswith(SOURCE_PREFIXES) or p in SOURCE_FILES)
        if code_changes:
            missing_updates = sorted(set(REQUIRED) - changed)
            if missing_updates:
                print("Code changed: " + ", ".join(code_changes[:20]), file=sys.stderr)
                print("Update all branch manuals in the same PR: "
                      + ", ".join(missing_updates), file=sys.stderr)
                return 1
    print("Jade branch documentation: required guides and change contract OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
