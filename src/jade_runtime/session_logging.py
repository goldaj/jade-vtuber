"""Session-scoped diagnostics: readable IDE console and private detailed file.

One timestamped file is created for each Python process start. Detailed
conversation contents stay local and are never committed to Git.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys

_CONTEXT = ContextVar("jade_log_context", default={})
_SESSION_FILE: Path | None = None
_AUDIT = logging.getLogger("jade.audit")
_SUMMARY = logging.getLogger("jade.summary")

_SECRET_PATTERNS = (
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\bgh[pousr]_[A-Za-z0-9_]{12,}\b"),
    re.compile(r"(?i)(\b(?:authorization|api[_-]?key|password|client_secret|access_token|refresh_token|token)\b\s*[:=]\s*)([^\s,;}\]]+)"),
    re.compile(r"(?i)(\bBearer\s+)([A-Za-z0-9._~+/-]{8,})"),
    re.compile(r"(?i)(!jade-memoire\s+confirmer\s+)\S+"),
)


def redact(value: str) -> str:
    """Best-effort secret redaction. The file remains sensitive: keep it private."""
    if not isinstance(value, str):
        value = str(value)
    for index, pattern in enumerate(_SECRET_PATTERNS):
        if index < 2:
            value = pattern.sub("[SECRET MASQUÉ]", value)
        else:
            value = pattern.sub(lambda match: match.group(1) + "[SECRET MASQUÉ]", value)
    return value


def _safe(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_safe(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact(repr(value))


class _SafeFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


class _ConsoleFilter(logging.Filter):
    def filter(self, record):
        # Full incoming texts, raw model output and database events belong
        # exclusively in the local detailed file, never in the IDE console.
        return record.name not in ("jade.audit", "jade.conversation")


def start_session_logging(directory: str | Path | None = None) -> Path:
    """Attach one console and one file handler, without truncating older sessions."""
    global _SESSION_FILE
    if _SESSION_FILE is not None:
        return _SESSION_FILE
    folder = (Path(directory) if directory is not None
              else Path(__file__).resolve().parents[2] / "logs" / "sessions")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d_%H-%M-%S_%f%z")
    filepath = folder / f"jade_{stamp}_pid-{os.getpid()}.log"
    file_handler = logging.FileHandler(filepath, mode="x", encoding="utf-8")
    try:
        os.chmod(filepath, 0o600)
    except OSError:
        pass  # Windows ACLs remain controlled by the current user.
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(_SafeFormatter(
        "%(asctime)s %(levelname)-7s %(name)s %(message)s"))

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(_SafeFormatter(
        "%(asctime)s %(levelname)-7s %(name)s %(message)s"))
    console_handler.addFilter(_ConsoleFilter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    logging.captureWarnings(True)
    _SESSION_FILE = filepath
    summary("session_started", log_file=str(filepath), pid=os.getpid())
    event("session_started", log_file=str(filepath), pid=os.getpid())
    return filepath


def session_file() -> Path | None:
    return _SESSION_FILE


def bind_turn(turn: int, incoming):
    return _CONTEXT.set({
        "turn": turn,
        "source_platform": incoming.platform,
        "source_channel": "[privé]" if (incoming.platform in ("mobile", "microphone", "local_http")
            or (incoming.platform == "discord" and incoming.private_channel)) else incoming.channel,
    })


def reset_turn(token) -> None:
    _CONTEXT.reset(token)


def event(name: str, **fields) -> None:
    """Detailed JSON line in the session log, with no console duplication."""
    payload = {"event": name, **_CONTEXT.get(), **fields}
    _AUDIT.info("%s", json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":")))


def summary(name: str, **fields) -> None:
    """Short structured milestone in PyCharm and the session file."""
    payload = {"event": name, **fields}
    _SUMMARY.info("%s", json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":")))
