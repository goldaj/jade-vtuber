"""Strict, private, fail-closed runtime settings. No network on import."""
from dataclasses import dataclass
from pathlib import Path

from src.utility.private_config import environ


def _enabled(value: str) -> bool:
    if value in ("1", "true", "yes"):
        return True
    if value in ("0", "false", "no", ""):
        return False
    raise ValueError("boolean settings must be 0/1 or true/false")


@dataclass(frozen=True)
class Settings:
    model: str = "gpt-4.1-mini"
    stt_model: str = "gpt-4o-mini-transcribe"
    tts_model: str = "gpt-4o-mini-tts"
    voice: str = "coral"
    api_key: str = ""
    channel: str = ""
    bot_name: str = "Jade"
    twitch_oauth: str = ""
    twitch_login: str = ""
    twitch_enabled: bool = False
    twitch_send: bool = False
    discord_token: str = ""
    discord_enabled: bool = False
    discord_send: bool = False
    discord_voice_enabled: bool = False
    discord_voice_channel: int = 0
    vts_enabled: bool = False
    vts_token: str = ""
    vts_url: str = "ws://127.0.0.1:8001"
    vts_speak_hotkey: str = ""
    http_enabled: bool = False
    http_token: str = ""
    http_port: int = 8765
    audio_output: str = "none"
    subtitle_path: Path = Path("subtitle.txt")
    max_history_messages: int = 24
    max_queue: int = 64
    reply_probability: float = 0.0
    timeout_seconds: float = 20.0

    @classmethod
    def load(cls) -> "Settings":
        """The project-private dotenv is preferred over a tracked file."""
        cfg = cls(
            model=str(environ("JADE_LLM_MODEL", "gpt-4.1-mini")),
            stt_model=str(environ("JADE_STT_MODEL", "gpt-4o-mini-transcribe")),
            tts_model=str(environ("JADE_TTS_MODEL", "gpt-4o-mini-tts")),
            voice=str(environ("JADE_TTS_VOICE", "coral")),
            api_key=str(environ("OPENAI_API_KEY", "")),
            channel=str(environ("TWITCH_CHANNEL", "")),
            bot_name=str(environ("BOT_NAME", "Jade")),
            twitch_oauth=str(environ("TWITCH_TOKEN", "")),
            twitch_login=str(environ("TWITCH_BOT_LOGIN", "")),
            twitch_enabled=_enabled(str(environ("JADE_TWITCH_ENABLED", "0")).lower()),
            twitch_send=_enabled(str(environ("JADE_TWITCH_SEND", "0")).lower()),
            discord_token=str(environ("DISCORD_TOKEN", "")),
            discord_enabled=_enabled(str(environ("JADE_DISCORD_ENABLED", "0")).lower()),
            discord_send=_enabled(str(environ("JADE_DISCORD_SEND", "0")).lower()),
            discord_voice_enabled=_enabled(str(environ("JADE_DISCORD_VOICE_ENABLED", "0")).lower()),
            discord_voice_channel=int(environ("DISCORD_VOICE_CHANNEL", "0") or 0),
            vts_enabled=_enabled(str(environ("JADE_VTS_ENABLED", "0")).lower()),
            vts_token=str(environ("JADE_VTS_TOKEN", "")),
            vts_url=str(environ("JADE_VTS_URL", "ws://127.0.0.1:8001")),
            vts_speak_hotkey=str(environ("JADE_VTS_SPEAK_HOTKEY", "")),
            http_enabled=_enabled(str(environ("JADE_HTTP_ENABLED", "0")).lower()),
            http_token=str(environ("JADE_HTTP_TOKEN", "")),
            http_port=int(environ("JADE_HTTP_PORT", "8765")),
            audio_output=str(environ("JADE_AUDIO_OUTPUT", "none")),
            subtitle_path=Path(str(environ("JADE_SUBTITLE_PATH", "subtitle.txt"))),
            max_history_messages=int(environ("JADE_HISTORY_LIMIT", "24")),
            max_queue=int(environ("JADE_QUEUE_LIMIT", "64")),
            reply_probability=float(environ("JADE_RANDOM_REPLY_RATE", "0")),
            timeout_seconds=float(environ("JADE_API_TIMEOUT", "20")),
        )
        cfg.validate()
        return cfg

    def validate(self):
        if (not self.model or not self.stt_model or not self.tts_model or not self.voice
                or not self.bot_name.strip()):
            raise ValueError("model names and Jade name must not be blank")
        if (self.max_history_messages < 2 or self.max_history_messages > 100
                or not 1 <= self.max_queue <= 1024
                or not 0 <= self.reply_probability <= 1
                or not 1 <= self.timeout_seconds <= 120):
            raise ValueError("invalid runtime safety bounds")
        if not 1024 <= self.http_port <= 65535:
            raise ValueError("invalid local API port")
        if self.http_enabled and len(self.http_token) < 32:
            raise ValueError("HTTP API requires an independent 32+ character token")
        if self.audio_output not in ("none", "ffplay"):
            raise ValueError("audio output must be 'none' or 'ffplay'")
        if self.twitch_enabled and not (self.channel and self.twitch_oauth and self.twitch_login):
            raise ValueError("Twitch explicitly enabled but credentials missing")
        if self.twitch_send and not self.twitch_enabled:
            raise ValueError("Twitch output requires explicitly enabled connector")
        if self.discord_voice_enabled and (
                not self.discord_enabled or self.discord_voice_channel <= 0):
            raise ValueError("Discord voice needs explicit Discord and channel activation")
        if self.discord_send and not self.discord_enabled:
            raise ValueError("Discord output requires explicitly enabled connector")
        if self.vts_enabled and not self.vts_token:
            raise ValueError("VTube Studio enabled but local API token missing")
        if self.discord_enabled and not self.discord_token:
            raise ValueError("Discord explicitly enabled but token missing")

    def require_openai(self):
        if not self.api_key or self.api_key.strip() == "example":
            raise ValueError("OPENAI_API_KEY required for live OpenAI requests")
