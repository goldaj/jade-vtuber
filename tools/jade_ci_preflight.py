"""Dependency-free, offline Jade source preflight. No paid/API calls.

Checks tracked Python syntax and TOML manifests, and basic current-tree
credential hygiene. Does not execute application modules or print secrets.
"""
from __future__ import annotations
import ast
import subprocess
import sys
import tomllib
from pathlib import Path
if __package__:
    from .jade_publication_audit import audit_worktree, tracked_paths
else:
    from jade_publication_audit import audit_worktree, tracked_paths

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = frozenset({
    "JADE_LLM_MODEL", "JADE_STT_MODEL", "JADE_TTS_MODEL", "JADE_TTS_VOICE", "JADE_EARLY_VOICE",
    "JADE_API_TIMEOUT", "JADE_AUDIO_OUTPUT", "JADE_HISTORY_LIMIT",
    "JADE_QUEUE_LIMIT", "JADE_RANDOM_REPLY_RATE", "JADE_TWITCH_ENABLED",
    "JADE_TWITCH_SEND", "JADE_DISCORD_ENABLED", "JADE_DISCORD_SEND",
    "JADE_DISCORD_VOICE_ENABLED", "JADE_VTS_ENABLED", "JADE_HTTP_ENABLED",
    "JADE_HTTP_PORT",
})

def validate(root: Path = ROOT) -> tuple[int, list[str]]:
    errors = []
    count = 0
    try:
        names = tracked_paths(root)
    except (OSError, subprocess.CalledProcessError):
        return 0, ["GIT_TRACKING_UNAVAILABLE"]
    for name in names:
        path = root / name
        if not path.is_file():
            continue
        if name.endswith(".py"):
            try:
                if path.stat().st_size > 2_000_000:
                    raise ValueError("oversize")
                ast.parse(path.read_text(encoding="utf-8"), filename="<tracked Python>")
                count += 1
            except (SyntaxError, ValueError, UnicodeError, OSError):
                errors.append("INVALID_PYTHON_SOURCE")
        if name == "pyproject.toml" or (name.startswith("config/profiles/") and name.endswith(".toml")):
            try:
                with path.open("rb") as handle:
                    obj = tomllib.load(handle)
                if name.startswith("config/profiles/"):
                    if set(obj) != {"settings"} or not isinstance(obj["settings"], dict):
                        raise ValueError("invalid tables")
                    for key, value in obj["settings"].items():
                        if key not in ALLOWED or not isinstance(value, (str, int, float, bool)):
                            raise ValueError("invalid public profile")
                count += 1
            except (OSError, tomllib.TOMLDecodeError, ValueError):
                errors.append("INVALID_TOML_OR_PUBLIC_PROFILE")
    try:
        errors.extend(code for code, _ in audit_worktree(root))
    except (OSError, subprocess.CalledProcessError):
        errors.append("SECRET_SCAN_UNAVAILABLE")
    return count, sorted(set(errors))

def main() -> int:
    count, errors = validate()
    print("Jade offline preflight:", count, "Python/TOML files checked")
    for error in errors:
        print("BLOCKED:", error)
    if errors:
        print("No source contents or credential values printed.")
        return 1
    print("Basic checks passed. NOT a deployment or public-release certificate.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
