"""OpenAI STT microphone bridge, serialized against Jade speech playback."""
import asyncio

from .messages import Incoming
from .orchestrator import Runtime


class VoiceInput:
    def __init__(self, services, runtime: Runtime, *, capture=None, audio_gate=None):
        from .microphone import MicrophoneCapture
        self.capture = capture or MicrophoneCapture()
        self.audio_gate = audio_gate
        self.services = services
        self.runtime = runtime
        self.segment = 0

    async def once(self, duration=3.0) -> bool:
        if self.audio_gate is None:
            audio, generation = await self.capture(duration), None
        else:
            audio, generation = await self.audio_gate.capture(self.capture, duration)
        if audio is None:
            return False
        if self.audio_gate is not None and not await self.audio_gate.valid(generation):
            return False
        text = await self.services.transcribe_wav(audio)
        if not text:
            return False
        if self.audio_gate is not None and not await self.audio_gate.valid(generation):
            return False
        self.segment += 1
        await self.runtime.submit(Incoming(
            platform="microphone", author="local",
            channel="mic", message_id=f"mic-{self.segment}",
            text=text, force_reply=True))
        # Wait for playback to stop before listening again.
        await self.runtime.idle()
        return True

    async def loop(self, duration=3.0):
        while True:
            try:
                await self.once(duration)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Never log raw microphone audio / transcript / API response body.
                import logging
                logging.getLogger("jade.microphone").warning(
                    "Microphone / OpenAI transcription step failed")
                await asyncio.sleep(2)
