"""Bounded sentence splitting for early spoken replies.

A limited number of early segments controls extra TTS calls. Common French
abbreviations and decimal prefixes are never spoken as separate sentences.
The final remainder is always emitted, so the audio never loses response text.
This is a heuristic, not a full natural-language sentence parser.
"""
from __future__ import annotations

import re


_ABBREVIATION = re.compile(
    r"(?:\b(?:m|mme|mlle|dr|pr|st|ste|etc|cf|env|av|ex)\.|\d+\.)$",
    re.IGNORECASE,
)
_BOUNDARY = re.compile(r"[.!?]+(?=\s|$)")


class SentenceAccumulator:
    def __init__(self, *, max_pending=240, max_total=4096, max_segments=6):
        if (not 50 <= max_pending <= max_total <= 8192
                or type(max_segments) is not int or not 1 <= max_segments <= 20):
            raise ValueError("invalid sentence bounds")
        self._pending = ""
        self._total = 0
        self._emitted = 0
        self.max_pending = max_pending
        self.max_total = max_total
        self.max_segments = max_segments

    def feed(self, fragment: str) -> list[str]:
        if not isinstance(fragment, str):
            raise ValueError("invalid dialogue fragment")
        self._total += len(fragment)
        if self._total > self.max_total:
            raise ValueError("streamed dialogue exceeds size limit")
        self._pending += fragment
        result = []
        cursor = 0
        # Reserve one call for the final remainder. This gives a predictable
        # upper bound even for "Oui. Non. Oui. Non." style responses.
        while self._pending and self._emitted < self.max_segments - 1:
            match = _BOUNDARY.search(self._pending, cursor)
            if match:
                cut = match.end()
                if _ABBREVIATION.search(self._pending[:cut]):
                    cursor = cut
                    continue
                sentence = self._pending[:cut].strip()
                self._pending = self._pending[cut:].lstrip()
            elif len(self._pending) > self.max_pending:
                cut = self._pending.rfind(" ", 50, self.max_pending)
                if cut < 0:
                    break
                sentence = self._pending[:cut].strip()
                self._pending = self._pending[cut:].lstrip()
            else:
                break
            cursor = 0
            if sentence:
                result.append(sentence)
                self._emitted += 1
        return result

    def finish(self) -> list[str]:
        text = self._pending.strip()
        self._pending = ""
        if text:
            self._emitted += 1
        return [text] if text else []
