"""Optional microphone *capture*, not an STT engine; recognition is OpenAI only."""
import asyncio
from array import array
from io import BytesIO
import math
import sys
import threading
import wave


def pcm_to_wav(samples: bytes, *, sample_rate=16000) -> bytes:
    if len(samples) % 2 or not 8000 <= sample_rate <= 48000:
        raise ValueError("invalid microphone PCM")
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples)
    return output.getvalue()


def is_speech_loud_enough(samples: bytes, *, threshold=550) -> bool:
    if len(samples) % 2 or not 0 < threshold < 32768:
        raise ValueError("invalid PCM or voice threshold")
    values = array("h")
    values.frombytes(samples)
    if sys.byteorder != "little":
        values.byteswap()
    if not values:
        return False
    rms = math.sqrt(sum(float(v)*v for v in values) / len(values))
    return rms >= threshold


def capture_wav(seconds: float = 3.0, *, sample_rate=16000,
                threshold=550, stop_event=None) -> bytes | None:
    """Blocking, opt-in capture. Never prints, stores or uploads a recording."""
    if not 0.5 <= seconds <= 15:
        raise ValueError("invalid capture duration")
    try:
        import sounddevice as sd  # Optional native capture, NOT transcription.
    except ImportError as exc:
        raise RuntimeError("install the optional microphone extra") from exc
    # Own a stream so cancellation does not stop an unrelated sounddevice user.
    stop_event = stop_event or threading.Event()
    chunks = bytearray()
    max_bytes = int(seconds * sample_rate) * 2
    def receive(indata, frames, time_info, status):
        remaining = max_bytes - len(chunks)
        if remaining > 0:
            chunks.extend(indata.tobytes()[:remaining])
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16", callback=receive):
        stopped = stop_event.wait(seconds)
    if stopped:
        return None
    samples = bytes(chunks)
    if not is_speech_loud_enough(samples, threshold=threshold):
        return None
    return pcm_to_wav(samples, sample_rate=sample_rate)


async def capture_async(seconds: float = 3.0) -> bytes | None:
    return await asyncio.to_thread(capture_wav, seconds)


class MicrophoneCapture:
    """One owned capture thread, with explicit stop and completion acknowledgement."""
    def __init__(self):
        self._task = None
        self._stop = None

    async def __call__(self, seconds):
        if self._task is not None and not self._task.done():
            raise RuntimeError("microphone capture is already running")
        stop = threading.Event()
        self._stop = stop
        task = asyncio.create_task(asyncio.to_thread(capture_wav, seconds, stop_event=stop))
        self._task = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            stop.set()
            # Even if the caller is cancelled again, retain the task reference;
            # a later capture cannot start while the hardware thread is alive.
            await asyncio.shield(task)
            raise

    def stop(self):
        if self._stop is not None:
            self._stop.set()


class AudioCoordinator:
    """Half duplex gate: invalidate a capture before speech, without holding locks across I/O."""
    def __init__(self, *, capture_stop_timeout=2.0):
        self._condition = asyncio.Condition()
        self._speech_lock = asyncio.Lock()
        self._speaking = False
        self._closed = False
        self._generation = 0
        self._capture = None
        self._stop = None
        self.capture_stop_timeout = capture_stop_timeout

    async def capture(self, capture, duration):
        async with self._condition:
            await self._condition.wait_for(lambda: self._closed or (
                not self._speaking and (self._capture is None or self._capture.done())))
            if self._closed:
                raise RuntimeError("audio coordinator is closed")
            generation = self._generation
            task = asyncio.create_task(capture(duration))
            self._capture = task
            self._stop = getattr(capture, "stop", None)
        try:
            return await asyncio.shield(task), generation
        except asyncio.CancelledError:
            if self._stop:
                self._stop()
            # Preserve a live capture task as a barrier if its owner is cancelled.
            raise
        finally:
            if task.done():
                async with self._condition:
                    if self._capture is task:
                        self._capture = None
                        self._stop = None
                    self._condition.notify_all()
            else:
                task.add_done_callback(lambda unused: asyncio.create_task(self._capture_done(task)))

    async def _capture_done(self, task):
        # Retrieve an otherwise unobserved exception on cancelled capture owners.
        if not task.cancelled():
            task.exception()
        async with self._condition:
            if self._capture is task:
                self._capture = None
                self._stop = None
            self._condition.notify_all()

    async def valid(self, generation):
        async with self._condition:
            return not self._closed and not self._speaking and generation == self._generation

    async def begin_speech(self):
        await self._speech_lock.acquire()
        try:
            async with self._condition:
                if self._closed:
                    raise RuntimeError("audio coordinator is closed")
                self._speaking = True
                self._generation += 1
                task, stop = self._capture, self._stop
                if stop:
                    stop()
            if task is not None and not task.done():
                await asyncio.wait_for(asyncio.shield(task), self.capture_stop_timeout)
            async with self._condition:
                if self._closed:
                    raise RuntimeError("audio coordinator is closed")
        except BaseException:
            await self.end_speech()
            raise

    async def end_speech(self):
        async with self._condition:
            self._speaking = False
            self._condition.notify_all()
        if self._speech_lock.locked():
            self._speech_lock.release()

    async def close(self):
        async with self._condition:
            self._closed = True
            self._generation += 1
            task, stop = self._capture, self._stop
            if stop:
                stop()
            self._condition.notify_all()
        if task is not None and not task.done():
            await asyncio.wait_for(asyncio.shield(task), self.capture_stop_timeout)
