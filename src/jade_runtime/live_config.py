"""Mobile Live defaults and transport limits, independent of classic STT/TTS."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from pathlib import Path
from typing import Callable

from .live_voice import LIVE_DELIVERY_PROMPT, PETILLANTE_SESSION_PROMPT, LiveVoice
from .discord_config import is_discord_enabled


def _default_db_path() -> str:
    # Keep the deployed filename so previous usage records remain readable.
    # Its historical name no longer denotes a financial admission policy.
    if os.name == "nt" and Path("D:/").is_dir():
        return "D:/Jade/private/jade-live-budget.sqlite3"
    return str(Path.home() / ".jade" / "jade-live-budget.sqlite3")


def _bool(value: object) -> bool:
    normalized = str(value).strip().lower()
    if normalized in ("1", "true", "yes"):
        return True
    if normalized in ("0", "false", "no", ""):
        return False
    raise ValueError("Live boolean settings must be true/false or 1/0")


@dataclass(frozen=True)
class LiveConfig:
    enabled: bool = True
    mobile_enabled: bool = True
    discord_enabled: bool = field(default_factory=is_discord_enabled)
    model: str = "gpt-live-1.1"
    voice: str = "brise"
    voice_id: str = ""
    heartbeat_seconds: float = 2.0
    lease_seconds: float = 5.0
    idle_standby_seconds: int = 8
    idle_close_seconds: float = 30.0
    opening_timeout_seconds: float = 8.0
    close_timeout_seconds: float = 5.0
    muted_drain_seconds: float = 15.0
    max_session_seconds: float = 600.0
    max_starts_per_minute: int = 3
    max_delegations_per_session: int = 12
    usage_db_path: str = field(default_factory=_default_db_path)
    session_db_path: str = ""
    voice_style: str = ""

    @classmethod
    def from_env(cls, getter: Callable[[str, str], object]) -> "LiveConfig":
        def get(name: str, default: object) -> str:
            return str(getter(name, str(default))).strip()

        cfg = cls(
            enabled=_bool(get("JADE_LIVE_ENABLED", "true")),
            mobile_enabled=_bool(get("JADE_MOBILE_LIVE_ENABLED", "true")),
            discord_enabled=is_discord_enabled(),
            model=get("JADE_LIVE_MODEL", "gpt-live-1.1"),
            voice=get("JADE_LIVE_VOICE", "brise"),
            voice_id=get("JADE_LIVE_VOICE_ID", ""),
            voice_style=get("JADE_LIVE_VOICE_STYLE", ""),
            heartbeat_seconds=float(get("JADE_LIVE_HEARTBEAT_SECONDS", 2)),
            lease_seconds=float(get("JADE_LIVE_LEASE_SECONDS", 5)),
            idle_standby_seconds=int(get("JADE_LIVE_IDLE_STANDBY_SECONDS", 8)),
            idle_close_seconds=float(get("JADE_LIVE_IDLE_CLOSE_SECONDS", 30)),
            opening_timeout_seconds=float(get("JADE_LIVE_OPENING_TIMEOUT_SECONDS", 8)),
            close_timeout_seconds=float(get("JADE_LIVE_CLOSE_TIMEOUT_SECONDS", 5)),
            muted_drain_seconds=float(get("JADE_LIVE_MUTED_DRAIN_SECONDS", 15)),
            max_session_seconds=float(get("JADE_LIVE_MAX_SESSION_SECONDS", 600)),
            max_starts_per_minute=int(get("JADE_LIVE_MAX_STARTS_PER_MINUTE", 3)),
            max_delegations_per_session=int(get("JADE_LIVE_MAX_DELEGATIONS_PER_SESSION", 12)),
            # Only the old path is retained as a migration alias. Former daily,
            # monthly and backend amounts are intentionally never read.
            usage_db_path=(get("JADE_LIVE_USAGE_DB_PATH", "")
                           or get("JADE_LIVE_BUDGET_DB_PATH", "") or _default_db_path()),
            session_db_path=get("JADE_LIVE_SESSION_DB_PATH", ""),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if any(type(value) is not bool for value in
               (self.enabled, self.mobile_enabled, self.discord_enabled)):
            raise ValueError("invalid Live feature flag")
        if self.model not in ("gpt-live-1", "gpt-live-1.1"):
            raise ValueError("Live requires a documented Live model, not a Realtime TTS model")
        LiveVoice(self.voice, self.voice_id).validate()
        if self.voice_style not in ("", "petillante"):
            raise ValueError("unsupported JADE_LIVE_VOICE_STYLE")
        if self.voice_style and not self.voice_id:
            raise ValueError("JADE_LIVE_VOICE_STYLE requires JADE_LIVE_VOICE_ID")
        bounds = {
            "heartbeat_seconds": (0.5, 10), "lease_seconds": (1, 30),
            "idle_close_seconds": (5, 300), "opening_timeout_seconds": (1, 30),
            "close_timeout_seconds": (1, 30), "muted_drain_seconds": (0, 60),
            "max_session_seconds": (15, 3600),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not low <= value <= high):
                raise ValueError(f"invalid Live {name}")
        if self.lease_seconds <= 2 * self.heartbeat_seconds:
            raise ValueError("Live lease must exceed two heartbeat intervals")
        if (type(self.idle_standby_seconds) is not int
                or not 5 <= self.idle_standby_seconds <= 60):
            raise ValueError("Live standby timeout must be an integer between 5 and 60")
        if self.idle_close_seconds <= self.idle_standby_seconds:
            raise ValueError("Live idle close must follow the standby timeout")
        for name, maximum in (("max_starts_per_minute", 10),
                              ("max_delegations_per_session", 100)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"invalid Live {name}")
        repo_root = Path(__file__).resolve().parents[2]
        for value in (self.usage_db_path, self.session_db_path):
            if not value:
                if value == self.usage_db_path:
                    raise ValueError("Live usage requires a private SQLite path")
                continue
            path = Path(value).expanduser()
            if (not path.is_absolute() or path.suffix != ".sqlite3"
                    or path.resolve().is_relative_to(repo_root)):
                raise ValueError("Live state must use an absolute private SQLite path outside Git")

    def preflight(self, api_key_present: bool = False,
                  discord_adapter_available: bool = True) -> dict:
        """Diagnostic only: no environment/secret reads, I/O or paid requests."""
        self.validate()
        reasons = []
        if not self.enabled:
            reasons.append("live_disabled")
        if not self.mobile_enabled:
            reasons.append("mobile_live_disabled")
        if not api_key_present:
            reasons.append("api_key_missing")
        discord_reason = ("discord_live_disabled" if not self.discord_enabled else
                          "discord_adapter_unavailable" if not discord_adapter_available else
                          "api_key_missing" if not api_key_present else "ready")
        return {"available": not reasons, "reasons": reasons, "model": self.model,
                "voice": LiveVoice(self.voice, self.voice_id).public_status(),
                "discord": {"enabled": self.discord_enabled,
                            "available": discord_reason == "ready", "reason": discord_reason,
                            "monthly_policy_required": True}}

    def session_config(self, *, instructions: str = "", input: list | None = None) -> dict:
        """Trusted server configuration; the mobile never chooses these settings."""
        self.validate()
        session = {
            "model": self.model,
            "audio": {"output": {"voice": LiveVoice(self.voice, self.voice_id).api_value()}},
            "delegation": {"type": "client", "acknowledgement_delay_ms": 800},
            "store": False,
            "wake_policy": {"type": "speech"},
            "idle_timeout_s": self.idle_standby_seconds,
            "client": {"data_channel": {
                "allowed_client_events": [],
                "allowed_server_events": [
                    {"type": "session.started"}, {"type": "session.resumed"},
                    {"type": "session.paused"}, {"type": "session.closed"},
                ],
            }},
            "input": input if input is not None else [],
        }
        sections = [instructions] if instructions else []
        if self.voice_style == "petillante":
            sections.append(f"Direction vocale\n{PETILLANTE_SESSION_PROMPT}")
        sections.append(f"Jeu et débit\n{LIVE_DELIVERY_PROMPT}")
        session["instructions"] = "\n\n".join(sections)
        if len(session["instructions"].encode("utf-8")) > 16384:
            raise ValueError("Live instructions and vocal delivery exceed the conservative instruction budget")
        return session
