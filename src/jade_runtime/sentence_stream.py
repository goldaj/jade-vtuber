"""Small bounded splitter for incremental spoken replies.

Only confirmed sentence boundaries are emitted before the final text. The
remaining fragment is sent at completion. This is a speech heuristic, not a
linguistic parser; callers preserve the original unmodified full reply.
"""
from __future__ import annotations

import re


class SentenceAccumulator:
    def __init__(self, *, max_pending=240, max_total=4096):
        if not 50 <= max_pending <= max_total <= 8192:
            raise ValueError("invalid sentence bounds")
        self._pending = ""
        self._total = 0
        self.max_pending = max_pending
        self.max_total = max_total

    def feed(self, fragment: str) -> list[str]:
        if not isinstance(fragment, str):
            raise ValueError("invalid dialogue fragment")
        self._total += len(fragment)
        if self._total > self.max_total:
            raise ValueError("streamed dialogue exceeds size limit")
        self._pending += fragment
        result = []
        while self._pending:
            # Punctuation must be followed by whitespace or more text before
            # emitting, so a token fragment containing only "." is not lost.
            match = re.search(r"[.!?]+(?=\s|$)", self._pending)
            if match is not None:
                cut = match.end()
                result.append(self._pending[:cut].strip())
                self._pending = self._pending[cut:].lstrip()
            elif len(self._pending) > self.max_pending:
                cut = self._pending.rfind(" ", 50, self.max_pending)
                if cut < 0:
                    break
                result.append(self._pending[:cut].strip())
                self._pending = self._pending[cut:].lstrip()
            else:
                break
        return [item for item in result if item]

    def finish(self) -> list[str]:
        text = self._pending.strip()
        self._pending = ""
        return [text] if text else []
