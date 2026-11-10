"""Demo conversation controller, independent of Tk/Qt and Live2D.

This module starts no work on import. A client must explicitly supply its own
API key and invoke a text or microphone turn. Event callbacks may execute on
the audio worker thread: a GUI must marshal them onto its UI thread.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
import math
import struct
import threading
import wave
from typing import Callable

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.microphone import capture_wav
from src.jade_runtime.openai_services import OpenAIServices
from demo.reelle.realtime_tts import RealtimeTTS, _words


@dataclass(frozen=True)
class DemoEvent:
    """Events for the UI; never include the API key, PCM, or exception text.

    kind: state, user_text, reply_text, spoken_text, audio_level or error.
    Audio levels are approximate 0..1 RMS observations from the played WAV,
    not timestamps or visemes. The renderer must return to rest at 0.
    """

    kind: str
    value: str | float


def _wav_pcm(audio: bytes) -> tuple[bytes, int, int]:
    """Decode bounded 16-bit PCM WAV, tolerating a streaming length header."""
    if not isinstance(audio, bytes) or not 44 <= len(audio) <= 20_000_000:
        raise ValueError("invalid audio")
    try:
        with wave.open(BytesIO(audio), "rb") as stream:
            rate, channels = stream.getframerate(), stream.getnchannels()
            if (stream.getsampwidth() != 2 or channels not in (1, 2)
                    or not 8000 <= rate <= 48000 or stream.getcomptype() != "NONE"):
                raise ValueError("unsupported audio format")
            # Some valid streamed WAVs advertise an unknown, very large length.
            # Never allocate based on that header: the actual byte length is the bound.
            pcm = stream.readframes(len(audio) // (channels * 2))
    except (EOFError, wave.Error, OSError) as exc:
        raise ValueError("invalid audio") from exc
    if not pcm or len(pcm) % (channels * 2):
        raise ValueError("invalid audio frames")
    return pcm, rate, channels


def _level(pcm: bytes) -> float:
    count = len(pcm) // 2
    if not count:
        return 0.0
    rms = math.sqrt(sum(sample * sample for (sample,) in struct.iter_unpack("<h", pcm)) / count)
    return min(1.0, rms / 10000.0)


def play_wav(audio: bytes, stop: threading.Event, notify: Callable[[DemoEvent], None]) -> None:
    """Play bounded WAV using PortAudio; no temporary file or other TTS engine."""
    pcm, rate, channels = _wav_pcm(audio)
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("audio output unavailable") from exc
    frame_bytes = channels * 2
    # 20 ms chunks keep cancellation bounded by device/driver behavior.
    chunk_bytes = max(1, rate // 50) * frame_bytes
    try:
        with sd.RawOutputStream(samplerate=rate, channels=channels, dtype="int16") as stream:
            for offset in range(0, len(pcm), chunk_bytes):
                if stop.is_set():
                    stream.abort()
                    return
                chunk = pcm[offset:offset + chunk_bytes]
                notify(DemoEvent("audio_level", _level(chunk)))
                stream.write(chunk)
    finally:
        notify(DemoEvent("audio_level", 0.0))


def _isolated_openai_client(settings: Settings, *, http_client=None):
    """Create a client that cannot inherit arbitrary SDK environment headers.

    The SDK accepts OPENAI_CUSTOM_HEADERS in addition to explicit headers. A
    caller-supplied Authorization alone is insufficient: unknown environment
    headers can contain private identifiers or change request behavior. Both
    REST and Realtime use this fixed public header property; authentication still
    comes from the supplied key through the SDK's bearer-auth mechanism.
    """
    from openai import AsyncOpenAI

    class DemoOpenAI(AsyncOpenAI):
        @property
        def default_headers(self):
            return {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            }

    options = {
        "api_key": settings.api_key,
        "timeout": settings.timeout_seconds,
        "max_retries": 0,
        "base_url": "https://api.openai.com/v1",
        "organization": "",
        "project": "",
        "admin_api_key": "",
        "webhook_secret": "",
    }
    if http_client is not None:
        options["http_client"] = http_client
    return DemoOpenAI(**options)


class DemoSession:
    """One in-memory-key demo session; call all async methods on one event loop.

    A single turn is admitted at a time. The recipient explicitly starts each
    microphone recording; microphone audio, transcripts, key and conversation
    history stay in memory. OpenAI requests are billable. No retry is initiated
    by this controller or by the SDK, so one turn does not silently retry a
    billable request. The key is not written to disk by this controller.
    """

    def __init__(self, api_key: str, prompt: str, on_event: Callable[[DemoEvent], None],
                 *, model="gpt-6-luna", stt_model="gpt-transcribe",
                 tts_model="gpt-realtime-2.1-mini", voice="coral", services=None,
                 synthesizer=None,
                 player=play_wav, capture=capture_wav):
        if (not isinstance(api_key, str) or not api_key.strip() or len(api_key) > 4096
                or any(ord(char) < 33 or ord(char) > 126 for char in api_key.strip())):
            raise ValueError("API key required")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt required")
        if not callable(on_event) or not callable(player) or not callable(capture):
            raise ValueError("demo callbacks required")
        if services is None:
            # Do not read the host's private configuration or inherit a retry
            # policy that could unexpectedly repeat a billable request.
            settings = Settings(api_key=api_key.strip(), model=model,
                                stt_model=stt_model, tts_model=tts_model, voice=voice)
            settings.validate()
            settings.require_openai()
            client = _isolated_openai_client(settings)
            services = OpenAIServices(settings, client=client)
            if synthesizer is None:
                # Realtime is a different endpoint: changing a Speech API model
                # string alone cannot produce speech with this replacement.
                synthesizer = RealtimeTTS(client, model=tts_model, voice=voice,
                                          verify_transcript=False)
        self._services = services
        # Injectable doubles implement the same synthesize() contract. There is
        # no retry or fallback to a second paid provider request on failure.
        self._synthesizer = synthesizer if synthesizer is not None else services
        self._dialogue = Dialogue(self._services, prompt)
        self._notify = on_event
        self._player = player
        self._capture = capture
        self._lock = asyncio.Lock()
        self._stop = threading.Event()
        self._active = None
        self._worker = None
        self._closed = False
        self._counter = 0

    def _event(self, kind: str, value: str | float) -> None:
        # A broken UI must not leak provider or secret-bearing exception text.
        try:
            self._notify(DemoEvent(kind, value))
        except Exception:
            pass

    async def _run_worker(self, function, *args, **kwargs):
        task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
        self._worker = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            self._stop.set()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=2)
            except (TimeoutError, Exception):
                pass
            raise
        finally:
            if task.done():
                self._worker = None

    async def _reply(self, text: str) -> None:
        if not isinstance(text, str) or not text.strip() or len(text) > 1200:
            raise ValueError("invalid message")
        text = text.strip()
        self._counter += 1
        self._event("user_text", text)
        self._event("state", "thinking")
        message = Incoming("demo", "Visiteur", text, force_reply=True,
                           message_id=f"demo-{self._counter}")
        reply = await self._dialogue.respond(message)
        if self._stop.is_set():
            return
        if reply is None:
            raise RuntimeError("no reply")
        self._event("reply_text", reply.text)
        self._event("state", "synthesizing")
        spoken = await self._synthesizer.synthesize(reply.text)
        if self._stop.is_set():
            return
        if _words(spoken.transcript) != _words(reply.text):
            self._event("spoken_text", spoken.transcript)
        self._event("state", "speaking")
        # Playback runs outside the loop; a GUI receives approximate mouth levels.
        await self._run_worker(self._player, spoken.audio, self._stop,
                               lambda event: self._event(event.kind, event.value))

    async def _run(self, action) -> bool:
        if self._closed:
            raise RuntimeError("session closed")
        # Do not queue an unexpected second paid request while a turn runs.
        if self._lock.locked() or (self._worker is not None and not self._worker.done()):
            raise RuntimeError("demo busy")
        async with self._lock:
            self._stop.clear()
            self._active = asyncio.current_task()
            try:
                result = await action()
                return result is not False and not self._stop.is_set()
            except asyncio.CancelledError:
                self._stop.set()
                raise
            except Exception:
                # Do not expose HTTP bodies, credentials, or OS/device paths.
                self._event("error", "Opération impossible. Vérifiez la clé, le réseau et les périphériques.")
                return False
            finally:
                self._active = None
                self._event("audio_level", 0.0)
                self._event("state", "idle")

    async def send_text(self, text: str) -> bool:
        return await self._run(lambda: self._reply(text))

    async def record_and_reply(self, seconds: float = 3.0) -> bool:
        if not 0.5 <= seconds <= 15:
            raise ValueError("invalid capture duration")

        async def action():
            self._event("state", "recording")
            audio = await self._run_worker(self._capture, seconds, stop_event=self._stop)
            if audio is None or self._stop.is_set():
                if not self._stop.is_set():
                    self._event("error", "Aucune voix détectée. Réessayez près du microphone.")
                return False
            self._event("state", "transcribing")
            text = await self._services.transcribe_wav(audio)
            if self._stop.is_set() or not text:
                if not self._stop.is_set():
                    self._event("error", "Aucune parole reconnue. Réessayez.")
                return False
            await self._reply(text)

        return await self._run(action)

    def cancel(self) -> None:
        """Request cancellation on the owning event-loop thread."""
        self._stop.set()
        if self._active is not None:
            self._active.cancel()

    async def close(self) -> None:
        self._closed = True
        self.cancel()
        async with self._lock:
            try:
                client = getattr(self._services, "client", None)
                close = getattr(client, "close", None)
                if callable(close):
                    result = close()
                    if hasattr(result, "__await__"):
                        await result
            finally:
                self._dialogue.history.clear()
                self._dialogue.seen.clear()
                self._dialogue.backend = None
                self._synthesizer = None
                self._services = None
