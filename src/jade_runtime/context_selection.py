"""Select useful 24-hour dialogue fragments without truncating SQLite storage.

Only the already authorized channel/identity history is accepted. This module
never opens another channel or invokes an embedding/LLM model.
"""
from __future__ import annotations

import re
import unicodedata

_WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)
_STOP = frozenset(("dans", "avec", "pour", "mais", "nous", "vous", "cette",
                   "comme", "sont", "avait", "jade", "goldaj", "elle", "moi",
                   "est", "sur", "des", "une", "les", "plus", "pas", "que"))


def _words(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return {w for w in _WORD.findall(folded) if w not in _STOP}


def select_context(history, question: str, *, max_chars: int = 12000,
                   recent_pairs: int = 5, older_pairs: int = 4) -> list[dict[str, str]]:
    """Retain recent dialogue, then score older *paired* exchanges for relevance.

    Storage is untouched. Input must already be scoped by the caller. Retains
    original chronological ordering; older exchanges cannot become instructions.
    """
    if max_chars < 1000 or recent_pairs < 1 or older_pairs < 0:
        raise ValueError("invalid dialogue context budget")
    entries = [dict(m) for m in history if isinstance(m, dict)
               and m.get("role") in ("user", "assistant")
               and isinstance(m.get("content"), str)]
    # Discord's linked voice/text context may contain unpaired passive user
    # messages. Preserve their chronology without assigning a later answer
    # to the wrong speaker.
    pairs = []
    current = []
    for entry in entries:
        if entry["role"] == "user":
            if current:
                pairs.append(current)
            current = [entry]
        elif current:
            current.append(entry)
            pairs.append(current)
            current = []
        else:
            pairs.append([entry])
    if current:
        pairs.append(current)
    if not pairs:
        return []
    recent_indices = list(range(max(0, len(pairs) - recent_pairs), len(pairs)))
    selected = set()
    used = 0

    def fit(index: int) -> bool:
        nonlocal used
        cost = sum(len(m["content"]) for m in pairs[index])
        if cost + used > max_chars:
            return False
        selected.add(index)
        used += cost
        return True

    # Most recent exchanges take precedence under a hard input budget.
    for index in reversed(recent_indices):
        fit(index)
    terms = _words(question)
    older = []
    for index in range(max(0, len(pairs) - recent_pairs)):
        content = " ".join(m["content"] for m in pairs[index])
        intersection = len(_words(content) & terms)
        if intersection:
            older.append((intersection, index))
    for _score, index in sorted(older, reverse=True)[:older_pairs]:
        fit(index)
    return [entry for index in sorted(selected) for entry in pairs[index]]
