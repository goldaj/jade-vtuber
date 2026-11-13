"""Optional one-turn LLM-to-TTS sentence pipeline for Discord voice.

The full reply is returned once by Dialogue/Runtime; a bounded sentence queue
lets earlier phrases speak while the LLM finishes later text. This mode uses
one TTS call per segment, never duplicates the whole answer, and leaves the
legacy full-text WAV route untouched unless explicitly enabled.
"""
from __future__ import annotations

import asyncio
import logging


class EarlySpeechTurn:
    def __init__(self, output, source, *, max_seconds=180):
        if not 1 <= max_seconds <= 180:
            raise ValueError("invalid early speech deadline")
        self.max_seconds = max_seconds
        self.output = output
        self.source = source
        self._phrases = asyncio.Queue(maxsize=2)
        self._ended = False
        self.has_submitted = False
        self.on_first_sentence = None
        self._first_callback_task = None
        self._task = asyncio.create_task(
            self._run_bounded(), name="jade-early-speech")

    async def _run_bounded(self):
        # Total turn limit: LLM may emit phrases faster than Discord can play.
        # Without a deadline, an interrupted or slow stream blocks the runtime
        # worker indefinitely, even though text delivery has already finished.
        try:
            async with asyncio.timeout(self.max_seconds):
                return await self._run()
        finally:
            callback = self._first_callback_task
            if callback is not None:
                if not callback.done():
                    callback.cancel()
                await asyncio.gather(callback, return_exceptions=True)

    async def _offer(self, text):
        while self._phrases.full():
            if self._task.done():
                await self._task
                raise RuntimeError("early speech stopped before input finished")
            await asyncio.sleep(0.01)
        if self._task.done():
            await self._task
            raise RuntimeError("early speech stopped before input finished")
        self._phrases.put_nowait(text)

    async def emit(self, sentence: str):
        if self._ended:
            raise RuntimeError("early speech input is closed")
        if not isinstance(sentence, str) or not sentence.strip():
            raise ValueError("invalid speech segment")
        await self._offer(sentence.strip())
        self.has_submitted = True

    async def finish_input(self):
        if not self._ended:
            self._ended = True
            await self._offer(None)

    async def wait(self):
        return await self._task

    async def abort(self):
        self._ended = True
        if not self._task.done():
            self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)

    async def _run(self):
        output = self.output
        source = self.source
        first = await self._phrases.get()
        if first is None:
            return False
        bridge = output.secondary_player

        def require_session():
            if not callable(getattr(bridge, "reply_authorized", None)) or not bridge.reply_authorized(source):
                raise PermissionError("early speech voice session expired")

        async with output.lock:
            require_session()
            gated = False
            written = False
            path = output.subtitle_path

            async def audio():
                sentence = first
                first_sentence = True
                while sentence is not None:
                    require_session()
                    if first_sentence:
                        first_sentence = False
                        callback = self.on_first_sentence
                        if callable(callback):
                            async def invoke():
                                try:
                                    await callback()
                                except asyncio.CancelledError:
                                    raise
                                except Exception:
                                    logging.getLogger("jade.output").warning(
                                        "Early speech first-sentence callback failed")
                            self._first_callback_task = asyncio.create_task(invoke())
                            await asyncio.sleep(0)  # Start, but do not wait for the hotkey.
                    # OBS may read this file from another process at any time.
                    # Publish complete subtitle replacements, never partial writes.
                    subtitle_tmp = path.with_name(path.name + ".tmp")
                    subtitle_tmp.write_text(sentence, encoding="utf-8")
                    subtitle_tmp.replace(path)
                    stream = output.services.stream_speech_pcm(sentence)
                    if stream is None:
                        raise RuntimeError("early speech requires Realtime TTS")
                    try:
                        async for chunk in stream:
                            require_session()
                            yield chunk
                    finally:
                        close = getattr(stream, "aclose", None)
                        if callable(close):
                            await close()
                    sentence = await self._phrases.get()

            try:
                if output.audio_gate is not None:
                    await output.audio_gate.begin_speech()
                    gated = True
                require_session()
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(path.name + ".tmp")
                tmp.write_text(first, encoding="utf-8")
                tmp.replace(path)
                written = True
                played = await bridge.play_pcm_stream_for_reply(audio(), source)
            finally:
                try:
                    if gated:
                        await output.audio_gate.end_speech()
                finally:
                    if written:
                        path.write_text("", encoding="utf-8")
            if played is True:
                require_session()
                mark = getattr(bridge, "mark_voice_reply_played", None)
                if callable(mark):
                    mark(source)
            return played is True
