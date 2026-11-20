"""Produce bounded audio events for the private mobile streaming response."""

import base64

from .pitch_shift import shift_pcm, shift_wav

PCM_RATE = 24_000
MAX_AUDIO_BYTES = 7_000_000
PCM_EVENT_BYTES = 8_192


async def speech_events(services, text, intent):
    """Stream one synthesis as PCM, or one WAV for non-Realtime models.

    Selection is made before synthesis. Once a PCM request has started, an
    error is propagated rather than requesting (and billing) a second voice.
    Consumers must close this generator when their HTTP client disconnects.
    """
    settings = getattr(services, "settings", None)
    pitch = getattr(settings, "tts_pitch_semitones", 0)
    factory = getattr(services, "stream_speech_pcm", None)
    source = factory(text, intent=intent) if callable(factory) else None
    if source is None:
        speech = await services.synthesize_speech(text, intent=intent)
        audio = speech.audio
        if not isinstance(audio, bytes) or not 44 <= len(audio) <= MAX_AUDIO_BYTES:
            raise ValueError("invalid synthesized WAV")
        if pitch:
            audio = await shift_wav(audio, pitch)
        if not isinstance(audio, bytes) or not 44 <= len(audio) <= MAX_AUDIO_BYTES:
            raise ValueError("invalid synthesized WAV")
        yield {"type": "wav", "audio_wav_b64": base64.b64encode(audio).decode("ascii")}
        return

    stream = shift_pcm(source, pitch)
    total = 0
    pending = b""
    try:
        async for chunk in stream:
            if not isinstance(chunk, bytes) or not chunk:
                raise ValueError("invalid PCM fragment")
            total += len(chunk)
            if total > MAX_AUDIO_BYTES:
                raise ValueError("PCM response exceeds limit")
            chunk = pending + chunk
            pending = chunk[-1:] if len(chunk) % 2 else b""
            chunk = chunk[:len(chunk) - len(pending)]
            for offset in range(0, len(chunk), PCM_EVENT_BYTES):
                data = chunk[offset:offset + PCM_EVENT_BYTES]
                yield {"type": "pcm", "sample_rate": PCM_RATE,
                       "pcm_b64": base64.b64encode(data).decode("ascii")}
        if pending or not total:
            raise ValueError("incomplete or empty PCM response")
    finally:
        await stream.aclose()
