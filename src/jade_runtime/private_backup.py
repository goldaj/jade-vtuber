"""Synchronize an active private configuration to its verified private GitHub backup.

The caller must serialize this operation with token rotation using the same
interprocess lock. Secrets are sent only on stdin to the authenticated gh client;
neither command arguments nor exceptions include file contents.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from dotenv import dotenv_values


class PrivateBackupError(RuntimeError):
    """The private backup could not be verified or updated safely."""


def _fail():
    raise PrivateBackupError("Sauvegarde privée non confirmée ; la configuration locale est conservée.") from None


def _github(method: str, endpoint: str, body: dict | None = None) -> dict:
    env = os.environ.copy()
    env["GH_HOST"] = "github.com"
    for key in ("GH_DEBUG", "DEBUG", "GIT_TRACE", "GIT_TRACE_CURL", "GIT_TRACE_PACKET"):
        env.pop(key, None)
    args = ["gh", "api", "--hostname", "github.com", "--method", method, endpoint]
    payload = None
    if body is not None:
        args += ["--input", "-"]
        payload = json.dumps(body).encode("utf-8")
    try:
        result = subprocess.run(args, input=payload, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, timeout=45, check=False)
        if result.returncode:
            _fail()
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            _fail()
        return data
    except (OSError, subprocess.SubprocessError, UnicodeError, ValueError):
        _fail()


def _target(path: Path):
    try:
        selected = os.environ.get("JADE_SECRETS_FILE", "")
        if not selected or path.is_symlink() or not path.is_file():
            _fail()
        path = path.resolve(strict=True)
        if path != Path(selected).expanduser().resolve(strict=True):
            _fail()
        if any((p / ".git").exists() for p in (path.parent, *path.parents)):
            _fail()
        if path.stat().st_size > 262144:
            _fail()
        data = path.read_bytes()
        config = dotenv_values(path, interpolate=False)
        repo = config.get("JADE_BACKUP_REPOSITORY") or ""
        repo_id = config.get("JADE_BACKUP_REPOSITORY_ID") or ""
        remote_file = config.get("JADE_BACKUP_FILE") or ""
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
                or any(part in {".", ".."} for part in repo.split("/"))
                or not re.fullmatch(r"[1-9][0-9]{0,19}", repo_id)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.env", remote_file)
                or remote_file != path.name):
            _fail()
        return path, data, repo, int(repo_id), remote_file
    except (OSError, ValueError, TypeError):
        _fail()


def _verify_repo(repo: str, repo_id: int):
    meta = _github("GET", "repos/" + repo)
    if (meta.get("id") != repo_id or meta.get("full_name", "").casefold() != repo.casefold()
            or meta.get("private") is not True or meta.get("default_branch") != "main"):
        _fail()


def _remote(repo: str, remote_file: str):
    result = _github("GET", "repos/" + repo + "/contents/" + remote_file + "?ref=main")
    try:
        if result.get("type") != "file" or result.get("encoding") != "base64":
            _fail()
        sha = result["sha"]
        content = base64.b64decode(result["content"], validate=False)
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            _fail()
        expected = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if sha != expected:
            _fail()
        return sha, content
    except (KeyError, ValueError, TypeError):
        _fail()


def _state_path(path: Path) -> Path:
    return path.with_name(path.name + ".backup-state.json")


def _read_state(path: Path, repo: str, repo_id: int, remote_file: str):
    state_file = _state_path(path)
    if state_file.is_symlink():
        _fail()
    if not state_file.exists():
        return None
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if (state.get("repository") != repo or state.get("repository_id") != repo_id
                or state.get("file") != remote_file
                or not re.fullmatch(r"[0-9a-f]{40}", state.get("sha", ""))):
            _fail()
        return state["sha"]
    except (OSError, ValueError, AttributeError, TypeError):
        _fail()


def _write_state(path: Path, repo: str, repo_id: int, remote_file: str, sha: str):
    state_file = _state_path(path)
    if state_file.is_symlink():
        _fail()
    tmp = None
    try:
        fd, name = tempfile.mkstemp(prefix=".jade-backup-", dir=path.parent)
        tmp = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"repository": repo, "repository_id": repo_id,
                       "file": remote_file, "sha": sha}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, state_file)
    except OSError:
        _fail()
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


def sync_private_backup(active_file: Path) -> None:
    """Verify/update the configured private backup; never refresh the token.

    An absent local state is initialized only when remote and local bytes match.
    A remotely changed blob is never overwritten from a stale local state. A
    failed or ambiguous update may be retried with the same local file: it never
    invokes Twitch. This does not eliminate a visibility change race on GitHub.
    """
    path, data, repo, repo_id, remote_file = _target(Path(active_file))
    _verify_repo(repo, repo_id)
    previous, remote_data = _remote(repo, remote_file)
    state = _read_state(path, repo, repo_id, remote_file)
    if remote_data == data:
        _write_state(path, repo, repo_id, remote_file, previous)
        return
    if state is None or state != previous:
        _fail()
    # Repeat identity/privacy check immediately before transmitting the file.
    _verify_repo(repo, repo_id)
    try:
        _github("PUT", "repos/" + repo + "/contents/" + remote_file, {
            "message": "Update private Jade configuration",
            "content": base64.b64encode(data).decode("ascii"),
            "sha": previous, "branch": "main",
        })
    except PrivateBackupError:
        # A timeout can hide a successful PUT; re-read, never issue another PUT.
        pass
    _verify_repo(repo, repo_id)
    current, confirmed = _remote(repo, remote_file)
    try:
        if confirmed != data or path.read_bytes() != data:
            _fail()
    except OSError:
        _fail()
    _write_state(path, repo, repo_id, remote_file, current)
