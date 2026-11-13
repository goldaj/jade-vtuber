"""Bounded bridge from asynchronous 24 kHz mono to Discord PCM frames."""
from __future__ import annotations

import asyncio
from array import array
import queue
import sys


FRAME_BYTES = 3840  # 20 ms × 48 kHz × stereo × signed 16-bit
SILENCE = bytes(FRAME_BYTES)
_END = object()


class Pcm48StereoBuffer:
    """Linear 2x resampler with continuity between arbitrary PCM deltas.

    Producer is asynchronous, consumer is discord.py's audio thread. Empty
    queues yield silence; only a real end marker ends Discord's audio player.
    """

    def __init__(self, *, max_frames=100, prebuffer_frames=5):
        self.frames = queue.Queue(maxsize=max_frames)
        self.prebuffer_frames = prebuffer_frames
        self.ready = asyncio.Event()
        self.pending_byte = b""
        self.previous = None
        self.output = bytearray()
        self.closed = False

    async def _put(self, frame):
        while not self.closed:
            try:
                self.frames.put_nowait(frame)
                if self.frames.qsize() >= self.prebuffer_frames:
                    self.ready.set()
                return
            except queue.Full:
                await asyncio.sleep(0.01)
        raise asyncio.CancelledError

    async def _emit(self):
        while len(self.output) >= FRAME_BYTES:
            frame = bytes(self.output[:FRAME_BYTES])
            del self.output[:FRAME_BYTES]
            await self._put(frame)

    async def feed(self, data):
        if not isinstance(data, bytes):
            raise ValueError("invalid PCM data")
        raw = self.pending_byte + data
        self.pending_byte = raw[len(raw) // 2 * 2:]
        samples = array("h")
        samples.frombytes(raw[:len(raw) // 2 * 2])
        if sys.byteorder != "little":
            samples.byteswap()
        converted = array("h")
        for current in samples:
            if self.previous is not None:
                midpoint = (self.previous + current) // 2
                converted.extend((self.previous, self.previous, midpoint, midpoint))
            self.previous = current
        if sys.byteorder != "little":
            converted.byteswap()
        self.output.extend(converted.tobytes())
        await self._emit()

    async def finish(self):
        if self.pending_byte:
            raise ValueError("incomplete PCM sample")
        if self.previous is not None:
            sample = array("h", (self.previous,) * 4)
            if sys.byteorder != "little":
                sample.byteswap()
            self.output.extend(sample.tobytes())
        if self.output:
            self.output.extend(bytes((-len(self.output)) % FRAME_BYTES))
            await self._emit()
        # Wake an utterance shorter than the prebuffer before a potentially full queue.
        self.ready.set()
        await self._put(_END)

    def read(self):
        if self.closed:
            return b""
        try:
            frame = self.frames.get_nowait()
        except queue.Empty:
            return SILENCE
        return b"" if frame is _END else frame

    def close(self):
        self.closed = True
        self.ready.set()
        while True:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                break
