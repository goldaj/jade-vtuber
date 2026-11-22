"""Persistent, owner-scoped reminders. No LLM polling or mobile background process.

The SQLite store is outside Git. A lightweight asyncio worker claims due reminders
and delivers to the original verified Discord channel or subscribed mobile PWA.
A push service acknowledging a message is not proof of handset presentation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import importlib.util
import ipaddress
import json
import logging
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

LOG = logging.getLogger("jade.reminders")

REMINDER_TOOL = {
    "type": "function",
    "function": {
        "name": "jade_manage_reminders",
        "description": (
            "Créer, consulter, modifier ou annuler un rappel planifié explicitement "
            "demandé par l'interlocuteur propriétaire vérifié. Ne jamais prétendre "
            "qu'une notification a été reçue sur un téléphone."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "list", "update", "cancel"]},
                "id": {"type": ["string", "null"]},
                "title": {"type": ["string", "null"]},
                "due_at": {"type": ["string", "null"],
                           "description": "Date ISO 8601 avec fuseau/offset, ex. 2026-11-24T10:00:00+01:00"},
            },
            "required": ["action", "id", "title", "due_at"],
            "additionalProperties": False,
        },
    },
}

REMINDER_PROMPT = (
    "\n\nTu peux appeler jade_manage_reminders pour gérer des rappels du "
    "propriétaire authentifié. Pour créer ou décaler un rappel, donne une date "
    "ISO 8601 avec décalage UTC explicite ; demande une précision si l'heure "
    "ou le jour est ambigu. Appelle l'outil AVANT de confirmer la création, "
    "la modification ou l'annulation. Si l'outil échoue, dis-le. Une "
    "programmation réussie ne garantit pas la réception physique des "
    "notifications ; le PC doit tourner et les notifications être autorisées."
)
_ID = re.compile(r"[0-9a-f]{24}\Z")
_KEY = re.compile(r"[A-Za-z0-9_-]{8,200}\Z")
_PUSH_HOSTS = (
    "fcm.googleapis.com", "updates.push.services.mozilla.com",
    "web.push.apple.com", "notify.windows.com",
)


def _valid_due(value: str) -> int:
    if not isinstance(value, str) or len(value) > 45:
        raise ValueError("date absente ou invalide")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("date ISO 8601 invalide") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("un fuseau horaire explicite est nécessaire")
    stamp = int(parsed.timestamp())
    if not time.time() < stamp <= time.time() + 366 * 86400:
        raise ValueError("le rappel doit être dans le futur, à moins d'un an")
    return stamp


def _valid_subscription(value: dict) -> tuple[str, str]:
    if not isinstance(value, dict) or set(value) != {"endpoint", "keys"}:
        raise ValueError("abonnement push invalide")
    endpoint, keys = value["endpoint"], value["keys"]
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        raise ValueError("endpoint push invalide")
    parsed = urlsplit(endpoint)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or not host
            or parsed.username or parsed.password or parsed.fragment
            or not any(host == v or host.endswith("." + v) for v in _PUSH_HOSTS)):
        raise ValueError("fournisseur push non pris en charge")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("endpoint IP interdit")
    if (not isinstance(keys, dict) or set(keys) != {"p256dh", "auth"}
            or not all(isinstance(keys[k], str) and _KEY.fullmatch(keys[k])
                       for k in ("p256dh", "auth"))):
        raise ValueError("clés d'abonnement invalides")
    return endpoint, json.dumps(
        {"endpoint": endpoint, "keys": keys}, separators=(",", ":"))


class ReminderStore:
    """Transactional claims protect against duplicate sends across worker ticks."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.suffix != ".sqlite3":
            raise ValueError("rappels : chemin SQLite privé absolu requis")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    due_at INTEGER NOT NULL,
                    destination TEXT NOT NULL,
                    channel TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL,
                    sent_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_reminders_due
                    ON reminders(state, next_attempt, due_at);
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    endpoint TEXT PRIMARY KEY,
                    subscription TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
            """)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def create(self, title: str, due_at: str, destination: str, channel="") -> dict:
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 180:
            raise ValueError("titre requis (180 caractères maximum)")
        if destination not in ("mobile", "discord"):
            raise ValueError("destination invalide")
        if destination == "discord" and not re.fullmatch(r"[0-9]{15,25}", channel):
            raise ValueError("salon Discord non vérifié")
        stamp, reminder_id, now = _valid_due(due_at), secrets.token_hex(12), int(time.time())
        with self._db() as db:
            db.execute(
                "INSERT INTO reminders "
                "(id,title,due_at,destination,channel,updated_at) VALUES (?,?,?,?,?,?)",
                (reminder_id, title.strip(), stamp, destination, channel, now),
            )
        return {"id": reminder_id, "title": title.strip(), "due_at": stamp,
                "destination": destination, "state": "pending"}

    def list(self, destination=None, channel="") -> list[dict]:
        where, args = "", []
        if destination == "discord":
            where, args = " WHERE destination='discord' AND channel=?", [channel]
        elif destination == "mobile":
            where = " WHERE destination='mobile'"
        with self._db() as db:
            rows = db.execute(
                "SELECT id,title,due_at,destination,state,sent_at "
                "FROM reminders" + where +
                " ORDER BY CASE state WHEN 'pending' THEN 0 WHEN 'retry' THEN 0 "
                "ELSE 1 END, due_at DESC LIMIT 40", args).fetchall()
        return [dict(row) for row in rows]

    def change(self, reminder_id: str, *, cancel=False, title=None, due_at=None,
               destination=None, channel="") -> dict:
        if not isinstance(reminder_id, str) or not _ID.fullmatch(reminder_id):
            raise ValueError("identifiant invalide")
        if not cancel and title is None and due_at is None:
            raise ValueError("nouveau titre ou nouvelle date requis")
        if title is not None and (not isinstance(title, str)
                                  or not 1 <= len(title.strip()) <= 180):
            raise ValueError("titre invalide")
        stamp = _valid_due(due_at) if due_at is not None else None
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
            if (row is None or (destination and row["destination"] != destination)
                    or (destination == "discord" and row["channel"] != channel)):
                raise ValueError("rappel introuvable")
            if cancel:
                if row["state"] == "sent":
                    raise ValueError("rappel déjà envoyé")
                db.execute(
                    "UPDATE reminders SET state='cancelled',updated_at=? WHERE id=?",
                    (int(time.time()), reminder_id))
            else:
                if row["state"] == "sending":
                    raise ValueError("envoi déjà en cours, réessaie ensuite")
                if row["state"] == "cancelled":
                    raise ValueError("rappel déjà annulé")
                db.execute(
                    "UPDATE reminders SET title=?,due_at=?,state='pending',"
                    "attempts=0,next_attempt=0,updated_at=?,sent_at=NULL WHERE id=?",
                    (title.strip() if title is not None else row["title"],
                     stamp if stamp is not None else row["due_at"],
                     int(time.time()), reminder_id))
            updated = db.execute(
                "SELECT id,title,due_at,destination,state FROM reminders WHERE id=?",
                (reminder_id,)).fetchone()
        return dict(updated)

    def subscribe(self, data: dict) -> None:
        endpoint, serialized = _valid_subscription(data)
        with self._db() as db:
            db.execute(
                "INSERT INTO push_subscriptions(endpoint,subscription,updated_at) "
                "VALUES (?,?,?) ON CONFLICT(endpoint) DO UPDATE SET "
                "subscription=excluded.subscription,updated_at=excluded.updated_at",
                (endpoint, serialized, int(time.time())))

    def unsubscribe(self, endpoint: str) -> None:
        if not isinstance(endpoint, str) or len(endpoint) > 2048:
            raise ValueError("endpoint invalide")
        with self._db() as db:
            db.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (endpoint,))

    def subscriptions(self) -> list[dict]:
        with self._db() as db:
            rows = db.execute(
                "SELECT subscription FROM push_subscriptions ORDER BY updated_at DESC "
                "LIMIT 12").fetchall()
        return [json.loads(row["subscription"]) for row in rows]

    def claim_due(self, limit=10) -> list[dict]:
        now = int(time.time())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE reminders SET state='retry',next_attempt=?,updated_at=? "
                "WHERE state='sending' AND updated_at<?",
                (now, now, now - 120))
            rows = db.execute(
                "SELECT id,title,due_at,destination,channel,attempts FROM reminders "
                "WHERE state IN ('pending','retry') AND due_at<=? AND next_attempt<=? "
                "ORDER BY due_at LIMIT ?", (now, now, limit)).fetchall()
            for row in rows:
                db.execute(
                    "UPDATE reminders SET state='sending',updated_at=? WHERE id=?",
                    (now, row["id"]))
        return [dict(row) for row in rows]

    def complete(self, reminder_id: str, success: bool) -> None:
        now = int(time.time())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT attempts,state FROM reminders WHERE id=?", (reminder_id,)).fetchone()
            if row is None or row["state"] != "sending":
                return
            attempts = row["attempts"] + 1
            state = ("sent" if success else "failed" if attempts >= 12 else "retry")
            delay = min(3600, 15 * (2 ** min(attempts - 1, 8)))
            db.execute(
                "UPDATE reminders SET state=?,attempts=?,next_attempt=?,updated_at=?,"
                "sent_at=? WHERE id=?",
                (state, attempts, now + delay if state == "retry" else 0,
                 now, now if success else None, reminder_id))


class PushSender:
    """Web Push only when explicitly configured; no hidden external providers."""

    def __init__(self, public_key="", private_key="", subject=""):
        self.public_key, self.private_key, self.subject = public_key, private_key, subject

    @property
    def configured(self) -> bool:
        return bool(self.public_key and self.private_key and self.subject
                    and importlib.util.find_spec("pywebpush") is not None)

    def send(self, subscription: dict, reminder_id: str) -> bool | None:
        """True=push provider accepted, None=subscription permanently expired."""
        if not self.configured:
            return False
        from pywebpush import webpush, WebPushException
        try:
            webpush(
                subscription_info=subscription,
                data=json.dumps({"type": "reminder", "id": reminder_id}),
                vapid_private_key=self.private_key,
                vapid_claims={"sub": self.subject},
                ttl=86400, timeout=8,
            )
            return True
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            if getattr(response, "status_code", None) in (404, 410):
                return None
            LOG.warning("Push provider rejected a reminder (no payload logged)")
            return False
        except (OSError, ValueError):
            LOG.warning("Push provider unavailable (no payload logged)")
            return False


class ReminderAction:
    def __init__(self, service, destination, channel):
        self.service, self.destination, self.channel = service, destination, channel

    async def manage_reminder(self, arguments: str) -> dict:
        try:
            value = json.loads(arguments)
            if (not isinstance(value, dict) or
                    set(value) != {"action", "id", "title", "due_at"}):
                raise ValueError("paramètres invalides")
            action = value["action"]
            if action == "list":
                items = await asyncio.to_thread(
                    self.service.store.list, self.destination, self.channel)
                return {"status": "ok", "items": items}
            if action == "create":
                result = await asyncio.to_thread(
                    self.service.store.create, value["title"], value["due_at"],
                    self.destination, self.channel)
            elif action in ("update", "cancel"):
                result = await asyncio.to_thread(
                    self.service.store.change, value["id"],
                    cancel=(action == "cancel"), title=value["title"],
                    due_at=value["due_at"], destination=self.destination,
                    channel=self.channel)
            else:
                raise ValueError("action inconnue")
            return {"status": "ok", "reminder": result}
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            return {"status": "refusé", "message": str(exc)}


class ReminderService:
    def __init__(self, path: str | Path, *, memory_store=None,
                 vapid_public="", vapid_private="", vapid_subject=""):
        self.store = ReminderStore(path)
        self.memory_store = memory_store
        self.push = PushSender(vapid_public, vapid_private, vapid_subject)

    async def for_turn(self, incoming):
        if incoming.platform == "mobile":
            return ReminderAction(self, "mobile", "")
        if (incoming.platform not in ("discord", "discord_voice")
                or not incoming.account_id or self.memory_store is None):
            return None
        try:
            linked = await asyncio.to_thread(
                self.memory_store.is_goldaj, ("discord", incoming.account_id))
        except (ValueError, sqlite3.Error, OSError):
            linked = False
        if linked and re.fullmatch(r"[0-9]{15,25}", incoming.channel):
            return ReminderAction(self, "discord", incoming.channel)
        return None

    async def run_forever(self, *, discord_sender=None):
        while True:
            try:
                due = await asyncio.to_thread(self.store.claim_due)
                for reminder in due:
                    success = False
                    try:
                        if reminder["destination"] == "discord":
                            if discord_sender is not None:
                                success = bool(await discord_sender(
                                    reminder["channel"],
                                    "Rappel Jade : " + reminder["title"]))
                        else:
                            subscriptions = await asyncio.to_thread(
                                self.store.subscriptions)
                            for subscription in subscriptions:
                                result = await asyncio.to_thread(
                                    self.push.send, subscription, reminder["id"])
                                if result is None:
                                    await asyncio.to_thread(
                                        self.store.unsubscribe, subscription["endpoint"])
                                else:
                                    success = result or success
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        LOG.warning("Reminder delivery unavailable (no content logged)")
                    finally:
                        await asyncio.to_thread(
                            self.store.complete, reminder["id"], success)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.warning("Reminder scheduler iteration failed (no content logged)")
            await asyncio.sleep(5)
