"""Recognize explicit conversational memory requests, never Core write authority.

Parsing is deliberately deterministic: no user (including Goldaj) can force
core_self or core_relationship through a natural-language instruction. Any
recognized request is scheduled, if consented, as a 365-day ordinary memory.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ExplicitMemoryIntent:
    summary: str
    requested_core: bool = False


_PREFIX = re.compile(
    r"^\s*(?:(?:hey\s+)?jade(?:\s*[,!:.]\s*|\s+))?"
    r"(?:(?:je\s+(?:veux|voudrais|souhaiterais)\s+que\s+tu|"
    r"je\s+te\s+demande\s+de|j'aimerais\s+que\s+tu|"
    r"(?:peux|pourrais)[-\s]tu|est-ce\s+que\s+tu\s+peux)\s+)?"
    r"(?P<verb>souviens[-\s]toi|rappelle[-\s]toi|"
    r"reti(?:ens|ent|enir)|m[ée]moris(?:e|es|er)|"
    r"enregistr(?:e|es|er)|gard(?:e|es|er)|"
    r"conserv(?:e|es|er)|ajout(?:e|es|er)|"
    r"inscri(?:s|re)|mets?|mettre|not(?:e|es|er)|"
    r"stock(?:e|es|er))\b",
    re.I,
)
_MEMORY_MARKER = re.compile(
    r"\b(?:dans|à|en|comme)\s+(?:(?:tes?|ta|la|mes?)\s+)?"
    r"(?:(?:core[\s-]*memor(?:y|ies)|core[\s-]*m[ée]moir(?:e|es))|"
    r"(?:m[ée]moir(?:e|es)|souvenirs?)"
    r"(?:\s+(?:ordinaires?|profond(?:e|es)?|fondatric(?:e|es)|"
    r"essentiell(?:e|es)|autobiographiques?|fondateurs?|fondamentaux?))?"
    r")"
    r"|\b(?:un|ce|ces)\s+souvenirs?\b"
    r"|\bpour\s+(?:plus\s+tard|t'en\s+souvenir)\b",
    re.I,
)
_CORE_MARKER = re.compile(
    r"\b(?:core[\s-]*memor(?:y|ies)|core[\s-]*m[ée]moir(?:e|es)|"
    r"m[ée]moir(?:e|es)\s+(?:profond(?:e|es)?|"
    r"fondatric(?:e|es)|essentiell(?:e|es)|autobiographiques?)|"
    r"souvenirs?\s+(?:fondateurs?|fondamentaux?|autobiographiques?))\b",
    re.I,
)
_DELIMITER = re.compile(
    r"^\s*(?:(?:[:：,;=–-]+\s*)|"
    r"(?:(?:ceci|cela|[çc]a|le\s+fait)\s+)?que(?:\s+|$)|"
    r"(?:bien\s+que\s+)|"
    r"(?:(?:ceci|cela|[çc]a)\s*[:：]\s*))",
    re.I,
)
_QUALIFIER = re.compile(
    r"^\s*(?:(?:de|sur|pour)\s+(?:toi|jade)|"
    r"autobiographique|relationnelle)\s*(?=[:：,;=-]|\bque\b)",
    re.I,
)
_STRONG = re.compile(r"^(?:souviens|rappelle|retie|m[ée]morise)", re.I)


def parse_explicit_memory_intent(text: str) -> ExplicitMemoryIntent | None:
    """A direct request to remember, never a direct request to write a Core."""
    if not isinstance(text, str) or not text.strip():
        return None
    prefix = _PREFIX.match(text)
    if prefix is None:
        return None
    body = text[prefix.end():]
    marker = _MEMORY_MARKER.search(body)
    # "Retiens que..." and "Souviens-toi que..." are unambiguously memory
    # requests. Generic verbs like "mets" require a memory destination.
    strong = bool(_STRONG.match(prefix.group("verb")))
    if marker is None or marker.start() > 120:
        if not strong or not re.match(r"^\s*(?:bien\s+)?(?:que\b|[:：])", body, re.I):
            return None
        payload = body
        requested_core = False
    else:
        if re.search(r"\b(?:ne|pas|jamais|sans)\b", body[:marker.start()], re.I):
            return None
        payload = body[marker.end():]
        requested_core = bool(_CORE_MARKER.search(marker.group()))
    qualifier = _QUALIFIER.match(payload)
    if qualifier is not None:
        payload = payload[qualifier.end():]
    for _ in range(3):
        delimiter = _DELIMITER.match(payload)
        if delimiter is None:
            break
        payload = payload[delimiter.end():]
    summary = payload.strip(" \t\r\n\"'«»“”")
    return ExplicitMemoryIntent(summary=summary, requested_core=requested_core)
