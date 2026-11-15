"""Private, opt-in, portable SQLite memory for Jade (no cloud dependency).

Identity comes from trusted transport IDs, NEVER nickname or spoken claim.
Core memories have no TTL; explicit user erasure remains possible.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
import secrets
import sqlite3
import uuid

SCHEMA_VERSION = 1
KINDS = frozenset(("ordinary", "core_self", "core_relationship"))
_ID = re.compile(r"^[1-9][0-9]{0,24}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def identity_of(message) -> tuple[str, str] | None:
    """Return verified platform account ID or None; mic/HTTP stay anonymous."""
    if message.platform == "discord_voice":
        value = getattr(message, "speaker_id", None)
        return ("discord", str(value)) if type(value) is int and value > 0 else None
    if message.platform in ("microphone", "mobile"):
        # Local hardware and the authenticated, owner-only mobile gateway map
        # to ONE Goldaj profile. Both transport origins are assigned by trusted
        # connectors, not by a caller's nickname or spoken self-introduction.
        # Mobile must be gated by Tailscale owner identity + private Bearer
        # before constructing Incoming(platform="mobile").
        return ("microphone", "goldaj")
    if message.platform in ("discord", "twitch"):
        value = getattr(message, "account_id", "")
        if isinstance(value, str) and _ID.fullmatch(value):
            return (message.platform, value)
    return None


def _validate_key(key: tuple[str, str]) -> None:
    if (not isinstance(key, tuple) or len(key) != 2
            or not isinstance(key[1], str)
            or not ((key[0] in ("discord", "twitch") and _ID.fullmatch(key[1]))
                    or key == ("microphone", "goldaj"))):
        raise ValueError("trusted transport account ID required")


def _fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join(text.strip().casefold().split()).encode("utf-8")).hexdigest()


class MemoryStore:
    """One SQLite database, short-lived connections; no network or extra service."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        if (not self.path.is_absolute() or self.path.is_symlink()
                or not self.path.name.endswith(".sqlite3")):
            raise ValueError("use an absolute private .sqlite3 path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise RuntimeError("unsupported Jade memory schema; migrate before starting")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS persons (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS identities (
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                    PRIMARY KEY(platform, account_id)
                );
                CREATE INDEX IF NOT EXISTS idx_identity_person ON identities(person_id);
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL CHECK(kind IN ('ordinary','core_self','core_relationship')),
                    scope TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    significance TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    source_platform TEXT NOT NULL,
                    source_account_id TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    UNIQUE(person_id,kind,scope,source_platform,source_account_id,fingerprint),
                    CHECK ((kind='ordinary' AND expires_at IS NOT NULL)
                        OR (kind!='ordinary' AND expires_at IS NULL))
                );
                CREATE INDEX IF NOT EXISTS idx_memory_owner
                    ON memories(person_id,scope,kind,created_at);
                CREATE TABLE IF NOT EXISTS link_challenges (
                    token_hash TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
            """)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(str(self.path), timeout=5)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=5000")
            with db:
                yield db
        finally:
            db.close()

    def account(self, key: tuple[str, str]) -> str | None:
        _validate_key(key)
        with self._db() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
        return row["person_id"] if row else None

    def enable(self, key: tuple[str, str]) -> str:
        """Called by an authenticated user's explicit opt-in, never automatically."""
        _validate_key(key)
        with self._db() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if row:
                return row["person_id"]
            person = uuid.uuid4().hex
            db.execute("INSERT INTO persons(id,created_at) VALUES (?,?)",
                       (person, _now().isoformat()))
            db.execute("INSERT INTO identities(platform,account_id,person_id) VALUES (?,?,?)",
                       (*key, person))
            return person

    def forget(self, key: tuple[str, str]) -> bool:
        """Erase linked person and ALL ordinary/core memories explicitly."""
        _validate_key(key)
        with self._db() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if not row:
                return False
            db.execute("DELETE FROM persons WHERE id=?", (row["person_id"],))
            db.execute("DELETE FROM link_challenges WHERE platform=? AND account_id=?", key)
            return True

    def put(self, key: tuple[str, str], *, kind: str, scope: str, summary: str,
            significance: str = "", message_id: str = "", ordinary_days: int = 90) -> bool:
        """No consent -> no write; Core always has an SQL-enforced NULL TTL."""
        _validate_key(key)
        if (kind not in KINDS or not isinstance(scope, str)
                or not (scope == "person" or
                        (scope.startswith(("discord:", "discord_voice:", "twitch:"))
                         and 1 <= len(scope) <= 128))
                or type(ordinary_days) is not int or not 1 <= ordinary_days <= 365):
            raise ValueError("invalid memory scope or retention")
        if (not isinstance(summary, str) or not summary.strip()
                or len(summary) > 400 or not isinstance(significance, str)
                or len(significance) > 280):
            raise ValueError("invalid memory contents")
        when = _now()
        expires = (when + timedelta(days=ordinary_days)).isoformat() if kind == "ordinary" else None
        with self._db() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if not row:
                return False
            result = db.execute("""
                INSERT OR IGNORE INTO memories(
                    id,person_id,kind,scope,summary,significance,fingerprint,
                    source_platform,source_account_id,source_message_id,created_at,expires_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    uuid.uuid4().hex, row["person_id"], kind, scope,
                    summary.strip(), significance.strip(), _fingerprint(summary),
                    key[0], key[1], message_id[:128], when.isoformat(), expires,
                ))
            return result.rowcount > 0

    def recall(self, key: tuple[str, str], scope: str, *, limit: int = 8) -> list[dict]:
        """Personal and current-channel memories; never another person's memories."""
        _validate_key(key)
        if not 1 <= limit <= 32:
            raise ValueError("invalid recall limit")
        with self._db() as db:
            rows = db.execute("""
                SELECT m.kind,m.scope,m.summary,m.significance,m.created_at
                FROM memories m JOIN identities i ON i.person_id=m.person_id
                WHERE i.platform=? AND i.account_id=?
                  AND m.scope=?
                  AND (m.expires_at IS NULL OR m.expires_at>?)
                ORDER BY CASE WHEN m.kind='ordinary' THEN 1 ELSE 0 END,
                         m.created_at DESC LIMIT ?
                """, (*key, scope, _now().isoformat(), limit)).fetchall()
        return [dict(row) for row in rows]

    def list_for_account(self, key: tuple[str, str]) -> list[dict]:
        _validate_key(key)
        with self._db() as db:
            rows = db.execute("""
                SELECT m.id,m.kind,m.scope,m.summary,m.significance,
                       m.created_at,m.expires_at
                FROM memories m JOIN identities i ON i.person_id=m.person_id
                WHERE i.platform=? AND i.account_id=? ORDER BY m.created_at DESC
                """, key).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, key: tuple[str, str], memory_id: str) -> bool:
        """Explicit correction/erasure by owner, including Core."""
        _validate_key(key)
        with self._db() as db:
            row = db.execute("""
                DELETE FROM memories WHERE id=? AND person_id=(
                    SELECT person_id FROM identities WHERE platform=? AND account_id=?)
                """, (memory_id, *key))
            return row.rowcount > 0

    def prune_ordinary(self) -> int:
        with self._db() as db:
            deleted = db.execute(
                "DELETE FROM memories WHERE kind='ordinary' AND expires_at<=?",
                (_now().isoformat(),))
            return deleted.rowcount

    def begin_link(self, key: tuple[str, str], *, ttl_seconds: int = 300) -> str:
        """Generate a one-time, short-lived secret for *another* authenticated account.

        UI must deliver this out of band/privately, NEVER to a public chat.
        """
        _validate_key(key)
        if not 30 <= ttl_seconds <= 600:
            raise ValueError("invalid link TTL")
        token = secrets.token_urlsafe(24)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._db() as db:
            if not db.execute(
                "SELECT 1 FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone():
                raise PermissionError("opt-in required for both accounts")
            db.execute("DELETE FROM link_challenges WHERE expires_at<=?",
                       (_now().isoformat(),))
            db.execute("INSERT INTO link_challenges VALUES (?,?,?,?)",
                       (digest, *key, (_now() + timedelta(seconds=ttl_seconds)).isoformat()))
        return token

    def complete_link(self, target: tuple[str, str], token: str) -> bool:
        """Prove control of both accounts by making each call under its trusted ID.

        This is an API, NOT a Twitch or Discord command exposed in public.
        """
        _validate_key(target)
        if not isinstance(token, str) or len(token) > 128:
            return False
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._db() as db:
            challenge = db.execute(
                "SELECT platform,account_id FROM link_challenges "
                "WHERE token_hash=? AND expires_at>?",
                (digest, _now().isoformat()),
            ).fetchone()
            if challenge is None:
                return False
            source = (challenge["platform"], challenge["account_id"])
            if source == target or source[0] == target[0]:
                return False  # Cross-platform only; same-provider accounts not merged.
            first = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", source
            ).fetchone()
            second = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", target
            ).fetchone()
            if first is None or second is None:
                return False
            a, b = first["person_id"], second["person_id"]
            if a != b:
                # A core must never be silently discarded during identity linking;
                # source account is part of the uniqueness key.
                db.execute("UPDATE memories SET person_id=? WHERE person_id=?", (a, b))
                db.execute("UPDATE identities SET person_id=? WHERE person_id=?", (a, b))
                db.execute("DELETE FROM persons WHERE id=?", (b,))
            db.execute("DELETE FROM link_challenges WHERE token_hash=?", (digest,))
            return True

    def unlink(self, key: tuple[str, str]) -> bool:
        """Detach a platform, preserving only memories sourced by that account."""
        _validate_key(key)
        with self._db() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if not row:
                return False
            person = row["person_id"]
            size = db.execute("SELECT COUNT(*) FROM identities WHERE person_id=?",
                              (person,)).fetchone()[0]
            if size <= 1:
                return False
            separate = uuid.uuid4().hex
            db.execute("INSERT INTO persons(id,created_at) VALUES (?,?)",
                       (separate, _now().isoformat()))
            db.execute("UPDATE identities SET person_id=? WHERE platform=? AND account_id=?",
                       (separate, *key))
            db.execute("""
                UPDATE memories SET person_id=?
                WHERE person_id=? AND source_platform=? AND source_account_id=?
            """, (separate, person, *key))
            db.execute("DELETE FROM link_challenges WHERE platform=? AND account_id=?", key)
            return True
