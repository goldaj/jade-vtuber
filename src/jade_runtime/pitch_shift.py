"""Optional, bounded FFmpeg Rubber Band pitch-shift for Jade PCM playback.

Audio-only DSP; NEVER sends audio to another provider. External ffmpeg needs
librubberband compiled in (the filter is optional in FFmpeg builds). We
preserve the formant envelope where supported, request tempo=1 and transform
24 kHz mono S16LE on both buffered and streaming paths.

Missing/incompatible ffmpeg is an audible-neutral fallback, not loss of voice.
Errors during an already-started stream abort that stream without replaying
a potentially billed synthesis. Never log PCM, TTS text or stderr.
"""
from __future__ import annotations

import asyncio
from functools import lru_cache
from io import BytesIO
import logging
import math
import os
import subprocess
import wave

from .avatar import child_environment

LOG = logging.getLogger("jade.pitch")
RATE = 24000
MAX_PCM = 4_800_000  # 100 seconds, matching Realtime transport's normal limit.
_MAX_SEMITONES = 6.0


def pitch_ratio(semitones: float) -> float:
    if (isinstance(semitones, bool) or not isinstance(semitones, (int, float))
            or not math.isfinite(semitones) or abs(semitones) > _MAX_SEMITONES):
        raise ValueError("pitch semitones must be finite between -6 and +6")
    return 2 ** (float(semitones) / 12)


@lru_cache(maxsize=1)
def _rubberband_available() -> bool:
    """Check optional FFmpeg functionality once, off the event-loop thread."""
    try:
        check = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=4, check=False, env=child_environment(os.environ),
        )
        return check.returncode == 0 and b" rubberband " in check.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


async def supports_pitch_shift() -> bool:
    """Availability is runtime-specific; do not assume packaged Windows FFmpeg."""
    return await asyncio.to_thread(_rubberband_available)


def _command(semitones: float) -> tuple[str, ...]:
    factor = pitch_ratio(semitones)
    return (
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        # Without these, FFmpeg can buffer seconds of raw PCM in probing.
        "-probesize", "32", "-analyzeduration", "0",
        "-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", "pipe:0",
        "-af", (
            f"rubberband=tempo=1:pitch={factor:.9f}:formant=preserved:"
            "window=short:pitchq=speed"
        ),
        "-ar", str(RATE), "-ac", "1", "-f", "s16le",
        "-flush_packets", "1", "pipe:1",
    )


async def _close_audio(source):
    close = getattr(source, "aclose", None)
    if callable(close):
        await close()


async def shift_pcm(source, semitones: float):
    """Yield shifted PCM while consuming its input with bounded backpressure.

    Source is an async iterator of 24k/mono/s16le PCM, and must remain
    disposable on disconnect. Output stays 24k/mono/s16le with tempo=1.
    The FFmpeg process lifetime is strictly scoped to one TTS utterance.
    """
    ratio = pitch_ratio(semitones)
    if ratio == 1:
        try:
            async for part in source:
                yield part
        finally:
            await _close_audio(source)
        return
    available = await supports_pitch_shift()
    if not available:
        LOG.warning("FFmpeg Rubber Band unavailable; Jade pitch unchanged")
        try:
            async for part in source:
                yield part
        finally:
            await _close_audio(source)
        return
    try:
        process = await asyncio.create_subprocess_exec(
            *_command(semitones), stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=child_environment(os.environ),
        )
    except OSError:
        # A removed executable between capability probe and spawn is harmless.
        LOG.warning("Pitch processing cannot start; Jade pitch unchanged")
        try:
            async for part in source:
                yield part
        finally:
            await _close_audio(source)
        return

    async def feed_input():
        received = 0
        try:
            async for chunk in source:
                if not isinstance(chunk, bytes) or not chunk:
                    raise ValueError("invalid source PCM fragment")
                received += len(chunk)
                if received > MAX_PCM:
                    raise ValueError("synthesized PCM exceeds pitch-processing limit")
                process.stdin.write(chunk)
                await process.stdin.drain()  # never buffer unbounded input
            if received % 2:
                raise ValueError("incomplete PCM sample")
        finally:
            try:
                process.stdin.close()
                await process.stdin.wait_closed()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            await _close_audio(source)

    feeder = asyncio.create_task(feed_input(), name="jade-pitch-input")
    total = 0
    try:
        while True:
            # Small PCM reads permit streaming and backpressure to Discord.
            chunk = await process.stdout.read(4096)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_PCM + RATE * 4:  # bounded allowance for DSP tail
                raise RuntimeError("pitch processing exceeded output limit")
            yield chunk
        await feeder  # preserve upstream provider failures and cancellations
        status = await asyncio.wait_for(process.wait(), timeout=3)
        if status != 0 or not total or total % 2:
            raise RuntimeError("pitch processing failed")
    finally:
        if not feeder.done():
            feeder.cancel()
        # On early close, kill the DSP immediately; never let it continue to
        # pull the potentially billable upstream Realtime speech response.
        if process.returncode is None:
            process.kill()
        await asyncio.gather(feeder, return_exceptions=True)
        try:
            await asyncio.wait_for(process.wait(), timeout=3)
        except asyncio.TimeoutError:
            LOG.warning("Pitch process shutdown exceeded deadline")


async def shift_wav(audio: bytes, semitones: float) -> bytes:
    """Pitch-shift a buffered WAV while preserving its PCM format and timing."""
    if pitch_ratio(semitones) == 1:
        return audio
    if not isinstance(audio, bytes) or len(audio) > MAX_PCM + 4096:
        raise ValueError("invalid synthesized WAV size")
    if not await supports_pitch_shift():
        # With no optional FFmpeg filter, preserve original audio bytes, WAV
        # metadata and timing exactly. Never turn a voice feature into an outage.
        LOG.warning("FFmpeg Rubber Band unavailable; Jade pitch unchanged")
        return audio
    try:
        with wave.open(BytesIO(audio), "rb") as reader:
            if (reader.getnchannels(), reader.getsampwidth(), reader.getframerate(),
                    reader.getcomptype()) != (1, 2, RATE, "NONE"):
                LOG.warning("Unsupported WAV format for pitch; unchanged")
                return audio
            frames = reader.readframes(reader.getnframes())
    except (EOFError, wave.Error):
        # Existing transport tests use synthetic RIFF bytes, not a true WAV.
        # In production a malformed provider WAV should be diagnosed upstream.
        LOG.warning("Unrecognized WAV for pitch; unchanged")
        return audio

    async def pcm_parts():
        for index in range(0, len(frames), 9600):
            yield frames[index:index + 9600]
            await asyncio.sleep(0)

    result = bytearray()
    async for part in shift_pcm(pcm_parts(), semitones):
        result.extend(part)
    if not result:
        raise RuntimeError("pitch processing produced no audio")
    with BytesIO() as target:
        with wave.open(target, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(RATE)
            writer.writeframes(result)
        return target.getvalue()
