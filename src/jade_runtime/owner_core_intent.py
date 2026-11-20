"""Conservative, deterministic parser for creator-directed Core Memory requests.

A request must begin with a write verb and explicitly mention Core Memories
(or a French equivalent). Quoted conversations and casual "remember this" text
must never silently trigger permanent storage. This module performs no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class OwnerCoreIntent:
    kind: str
    summary: str


_OWNER_PREFIX = re.compile(
    r"^\s*(?:(?:hey\s+)?jade\s*[,!:]\s*)?"
    r"(?:(?:je\s+(?:veux|voudrais)\s+que\s+tu|"
    r"je\s+te\s+demande\s+de|"
    r"(?:peux|pourrais)[-\s]tu)\s+)?"
    r"(?:ajout(?:e|es|er)|enregistr(?:e|es|er)|"
    r"gard(?:e|es|er)|conserv(?:e|es|er)|"
    r"m[ée]moris(?:e|es|er)|inscri(?:s|re)|"
    r"mets?|mettre|not(?:e|es|er)|reti(?:ens|ent|enir))\b",
    re.IGNORECASE,
)
_CORE_MARKER = re.compile(
    r"\b(?:core[\s-]*memor(?:y|ies)|core[\s-]*m[ée]moir(?:e|es)|"
    r"m[ée]moir(?:e|es)\s+(?:fondatric(?:e|es)|"
    r"essentiell(?:e|es)|autobiographiques?)|"
    r"souvenirs?\s+(?:fondateurs?|fondamentaux?|autobiographiques?))\b",
    re.IGNORECASE,
)
_SELF_CUES = re.compile(
    r"\b(?:autobiograph\w*|core[_ -]?self|"
    r"(?:de|sur|pour)\s+toi|ton\s+v[ée]cu|"
    r"notre\s+premi[eè]r(?:e)?\s+(?:conversation|"
    r"rencontre|discussion)|notre\s+premier\s+[ée]change|"
    r"tu\s+as\s+v[ée]cu)\b",
    re.IGNORECASE,
)
_LEADING_TYPE = re.compile(
    r"^\s*(?:de\s+(?:toi|jade)|sur\s+toi|"
    r"autobiographiques?|relationnel(?:le|les))"
    r"(?=\s*(?:[:：,;-]|que\b))",
    re.IGNORECASE,
)
_LEADING_SEPARATOR = re.compile(
    r"^\s*(?:(?:[:：,;=–\-]+\s*)|"
    r"(?:(?:ceci|cela|[çc]a|le\s+fait)\s+)?que\s+|"
    r"(?:(?:ceci|cela|[çc]a)\s*[:：]\s*))",
    re.IGNORECASE,
)


def parse_owner_core_intent(text: str) -> OwnerCoreIntent | None:
    """Recognize an explicit Core Memory write without relying on LLM curation."""
    if not isinstance(text, str) or not text.strip():
        return None
    prefix = _OWNER_PREFIX.match(text)
    if prefix is None:
        return None
    marker = _CORE_MARKER.search(text, prefix.end())
    if marker is None or marker.start() - prefix.end() > 110:
        return None
    # Reject negated write requests instead of guessing their intent.
    if re.search(r"\b(?:ne|pas|jamais)\b", text[prefix.end():marker.start()], re.I):
        return None
    kind = ("core_self" if _SELF_CUES.search(text[:marker.end()]) else
            "core_relationship")
    suffix = text[marker.end():]
    typed = _LEADING_TYPE.match(suffix)
    if typed is not None:
        if _SELF_CUES.search(typed.group()):
            kind = "core_self"
        suffix = suffix[typed.end():]
    # A spoken colon often arrives as "que" in STT; accept either delimiter.
    while True:
        separator = _LEADING_SEPARATOR.match(suffix)
        if separator is None:
            break
        suffix = suffix[separator.end():]
    summary = suffix.strip(" \t\r\n\"'«»“”")
    if kind != "core_self" and _SELF_CUES.search(summary):
        kind = "core_self"
    return OwnerCoreIntent(kind=kind, summary=summary)
