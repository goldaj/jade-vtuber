"""The **only** speech/voice AI provider: OpenAI. Lazy SDK initialization."""
from io import BytesIO

from .config import Settings


class OpenAIServices:
    def __init__(self, settings: Settings, client=None):
        settings.validate()
        self.settings = settings
        if client is None:
            settings.require_openai()
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=settings.api_key,
                timeout=settings.timeout_seconds,
                max_retries=1,
            )
        self.client = client

    async def complete(self, messages: list[dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(
            model=self.settings.model,
            messages=messages,
            max_completion_tokens=160,
        )
        value = response.choices[0].message.content
        if not value:
            raise ValueError("OpenAI returned no dialogue text")
        return value

    async def transcribe_wav(self, audio: bytes) -> str:
        if not isinstance(audio, bytes) or not 44 <= len(audio) <= 20_000_000:
            raise ValueError("recorded WAV missing or exceeds local limit")
        # An in-memory WAV avoids exposing recorded user audio to a public file.
        memory = BytesIO(audio)
        memory.name = "speech.wav"
        result = await self.client.audio.transcriptions.create(
            model=self.settings.stt_model,
            file=memory,
            language="fr",
        )
        value = result.text
        if not isinstance(value, str):
            raise ValueError("OpenAI STT returned no text")
        return value.strip()

    async def synthesize_wav(self, text: str) -> bytes:
        if not isinstance(text, str) or not 1 <= len(text) <= 4096:
            raise ValueError("invalid OpenAI TTS length")
        # WAV output permits decoding/playing with no additional TTS engine.
        response = await self.client.audio.speech.create(
            model=self.settings.tts_model,
            voice=self.settings.voice,
            input=text,
            response_format="wav",
            speed=1.1,
        )
        data = response.content
        if not isinstance(data, bytes) or not data:
            raise ValueError("OpenAI TTS returned no audio")
        return data
