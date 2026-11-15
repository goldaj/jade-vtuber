"""Strict, private, fail-closed runtime settings. No network on import."""
from dataclasses import dataclass, field
import math
from pathlib import Path
from urllib.parse import urlsplit

from src.utility.private_config import environ


def _enabled(value: str) -> bool:
    if value in ("1", "true", "yes"):
        return True
    if value in ("0", "false", "no", ""):
        return False
    raise ValueError("boolean settings must be 0/1 or true/false")


def _voice_users(value: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    parts = value.split(",")
    if (len(parts) > 32 or any(not part.strip().isascii() or not part.strip().isdigit()
                               for part in parts)):
        raise ValueError("invalid Discord voice authorization list")
    values = tuple(int(part.strip()) for part in parts)
    if any(not 0 < value < 2**64 for value in values) or len(set(values)) != len(values):
        raise ValueError("invalid Discord voice authorization list")
    return values


@dataclass(frozen=True)
class Settings:
    model: str = "gpt-6-luna"
    reasoning_effort: str = "low"
    max_completion_tokens: int = 320
    stt_model: str = "gpt-transcribe"
    tts_model: str = "gpt-realtime-2.1-mini"
    voice: str = "shimmer"
    tts_speed: float = 1.25
    tts_pitch_semitones: float = 2.0  # Étincelle: DSP, not an OpenAI API parameter.
    api_key: str = ""
    channel: str = ""
    bot_name: str = "Jade"
    twitch_oauth: str = ""
    twitch_login: str = ""
    twitch_enabled: bool = False
    twitch_send: bool = False
    twitch_auto_refresh: bool = False
    discord_token: str = ""
    # Legacy switches remain readable for old callers but are ignored by CLI.
    discord_enabled: bool = False
    discord_send: bool = False
    discord_voice_enabled: bool = False
    # Legacy compatibility fields. The active open Discord bridge ignores them.
    discord_voice_broadcast: bool = False
    discord_voice_consent: bool = False
    discord_voice_allowed_users: tuple[int, ...] = field(default=(), repr=False)
    discord_voice_channel: int = 0
    discord_text_auto_rate: float = 0.30
    discord_text_cooldown_seconds: int = 180
    avatar_intent_enabled: bool = True  # Facial/text reactions, not voice intent metadata.
    vts_enabled: bool = False
    vts_token: str = ""
    vts_url: str = "ws://127.0.0.1:8001"
    vts_speak_hotkey: str = ""
    http_enabled: bool = False
    http_token: str = ""
    http_port: int = 8765
    audio_output: str = "none"
    early_voice: bool = False
    subtitle_path: Path = Path("subtitle.txt")
    max_history_messages: int = 48
    max_queue: int = 64
    reply_probability: float = 0.30
    timeout_seconds: float = 20.0
    # Optional, private persistent SQLite data; disabled unless explicitly enabled.
    memory_enabled: bool = False
    memory_curator_enabled: bool = False
    memory_db_path: str = ""
    # Private PWA, opt-in via Tailscale Serve; separate HTTP secret from chat.
    mobile_enabled: bool = False
    mobile_token: str = field(default="", repr=False)
    mobile_owner_login: str = ""
    mobile_public_origin: str = ""
    mobile_port: int = 8766
    mobile_vendor_dir: str = ""
    mobile_model_dir: str = ""

    @classmethod
    def load(cls) -> "Settings":
        """The project-private dotenv is preferred over a tracked file."""
        cfg = cls(
            model=str(environ("JADE_LLM_MODEL", "gpt-6-luna")),
            reasoning_effort=str(environ("JADE_LLM_REASONING_EFFORT", "low")).lower(),
            max_completion_tokens=int(environ("JADE_MAX_COMPLETION_TOKENS", "320")),
            stt_model=str(environ("JADE_STT_MODEL", "gpt-transcribe")),
            tts_model=str(environ("JADE_TTS_MODEL", "gpt-realtime-2.1-mini")),
            voice=str(environ("JADE_TTS_VOICE", "shimmer")),
            tts_speed=float(environ("JADE_TTS_SPEED", "1.25")),
            tts_pitch_semitones=float(environ("JADE_TTS_PITCH_SEMITONES", "2.0")),
            api_key=str(environ("OPENAI_API_KEY", "")),
            channel=str(environ("TWITCH_CHANNEL", "")),
            bot_name=str(environ("BOT_NAME", "Jade")),
            twitch_oauth=str(environ("TWITCH_TOKEN", "")),
            twitch_login=str(environ("TWITCH_BOT_LOGIN", "")),
            twitch_enabled=_enabled(str(environ("JADE_TWITCH_ENABLED", "0")).lower()),
            twitch_send=_enabled(str(environ("JADE_TWITCH_SEND", "0")).lower()),
            twitch_auto_refresh=_enabled(str(environ("JADE_TWITCH_AUTO_REFRESH", "0")).lower()),
            discord_token=str(environ("DISCORD_TOKEN", "")),
            # Obsolete Discord activation/broadcast/list/confirmation values are not
            # loaded: existing private files are preserved but have no effect.
            discord_voice_channel=int(environ("DISCORD_VOICE_CHANNEL", "0") or 0),
            discord_text_auto_rate=float(environ("JADE_DISCORD_TEXT_AUTO_RATE", "0.30")),
            discord_text_cooldown_seconds=int(environ("JADE_DISCORD_TEXT_COOLDOWN_SECONDS", "180")),
            avatar_intent_enabled=_enabled(str(environ("JADE_AVATAR_INTENT_ENABLED", "1")).lower()),
            vts_enabled=_enabled(str(environ("JADE_VTS_ENABLED", "0")).lower()),
            vts_token=str(environ("JADE_VTS_TOKEN", "")),
            vts_url=str(environ("JADE_VTS_URL", "ws://127.0.0.1:8001")),
            vts_speak_hotkey=str(environ("JADE_VTS_SPEAK_HOTKEY", "")),
            http_enabled=_enabled(str(environ("JADE_HTTP_ENABLED", "0")).lower()),
            http_token=str(environ("JADE_HTTP_TOKEN", "")),
            http_port=int(environ("JADE_HTTP_PORT", "8765")),
            audio_output=str(environ("JADE_AUDIO_OUTPUT", "none")),
            early_voice=_enabled(str(environ("JADE_EARLY_VOICE", "0")).lower()),
            subtitle_path=Path(str(environ("JADE_SUBTITLE_PATH", "subtitle.txt"))),
            max_history_messages=int(environ("JADE_HISTORY_LIMIT", "48")),
            max_queue=int(environ("JADE_QUEUE_LIMIT", "64")),
            reply_probability=float(environ("JADE_RANDOM_REPLY_RATE", "0.30")),
            timeout_seconds=float(environ("JADE_API_TIMEOUT", "20")),
            memory_enabled=_enabled(str(environ("JADE_MEMORY_ENABLED", "0")).lower()),
            memory_curator_enabled=_enabled(str(environ("JADE_MEMORY_CURATOR_ENABLED", "0")).lower()),
            memory_db_path=str(environ("JADE_MEMORY_DB_PATH", "")),
            mobile_enabled=_enabled(str(environ("JADE_MOBILE_ENABLED", "0")).lower()),
            mobile_token=str(environ("JADE_MOBILE_TOKEN", "")),
            mobile_owner_login=str(environ("JADE_MOBILE_OWNER_LOGIN", "")).strip(),
            mobile_public_origin=str(environ("JADE_MOBILE_PUBLIC_ORIGIN", "")).strip(),
            mobile_port=int(environ("JADE_MOBILE_PORT", "8766")),
            mobile_vendor_dir=str(environ("JADE_MOBILE_VENDOR_DIR", "")),
            mobile_model_dir=str(environ("JADE_MOBILE_MODEL_DIR", "")),
        )
        cfg.validate()
        return cfg

    def validate(self):
        if (self.reasoning_effort not in ("none", "low", "medium", "high", "xhigh", "max")
                or not 128 <= self.max_completion_tokens <= 8192):
            raise ValueError("invalid LLM effort or completion budget")
        if (not self.model or not self.stt_model or not self.tts_model or not self.voice
                or not self.bot_name.strip()):
            raise ValueError("model names and Jade name must not be blank")
        if (isinstance(self.tts_speed, bool) or not isinstance(self.tts_speed, (int, float))
                or not 0.25 <= self.tts_speed <= 1.5):
            raise ValueError("TTS speed must be between 0.25 and 1.5")
        if (isinstance(self.tts_pitch_semitones, bool)
                or not isinstance(self.tts_pitch_semitones, (float, int))
                or not math.isfinite(self.tts_pitch_semitones)
                or not -6 <= self.tts_pitch_semitones <= 6):
            raise ValueError("pitch semitones must be between -6 and 6")
        if (self.max_history_messages < 2 or self.max_history_messages > 100
                or not 1 <= self.max_queue <= 1024
                or not 0 <= self.reply_probability <= 1
                or not 1 <= self.timeout_seconds <= 120):
            raise ValueError("invalid runtime safety bounds")
        if (not 0 <= self.discord_text_auto_rate <= 1
                or not 30 <= self.discord_text_cooldown_seconds <= 3600):
            raise ValueError("invalid Discord text participation limits")
        if not 1024 <= self.http_port <= 65535:
            raise ValueError("invalid local API port")
        if not 1024 <= self.mobile_port <= 65535:
            raise ValueError("invalid mobile port")
        if self.mobile_enabled and not 32 <= len(self.mobile_token) <= 256:
            raise ValueError("mobile app requires a separate 32+ character token")
        if self.mobile_enabled and not (3 <= len(self.mobile_owner_login) <= 256
                                        and "\r" not in self.mobile_owner_login
                                        and "\n" not in self.mobile_owner_login
                                        and self.mobile_owner_login.isascii()):
            raise ValueError("mobile app requires JADE_MOBILE_OWNER_LOGIN (Tailscale identity)")
        if self.mobile_enabled:
            origin = urlsplit(self.mobile_public_origin)
            if (origin.scheme != "https" or not origin.hostname
                    or not origin.hostname.endswith(".ts.net") or origin.path
                    or origin.query or origin.fragment or origin.username
                    or origin.password or self.mobile_public_origin.endswith("/")):
                raise ValueError("mobile requires exact HTTPS .ts.net JADE_MOBILE_PUBLIC_ORIGIN")
            try:
                if origin.port is not None and not 1024 <= origin.port <= 65535:
                    raise ValueError("invalid mobile HTTPS public port")
            except ValueError as exc:
                raise ValueError("invalid mobile HTTPS origin port") from exc
        if self.mobile_enabled and self.http_enabled and self.mobile_port == self.http_port:
            raise ValueError("mobile and legacy HTTP cannot share one port")
        if self.http_enabled and len(self.http_token) < 32:
            raise ValueError("HTTP API requires an independent 32+ character token")
        if self.audio_output not in ("none", "ffplay"):
            raise ValueError("audio output must be 'none' or 'ffplay'")
        if self.memory_curator_enabled and not self.memory_enabled:
            raise ValueError("memory curator needs JADE_MEMORY_ENABLED=1")
        if self.memory_enabled and (not self.memory_db_path
                                    or not Path(self.memory_db_path).is_absolute()
                                    or not self.memory_db_path.endswith(".sqlite3")):
            raise ValueError("memory requires absolute private JADE_MEMORY_DB_PATH (.sqlite3)")
        if self.twitch_enabled and not (self.channel and self.twitch_oauth):
            raise ValueError("Twitch explicitly enabled but credentials missing")
        if self.twitch_send and not self.twitch_enabled:
            raise ValueError("Twitch output requires explicitly enabled connector")
        if self.vts_enabled and not self.vts_token:
            raise ValueError("VTube Studio enabled but local API token missing")

    def require_openai(self):
        if not self.api_key or self.api_key.strip() == "example":
            raise ValueError("OPENAI_API_KEY required for live OpenAI requests")
