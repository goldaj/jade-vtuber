"""Jade's bounded, extensible intent-to-prosody contract.

One leading [INTENT:label] is emitted by the dialogue model and NEVER leaves
this boundary. Labels only select static, application-authored TTS directions:
Realtime supports prompting for delivery, NOT native guaranteed emotion modes.
The parser accepts streams split at any byte/character boundary, without
publishing an unfinished tag to Discord, subtitles, speech or history.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType

# Changing these labels is a prompt/contract change: keep additions small and
# verify them by listening before claiming a voice supports them reliably.
_DIRECTIONS = MappingProxyType({
    "neutral": "",
    "playful": (
        "Use light, mischievous, friendly teasing with confident, lively "
        "intonation. No exaggerated giggles, shrieking or childish acting."
    ),
    "excited": (
        "Sound bright, genuinely enthusiastic and energetic, with clear French "
        "articulation. Never shout or rush through words."
    ),
    "curious": (
        "Sound interested, attentive and animated, with subtle questioning "
        "intonation when the punctuation calls for it."
    ),
    "tender": (
        "Use a warm, briefly soft and slightly shy delivery, with restrained "
        "affection. No exaggerated sentimentality, whispering or baby voice."
    ),
    "reassuring": (
        "Speak warmly and reassuringly, with calm steady cadence and clear "
        "pronunciation, without losing Jade's youthful voice."
    ),
    "serious": (
        "Speak in a focused, composed, respectful tone, clearly and naturally, "
        "without melodrama or a robotic monotone."
    ),
})

INTENTS = frozenset(_DIRECTIONS)

INTENT_PROMPT = """\
Voice-intention output contract (required for EVERY reply, text or voice):
Begin the response with EXACTLY ONE tag [INTENT:label], followed by the
spoken/written French answer on the same line. The only valid labels are:
neutral, playful, excited, curious, tender, reassuring, serious.
Select the single dominant delivery intention for the whole response:
playful for friendly teasing, excited for genuine enthusiasm,
curious for interest or questions, tender for rare shy affection,
reassuring for comfort, serious for weighty matters, neutral otherwise.
The tag is metadata only and is removed before delivery. Never include it
in speech, visible text, quotes, code or the reply body. Do not invent labels.
Never add a tender or familial phrase merely to justify an intention.
For mixed moods choose the predominant intention. Keep the existing persona.
"""

_PREFIX = re.compile(r"^\[INTENT:([a-z]+)\]$", flags=re.ASCII)
_SUSPECT = re.compile(r"^\[\s*intent\b", flags=re.IGNORECASE | re.ASCII)
_MAX_HEAD = 128


def normalize_intent(label: str) -> str:
    """Only application-authored, allowlisted labels may affect the TTS."""
    return label if isinstance(label, str) and label in INTENTS else "neutral"


def voice_direction(label: str) -> str:
    """Return ONLY static trusted instructions, never LLM-supplied metadata."""
    return _DIRECTIONS[normalize_intent(label)]


@dataclass(frozen=True)
class IntentReply:
    text: str
    intent: str = "neutral"


class IntentStreamParser:
    """Parse one optional prefix without delaying the rest of the stream.

    A missing or unknown label becomes neutral. A malformed [INTENT...] prefix
    that ends without ']' fails closed rather than leaking private metadata.
    Ordinary leading brackets (e.g. [bonjour]) stay in the user's text.
    """

    def __init__(self):
        self.intent = "neutral"
        self.resolved = False
        self._head = ""

    def feed(self, chunk: str) -> str:
        if not isinstance(chunk, str):
            raise TypeError("stream fragment must be text")
        if not chunk:
            return ""
        if self.resolved:
            return chunk
        self._head += chunk
        trimmed = self._head.lstrip()
        if not trimmed:
            if len(self._head) > _MAX_HEAD:
                self.resolved = True
                result, self._head = self._head, ""
                return result
            return ""
        if not trimmed.startswith("["):
            self.resolved = True
            result, self._head = self._head, ""
            return result
        end = trimmed.find("]")
        if end < 0:
            if len(self._head) > _MAX_HEAD:
                if _SUSPECT.match(trimmed):
                    raise ValueError("unfinished intent metadata")
                self.resolved = True
                result, self._head = self._head, ""
                return result
            return ""
        prefix = trimmed[:end + 1]
        suffix = trimmed[end + 1:]
        if _SUSPECT.match(trimmed):
            match = _PREFIX.fullmatch(prefix)
            self.intent = normalize_intent(match.group(1) if match else "")
            result = suffix.lstrip()
        else:
            result = self._head
        self._head = ""
        self.resolved = True
        return result

    def finish(self) -> str:
        if self.resolved:
            return ""
        trailing = self._head
        self._head = ""
        self.resolved = True
        if _SUSPECT.match(trailing.lstrip()):
            raise ValueError("unfinished intent metadata")
        return trailing


def parse_reply(answer: str) -> IntentReply:
    """Non-streaming path shares exactly the streaming parsing contract."""
    if not isinstance(answer, str):
        raise TypeError("model reply must be text")
    parser = IntentStreamParser()
    text = parser.feed(answer) + parser.finish()
    return IntentReply(text.strip(), parser.intent)
