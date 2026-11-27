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
    "sad": (
        "Convey sadness or disappointment with a softened, slightly slower "
        "cadence and falling phrase endings. Keep Jade's youthful timbre and "
        "clearly audible words; no sobbing, whispering or melodrama."
    ),
    "angry": (
        "Convey controlled anger or indignation with firmer articulation, "
        "short decisive accents and a tense but natural cadence. Keep Jade's "
        "youthful timbre and normal speaking volume; no shouting or growling."
    ),
})

INTENTS = frozenset(_DIRECTIONS)

# Native Live speaks without the text model's leading metadata tag. A small
# set of early, unambiguous French cues gives the avatar a local default.
_LIVE_COMFORT_CUE = re.compile(
    r"\b(?:ne t'inquiète pas|t'inquiète pas|pas de panique|prends ton temps|tu n'es pas seul[e]?)\b"
)
_LIVE_PREAMBLE_ONLY = re.compile(r"(?:oh|ah|là|franchement|honnêtement)\s*[,!.…]*")
_LIVE_CUES = tuple((label, re.compile(pattern)) for label, pattern in (
    ("tender", r"\b(?:ça me touche|tu me touches|je t'envoie un câlin|avec tendresse)\b"),
    ("playful", r"\b(?:haha|héhé|je te taquine|bien tenté|petit malin|tu m'as eue?)\b"),
    ("excited", r"\b(?:génial[e]?|bravo|trop bien|youpi|quelle bonne nouvelle|c'est fantastique)\b"),
    ("serious", r"\b(?:c'est (?:très )?important|c'est sérieux|il y a un risque|en cas d'urgence|attention à)\b"),
    ("curious", r"\b(?:raconte-moi|je me demande|comment ça|qu'est-ce qui|dis-m'en plus)\b"),
))

# Negative emotions require Jade to express her own state at the beginning of
# the reply. A mention, quotation or acknowledgement of the user's feelings is
# not evidence that Jade is sad/angry. Existing comfort cues keep precedence.
_LIVE_SELF_MOODS = tuple((label, re.compile(
    r"^(?:(?:oh|ah|là|franchement|honnêtement)(?:\s*[,!.…]+\s*|\s+))?(?:" + pattern + r")\b"
)) for label, pattern in (
    ("sad", (
        r"je suis (?:(?:vraiment|tellement|très|un peu) )?(?:triste|peinée|déçue)"
        r"|ça me (?:rend (?:vraiment )?triste|peine)"
        r"|j'ai (?:vraiment )?de la peine"
    )),
    ("angry", (
        r"je suis (?:(?:vraiment|tellement|très|un peu) )?(?:en colère|furieuse|fâchée)"
        r"|ça me (?:met (?:vraiment )?en colère|révolte)"
    )),
))


def classify_live_intent(text: str) -> str | None:
    """Choose a visual intention after enough of the spoken prefix arrives."""
    prefix = text[:160].strip().casefold().replace("’", "'")
    if _LIVE_COMFORT_CUE.search(prefix):
        return "reassuring"
    # An explicit opening emotion must not depend on whether a later sentence
    # ("je me demande...", "c'est important...") arrives in the same fragment.
    for label, pattern in _LIVE_SELF_MOODS:
        if pattern.search(prefix):
            return label
    for label, pattern in _LIVE_CUES:
        if pattern.search(prefix):
            return label
    if _LIVE_PREAMBLE_ONLY.fullmatch(prefix):
        # "Oh !" can arrive before the actual emotional phrase. Do not lock a
        # neutral reaction until it arrives; an unfinished preamble keeps the
        # avatar's ordinary idle/closure behaviour without a late animation.
        return None
    if "?" in prefix:
        return "curious"
    if len(prefix) >= 64 or prefix.endswith((".", "!", "…")):
        return "neutral"
    return None


INTENT_PROMPT = """\
Voice-intention output contract (required for EVERY reply, text or voice):
Begin the response with EXACTLY ONE tag [INTENT:label], followed by the
spoken/written French answer on the same line. The only valid labels are:
neutral, playful, excited, curious, tender, reassuring, serious, sad, angry.
Select the single dominant delivery intention for the whole response:
playful for friendly teasing, excited for genuine enthusiasm,
curious for interest or questions, tender for rare shy affection,
reassuring for comfort, serious for weighty matters,
sad for Jade's own sadness or disappointment, angry for Jade's own anger or
indignation, neutral otherwise. Do not adopt an emotion merely because the
user mentions it: comforting sadness can be reassuring, and a firm factual
explanation can be serious without being angry.
The tag is metadata only and is removed before delivery. Never include it
in speech, visible text, quotes, code or the reply body. Do not invent labels.
Do not include any other bracketed stage direction such as [playful] or [rires].
Never add a tender or familial phrase merely to justify an intention.
For mixed moods choose the predominant intention. Keep the existing persona.
"""

