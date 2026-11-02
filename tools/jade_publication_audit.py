"""Conservative, offline Git hygiene scanner. NEVER display credential values.

--working-tree checks tracked current files. --history checks names of objects
reachable from all local refs. Neither certifies public release: specialist
additional review of history, credentials and binary content may be necessary.
"""
from __future__ import annotations
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUSPECT = re.compile(r"(?i)(?:^|/)(?:\.env(?:\.(?!example$)[^/]*)?|id_rsa|id_ed25519|[^/]+\.(?:pem|p12|pfx|key)|credentials\.(?:json|env)|service[-_]account[^/]*\.json)$")
TOKEN = re.compile(r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{18,}|gh[pousr]_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b")
ASSIGN = re.compile(r"(?im)^\s*(?:export\s+)?(?:OPENAI_API_KEY|TWITCH_TOKEN|TWITCH_REFRESH_TOKEN|TWITCH_CLIENT_SECRET|DISCORD_TOKEN|JADE_HTTP_TOKEN|JADE_VTS_TOKEN|ELEVENLABS_API_KEY)\s*[:=]\s*['\"]?([^\s#'\",}{]+)")
EXAMPLE = frozenset({"example", "placeholder", "changeme", "none", "null", "test", "xxx"})
TEXT = frozenset({".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".xml", ".json", ".jsonl", ".ps1", ".sh", ".js", ".ts"})

def suspect_filename(name: str) -> bool:
    return bool(SUSPECT.search(name.replace("\\", "/")))

def scan_text(content: str) -> set[str]:
    found = {"TOKEN_PATTERN"} if TOKEN.search(content) else set()
    for match in ASSIGN.finditer(content):
        value = match.group(1).strip().strip("'\"")
        if (value.lower() not in EXAMPLE and len(value) >= 16
                and not value.startswith(("str(", "environ(", "os.", "fake-", "test-", "<", "$", "{"))):
            found.add("SENSITIVE_ASSIGNMENT")
    return found

def tracked_paths(root: Path) -> list[str]:
    raw = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached"],
                         capture_output=True, check=True).stdout
    return [name.decode("utf-8", "replace") for name in raw.split(b"\0") if name]

def audit_worktree(root: Path) -> list[tuple[str, str]]:
    issues = []
    for name in tracked_paths(root):
        if suspect_filename(name):
            issues.append(("TRACKED_PRIVATE_PATH", name))
        file = root / name
        if file.suffix.lower() not in TEXT and file.name not in {".env", ".env.example"}:
            continue
        if not file.is_file():
            issues.append(("MISSING_TRACKED_FILE", name))
            continue
        if file.stat().st_size > 2_000_000:
            issues.append(("UNSCANNED_LARGE_TEXT_FILE", name))
            continue
        try:
            content = file.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            issues.append(("UNREADABLE_TEXT_FILE", name))
            continue
        for code in sorted(scan_text(content)):
            issues.append((code, name))
    return sorted(set(issues))

def audit_history(root: Path) -> list[tuple[str, str]]:
    raw = subprocess.run(["git", "-C", str(root), "rev-list", "--objects", "--all"],
                         capture_output=True, check=True, text=True).stdout
    return sorted({("HISTORIC_PRIVATE_PATH", line.split(" ", 1)[1])
                   for line in raw.splitlines()
                   if " " in line and suspect_filename(line.split(" ", 1)[1])})

def main() -> int:
    parser = argparse.ArgumentParser(description="Jade basic secret hygiene: no values printed")
    parser.add_argument("--working-tree", action="store_true")
    parser.add_argument("--history", action="store_true")
    opts = parser.parse_args()
    if not (opts.working_tree or opts.history):
        parser.error("select --working-tree and/or --history")
    try:
        findings = (audit_worktree(ROOT) if opts.working_tree else [])
        if opts.history:
            findings.extend(audit_history(ROOT))
    except (OSError, subprocess.CalledProcessError):
        print("BLOCKED: scanner could not complete")
        return 2
    for code, _ in sorted(set(findings)):
        print("BLOCKED:", code)
    if findings:
        print("BLOCKED:", len(set(findings)), "finding(s). No values or paths displayed.")
        return 1
    print("Basic tracked-file hygiene passed; NOT authorization for public release.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
