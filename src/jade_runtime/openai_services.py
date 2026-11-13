"""The **only** speech/voice AI provider: OpenAI. Lazy SDK initialization."""
from io import BytesIO

from .config import Settings
from .openai_client import isolated_openai_client
from .realtime_tts import RealtimeTTS, SpokenAudio


class OpenAIServices:
    def __init__(self, settings: Settings, client=None):
        settings.validate()
        self.settings = settings
        if client is None:
            settings.require_openai()
            client = isolated_openai_client(settings)
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
        # gpt-transcribe uses the plural languages field; older models use
        # the singular language field. extra_body also supports older SDKs.
        language = (
            {"extra_body": {"languages": ["fr"]}}
            if self.settings.stt_model == "gpt-transcribe"
            else {"language": "fr"}
        )
        result = await self.client.audio.transcriptions.create(
            model=self.settings.stt_model,
            file=memory,
            **language,
        )
        value = result.text
        if not isinstance(value, str):
            raise ValueError("OpenAI STT returned no text")
        return value.strip()

    async def synthesize_speech(self, text: str) -> SpokenAudio:
        """Return the audio and spoken text without issuing a second request."""
        if not isinstance(text, str) or not 1 <= len(text) <= 4096:
            raise ValueError("invalid OpenAI TTS length")
        if self.settings.tts_model.startswith(("gpt-realtime", "gpt-4o-realtime")):
            return await RealtimeTTS(
                self.client, model=self.settings.tts_model, voice=self.settings.voice,
                timeout_seconds=self.settings.timeout_seconds, verify_transcript=False,
            ).synthesize(text)
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
        # The legacy Speech API does not return a separate spoken transcript.
        return SpokenAudio(data, text)

    def stream_speech_pcm(self, text: str):
        """Return a single-request async PCM iterator for realtime TTS.

        Callers consume and close this stream within the active voice session.
        Legacy Speech API models deliberately retain the buffered WAV path.
        """
        if not isinstance(text, str) or not 1 <= len(text) <= 4096:
            raise ValueError("invalid OpenAI TTS length")
        if not self.settings.tts_model.startswith(("gpt-realtime", "gpt-4o-realtime")):
            return None
        return RealtimeTTS(
            self.client, model=self.settings.tts_model, voice=self.settings.voice,
            timeout_seconds=self.settings.timeout_seconds, verify_transcript=False,
        ).stream_pcm(text)

    async def synthesize_wav(self, text: str) -> bytes:
        """Compatibility for callers that only need the WAV."""
        return (await self.synthesize_speech(text)).audio