_INTENT_TAG = re.compile(r"\[\s*intent\s*:\s*([a-z]+)\s*\]", re.I | re.ASCII)
_ANY_INTENT = re.compile(r"\[\s*intent\b", re.I | re.ASCII)
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
    """Extract one leading intent; never publish bracketed annotations.

    Leading groups are buffered: [playful] [INTENT:curious] selects curious.
    Without any valid intent, neutral is used and brackets are STILL removed.
    Nested, repeated and unfinished groups are held back across stream chunks.
    """

    def __init__(self):
        self.intent = "neutral"
        self.resolved = False
        self._head = ""
        self._bracket_depth = 0
        self._bracket_sample = ""
        self._gap = ""
        self._removed = False
        self._has_visible = False

    def _visible_body(self, chunk: str, *, final=False) -> str:
        """Discard bracket groups regardless of whether an intent was found."""
        visible = []
        for char in chunk:
            if char == "[":
                if self._bracket_depth == 0:
                    self._removed = True
                    self._bracket_sample = ""
                self._bracket_depth += 1
                continue
            if char == "]" and self._bracket_depth:
                self._bracket_depth -= 1
                continue
            if self._bracket_depth:
                if len(self._bracket_sample) < _MAX_HEAD:
                    self._bracket_sample += char
                continue
            if char == "]":
                # A stray closer after metadata is never spoken.
                continue
            if char.isspace():
                self._gap += char
                continue
            if self._gap:
                if self._has_visible:
                    if self._removed:
                        if char not in ",.":
                            visible.append(" ")
                    else:
                        visible.append(self._gap)
                self._gap = ""
            self._removed = False
            visible.append(char)
            self._has_visible = True
        if final:
            if self._bracket_depth and re.match(
                r"\s*intent\b", self._bracket_sample, re.I | re.ASCII
            ):
                raise ValueError("unfinished inline intent metadata")
            if self._gap and not self._removed:
                visible.append(self._gap)
            self._gap = ""
        return "".join(visible)


    def feed(self, chunk: str) -> str:
        if not isinstance(chunk, str):
            raise TypeError("stream fragment must be text")
        if not chunk:
            return ""
        if self.resolved:
            return self._visible_body(chunk)
        self._head += chunk
        cursor = 0
        while True:
            while cursor < len(self._head) and self._head[cursor].isspace():
                cursor += 1
            if cursor >= len(self._head):
                if len(self._head) <= _MAX_HEAD:
                    return ""
                break
            if self._head[cursor] != "[":
                break
            depth = 0
            end = None
            for pos in range(cursor, len(self._head)):
                if self._head[pos] == "[":
                    depth += 1
                elif self._head[pos] == "]":
                    depth -= 1
                    if depth == 0:
                        end = pos
                        break
            if end is None:
                if len(self._head) <= _MAX_HEAD:
                    return ""
                if _ANY_INTENT.search(self._head):
                    raise ValueError("unfinished intent metadata")
                break
            group = self._head[cursor:end + 1]
            tag = _INTENT_TAG.search(group)
            if tag is not None and tag.group(1).lower() in INTENTS:
                self.intent = tag.group(1).lower()
                break
            cursor = end + 1
            if len(self._head) > _MAX_HEAD:
                break
        self.resolved = True
        result, self._head = self._head, ""
        return self._visible_body(result)

    def finish(self) -> str:
        if self.resolved:
            return self._visible_body("", final=True)
        trailing = self._head
        self._head = ""
        self.resolved = True
        if (_ANY_INTENT.search(trailing)
                and trailing.count("[") > trailing.count("]")):
            raise ValueError("unfinished intent metadata")
        return self._visible_body(trailing, final=True)


def parse_reply(answer: str) -> IntentReply:
    """Non-streaming path shares exactly the streaming parsing contract."""
    if not isinstance(answer, str):
        raise TypeError("model reply must be text")
    parser = IntentStreamParser()
    text = parser.feed(answer) + parser.finish()
    return IntentReply(text.strip(), parser.intent)
