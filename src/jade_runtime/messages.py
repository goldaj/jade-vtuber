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
    # Verified transport account ID; NEVER use an untrusted nickname as ID.
    account_id: str = field(default="", repr=False)
    # Ephemeral key assigned only by trusted Discord connectors.
    conversation_id: str = field(default="", repr=False)
    # Trusted Discord parser marks direct messages: no public voice playback.
    private_channel: bool = field(default=False, repr=False)
    # Mobile PWA requests use the trusted gateway, not the Discord session.
    input_modality: str = field(default="text", repr=False)
    preprocess_ms: float | None = field(default=None, repr=False)  # trusted STT duration, not user-supplied
    requested_speech: bool = field(default=False, repr=False)
    # Only runtime-created events; never attribute Jade\u0027s speech to a human.
    system_initiative: bool = field(default=False, repr=False)

    def __post_init__(self):
        if (not self.platform.strip() or not self.author.strip()
                or not self.channel.strip() or not isinstance(self.text, str)
                or not self.text.strip()):
            raise ValueError("invalid incoming message")
        if (self.input_modality not in ("text", "voice")
                or type(self.requested_speech) is not bool):
            raise ValueError("invalid input/output modality")
        if (self.preprocess_ms is not None
                and (type(self.preprocess_ms) not in (int, float)
                     or not math.isfinite(self.preprocess_ms)
                     or not 0 <= self.preprocess_ms <= 120000)):
            raise ValueError("invalid preprocessing metric")
        if type(self.system_initiative) is not bool:
            raise ValueError("invalid system event flag")
        if type(self.private_channel) is not bool:
            raise ValueError("invalid private channel flag")
        if len(self.text) > 4000:
            raise ValueError("incoming message too long")
        if (not isinstance(self.context, tuple) or len(self.context) > 6
                or any(not isinstance(line, str) or len(line) > 320 for line in self.context)):
            raise ValueError("invalid context")
        if self.speaker_id is not None and (type(self.speaker_id) is not int or self.speaker_id <= 0):
            raise ValueError("invalid speaker identifier")
        if self.conversation_id and (self.platform not in ("discord", "discord_voice")
                or not re.fullmatch(r"dc-[0-9a-f]{32}", self.conversation_id)):
            raise ValueError("invalid conversation routing key")
        if self.voice_session_id and (self.platform != "discord_voice" or not re.fullmatch(
                r"[A-Za-z0-9_-]{16,128}", self.voice_session_id)):
            raise ValueError("invalid voice session identifier")

    @property
    def history_key(self) -> tuple[str, str]:
        return ("discord_conversation", self.conversation_id) if self.conversation_id else self.session

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
