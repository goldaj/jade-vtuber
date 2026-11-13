"""Check the CI scanner on a synthetic removed secret without printing it."""
from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
import tempfile


def main() -> int:
    binary = os.environ.get("GITLEAKS_BIN", "gitleaks")
    with tempfile.TemporaryDirectory(prefix="jade-scan-selftest-") as tmp:
        repo = Path(tmp)
        # Use a deterministic synthetic value matching Gitleaks' twitch-api-token
        # rule. Random values can accidentally contain generic-rule allowlisted
        # words, making an otherwise working scanner fail this test intermittently.
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
        secret = "".join(alphabet[(index * 7 + 3) % len(alphabet)] for index in range(30))

        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=repo, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        git("init", "-q")
        git("config", "user.name", "Jade CI")
        git("config", "user.email", "jade-ci@example.invalid")
        (repo / "README.md").write_text("Clean synthetic repository.\n", encoding="utf-8")
        git("add", "README.md")
        git("-c", "core.hooksPath=", "commit", "-q", "-m", "clean fixture")
        clean = subprocess.run(
            [binary, "git", "--log-opts=--all HEAD", "--redact=100", "--no-banner", "--exit-code=1"],
            cwd=repo, capture_output=True, text=True, timeout=60, check=False,
        )
        if clean.returncode != 0:
            print("BLOCKED: scanner rejected a clean synthetic repository.")
            return 1
        path = repo / "docs" / "archives" / "fixture.md"
        path.parent.mkdir(parents=True)
        path.write_text("TWITCH_TOKEN=" + secret + "\n", encoding="utf-8")
        git("add", "docs/archives/fixture.md")
        git("-c", "core.hooksPath=", "commit", "-q", "-m", "synthetic fixture")
        path.write_text("Credential removed.\n", encoding="utf-8")
        git("add", "docs/archives/fixture.md")
        git("-c", "core.hooksPath=", "commit", "-q", "-m", "remove fixture")
        report = repo / "synthetic-report.json"
        result = subprocess.run(
            [binary, "git", "--log-opts=--all HEAD", "--redact=100", "--no-banner", "--exit-code=1",
             "--report-format=json", "--report-path", str(report)],
            cwd=repo, capture_output=True, text=True, timeout=60, check=False,
        )
        try:
            report_text = report.read_text(encoding="utf-8")
            findings = json.loads(report_text)
        except (OSError, ValueError):
            print("BLOCKED: synthetic scan did not produce a valid report.")
            return 1
        if (result.returncode != 1 or secret in result.stdout or secret in result.stderr
                or secret in report_text or not any(
                    item.get("RuleID") == "twitch-api-token"
                    and item.get("File", "").replace("\\", "/") == "docs/archives/fixture.md"
                    for item in findings)):
            print("BLOCKED: synthetic history scan failed or did not redact output.")
            return 1
    print("Synthetic history scan and output redaction verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
