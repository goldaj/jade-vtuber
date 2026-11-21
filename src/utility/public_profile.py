"""Non-secret, opt-in Jade profiles. Secrets and identities NEVER belong in TOML.

Layering: OS environment > private dotenv > allowlisted public profile > defaults.
This module has no network access and does not read provider secrets.
"""
from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_ROOT = PROJECT_ROOT / "config" / "profiles"

# Conservative allowlist: machine preferences only; private identities and tokens
# remain exclusively in environment or JADE_SECRETS_FILE.
ALLOWED_PROFILE_KEYS = frozenset({
    "JADE_LLM_MODEL",
    "JADE_STT_MODEL",
    "JADE_TTS_MODEL",
    "JADE_TTS_VOICE",
    "JADE_TTS_SPEED",
    "JADE_TTS_PITCH_SEMITONES",
    "JADE_API_TIMEOUT",
    "JADE_AUDIO_OUTPUT",
    "JADE_EARLY_VOICE",
    "JADE_HISTORY_LIMIT",
    "JADE_QUEUE_LIMIT",
    "JADE_RANDOM_REPLY_RATE",
    "JADE_TWITCH_ENABLED",
    "JADE_TWITCH_SEND",
    "JADE_DISCORD_ENABLED",
    "JADE_DISCORD_SEND",
    "JADE_DISCORD_VOICE_ENABLED",
    "JADE_VTS_ENABLED",
    "JADE_HTTP_ENABLED",
    "JADE_HTTP_PORT",
})


def selected_profile() -> Path | None:
    """Explicit private TOML path overrides the named, checked-in safe profile."""
    override = os.environ.get("JADE_PROFILE_FILE")
    if override:
        return Path(override).expanduser()
    name = os.environ.get("JADE_PROFILE", "")
    if not name:
        return None
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name):
        raise ValueError("JADE_PROFILE must be a simple profile name")
    return PROFILE_ROOT / (name + ".toml")


def load_profile() -> dict[str, str]:
    """Load only public-safe typed settings; fail closed on unknown/sensitive keys."""
    path = selected_profile()
    if path is None:
        return {}
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("Jade non-secret profile is missing or invalid") from exc
    if set(document) != {"settings"} or not isinstance(document["settings"], dict):
        raise ValueError("Jade profile must contain only the [settings] table")
    values = document["settings"]
    unknown = set(values) - ALLOWED_PROFILE_KEYS
    if unknown:
        # Do not echo values or potentially sensitive names in logs.
        raise ValueError("Jade profile contains forbidden or unknown settings")
    result: dict[str, str] = {}
    for name, value in values.items():
        if isinstance(value, bool):
            result[name] = "1" if value else "0"
        elif isinstance(value, (str, int, float)) and not isinstance(value, complex):
            result[name] = str(value)
        else:
            raise ValueError("Unsupported Jade profile value type")
        if not result[name].strip():
            raise ValueError("Jade profile settings may not be blank")
    return result


def profile_default(name: str, default: str = "") -> str:
    """A profile cannot ever supply credentials because of the allowlist."""
    if name not in ALLOWED_PROFILE_KEYS:
        return default
    return load_profile().get(name, default)
