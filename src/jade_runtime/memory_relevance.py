"""Local, permission-filtered relevance ranking; never calls a language model."""
from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata

_WORDS = re.compile(r"[^\W_]{3,}", re.UNICODE)
_STOP = {"avec", "pour", "dans", "mais", "elle", "vous", "nous", "avoir",
         "quel", "quelle", "cette", "comment", "est", "des", "une", "les",
         "que", "plus", "jade", "goldaj", "sont", "their", "from", "what"}


def terms(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return {t for t in _WORDS.findall(folded) if t not in _STOP}


def rank_memories(candidates: list[dict], question: str, *, limit: int = 8,
                  now: datetime | None = None) -> list[dict]:
    """Rank only candidates already filtered for identity and audience by SQLite.

    Core memories get a modest importance boost; a strong lexical match can
    outrank a recent unrelated Core. Unrelated candidates are not promoted by
    an arbitrary importance score when a query has useful terms.
    """
    if not 1 <= limit <= 32:
        raise ValueError("invalid memory selection limit")
    query = terms(question[:1200])
    # A generic "what do you remember about me?" is a request for an overview,
    # not a literal search for the words "remember" and "me".
    overview = bool(re.search(
        r"(?i)(souvenirs?|souviens|rappelle.moi|que sais.tu de moi|"
        r"que connais.tu de moi|what do you remember)",
        question[:1200]))
    if overview or not query:
        return candidates[:limit]
    clock = now or datetime.now(timezone.utc)
    ranked = []
    for index, memory in enumerate(candidates):
        if not isinstance(memory, dict):
            continue
        summary = memory.get("summary", "")
        if not isinstance(summary, str):
            continue
        words = terms(summary + " " + (memory.get("significance") or ""))
        overlap = len(words & query)
        if query and not overlap:
            continue
        created = memory.get("created_at") or ""
        try:
            stamp = datetime.fromisoformat(created)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age = max(0, (clock - stamp).days)
        except (ValueError, TypeError):
            age = 365
        kind = memory.get("kind", "")
        relevance = (overlap / max(1, len(query))) if query else 0
        score = (10 * relevance + 0.8 * overlap
                 + (0.8 if kind in ("core_self", "core_relationship") else 0)
                 + 1 / (1 + age / 45))
        ranked.append((score, -index, memory))
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    # Preserve a small contextual fallback when lexical overlap misses
    # useful paraphrases in the person's own authorized memories.
    if not ranked:
        return candidates[:min(2, limit)]
    return [item[2] for item in ranked[:limit]]
