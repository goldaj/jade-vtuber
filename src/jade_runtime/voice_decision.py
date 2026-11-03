"""Bounded, offline voice-turn decisions; no audio or transcript is retained.

This is a conservative policy primitive, not a classifier or a consent gate.
The transport must reject unauthorized PCM before transcription, call this only
for completed turns, and discard a session on participant change or revocation.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import re
import secrets
import time
import unicodedata
from typing import Callable


@dataclass(frozen=True)
class TurnDecision:
    should_reply: bool
    reason: str
    turn_id: str = field(default="", repr=False)


@dataclass
class _Session:
    touched: float
    muted: bool = False
    last_speaker: int | None = field(default=None, repr=False)
    active_until: float = 0.0
    pending: OrderedDict[str, tuple[int, float]] = field(default_factory=OrderedDict, repr=False)


def _words(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", without_marks, flags=re.UNICODE))


_MUTE = frozenset({"silence", "chut", "stop", "arrete", "tais toi", "arrete de parler",
                   "arrete de repondre", "ne reponds plus", "ne parle plus"})
_RESUME = frozenset({"reprends", "tu peux reprendre", "tu peux parler", "tu peux repondre",
                     "reponds a nouveau", "recommence a parler"})
_NOISE = frozenset({"euh", "heu", "hmm", "hum", "mm", "mmm", "bruit", "silence audio",
                    "musique", "music", "inaudible", "applaudissements"})
_ASIDE = frozenset({"je ne te parle pas", "je te parle pas", "je parle pas a toi", "ce n est pas pour toi",
                    "ce n est pas a toi que je parle", "je parle a quelqu un d autre",
                    "je pense tout haut", "je reflechis tout haut"})


class ConversationTurnDecider:
    """Decide from trusted session metadata and one completed transcription.

    `direct_address` is a trusted upstream signal, not an automatic inference
    from a name or question mark. `participant_count` counts authorized humans.
    A completed response must be acknowledged with `mark_replied` before a
    same-speaker group follow-up can use the short context window.
    """

    def __init__(self, *, max_sessions: int = 128, ttl: float = 1800,
                 follow_up_seconds: float = 30, clock: Callable[[], float] = time.monotonic):
        if (type(max_sessions) is not int or not 1 <= max_sessions <= 256
                or not 0 < ttl <= 86400 or not 0 <= follow_up_seconds <= ttl):
            raise ValueError("invalid voice policy bounds")
        self.max_sessions = max_sessions
        self.ttl = ttl
        self.follow_up_seconds = follow_up_seconds
        self.clock = clock
        self._sessions: OrderedDict[str, _Session] = OrderedDict()

    def _session(self, session_id: str, now: float) -> _Session | None:
        for key, state in list(self._sessions.items()):
            if not state.muted and now - state.touched >= self.ttl:
                del self._sessions[key]
        state = self._sessions.get(session_id)
        if state is None:
            if len(self._sessions) >= self.max_sessions:
                candidates = (key for key, item in self._sessions.items() if not item.muted)
                evict = next(candidates, None)
                if evict is None:
                    return None
                del self._sessions[evict]
            state = _Session(now)
            self._sessions[session_id] = state
        state.touched = now
        self._sessions.move_to_end(session_id)
        return state

    def decide(self, session_id: str, speaker_id: int, text: str, *,
               authorized: bool, consent_confirmed: bool, participant_count: int,
               direct_address: bool = False, is_bot: bool = False) -> TurnDecision:
        # Explicit authorization must already have been enforced before STT.
        if authorized is not True or consent_confirmed is not True or is_bot is not False:
            return TurnDecision(False, "not_authorized")
        if (not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", session_id)
                or type(speaker_id) is not int or speaker_id <= 0
                or type(participant_count) is not int or not 1 <= participant_count <= 32
                or type(direct_address) is not bool or not isinstance(text, str) or len(text) > 4000):
            return TurnDecision(False, "invalid_turn")
        normalized = _words(text)
        if not normalized or normalized in _NOISE or sum(c.isalnum() for c in normalized) < 2:
            return TurnDecision(False, "noise_or_fragment")
        now = self.clock()
        state = self._session(session_id, now)
        if state is None:
            return TurnDecision(False, "session_capacity")
        addressed = participant_count == 1 or direct_address or (
            state.last_speaker == speaker_id and now < state.active_until)
        if normalized in (_MUTE | _RESUME) and not addressed:
            return TurnDecision(False, "ambiguous_group")
        if normalized in _MUTE:
            state.muted = True
            state.pending.clear()
            state.active_until = 0.0
            return TurnDecision(False, "muted")
        if normalized in _RESUME:
            state.muted = False
            state.active_until = 0.0
            return TurnDecision(False, "resumed")
        if state.muted:
            return TurnDecision(False, "muted")
        if normalized in _ASIDE:
            return TurnDecision(False, "aside")
        if not addressed:
            return TurnDecision(False, "ambiguous_group")
        turn_id = secrets.token_hex(16)
        if len(state.pending) >= 8:
            state.pending.popitem(last=False)
        state.pending[turn_id] = (speaker_id, now)
        return TurnDecision(True, "solo" if participant_count == 1 else "addressed_or_followup", turn_id)

    def mark_replied(self, session_id: str, turn_id: str) -> bool:
        """Start a follow-up window only after the application emitted a reply."""
        state = self._sessions.get(session_id)
        now = self.clock()
        if state is None:
            return False
        if state.muted:
            return False
        if now - state.touched >= self.ttl:
            self._sessions.pop(session_id, None)
            return False
        accepted = state.pending.pop(turn_id, None)
        if accepted is None or now - accepted[1] > 120:
            return False
        state.last_speaker = accepted[0]
        state.active_until = now + self.follow_up_seconds
        state.touched = now
        self._sessions.move_to_end(session_id)
        return True

    def revoke(self, session_id: str) -> None:
        """Forget session state; the transport must also cancel audio and work."""
        self._sessions.pop(session_id, None)
