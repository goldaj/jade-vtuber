"""Conservative longitudinal personality cues derived from existing opt-in memory.

Jade's core identity stays in the system prompt. This module reads only the
authorized memories passed by the caller. It never learns a third party's
preferences as Jade's own, alters Core Memories or makes a model/API call.
The derived version is reproducible after restart, since SQLite is the source.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import re
import unicodedata

_STYLE = re.compile(
    r"(?i)(humour|ton |style |personnalit|préfér|aime|n'aime|"
    r"voix |façon de parler|évolu|expérience marquante|habitude|souvenir)"
)
_JADE_SUBJECT = re.compile(r"(?i)^\s*jade\b")


def _normalized(text: str) -> str:
    lowered = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(ch for ch in lowered
                           if not unicodedata.combining(ch)).split())


def personality_snapshot(memories, autobiography=(), *, max_observations=4) -> dict:
    """Recompute a dated, deterministic profile from confirmed Jade memories.

    Ordinary observations require repetition over two memory rows unless they
    were voluntarily classified Core; autobiography is always owner-only.
    Deletion/correction therefore instantly changes the derived profile.
    """
    if not 1 <= max_observations <= 8:
        raise ValueError("invalid personality profile size")
    candidates = []
    for row in autobiography:
        if isinstance(row, dict) and isinstance(row.get("summary"), str):
            if row["summary"].strip():
                candidates.append((True, row["summary"].strip(), row.get("created_at", "")))
    for row in memories:
        if not isinstance(row, dict):
            continue
        summary = row.get("summary")
        if not isinstance(summary, str) or not _JADE_SUBJECT.search(summary):
            continue
        if not _STYLE.search(summary + " " + str(row.get("significance") or "")):
            continue
        candidates.append((row.get("kind") in ("core_self", "core_relationship"),
                           summary.strip(), row.get("created_at", "")))
    counts = Counter(_normalized(summary) for _, summary, _ in candidates)
    selected, used = [], set()
    for core, summary, date in sorted(candidates, key=lambda x: (x[0], x[2]), reverse=True):
        tag = _normalized(summary)
        # A curated Jade statement is already an intentional memory event.
        # Repetition adds confidence but is not needed for an initial cue.
        if tag in used:
            continue
        used.add(tag)
        selected.append({"summary": summary[:145], "date": str(date)[:10],
                         "core": bool(core), "evidence_count": counts[tag]})
        if len(selected) >= max_observations:
            break
    version = hashlib.sha256(
        repr([(x["summary"], x["date"], x["core"], x["evidence_count"])
              for x in selected]).encode("utf-8")).hexdigest()[:12]
    return {"version": version, "observations": selected}


def personality_cues(memories, autobiography=(), *, max_chars=280):
    """Compact non-prescriptive snapshot, never a second LLM request."""
    profile = personality_snapshot(memories, autobiography)
    if not profile["observations"]:
        return ""
    lines = []
    used = 0
    for item in profile["observations"]:
        note = item["summary"]
        if used + len(note) > max_chars:
            break
        lines.append("- " + note)
        used += len(note)
    if not lines:
        return ""
    return ("Repères évolutifs factuels de Jade (version "
            + profile["version"] + " ; souvenirs non prescriptifs ; "
            "ne pas divulguer en public) :\n" + "\n".join(lines))
