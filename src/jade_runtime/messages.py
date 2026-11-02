"""Transport-independent messages. Preserve original Unicode content."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Incoming:
    platform: str
    author: str
    text: str
    channel: str = "default"
    message_id: str = ""
    force_reply: bool = False

    def __post_init__(self):
        if (not self.platform.strip() or not self.author.strip()
                or not self.channel.strip() or not isinstance(self.text, str)
                or not self.text.strip()):
            raise ValueError("invalid incoming message")
        if len(self.text) > 4000:
            raise ValueError("incoming message too long")

    @property
    def session(self) -> tuple[str, str]:
        return (self.platform, self.channel)


@dataclass(frozen=True)
class Reply:
    source: Incoming
    text: str

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("empty reply")
