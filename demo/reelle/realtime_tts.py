"""Experimental OpenAI Realtime text-to-speech transport for the demo.

This does not replace the active runtime configuration. Each synthesis uses an
isolated, short-lived session, requests PCM 24 kHz, waits for a successful final
response, and returns an in-memory WAV. No audio, text, key or provider error is
logged. Real speech fidelity, latency, account access and cost are unverified.

OpenAI references:
https://developers.openai.com/api/docs/guides/text-to-speech
https://developers.openai.com/api/docs/guides/realtime-conversations
https://developers.openai.com/api/reference/resources/realtime/server-events
"""
from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
from io import BytesIO
import math
import re
import unicodedata
import wave


class RealtimeTTSError(RuntimeError):
    """Sanitized error; never includes transmitted text or provider details."""


@dataclass(frozen=True, repr=False)
class SpokenAudio:
    """WAV and provider transcript, both kept in memory by the caller."""

    audio: bytes
    transcript: str


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _words(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def _wav(pcm: bytes) -> bytes:
    if not pcm or len(pcm) % 2:
        raise RealtimeTTSError("Invalid synthesized audio")
    out = BytesIO()
    with wave.open(out, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes(pcm)
    return out.getvalue()


class RealtimeTTS:
    """Synthesize one response at a time on a caller-owned AsyncOpenAI client.

    `client.realtime.connect()` is injectable to permit tests without a network.
    The default transcript check fails closed on wording changes; formatting,
    spoken numbers, abbreviations and other legitimate variations may therefore
    be rejected. Disabling it removes that safeguard, not the completion checks.
    """

    def __init__(self, client, *, model="gpt-realtime-2.1-mini", voice="coral",
                 timeout_seconds=60.0, max_audio_bytes=4_800_000,
                 verify_transcript=True):
        if (not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model)
                or not isinstance(voice, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", voice)
                or isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (float, int))
                or not math.isfinite(timeout_seconds) or not 1 <= timeout_seconds <= 180
                or type(max_audio_bytes) is not int or not 2 <= max_audio_bytes <= 10_000_000
                or type(verify_transcript) is not bool):
            raise ValueError("invalid realtime synthesis settings")
        self.client = client
        self.model = model
        self.voice = voice
        self.timeout_seconds = float(timeout_seconds)
        self.max_audio_bytes = max_audio_bytes
        self.verify_transcript = verify_transcript

    async def synthesize_wav(self, text: str) -> bytes:
        """Compatibility wrapper when the provider transcript is not needed."""
        return (await self.synthesize(text)).audio

    async def synthesize(self, text: str) -> SpokenAudio:
        if not isinstance(text, str) or not text.strip() or len(text) > 4096:
            raise ValueError("invalid speech text")
        if self.verify_transcript and not _words(text):
            raise ValueError("speech text contains no comparable words")
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with self.client.realtime.connect(
                    model=self.model, max_retries=0, max_queue_size=64,
                    websocket_connection_options={"max_size": 1_048_576},
                ) as connection:
                    return await self._request(connection, text)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            raise RealtimeTTSError("Realtime synthesis timed out") from None
        except RealtimeTTSError:
            raise
        except Exception:
            raise RealtimeTTSError("Realtime synthesis failed") from None

    async def _request(self, connection, text: str) -> SpokenAudio:
        response_requested = False
        response_finished = False
        response_id = None
        pcm = bytearray()
        transcript = None
        content_identity = None
        event_count = 0
        try:
            await connection.session.update(session={
                "type": "realtime",
                "output_modalities": ["audio"],
                "instructions": (
                    "Read the user's text aloud exactly as provided. "
                    "Do not add, omit, answer, translate, or explain anything."
                ),
                "audio": {"input": {"turn_detection": None},
                          "output": {"format": {"type": "audio/pcm", "rate": 24000},
                                     "voice": self.voice}},
            })
            while True:
                event_count += 1
                if event_count > 10_000:
                    raise RealtimeTTSError("Too many realtime events")
                event = await connection.recv()
                kind = _field(event, "type")
                if kind == "error":
                    raise RealtimeTTSError("Realtime session rejected")
                if kind == "session.updated":
                    session = _field(event, "session")
                    audio = _field(session, "audio")
                    output = _field(audio, "output")
                    fmt = _field(output, "format")
                    if (_field(session, "type") != "realtime"
                            or _field(session, "output_modalities") != ["audio"]
                            or _field(fmt, "type") != "audio/pcm"
                            or _field(fmt, "rate") != 24000
                            or _field(output, "voice") != self.voice):
                        raise RealtimeTTSError("Realtime audio settings not confirmed")
                    break

            # A fresh connection and out-of-band response avoid carrying history.
            # Retry/reconnect are disabled so a failure cannot repeat a paid turn.
            await connection.response.create(response={
                "conversation": "none", "output_modalities": ["audio"],
                "max_output_tokens": 4096,
                "metadata": {"purpose": "jade_tts"},
                "input": [{"type": "message", "role": "user",
                           "content": [{"type": "input_text", "text": text}]}],
            })
            response_requested = True
            while True:
                event_count += 1
                if event_count > 10_000:
                    raise RealtimeTTSError("Too many realtime events")
                event = await connection.recv()
                kind = _field(event, "type")
                if kind == "error":
                    raise RealtimeTTSError("Realtime response rejected")
                if kind == "response.created":
                    response = _field(event, "response")
                    metadata = _field(response, "metadata")
                    candidate = _field(response, "id")
                    if (_field(metadata, "purpose") != "jade_tts"
                            or not isinstance(candidate, str) or not candidate
                            or response_id is not None):
                        raise RealtimeTTSError("Unexpected realtime response")
                    response_id = candidate
                elif kind == "response.output_audio.delta":
                    if not response_id or _field(event, "response_id") != response_id:
                        raise RealtimeTTSError("Unexpected audio response")
                    identity = (_field(event, "item_id"), _field(event, "output_index"),
                                _field(event, "content_index"))
                    if (not isinstance(identity[0], str) or not identity[0]
                            or type(identity[1]) is not int or type(identity[2]) is not int
                            or (content_identity is not None and identity != content_identity)):
                        raise RealtimeTTSError("Unexpected audio content")
                    content_identity = identity
                    delta = _field(event, "delta")
                    if (not isinstance(delta, str)
                            or len(delta) > ((self.max_audio_bytes - len(pcm) + 2) // 3) * 4):
                        raise RealtimeTTSError("Synthesized audio exceeds local limit")
                    try:
                        chunk = base64.b64decode(delta, validate=True)
                    except (ValueError, binascii.Error):
                        raise RealtimeTTSError("Invalid synthesized audio") from None
                    if len(pcm) + len(chunk) > self.max_audio_bytes:
                        raise RealtimeTTSError("Synthesized audio exceeds local limit")
                    pcm.extend(chunk)
                elif kind == "response.output_audio_transcript.done":
                    if not response_id or _field(event, "response_id") != response_id:
                        raise RealtimeTTSError("Unexpected audio transcript")
                    identity = (_field(event, "item_id"), _field(event, "output_index"),
                                _field(event, "content_index"))
                    value = _field(event, "transcript")
                    if (not isinstance(identity[0], str) or not identity[0]
                            or type(identity[1]) is not int or type(identity[2]) is not int
                            or (content_identity is not None and identity != content_identity)
                            or transcript is not None
                            or not isinstance(value, str) or len(value) > 10_000):
                        raise RealtimeTTSError("Invalid audio transcript")
                    content_identity = identity
                    transcript = value
                elif kind == "response.done":
                    response = _field(event, "response")
                    if not response_id or _field(response, "id") != response_id:
                        raise RealtimeTTSError("Unexpected realtime completion")
                    response_finished = True
                    if _field(response, "status") != "completed":
                        raise RealtimeTTSError("Realtime response did not complete")
                    if transcript is None or not transcript.strip():
                        raise RealtimeTTSError("Synthesized audio transcript missing")
                    if self.verify_transcript and _words(transcript) != _words(text):
                        raise RealtimeTTSError("Synthesized wording differs from the text")
                    return SpokenAudio(_wav(bytes(pcm)), transcript)
        finally:
            if response_requested and not response_finished:
                try:
                    cancel = connection.response.cancel
                    if response_id:
                        await asyncio.wait_for(cancel(response_id=response_id), timeout=1.0)
                    else:
                        await asyncio.wait_for(cancel(), timeout=1.0)
                except (Exception, asyncio.CancelledError):
                    # Closing the isolated connection is the final fallback.
                    pass
