"""Stable identity with limited autobiographical and Jade-specific cues.

Other peoples' stated preferences remain contextual facts, not traits of Jade.
Do not call an additional LLM to compile them.
"""
from __future__ import annotations

import re

_STYLE = re.compile(
    r"(?i)(humour|ton |style |personnalit|préfér|aime|n'aime|"
    r"voix |façon de parler|évolu|expérience marquante)"
)
_JADE_SUBJECT = re.compile(r"(?i)^\s*jade\b")


def personality_cues(memories, autobiography=(), *, max_chars=280):
    """Use only authorized memories; never promote others' tastes to Jade's."""
    notes = []
    for event in autobiography[:3]:
        if isinstance(event, dict):
            summary = event.get("summary", "")
            if isinstance(summary, str) and summary.strip():
                notes.append(summary.strip()[:145])
    for event in memories:
        if not isinstance(event, dict):
            continue
        summary, significance = event.get("summary", ""), event.get("significance", "")
        if (isinstance(summary, str) and isinstance(significance, str)
                and _JADE_SUBJECT.search(summary)
                and _STYLE.search(summary + " " + significance)):
            note = summary.strip()[:145]
            if note not in notes:
                notes.append(note)
        if len(notes) >= 3:
            break
    if not notes:
        return ""
    lines, used = [], 0
    for note in notes[:3]:
        if used + len(note) > max_chars:
            break
        lines.append("- " + note)
        used += len(note)
    if not lines:
        return ""
    return ("Repères factuels de Jade (souvenirs non prescriptifs ; "
            "ne pas divulguer en public) :\n" + "\n".join(lines))
