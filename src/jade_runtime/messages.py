"""Transport-independent messages. Preserve original Unicode content."""
from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class Incoming:
    platform: str
    author: str
    text: str
    channel: str = "default"
    message_id: str = ""
    force_reply: bool = False
    speaker_id: int | None = field(default=None, repr=False)
    voice_session_id: str = field(default="", repr=False)
    # Volatile recent Discord messages, never persisted or emitted in logs.
    context: tuple[str, ...] = field(default=(), repr=False)

    def __post_init__(self):
        if (not self.platform.strip() or not self.author.strip()
                or not self.channel.strip() or not isinstance(self.text, str)
                or not self.text.strip()):
            raise ValueError("invalid incoming message")
        if len(self.text) > 4000:
            raise ValueError("incoming message too long")
        if (not isinstance(self.context, tuple) or len(self.context) > 6
                or any(not isinstance(line, str) or len(line) > 320 for line in self.context)):
            raise ValueError("invalid context")
        if self.speaker_id is not None and (type(self.speaker_id) is not int or self.speaker_id <= 0):
            raise ValueError("invalid speaker identifier")
        if self.voice_session_id and (self.platform != "discord_voice" or not re.fullmatch(
                r"[A-Za-z0-9_-]{16,128}", self.voice_session_id)):
            raise ValueError("invalid voice session identifier")

    @property
    def session(self) -> tuple[str, str]:
        if self.platform == "discord_voice" and self.voice_session_id:
            return (self.platform, self.channel + ":" + self.voice_session_id)
        return (self.platform, self.channel)


@dataclass(frozen=True)
class Reply:
    source: Incoming
    text: str
    spoken: bool = False  # Voice already delivered by early pipeline.
    intent: str = "neutral"  # Trusted metadata, not part of visible/speakable text.

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("empty reply")
        from .intent_engine import INTENTS
        if self.intent not in INTENTS:
            raise ValueError("invalid reply intention")
