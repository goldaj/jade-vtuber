"""Privacy-safe timing for a single Discord PCM playback attempt.

The clock starts when Discord begins its playback path, not when a user
finishes speaking. Values indicate a local audio-thread read, not that a
remote Discord listener actually heard the frame.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
import time

from .session_logging import event, summary


@dataclass
class PCMProgressTiming:
    started_at: float = field(default_factory=time.monotonic)
    tts_completed_at: float | None = None

    def mark_tts_completed(self) -> None:
        """Called only after a successful provider response.done."""
        if self.tts_completed_at is None:
            self.tts_completed_at = time.monotonic()

    def snapshot(self, first_pcm_at: float | None, *, playback_completed: bool) -> dict:
        first_ms = (None if first_pcm_at is None else
                    round((first_pcm_at - self.started_at) * 1000))
        done_ms = (None if self.tts_completed_at is None else
                   round((self.tts_completed_at - self.started_at) * 1000))
        overlap = (None if first_pcm_at is None or self.tts_completed_at is None
                   else first_pcm_at < self.tts_completed_at)
        if overlap is None:
            verdict = "inconclusive"
        elif overlap:
            verdict = ("progressive_confirmed" if playback_completed
                       else "progressive_observed_playback_incomplete")
        else:
            verdict = "no_overlap_observed"
        return {
            "source_platform": "discord_voice",
            "first_pcm_ms": first_ms,
            "tts_completed_ms": done_ms,
            "pcm_before_tts_complete": overlap,
            "playback_completed": playback_completed,
            "verdict": verdict,
        }

    def log(self, first_pcm_at: float | None, *, playback_completed: bool) -> None:
        fields = self.snapshot(first_pcm_at, playback_completed=playback_completed)
        summary("rec006_pcm_progress", **fields)
        event("rec006_pcm_progress", **fields)


active_pcm_timing: ContextVar[PCMProgressTiming | None] = ContextVar(
    "jade_active_discord_pcm_timing", default=None
)
