"""Bounded, thread-safe Discord PCM playback without temporary WAV/FFmpeg.

One input sample is 24 kHz mono signed 16-bit LE. Output is 48 kHz stereo
signed 16-bit LE with exactly 3,840 bytes per 20 ms Discord frame.
Linear interpolation preserves its previous sample across provider deltas.
No extra speech AI, external process, private audio storage or dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
import asyncio
from queue import Empty, Full, Queue
import struct
import threading
import time


FRAME_BYTES = 3840
_SILENCE = b"\x00" * FRAME_BYTES


@dataclass(frozen=True)
class PCMPlaybackMetrics:
    """Content-free local transport metrics, not proof of audible phone output."""

    first_nonzero_read_ms: int | None
    frames_read: int
    prebuffer_silence_frames: int
    underrun_silence_frames: int
    max_queued_frames: int




class DiscordPCMBuffer:
    """Async producer, synchronous VoiceClient audio thread consumer.

    A bounded queue caps audio buffered ahead of playback. No asyncio object
    is touched by Discord's audio thread. An empty live queue emits one silence
    frame; only finish+drain yields b'', so a temporary gap is not an EOF.
    """

    def __init__(self, *, max_frames=50, prebuffer_frames=1, on_frame=None, idle_timeout=30.0):
        if not isinstance(max_frames, int) or isinstance(max_frames, bool) or not 5 <= max_frames <= 150:
            raise ValueError("invalid PCM queue capacity")
        if not isinstance(prebuffer_frames, int) or not 1 <= prebuffer_frames <= max_frames:
            raise ValueError("invalid prebuffer length")
        if not 1 <= idle_timeout <= 120:
            raise ValueError("invalid PCM idle timeout")
        self._frames = Queue(maxsize=max_frames)
        self._tail = bytearray()
        self._pending_byte = b""
        self._previous = None
        self._done = threading.Event()
        self._aborted = threading.Event()
        self._on_frame = on_frame
        self._last_progress = time.monotonic()
        self._idle_timeout = idle_timeout
        self._received = 0
        self._prebuffer_frames = prebuffer_frames
        self._started = False
        self._created_at = time.monotonic()
        self._first_nonzero_at = None
        self._frames_read = 0
        self._prebuffer_silence = 0
        self._underrun_silence = 0
        self._peak_frames = 0

    async def _offer(self, frame: bytes):
        while not self._aborted.is_set():
            try:
                self._frames.put_nowait(frame)
                self._peak_frames = max(self._peak_frames, self._frames.qsize())
                self._last_progress = time.monotonic()
                return
            except Full:
                await asyncio.sleep(0.01)
        raise RuntimeError("Discord PCM playback interrupted")

    async def feed(self, pcm: bytes):
        if self._done.is_set() or self._aborted.is_set():
            raise RuntimeError("Discord PCM playback not accepting audio")
        if not isinstance(pcm, bytes) or not pcm:
            raise ValueError("invalid 24 kHz mono PCM chunk")
        self._received += len(pcm)
        if self._received > 4_800_000:
            raise ValueError("Discord PCM limit exceeded")
        # A transport delta can end between the bytes of a 16-bit sample.
        # Keep at most one byte until the next delta; do not pad or drop it.
        pcm = self._pending_byte + pcm
        self._pending_byte = pcm[-1:] if len(pcm) % 2 else b""
        pcm = memoryview(pcm)[:len(pcm) - len(self._pending_byte)]
        previous = self._previous
        # One 20-ms source slice at a time. Never expand an entire provider
        # delta into a large bytearray before a slow Discord reader can drain it.
        for offset in range(0, len(pcm), 960):
            converted = bytearray()
            for (sample,) in struct.iter_unpack("<h", pcm[offset:offset + 960]):
                first = sample if previous is None else (previous + sample) // 2
                converted.extend(struct.pack("<hhhh", first, first, sample, sample))
                previous = sample
            self._previous = previous
            self._tail.extend(converted)
            while len(self._tail) >= FRAME_BYTES:
                frame = bytes(self._tail[:FRAME_BYTES])
                del self._tail[:FRAME_BYTES]
                await self._offer(frame)
            # Very large caller-provided input must not monopolize the event
            # loop, even if Discord drains faster than it is produced.
            if offset and offset % 48_000 == 0:
                await asyncio.sleep(0)

    async def finish(self):
        if self._done.is_set():
            return
        if self._received == 0:
            raise ValueError("empty synthesized PCM stream")
        if self._pending_byte:
            raise ValueError("incomplete synthesized PCM sample")
        if self._tail:
            frame = bytes(self._tail).ljust(FRAME_BYTES, b"\x00")
            self._tail.clear()
            await self._offer(frame)
        self._done.set()

    def _silence(self, *, prebuffer=False) -> bytes:
        # Playback-time silence closes the mouth and counts real underruns.
        self._frames_read += 1
        if prebuffer:
            self._prebuffer_silence += 1
        else:
            self._underrun_silence += 1
        if self._on_frame is not None:
            try:
                self._on_frame(_SILENCE)
            except Exception:
                pass
        return _SILENCE

    def read(self) -> bytes:
        """Called by Discord voice player's independent thread every 20 ms."""
        if self._aborted.is_set():
            return b""
        if not self._started:
            if not self._done.is_set() and self._frames.qsize() < self._prebuffer_frames:
                if time.monotonic() - self._last_progress > self._idle_timeout:
                    self.abort()
                    return b""
                return self._silence(prebuffer=True)
            self._started = True
        try:
            frame = self._frames.get_nowait()
        except Empty:
            if self._done.is_set():
                return b""
            if time.monotonic() - self._last_progress > self._idle_timeout:
                self.abort()
                return b""
            return self._silence()
        self._last_progress = time.monotonic()
        self._frames_read += 1
        if self._first_nonzero_at is None and any(frame):
            self._first_nonzero_at = self._last_progress
        if self._on_frame is not None:
            try:
                self._on_frame(frame)
            except Exception:
                pass  # animation cannot block or break voice playback
        return frame

    def abort(self):
        self._aborted.set()
        self._done.set()
        self._pending_byte = b""
        self._tail.clear()
        while True:
            try:
                self._frames.get_nowait()
            except Empty:
                break

    def metrics(self) -> PCMPlaybackMetrics:
        """Snapshot numeric PCM reads; contains no user content or audio."""
        first_ms = (None if self._first_nonzero_at is None else
                    round((self._first_nonzero_at - self._created_at) * 1000))
        return PCMPlaybackMetrics(
            first_ms, self._frames_read, self._prebuffer_silence,
            self._underrun_silence, self._peak_frames)

    @property
    def aborted(self):
        return self._aborted.is_set()


def make_discord_source(buffer: DiscordPCMBuffer):
    """Delay Discord's optional import until a real voice transport is active."""
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("install the optional Discord voice extra") from exc

    class LivePCMSource(discord.AudioSource):
        def read(self):
            return buffer.read()

        def is_opus(self):
            return False

        def cleanup(self):
            buffer.abort()

    return LivePCMSource()
