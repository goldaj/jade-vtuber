"""Bounded, offline PCM turn segmentation; thresholds are experimental, not a VAD.

Input is 48 kHz stereo signed 16-bit little-endian PCM. Call feed/poll on one
serialized thread, with monotonic timestamps; call poll periodically even when
no packets arrive. Only feed audio after consent/authorization checks. On
revocation/disconnect call revoke immediately and discard previously emitted
turns; callers must invalidate in-flight work independently. No logging or
persistent storage occurs here. A max-duration result is a *partial* turn:
the caller must bound the combined size and timeout before STT
and responding. A final fragment can be empty when a turn ends exactly at the
limit. RMS cannot distinguish speech, music, echoes or quiet voices.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import struct
import time
from typing import Callable

_RATE = 48_000
_FRAME_BYTES = 4  # stereo signed 16 bit
_BYTES_PER_SECOND = _RATE * _FRAME_BYTES
_WINDOW_BYTES = _BYTES_PER_SECOND // 50  # 20 ms


@dataclass(frozen=True)
class AudioTurn:
    user_id: str = field(repr=False)
    pcm: bytes = field(repr=False)
    partial: bool = False


@dataclass
class _UserAudio:
    data: bytearray = field(default_factory=bytearray, repr=False)
    speech_bytes: int = 0
    silent_bytes: int = 0
    last_voice_at: float = 0.0
    last_at: float = 0.0
    continued: bool = False
    peak_rms: float = 0.0
    silent_peak_rms: float = 0.0


class PcmTurnSegmenter:
    """Isolated per-user buffers, explicit poll and fail-closed capacity.

    Defaults: 500 ms end silence, 120 ms voiced samples, 12 s max,
    RMS 350/32768, at most 16 speakers. A bounded relative threshold helps
    recognise persistent background noise after louder speech. Tune against
    real audio; energy windows are only a lightweight approximation.
    """

    def __init__(self, *, end_silence_s: float = 0.5,
                 min_speech_s: float = 0.12, max_turn_s: float = 12.0,
                 rms_threshold: float = 350.0, max_users: int = 16,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not (0.04 <= end_silence_s <= 3.0 and
                0.04 <= min_speech_s <= max_turn_s and
                0.5 <= max_turn_s <= 30.0 and
                0 < rms_threshold <= 32768 and
                isinstance(max_users, int) and not isinstance(max_users, bool) and
                1 <= max_users <= 64):
            raise ValueError('invalid segmentation limits')
        self._silence_s = end_silence_s
        self._min_bytes = math.ceil(min_speech_s * _RATE) * _FRAME_BYTES
        self._max_bytes = int(max_turn_s * _RATE) * _FRAME_BYTES
        self._threshold = rms_threshold
        self._max_users = max_users
        self._clock = clock
        self._users: dict[str, _UserAudio] = {}
        # Short-lived per-speaker background estimates, never persisted.
        self._ambient: dict[str, tuple[float, float]] = {}

    @staticmethod
    def _rms(data: memoryview) -> float:
        samples = struct.iter_unpack('<h', data)
        count = len(data) // 2
        return math.sqrt(sum(value * value for (value,) in samples) / count)

    def _finish(self, user_id: str, state: _UserAudio, *, partial: bool) -> list[AudioTurn]:
        result = []
        if state.speech_bytes >= self._min_bytes or state.continued:
            result.append(AudioTurn(user_id, bytes(state.data), partial))
        state.data.clear()
        state.speech_bytes = 0
        if not partial:
            if state.silent_peak_rms >= self._threshold:
                if user_id not in self._ambient and len(self._ambient) >= self._max_users:
                    self._ambient.pop(next(iter(self._ambient)))
                self._ambient[user_id] = (state.silent_peak_rms, state.last_at + 5.0)
            state.peak_rms = 0.0
            state.silent_peak_rms = 0.0
        state.continued = partial and bool(result)
        if not state.continued:
            state.silent_bytes = 0
        return result

    def feed(self, user_id: str, pcm: bytes, *, now: float | None = None) -> list[AudioTurn]:
        if not isinstance(user_id, str) or not user_id or len(user_id) > 128:
            raise ValueError('invalid user id')
        if not isinstance(pcm, bytes) or len(pcm) % _FRAME_BYTES:
            raise ValueError('PCM must be bytes aligned to stereo frames')
        at = self._clock() if now is None else now
        if not math.isfinite(at):
            raise ValueError('invalid timestamp')
        self._ambient = {uid: value for uid, value in self._ambient.items() if value[1] > at}
        state = self._users.get(user_id)
        if state is not None and at < state.last_at:
            raise ValueError('timestamps must be monotonic per user')
        if not pcm:
            return self.poll(now=at)
        if state is None:
            if len(self._users) >= self._max_users:
                raise ValueError('speaker capacity reached')
            state = self._users[user_id] = _UserAudio(last_at=at)
        results = self._expire_user(user_id, state, at)
        state.last_at = at
        view = memoryview(pcm)
        offset = 0
        while offset < len(view):
            available = self._max_bytes - len(state.data)
            n = min(_WINDOW_BYTES, len(view) - offset, available)
            chunk = view[offset:offset + n]
            level = self._rms(chunk)
            # A fan/open microphone can exceed the fixed threshold forever.
            # Once clearly louder speech is present, compare the remaining
            # energy to a slowly decaying peak as well as the fixed minimum.
            state.peak_rms = max(level, state.peak_rms * 0.998)
            relative = min(1500.0, state.peak_rms * 0.50) if state.peak_rms > self._threshold * 2 else 0.0
            ambient = self._ambient.get(user_id)
            ambient_threshold = 0.0 if ambient is None else min(1500.0, ambient[0] * 1.25)
            voiced = level >= max(self._threshold, relative, ambient_threshold)
            if ambient is not None and level <= ambient_threshold:
                self._ambient[user_id] = (ambient[0], at + 5.0)
            offset += n
            if voiced:
                state.data.extend(chunk)
                state.speech_bytes += n
                state.silent_bytes = 0
                state.silent_peak_rms = 0.0
                state.last_voice_at = at
            elif state.data or state.continued:
                state.data.extend(chunk)
                state.silent_bytes += n
                state.silent_peak_rms = max(state.silent_peak_rms, level)
            if state.data and state.silent_bytes >= self._silence_s * _BYTES_PER_SECOND:
                results.extend(self._finish(user_id, state, partial=False))
            elif state.data and len(state.data) >= self._max_bytes:
                results.extend(self._finish(user_id, state, partial=True))
        # Silent/non-speech users should not occupy capacity indefinitely.
        if not state.data and not state.continued:
            self._users.pop(user_id, None)
        return results

    def _expire_user(self, user_id: str, state: _UserAudio, at: float) -> list[AudioTurn]:
        if (state.data or state.continued) and at - state.last_voice_at >= self._silence_s:
            return self._finish(user_id, state, partial=False)
        return []

    def poll(self, *, now: float | None = None) -> list[AudioTurn]:
        at = self._clock() if now is None else now
        if not math.isfinite(at) or any(at < s.last_at for s in self._users.values()):
            raise ValueError('timestamps must be monotonic')
        results: list[AudioTurn] = []
        for user_id, state in list(self._users.items()):
            results.extend(self._expire_user(user_id, state, at))
            if not state.data and not state.continued:
                del self._users[user_id]
        return results

    def revoke(self, user_id: str | None = None) -> None:
        """Drop one user's pending PCM, or all PCM on session shutdown."""
        if user_id is None:
            self._users.clear()
            self._ambient.clear()
        else:
            self._users.pop(user_id, None)
            self._ambient.pop(user_id, None)
