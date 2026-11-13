"""Conservative, recoverable Twitch token rotation for an explicit private file.

No network or filesystem changes occur on import. Call check() in a worker thread.
"""
from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass, field
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dotenv import dotenv_values
from .twitch_token import TwitchTokenExpired, validate_twitch_token

ROOT = Path(__file__).resolve().parents[2]
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
MAX_VALIDATION_INTERVAL = 3000  # 50 minutes leaves a margin below Twitch's hourly limit.
_TOKEN = re.compile(r"[A-Za-z0-9._~+%=/\-]{10,512}\Z")


class RotationError(RuntimeError):
    """Generic error, never includes token values or response bodies."""


class RotationUncertain(RotationError):
    """Refresh may have consumed the one-use token; do not retry automatically."""


class BackupPending(RotationError):
    """Local credentials are saved but the independent backup is not current."""


@dataclass(frozen=True)
class TwitchCredentialState:
    access_token: str = field(repr=False)
    login: str = field(repr=False)
    rotated: bool = False
    backup_pending: bool = False


@contextmanager
def _lock(path: Path):
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RotationError("Twitch rotation already in progress") from None
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise RotationError("Twitch rotation already in progress") from None
        yield
    finally:
        os.close(fd)


def _secure_create(path: Path, data: bytes):
    """Exclusive file; on Windows remove inherited ACLs before writing data."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.name == "nt":
            proc = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                  capture_output=True, text=True, check=True)
            sid = next(csv.reader(io.StringIO(proc.stdout)))[-1].strip()
            if not re.fullmatch(r"S-1-(?:\d+-)+\d+", sid):
                raise RotationError("Could not secure private configuration")
            subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r",
                            "*" + sid + ":(F)", "*S-1-5-18:(F)", "*S-1-5-32-544:(F)"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with os.fdopen(fd, "wb") as f:
            fd = -1
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        if fd >= 0:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise RotationError("Could not secure private configuration") from None


def _marker(path: Path):
    if not path.exists():
        _secure_create(path, b"pending\n")


def _replace_pair(raw: bytes, access: str, refresh: str) -> bytes:
    if not _TOKEN.fullmatch(access) or not _TOKEN.fullmatch(refresh):
        raise RotationUncertain("Twitch returned an unusable token pair")
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise RotationError("Private configuration must be UTF-8") from None
    for key, value in (("TWITCH_TOKEN", access), ("TWITCH_REFRESH_TOKEN", refresh)):
        pattern = re.compile(r"(?m)^(\ufeff?)[ \t]*(?:export[ \t]+)?" + key + r"[ \t]*=[^\r\n]*")
        text, count = pattern.subn(lambda m: m.group(1) + key + "='" + value + "'", text)
        if count != 1:
            raise RotationError("Private configuration has missing or duplicate Twitch keys")
    return text.encode("utf-8")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _refresh(refresh_token: str, client_id: str, client_secret: str) -> tuple[str, str]:
    params = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id}
    if client_secret:
        params["client_secret"] = client_secret
    request = Request(TOKEN_URL, data=urlencode(params).encode("utf-8"), method="POST")
    try:
        with build_opener(_NoRedirect()).open(request, timeout=15) as response:
            payload = response.read(65537)
    except HTTPError as exc:
        if exc.code in (400, 401):
            raise RotationError("Twitch refresh was rejected; authorization is required") from None
        raise RotationUncertain("Twitch refresh outcome is uncertain; do not retry automatically") from None
    except (URLError, TimeoutError, OSError):
        raise RotationUncertain("Twitch refresh outcome is uncertain; do not retry automatically") from None
    try:
        if len(payload) > 65536:
            raise ValueError()
        data = json.loads(payload)
        access, refresh = data["access_token"], data["refresh_token"]
        if not isinstance(access, str) or not isinstance(refresh, str):
            raise ValueError()
        if not _TOKEN.fullmatch(access) or not _TOKEN.fullmatch(refresh):
            raise ValueError()
        return access, refresh
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise RotationUncertain("Twitch refresh outcome is uncertain; do not retry automatically") from None


class TwitchTokenManager:
    """One-process API; synchronizes other processes through a nonblocking lock.

    `sync_backup` must verify private remote backup or raise; it is called under
    the same lock. No remote operation or credential change happens until check().
    """
    def __init__(self, path: Path, *, sync_backup, login="", send_enabled=False,
                 validate=validate_twitch_token, refresh=_refresh):
        self.path = Path(path).expanduser().resolve()
        if (not self.path.is_file() or self.path.is_relative_to(ROOT)
                or any((p / ".git").exists() for p in self.path.parents)):
            raise RotationError("An existing private configuration outside Git is required")
        if not callable(sync_backup):
            raise RotationError("Private backup synchronization is required")
        self.backup = sync_backup
        self.login = login
        self.send_enabled = send_enabled
        self.validate = validate
        self.refresh = refresh
        self.lock = self.path.with_name(self.path.name + ".twitch-lock")
        self.pending = self.path.with_name(self.path.name + ".twitch-refresh-pending")
        self.backup_pending = self.path.with_name(self.path.name + ".twitch-backup-pending")

    def _sync(self):
        try:
            self.backup(self.path)
        except Exception:
            raise BackupPending("Private backup is pending; local credentials remain saved") from None
        self.backup_pending.unlink(missing_ok=True)

    def check(self) -> TwitchCredentialState:
        """Validate once; refresh only on Twitch 401, then persist and back up.

        A pending refresh marker is intentionally never cleared automatically:
        the request may have consumed the single-use refresh token before a crash.
        """
        if any(name in os.environ for name in ("TWITCH_TOKEN", "TWITCH_REFRESH_TOKEN",
                                               "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET")):
            raise RotationError("Remove Twitch process environment overrides before automatic rotation")
        with _lock(self.lock):
            if self.pending.exists():
                raise RotationUncertain("Previous Twitch refresh outcome requires manual recovery")
            if self.backup_pending.exists():
                self._sync()
            try:
                raw = self.path.read_bytes()
                values = dotenv_values(stream=io.StringIO(raw.decode("utf-8-sig")))
            except (OSError, UnicodeError):
                raise RotationError("Cannot read private Twitch configuration") from None
            token = values.get("TWITCH_TOKEN") or ""
            refresh_token = values.get("TWITCH_REFRESH_TOKEN") or ""
            client_id = values.get("TWITCH_CLIENT_ID") or ""
            client_secret = values.get("TWITCH_CLIENT_SECRET") or ""
            try:
                identity = self.validate(token, login=self.login, send_enabled=self.send_enabled)
                return TwitchCredentialState(token, identity.login)
            except TwitchTokenExpired:
                pass
            if not refresh_token or not client_id:
                raise RotationError("Twitch refresh configuration is incomplete")
            # Refuse to consume the single-use token unless its current state is
            # independently confirmed at the private destination first.
            try:
                self.backup(self.path)
            except Exception:
                raise BackupPending("Private backup cannot be verified; Twitch refresh was not attempted") from None
            try:
                if hashlib.sha256(self.path.read_bytes()).digest() != hashlib.sha256(raw).digest():
                    raise RotationError("Private configuration changed; Twitch refresh was not attempted")
            except OSError:
                raise RotationError("Cannot verify private Twitch configuration") from None
            # Validate the file layout and write a private snapshot before the one-use request.
            _replace_pair(raw, "synthetic-access", "synthetic-refresh")
            snapshot = self.path.with_name(self.path.name + ".before-twitch-" + uuid.uuid4().hex)
            _secure_create(snapshot, raw)
            _marker(self.backup_pending)
            _marker(self.pending)
            try:
                access, refresh_token = self.refresh(refresh_token, client_id, client_secret)
            except RotationUncertain:
                raise
            except RotationError:
                self.pending.unlink(missing_ok=True)
                # The old file remains current; no new token pair was issued.
                self.backup_pending.unlink(missing_ok=True)
                raise
            except Exception:
                raise RotationUncertain("Twitch refresh outcome is uncertain; do not retry automatically") from None
            try:
                replacement = _replace_pair(raw, access, refresh_token)
                temporary = self.path.with_name(self.path.name + ".twitch-recovery-" + uuid.uuid4().hex)
                # Keep the new one-use pair recoverable even if another process
                # changed the active file while the HTTP request was in flight.
                _secure_create(temporary, replacement)
                if hashlib.sha256(self.path.read_bytes()).digest() != hashlib.sha256(raw).digest():
                    raise RotationUncertain("Private configuration changed during refresh; manual recovery required")
                os.replace(temporary, self.path)
            except Exception:
                raise RotationUncertain("New Twitch credentials could not be safely persisted; manual recovery required") from None
            self.pending.unlink(missing_ok=True)
            pending = False
            try:
                self._sync()
            except BackupPending:
                pending = True
            identity = self.validate(access, login=self.login, send_enabled=self.send_enabled)
            return TwitchCredentialState(access, identity.login, rotated=True, backup_pending=pending)


async def _periodic_checks(check, interval, *, clock=None, sleep=None):
    """Schedule from each check's start, avoiding cumulative duration drift."""
    clock = clock or time.monotonic
    sleep = sleep or asyncio.sleep
    await sleep(interval)
    while True:
        started = clock()
        await check()
        await sleep(max(0, interval - (clock() - started)))


async def watch_twitch_token(manager: TwitchTokenManager, on_rotation, on_backup_pending,
                             *, interval: float = MAX_VALIDATION_INTERVAL):
    """Revalidate at least hourly; caller owns connector shutdown/reconnection.

    Both callbacks are coroutines. Failure propagates so the caller can stop
    the Twitch session rather than silently maintaining an invalid token.
    """
    if not 0 < interval <= MAX_VALIDATION_INTERVAL:
        raise ValueError("Twitch validation interval must be at most 50 minutes")
    async def check():
        state = await asyncio.to_thread(manager.check)
        if state.backup_pending:
            await on_backup_pending()
        if state.rotated:
            await on_rotation(state)
    await _periodic_checks(check, interval)
