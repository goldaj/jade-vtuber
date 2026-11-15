"""Opt-in SQLite memory for Jade. No raw audio, cloud service, or global singleton.

All records are scoped to a verified transport account and a conversation
channel. Core memories have no TTL; explicit account erasure still applies.
The database belongs on a private local data volume, never in this repository.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
import sqlite3
import uuid

SCHEMA_VERSION = 1
KINDS = frozenset(("ordinary", "core_self", "core_relationship"))
_CORE = ("core_self", "core_relationship")
_KEY = re.compile(r"^[1-9][0-9]{0,24}$")


def identity_of(message) -> tuple[str, str] | None:
    """Accept ONLY trusted connector-account identifiers, not display names."""
    platform = message.platform
    if platform == "discord_voice":
        value = getattr(message, "speaker_id", None)
        return ("discord", str(value)) if type(value) is int and value > 0 else None
    if platform not in ("discord", "twitch"):
        return None
    value = getattr(message, "account_id", "")
    return (platform, value) if isinstance(value, str) and _KEY.fullmatch(value) else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode("utf-8")).hexdigest()


def _scope(message) -> str:
    # A separate namespace per channel prevents accidental cross-channel recall.
    return f"{message.platform}:{message.channel}"


class MemoryStore:
    """A fresh SQLite connection per operation; works across async-to-thread calls."""

    def __init__(self, path: Path):
        self.path = Path(path).expanduser()
        if self.path.name in ("", ".", "..") or str(self.path) == ":memory:":
            raise ValueError("persistent memory requires a real file path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise RuntimeError("unsupported Jade memory database schema")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS persons (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    consent INTEGER NOT NULL DEFAULT 1 CHECK (consent = 1)
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
                    source_message_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    UNIQUE(person_id,kind,scope,fingerprint),
                    CHECK (
                        (kind = 'ordinary' AND expires_at IS NOT NULL)
                        OR (kind != 'ordinary' AND expires_at IS NULL)
                    )
                );
                CREATE INDEX IF NOT EXISTS idx_memory_owner ON
                    memories(person_id,scope,kind,created_at);
            """)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def account(self, key: tuple[str, str]) -> str | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?",
                key,
            ).fetchone()
        return row["person_id"] if row else None

    def enable(self, key: tuple[str, str]) -> str:
        """A user-initiated command explicitly authorizes personal memory."""
        if key[0] not in ("discord", "twitch") or not _KEY.fullmatch(key[1]):
            raise ValueError("unsupported authenticated identity")
        with self._connect() as db:
            found = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if found:
                return found["person_id"]
            person_id = uuid.uuid4().hex
            db.execute("INSERT INTO persons(id,created_at) VALUES (?,?)",
                       (person_id, _now()))
            db.execute("INSERT INTO identities(platform,account_id,person_id) VALUES (?,?,?)",
                       (*key, person_id))
            return person_id

    def forget(self, key: tuple[str, str]) -> bool:
        """Explicit user erasure, including Core Memories and linked identities."""
        with self._connect() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if row is None:
                return False
            db.execute("DELETE FROM persons WHERE id=?", (row["person_id"],))
            return True

    def put(self, key: tuple[str, str], *, kind: str, scope: str, summary: str,
            significance: str = "", message_id: str = "", ordinary_days: int = 90) -> bool:
        """Only consented accounts; Core has no expiry, even if pruned later."""
        if kind not in KINDS or not 1 <= ordinary_days <= 365 or not scope:
            raise ValueError("invalid memory metadata")
        if (not isinstance(summary, str) or not summary.strip() or len(summary) > 400
                or not isinstance(significance, str) or len(significance) > 280):
            raise ValueError("invalid memory contents")
        expires = (datetime.now(timezone.utc) + timedelta(days=ordinary_days)).isoformat(
            timespec="seconds") if kind == "ordinary" else None
        with self._connect() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if row is None:
                return False
            cursor = db.execute("""
                INSERT OR IGNORE INTO memories(
                    id,person_id,kind,scope,summary,significance,fingerprint,
                    source_platform,source_message_id,created_at,expires_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    uuid.uuid4().hex, row["person_id"], kind, scope,
                    summary.strip(), significance.strip(), _digest(summary),
                    key[0], message_id[:128], _now(), expires,
                ))
            return cursor.rowcount > 0

    def recall(self, key: tuple[str, str], scope: str, *, limit: int = 8) -> list[dict]:
        if not 1 <= limit <= 32:
            raise ValueError("invalid memory recall limit")
        with self._connect() as db:
            rows = db.execute("""
                SELECT m.kind,m.summary,m.significance,m.created_at
                FROM memories m JOIN identities i ON i.person_id=m.person_id
                WHERE i.platform=? AND i.account_id=? AND m.scope=?
                  AND (m.expires_at IS NULL OR m.expires_at>?)
                ORDER BY CASE WHEN m.kind='ordinary' THEN 1 ELSE 0 END,
                         m.created_at DESC
                LIMIT ?
                """, (*key, scope, _now(), limit)).fetchall()
        return [dict(row) for row in rows]

    def list_for_account(self, key: tuple[str, str]) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("""
                SELECT m.id,m.kind,m.scope,m.summary,m.significance,
                       m.created_at,m.expires_at
                FROM memories m JOIN identities i ON i.person_id=m.person_id
                WHERE i.platform=? AND i.account_id=?
                ORDER BY m.created_at DESC
                """, key).fetchall()
        return [dict(row) for row in rows]

    def prune_ordinary(self) -> int:
        """Never touches Core: these rows cannot have an expiry by constraint."""
        with self._connect() as db:
            result = db.execute(
                "DELETE FROM memories WHERE kind='ordinary' AND expires_at<=?", (_now(),)
            )
            return result.rowcount

    def link_verified(self, first: tuple[str, str], second: tuple[str, str], *,
                      verified: bool = False) -> bool:
        """A caller must verify BOTH accounts out of band before requesting a link.

        Not exposed to Discord/Twitch messages. The explicit flag is not proof,
        merely an API guard until an authenticated challenge flow is built.
        """
        if verified is not True:
            raise PermissionError("both accounts must be independently verified")
        if first == second:
            return False
        with self._connect() as db:
            rows = []
            for key in (first, second):
                rows.append(db.execute(
                    "SELECT person_id FROM identities WHERE platform=? AND account_id=?",
                    key).fetchone())
            if None in rows:
                return False
            primary, secondary = rows[0]["person_id"], rows[1]["person_id"]
            if primary == secondary:
                return False
            # Preserve all memories; avoid duplicate keys with the same fingerprint.
            db.execute("""
                DELETE FROM memories WHERE person_id=? AND EXISTS (
                    SELECT 1 FROM memories old WHERE old.person_id=?
                    AND old.kind=memories.kind AND old.scope=memories.scope
                    AND old.fingerprint=memories.fingerprint)
            """, (secondary, primary))
            db.execute("UPDATE memories SET person_id=? WHERE person_id=?", (primary, secondary))
            db.execute("UPDATE identities SET person_id=? WHERE person_id=?", (primary, secondary))
            db.execute("DELETE FROM persons WHERE id=?", (secondary,))
            return True

    def unlink(self, key: tuple[str, str]) -> bool:
        """Split one identity without copying another identity's private memories."""
        with self._connect() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if row is None:
                return False
            count = db.execute("SELECT COUNT(*) FROM identities WHERE person_id=?",
                               (row["person_id"],)).fetchone()[0]
            if count <= 1:
                return False
            new_id = uuid.uuid4().hex
            db.execute("INSERT INTO persons(id,created_at) VALUES (?,?)", (new_id, _now()))
            db.execute("UPDATE identities SET person_id=? WHERE platform=? AND account_id=?",
                       (new_id, *key))
            # Origin is recorded; only that account's source memories move.
            # Shared memories from other accounts never become accessible.
            db.execute("UPDATE memories SET person_id=? WHERE person_id=? AND source_platform=?",
                       (new_id, row["person_id"], key[0]))
            return True
