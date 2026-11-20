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

SCHEMA_VERSION = 4
CONVERSATION_RETENTION_DAYS = 7
CONVERSATION_RELOAD_HOURS = 24
ORDINARY_RETENTION_DAYS = 365
KINDS = frozenset(("ordinary", "core_self", "core_relationship"))
_ID = re.compile(r"^[1-9][0-9]{0,24}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def identity_of(message) -> tuple[str, str] | None:
    """Resolve trusted connector identities; local mic and private mobile are Goldaj."""
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
            if version not in (0, 1, 2, 3, SCHEMA_VERSION):
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
                -- A Discord user who erases memory must not be re-enrolled on next turn.
                CREATE TABLE IF NOT EXISTS memory_auto_enrollment_blocks (
                    platform TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(platform, account_id)
                );
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
                -- Separate autobiography from person-bound relationship memories.
                -- Global to Jade's own timeline, but initially owner-only.
                CREATE TABLE IF NOT EXISTS jade_self_core (
                    id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    significance TEXT NOT NULL,
                    fingerprint TEXT NOT NULL UNIQUE,
                    source_platform TEXT NOT NULL,
                    source_account_id TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    visibility TEXT NOT NULL DEFAULT 'owner_only'
                        CHECK(visibility='owner_only')
                );
                CREATE INDEX IF NOT EXISTS idx_jade_self_core_recency
                    ON jade_self_core(created_at DESC);
                -- Complete, non-summarized dialogue turns, strictly opt-in per verified identity.
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                    scope TEXT NOT NULL,
                    source_platform TEXT NOT NULL,
                    source_message_id TEXT,
                    user_content TEXT NOT NULL,
                    assistant_content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(person_id,scope,source_platform,source_message_id)
                );
                CREATE INDEX IF NOT EXISTS idx_conversation_turns_scope
                    ON conversation_turns(person_id,scope,id DESC);
                CREATE INDEX IF NOT EXISTS idx_conversation_turns_recent
                    ON conversation_turns(person_id,scope,created_at,id);
            """)
            if version < SCHEMA_VERSION:
                # One-time migration: extend existing ordinary memories from
                # their ORIGINAL creation timestamp, never from migration day.
                # Core rows are left untouched with NULL expiration.
                rows = db.execute(
                    "SELECT id,created_at FROM memories WHERE kind='ordinary'"
                ).fetchall()
                updates = []
                for row in rows:
                    created = datetime.fromisoformat(row["created_at"])
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    updates.append((
                        (created + timedelta(days=ORDINARY_RETENTION_DAYS)).isoformat(),
                        row["id"],
                    ))
                db.executemany(
                    "UPDATE memories SET expires_at=? WHERE id=?", updates)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        # Purge expired rows on open, including DBs created before this policy.
        self.prune_expired()

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

    def auto_enable(self, key: tuple[str, str]) -> bool:
        """Enroll a verified Discord user unless they explicitly opted out."""
        _validate_key(key)
        if key[0] != "discord":
            return False
        with self._db() as db:
            if db.execute(
                "SELECT 1 FROM memory_auto_enrollment_blocks WHERE platform=? AND account_id=?",
                key,
            ).fetchone():
                return False
            if db.execute(
                "SELECT 1 FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone():
                return True
            person = uuid.uuid4().hex
            db.execute("INSERT INTO persons(id,created_at) VALUES (?,?)",
                       (person, _now().isoformat()))
            db.execute("INSERT INTO identities(platform,account_id,person_id) VALUES (?,?,?)",
                       (*key, person))
            return True

    def block_auto_enrollment(self, key: tuple[str, str]) -> None:
        """Persist a minimal verified account ID after a Discord erasure."""
        _validate_key(key)
        if key[0] != "discord":
            return
        with self._db() as db:
            db.execute(
                "INSERT OR IGNORE INTO memory_auto_enrollment_blocks VALUES (?,?,?)",
                (*key, _now().isoformat()))

    def enable(self, key: tuple[str, str]) -> str:
        """Explicit activation, including reactivation after an opt-out."""
        _validate_key(key)
        with self._db() as db:
            db.execute(
                "DELETE FROM memory_auto_enrollment_blocks WHERE platform=? AND account_id=?", key)
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
            # Deleting *any* identity in the linked owner profile erases
            # autobiography sourced by Goldaj too. Otherwise an erasure from
            # a linked Discord/Twitch account leaves orphan core memories
            # which can reappear when the local owner is enabled again.
            owner_present = db.execute("""
                SELECT 1 FROM identities WHERE person_id=?
                  AND platform='microphone' AND account_id='goldaj'
                """, (row["person_id"],)).fetchone()
            if owner_present:
                db.execute("""
                    DELETE FROM jade_self_core
                    WHERE (source_platform,source_account_id) IN (
                        SELECT platform,account_id FROM identities WHERE person_id=?)
                    """, (row["person_id"],))
            db.execute("DELETE FROM persons WHERE id=?", (row["person_id"],))
            db.execute("DELETE FROM link_challenges WHERE platform=? AND account_id=?", key)
            return True

    def forget_own_identity(self, key: tuple[str, str]) -> bool:
        """Erase only data originating from the verified account.

        The legacy forget() API intentionally deletes an entire linked person.
        Public Discord/Twitch commands MUST use this narrower operation so an
        external account cannot wipe Goldaj's private memories or another
        account's data. Old turn rows lack account_id, so ambiguous same-provider
        detachments are refused rather than deleting another user's history.
        """
        _validate_key(key)
        with self._db() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if row is None:
                return False
            # Erase owner-directed autobiography entries originating from this
            # transport identity, without touching other linked accounts.
            db.execute(
                "DELETE FROM jade_self_core WHERE source_platform=? AND source_account_id=?",
                key)
            person = row["person_id"]
            size = db.execute(
                "SELECT COUNT(*) FROM identities WHERE person_id=?", (person,)
            ).fetchone()[0]
            if size == 1:
                # Isolated account: preserve existing complete-erasure behavior.
                if key == ("microphone", "goldaj"):
                    db.execute("""
                        DELETE FROM jade_self_core
                        WHERE source_platform='microphone' AND source_account_id='goldaj'
                    """)
                db.execute("DELETE FROM persons WHERE id=?", (person,))
            else:
                same_provider = db.execute(
                    "SELECT COUNT(*) FROM identities WHERE person_id=? AND platform=?",
                    (person, key[0])).fetchone()[0]
                if same_provider != 1:
                    raise ValueError("cannot safely erase an ambiguous linked account")
                if key == ("microphone", "goldaj"):
                    db.execute("""
                        DELETE FROM jade_self_core
                        WHERE source_platform='microphone' AND source_account_id='goldaj'
                    """)
                db.execute("""
                    DELETE FROM memories WHERE person_id=?
                    AND source_platform=? AND source_account_id=?
                """, (person, *key))
                platforms = (("microphone", "mobile") if key == ("microphone", "goldaj")
                             else ("discord", "discord_voice") if key[0] == "discord"
                             else (key[0],))
                db.execute(
                    "DELETE FROM conversation_turns WHERE person_id=? "
                    "AND source_platform IN (" +
                    ",".join("?" for _ in platforms) + ")",
                    (person, *platforms))
                db.execute(
                    "DELETE FROM identities WHERE platform=? AND account_id=?", key)
            db.execute(
                "DELETE FROM link_challenges WHERE platform=? AND account_id=?", key)
            return True

    def put(self, key: tuple[str, str], *, kind: str, scope: str, summary: str,
            significance: str = "", message_id: str = "", ordinary_days: int = ORDINARY_RETENTION_DAYS,
            expected_person_id: str | None = None) -> bool:
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
            if not row or (expected_person_id is not None
                           and row["person_id"] != expected_person_id):
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

    def put_requested_ordinary(self, key: tuple[str, str], *, scope: str,
                               summary: str, message_id: str = "",
                               expected_person_id: str | None = None,
                               ordinary_days: int = ORDINARY_RETENTION_DAYS) -> str:
        """Persist an explicit memory request as ORDINARY, never Core.

        Consent, identity, duplicate check and insertion happen atomically.
        Neither Goldaj nor external users may pick a Core kind through here.
        Returns created/already_exists/inactive after the transaction commits.
        """
        _validate_key(key)
        if (not isinstance(scope, str)
                or not (scope == "person" or
                        (scope.startswith(("discord:", "discord_voice:", "twitch:"))
                         and 1 <= len(scope) <= 128))
                or not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 400
                or not isinstance(message_id, str)
                or type(ordinary_days) is not int or not 1 <= ordinary_days <= 365):
            raise ValueError("invalid ordinary memory request")
        summary = summary.strip()
        fingerprint = _fingerprint(summary)
        when = _now()
        expires = (when + timedelta(days=ordinary_days)).isoformat()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            person = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if person is None or (expected_person_id is not None
                                  and person["person_id"] != expected_person_id):
                return "inactive"
            if db.execute("""
                SELECT 1 FROM memories
                WHERE person_id=? AND kind='ordinary' AND scope=? AND fingerprint=?
            """, (person["person_id"], scope, fingerprint)).fetchone():
                return "already_exists"
            db.execute("""
                INSERT INTO memories
                (id,person_id,kind,scope,summary,significance,fingerprint,
                 source_platform,source_account_id,source_message_id,
                 created_at,expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (uuid.uuid4().hex, person["person_id"], "ordinary", scope,
                  summary, "Souvenir conservé à la demande explicite de l'interlocuteur.",
                  fingerprint, *key, message_id[:128], when.isoformat(), expires))
            return "created"

    def put_self_core(self, key: tuple[str, str], *, summary: str,
                      significance: str = "", message_id: str = "",
                      expected_person_id: str | None = None) -> bool:
        """Jade's own lasting episodes, owner-only until explicit promotion exists.

        Only an opted-in, locally verified owner may populate the global table.
        No TTL, no retention purge, no copy into other people's prompt context.
        """
        _validate_key(key)
        if key != ("microphone", "goldaj"):
            return False
        if (not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 400
                or not isinstance(significance, str) or len(significance) > 280
                or not isinstance(message_id, str)):
            raise ValueError("invalid Jade autobiography")
        with self._db() as db:
            profile = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if not profile or (expected_person_id is not None
                               and profile["person_id"] != expected_person_id):
                return False
            written = db.execute("""
                INSERT OR IGNORE INTO jade_self_core
                (id,summary,significance,fingerprint,source_platform,
                 source_account_id,source_message_id,created_at,visibility)
                VALUES (?,?,?,?,?,?,?,?, 'owner_only')
                """, (uuid.uuid4().hex, summary.strip(), significance.strip(),
                      _fingerprint(summary), key[0], key[1], message_id[:128],
                      _now().isoformat()))
            return written.rowcount > 0

    def recall_self_core(self, key: tuple[str, str], *, limit: int = 6) -> list[dict]:
        """Read only for the verified Goldaj profile; never disclose to a server."""
        _validate_key(key)
        if not 1 <= limit <= 20:
            raise ValueError("invalid autobiography recall limit")
        if key != ("microphone", "goldaj"):
            return []
        with self._db() as db:
            if not db.execute(
                    "SELECT 1 FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone():
                return []
            rows = db.execute("""
                SELECT id,summary,significance,created_at,visibility
                FROM jade_self_core WHERE visibility='owner_only'
                ORDER BY created_at DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def delete_self_core(self, key: tuple[str, str], memory_id: str) -> bool:
        """Owner-selected erasure of one autobiographical Core Memory."""
        _validate_key(key)
        if key != ("microphone", "goldaj"):
            return False
        if not isinstance(memory_id, str) or not re.fullmatch(r"[0-9a-f]{32}", memory_id):
            raise ValueError("invalid autobiographical memory identifier")
        with self._db() as db:
            if not db.execute(
                    "SELECT 1 FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone():
                return False
            deleted = db.execute("""
                DELETE FROM jade_self_core WHERE id=? AND visibility='owner_only'""",
                (memory_id,))
            return deleted.rowcount > 0

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

    def prune_conversation_turns(self) -> int:
        """Delete raw conversations older than seven days; never Core rows."""
        cutoff = (_now() - timedelta(days=CONVERSATION_RETENTION_DAYS)).isoformat()
        with self._db() as db:
            deleted = db.execute(
                "DELETE FROM conversation_turns WHERE created_at<=?", (cutoff,))
            return deleted.rowcount

    def prune_expired(self) -> tuple[int, int]:
        """Periodic housekeeping: expired level-1 turns and ordinary level-2.

        Retention never deletes a Core Memory. Explicit user erasure remains
        possible independently of these automatic timers.
        """
        now = _now()
        with self._db() as db:
            turns = db.execute(
                "DELETE FROM conversation_turns WHERE created_at<=?",
                ((now - timedelta(days=CONVERSATION_RETENTION_DAYS)).isoformat(),)
            ).rowcount
            ordinary = db.execute(
                "DELETE FROM memories WHERE kind='ordinary' AND expires_at<=?",
                (now.isoformat(),)
            ).rowcount
        return (turns, ordinary)

    def append_conversation_turn(self, key: tuple[str, str], scope: str, *,
                                 source_platform: str, message_id: str,
                                 user_content: str, assistant_content: str) -> bool:
        """Persist a complete delivered turn only for an opted-in verified person.

        A blank transport message ID is stored as NULL so consecutive local turns
        cannot accidentally overwrite or deduplicate each other.
        """
        _validate_key(key)
        if (not isinstance(scope, str) or not 1 <= len(scope) <= 256
                or not isinstance(source_platform, str) or not 1 <= len(source_platform) <= 32
                or not isinstance(message_id, str) or len(message_id) > 128
                or not isinstance(user_content, str) or not 1 <= len(user_content) <= 5000
                or not isinstance(assistant_content, str) or not 1 <= len(assistant_content) <= 5000):
            raise ValueError("invalid conversation turn")
        with self._db() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if row is None:
                return False
            changed = db.execute("""
                INSERT OR IGNORE INTO conversation_turns
                  (person_id,scope,source_platform,source_message_id,
                   user_content,assistant_content,created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (row["person_id"],scope,source_platform,message_id or None,
                  user_content,assistant_content,_now().isoformat())).rowcount
            return bool(changed)

    def recent_conversation_turns(self, key: tuple[str, str], scope: str,
                                  *, within_hours: int = CONVERSATION_RELOAD_HOURS) -> list[dict]:
        """Return ALL verified-account turns within a rolling 24h window.

        No count-based SQL LIMIT; ordering and channel/identity isolation are
        preserved. The database only retains seven days of full transcripts.
        """
        _validate_key(key)
        if not isinstance(scope, str) or not 1 <= len(scope) <= 256:
            raise ValueError("invalid conversation history scope")
        if type(within_hours) is not int or not 1 <= within_hours <= 168:
            raise ValueError("invalid history recovery window")
        cutoff = (_now() - timedelta(hours=within_hours)).isoformat()
        with self._db() as db:
            row = db.execute(
                "SELECT person_id FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone()
            if row is None:
                return []
            turns = db.execute("""
                SELECT user_content, assistant_content FROM conversation_turns
                WHERE person_id=? AND scope=? AND created_at>=?
                ORDER BY created_at ASC,id ASC
            """, (row["person_id"], scope, cutoff)).fetchall()
        result = []
        for turn in turns:
            result.append({"role": "user", "content": turn["user_content"]})
            result.append({"role": "assistant", "content": turn["assistant_content"]})
        return result

    def begin_link(self, key: tuple[str, str], *, ttl_seconds: int = 300,
                   target: tuple[str, str] | None = None) -> str:
        """Generate a one-time, short-lived secret for *another* authenticated account.

        Unbound legacy tokens must stay private. Target-bound v1 codes may be
        confirmed in a public chat, since only the verified target can redeem.
        """
        _validate_key(key)
        if not 30 <= ttl_seconds <= 600:
            raise ValueError("invalid link TTL")
        if target is not None:
            _validate_key(target)
            if target[0] == key[0]:
                raise ValueError("identity links must cross platforms")
        token = secrets.token_urlsafe(24)
        if target is not None:
            # Trust the target identity supplied by its authenticated connector.
            # The target-bound token cannot be redeemed by another chatter.
            token = f"v1.{target[0]}.{target[1]}.{token}"
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._db() as db:
            if not db.execute(
                "SELECT 1 FROM identities WHERE platform=? AND account_id=?", key
            ).fetchone():
                raise PermissionError("opt-in required for source account")
            db.execute("DELETE FROM link_challenges WHERE expires_at<=?",
                       (_now().isoformat(),))
            # Keep at most one outstanding code per verified source account.
            # A new request invalidates the previous code rather than allowing
            # an unbounded pile of outstanding identity challenges.
            db.execute("DELETE FROM link_challenges WHERE platform=? AND account_id=?",
                       key)
            db.execute("INSERT INTO link_challenges VALUES (?,?,?,?)",
                       (digest, *key, (_now() + timedelta(seconds=ttl_seconds)).isoformat()))
        return token

    def complete_link(self, target: tuple[str, str], token: str) -> bool:
        """Prove control of both accounts by making each call under its trusted ID.

        Legacy unbound codes are for internal API only; public confirmation
        first verifies the target-bound v1 prefix against the trusted account.
        """
        _validate_key(target)
        if not isinstance(token, str) or len(token) > 128:
            return False
        if token.startswith("v1."):
            fields = token.split(".", 3)
            if (len(fields) != 4 or tuple(fields[1:3]) != target
                    or len(fields[3]) < 24):
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
                # Preserve complete opt-in conversation history before deleting the old
                # person; ON DELETE CASCADE would otherwise silently erase it.
                db.execute("UPDATE memories SET person_id=? WHERE person_id=?", (a, b))
                db.execute("UPDATE conversation_turns SET person_id=? WHERE person_id=?", (a, b))
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
            # Old turn rows identify a platform but not a specific account.
            # Refuse ambiguous detachments rather than misassign private history.
            same_platform = db.execute(
                "SELECT COUNT(*) FROM identities WHERE person_id=? AND platform=?",
                (person, key[0])).fetchone()[0]
            if same_platform != 1:
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
            # Both authenticated PWA and the private PC microphone represent
            # Goldaj; their stored source_platform fields are distinct even
            # though identity_of maps them to a single account key.
            if key == ("microphone", "goldaj"):
                platforms = ("microphone", "mobile")
            elif key[0] == "discord":
                # Discord text and voice carry separate transport labels but
                # share the same verified Discord identity.
                platforms = ("discord", "discord_voice")
            else:
                platforms = (key[0],)
            db.execute(
                "UPDATE conversation_turns SET person_id=? "
                "WHERE person_id=? AND source_platform IN (" +
                ",".join("?" for _ in platforms) + ")",
                (separate, person, *platforms))
            db.execute("DELETE FROM link_challenges WHERE platform=? AND account_id=?", key)
            return True
