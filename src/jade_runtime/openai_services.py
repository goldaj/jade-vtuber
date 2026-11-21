"""The **only** speech/voice AI provider: OpenAI. Lazy SDK initialization."""
from io import BytesIO
import inspect
import json

from .memory_actions import MEMORY_TOOL
from .session_logging import event

from .config import Settings
from .openai_client import isolated_openai_client
from .realtime_tts import RealtimeTTS, SpokenAudio, RealtimeConnectionPool


class OpenAIServices:
    def __init__(self, settings: Settings, client=None):
        settings.validate()
        self.settings = settings
        if client is None:
            settings.require_openai()
            client = isolated_openai_client(settings)
        self.client = client
        self._stream_pool = RealtimeConnectionPool(client)

    async def close(self):
        try:
            await self._stream_pool.close()
        finally:
            await self.client.close()

    async def complete(self, messages: list[dict[str, str]]) -> str:
        event("openai_request", operation="chat.complete", model=self.settings.model,
              tools_enabled=False, streaming=False)
        response = await self.client.chat.completions.create(
            model=self.settings.model,
            messages=messages,
            max_completion_tokens=self.settings.max_completion_tokens,
            reasoning_effort=self.settings.reasoning_effort,
        )
        value = response.choices[0].message.content
        event("openai_response", operation="chat.complete",
              finish_reason=response.choices[0].finish_reason, raw_output=value,
              request_id=getattr(response, "id", None))
        if not value:
            raise ValueError("OpenAI returned no dialogue text")
        return value

    async def complete_stream(self, messages: list[dict[str, str]]):
        """Yield OpenAI chat token fragments; do not retry on partial output."""
        event("openai_request", operation="chat.stream", model=self.settings.model,
              tools_enabled=False, streaming=True)
        stream = await self.client.chat.completions.create(
            model=self.settings.model, messages=messages,
            max_completion_tokens=self.settings.max_completion_tokens,
            reasoning_effort=self.settings.reasoning_effort, stream=True,
        )
        completed = False
        try:
            async for chunk in stream:
                for choice in getattr(chunk, "choices", ()):
                    if getattr(choice, "index", 0) != 0:
                        continue
                    reason = getattr(choice, "finish_reason", None)
                    if reason not in (None, "stop"):
                        raise ValueError("OpenAI dialogue stream ended incompletely")
                    delta = getattr(getattr(choice, "delta", None), "content", None)
                    if isinstance(delta, str) and delta:
                        if completed:
                            raise ValueError("OpenAI dialogue text after completion")
                        yield delta
                    if reason == "stop":
                        completed = True
            if not completed:
                # An EOF without finish_reason=stop can follow a broken
                # connection after some text was already sent to the speaker.
                raise ValueError("OpenAI dialogue stream ended without completion")
        finally:
            event("openai_stream_ended", operation="chat.stream", completed=completed)
            close = getattr(stream, "close", None)
            if callable(close):
                closing = close()
                if inspect.isawaitable(closing):
                    await closing

    def _chat_arguments(self, messages):
        return {
            "model": self.settings.model,
            "messages": messages,
            "max_completion_tokens": self.settings.max_completion_tokens,
            "reasoning_effort": self.settings.reasoning_effort,
        }

    @staticmethod
    async def _finish_memory_tool(messages, calls, action):
        """Append the model's tool call and an actual backend result.

        The server processes at most one write; parallel/unknown calls are
        refused without executing arbitrary operations.
        """
        if not calls or len(calls) > 4:
            raise ValueError("invalid memory tool calls")
        if any(not call["id"] or not call["name"] for call in calls):
            raise ValueError("missing function call identifier")
        continuation = list(messages)
        continuation.append({
            "role": "assistant", "content": None, "tool_calls": [
                {"id": call["id"], "type": "function", "function": {
                    "name": call["name"], "arguments": call["arguments"]}}
                for call in calls
            ],
        })
        for index, call in enumerate(calls):
            if (index == 0 and call["name"] == "jade_save_memory"
                    and len(call["arguments"]) <= 2400):
                try:
                    outcome = await action(call["arguments"])
                except Exception:
                    outcome = {"status": "échec", "level": None}
            else:
                outcome = {"status": "refusé", "level": None}
            event("memory_tool_result", name=call["name"],
                  call_index=index, outcome=outcome)
            continuation.append({
                "role": "tool", "tool_call_id": call["id"],
                "content": json.dumps(outcome, ensure_ascii=False),
            })
        return continuation

    async def complete_with_tools(self, messages, memory_action) -> str:
        """One call if unused, an additional completion only after tool use."""
        event("openai_request", operation="chat.complete_with_tools",
              model=self.settings.model, tools_enabled=True, streaming=False)
        response = await self.client.chat.completions.create(
            **self._chat_arguments(messages), tools=[MEMORY_TOOL],
            tool_choice="auto", parallel_tool_calls=False)
        choice = response.choices[0]
        event("openai_response", operation="chat.complete_with_tools",
              finish_reason=choice.finish_reason,
              raw_output=choice.message.content,
              tool_calls=[{"name": item.function.name, "arguments": item.function.arguments}
                          for item in (choice.message.tool_calls or ())],
              request_id=getattr(response, "id", None))
        if choice.finish_reason == "stop":
            value = choice.message.content
            if not isinstance(value, str) or not value:
                raise ValueError("OpenAI returned no dialogue text")
            return value
        if choice.finish_reason != "tool_calls":
            raise ValueError("OpenAI dialogue ended without completion")
        calls = [{
            "id": item.id, "name": item.function.name,
            "arguments": item.function.arguments,
        } for item in (choice.message.tool_calls or ())]
        followup = await self._finish_memory_tool(messages, calls, memory_action)
        return await self.complete(followup)

    async def complete_stream_with_tools(self, messages, memory_action):
        """Support streamed function arguments without speaking any tool payload."""
        event("openai_request", operation="chat.stream_with_tools",
              model=self.settings.model, tools_enabled=True, streaming=True)
        stream = await self.client.chat.completions.create(
            **self._chat_arguments(messages), tools=[MEMORY_TOOL],
            tool_choice="auto", parallel_tool_calls=False, stream=True)
        calls = {}
        finish = None
        try:
            async for chunk in stream:
                for choice in getattr(chunk, "choices", ()):
                    if getattr(choice, "index", 0) != 0:
                        continue
                    reason = getattr(choice, "finish_reason", None)
                    if reason not in (None, "stop", "tool_calls"):
                        raise ValueError("OpenAI dialogue stream ended incompletely")
                    if reason:
                        finish = reason
                    delta = getattr(choice, "delta", None)
                    for tool in (getattr(delta, "tool_calls", None) or ()):
                        index = tool.index
                        if type(index) is not int or index not in range(4):
                            raise ValueError("invalid tool call index")
                        call = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                        call["id"] += getattr(tool, "id", None) or ""
                        function = getattr(tool, "function", None)
                        if function is not None:
                            call["name"] += getattr(function, "name", None) or ""
                            call["arguments"] += getattr(function, "arguments", None) or ""
                        if len(call["arguments"]) > 2400:
                            raise ValueError("tool arguments exceed local limit")
                    fragment = getattr(delta, "content", None)
                    if isinstance(fragment, str) and fragment and not calls:
                        yield fragment
            event("openai_stream_ended", operation="chat.stream_with_tools",
                  finish_reason=finish, tool_calls=[calls[key] for key in sorted(calls)])
            if finish == "tool_calls":
                ordered = [calls[index] for index in sorted(calls)]
                followup = await self._finish_memory_tool(
                    messages, ordered, memory_action)
                async for fragment in self.complete_stream(followup):
                    yield fragment
            elif finish != "stop":
                raise ValueError("OpenAI dialogue stream ended without completion")
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                closing = close()
                if inspect.isawaitable(closing):
                    await closing

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

    async def synthesize_speech(self, text: str, *, intent="neutral") -> SpokenAudio:
        """Return the audio and spoken text without issuing a second request."""
        if not isinstance(text, str) or not 1 <= len(text) <= 4096:
            raise ValueError("invalid OpenAI TTS length")
        if self.settings.tts_model.startswith(("gpt-realtime", "gpt-4o-realtime")):
            # Preserve legacy mock/caller behavior when intent is neutral.
            intent_options = {"intent": intent} if intent != "neutral" else {}
            return await RealtimeTTS(
                self.client, model=self.settings.tts_model, voice=self.settings.voice,
                speed=self.settings.tts_speed,
                timeout_seconds=self.settings.timeout_seconds, verify_transcript=False,
                connection_pool=self._stream_pool, **intent_options,
            ).synthesize(text)
        # WAV output permits decoding/playing with no additional TTS engine.
        response = await self.client.audio.speech.create(
            model=self.settings.tts_model,
            voice=self.settings.voice,
            input=text,
            response_format="wav",
            speed=self.settings.tts_speed,
        )
        data = response.content
        if not isinstance(data, bytes) or not data:
            raise ValueError("OpenAI TTS returned no audio")
        # The legacy Speech API does not return a separate spoken transcript.
        return SpokenAudio(data, text)

    def stream_speech_pcm(self, text: str, *, intent="neutral"):
        """Return a single-request async PCM iterator for realtime TTS.

        Callers consume and close this stream within the active voice session.
        Legacy Speech API models deliberately retain the buffered WAV path.
        """
        if not isinstance(text, str) or not 1 <= len(text) <= 4096:
            raise ValueError("invalid OpenAI TTS length")
        if not self.settings.tts_model.startswith(("gpt-realtime", "gpt-4o-realtime")):
            return None
        intent_options = {"intent": intent} if intent != "neutral" else {}
        return RealtimeTTS(
            self.client, model=self.settings.tts_model, voice=self.settings.voice,
            speed=self.settings.tts_speed,
            timeout_seconds=self.settings.timeout_seconds, verify_transcript=False,
            connection_pool=self._stream_pool, **intent_options,
        ).stream_pcm(text)

    async def synthesize_wav(self, text: str) -> bytes:
        """Compatibility for callers that only need the WAV."""
        return (await self.synthesize_speech(text)).audio
