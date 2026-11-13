"""Bounded per-channel conversation. No paid calls in unit tests."""
import asyncio
from contextlib import aclosing
from collections import deque
import random
import re
import time
from typing import Protocol

from .messages import Incoming, Reply


class ChatBackend(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> str: ...


class _SpeechChunks:
    """Make speakable fragments without producing a TTS request for every token."""

    _end = re.compile(r"[.!?…]+[»\"')\]]*(?=\s)")
    _abbreviations = frozenset({"m", "mme", "mlle", "dr", "pr", "etc", "cf", "env", "ex"})

    def __init__(self):
        self.pending = ""

    def feed(self, delta: str) -> list[str]:
        self.pending += delta
        chunks = []
        while self.pending:
            boundary = None
            for match in self._end.finditer(self.pending):
                prefix = self.pending[:match.end()]
                # Do not split on common French abbreviations or initials.
                if match.group().startswith("."):
                    word = re.search(r"([A-Za-zÀ-ÿ]+)\.$", prefix)
                    if word and (word.group(1).casefold() in self._abbreviations
                                 or len(word.group(1)) == 1):
                        continue
                if len(prefix.strip()) >= 24:
                    boundary = match.end()
                    break
            # Long unpunctuated replies should still start; never cut a word.
            if boundary is None and len(self.pending) >= 220:
                boundary = self.pending.rfind(" ", 24, 221)
                if boundary < 24:
                    boundary = None
            if boundary is None:
                break
            part = self.pending[:boundary].strip()
            self.pending = self.pending[boundary:].lstrip()
            if part:
                chunks.append(part)
        return chunks

    def finish(self) -> str:
        part, self.pending = self.pending.strip(), ""
        return part


class Dialogue:
    def __init__(self, backend: ChatBackend, prompt: str, *, bot_name="Jade",
                 max_messages=24, random_reply_rate=0, rng=None,
                 max_sessions=256, session_ttl=1800):
        if not prompt.strip() or not 2 <= max_messages <= 100:
            raise ValueError("invalid prompt/history limit")
        if not 0 <= random_reply_rate <= 1:
            raise ValueError("invalid random rate")
        if max_sessions < 1 or session_ttl <= 0:
            raise ValueError("invalid session limits")
        self.backend = backend
        self.prompt = prompt
        self.bot_name = bot_name
        self.max_messages = max_messages
        self.random_reply_rate = random_reply_rate
        self.rng = rng or random.Random()
        self.history: dict[tuple[str, str], deque] = {}
        self.seen: dict[tuple[str, str], deque[str]] = {}
        self.locks: dict[tuple[str, str], asyncio.Lock] = {}
        self.max_sessions = max_sessions
        self.session_ttl = session_ttl
        self._last_used = {}
        self._users = {}

    def _remove(self, key):
        for mapping in (self.history, self.seen, self.locks, self._last_used, self._users):
            mapping.pop(key, None)

    def _acquire_session(self, key):
        now = time.monotonic()
        for old, last in list(self._last_used.items()):
            if not self._users.get(old) and now - last >= self.session_ttl:
                self._remove(old)
        if key not in self.locks:
            if len(self.locks) >= self.max_sessions:
                candidates = [k for k in self.locks if not self._users.get(k)]
                if not candidates:
                    raise RuntimeError("session limit reached")
                self._remove(min(candidates, key=lambda k: self._last_used[k]))
            self.locks[key] = asyncio.Lock()
        self._users[key] = self._users.get(key, 0) + 1
        self._last_used[key] = now
        return self.locks[key]

    def should_reply(self, message: Incoming) -> bool:
        words = message.text.casefold()
        if message.force_reply or words.startswith(("!response", "!rsp")):
            return True
        if self.bot_name and self.bot_name.casefold() in words:
            return True
        return self.rng.random() < self.random_reply_rate

    async def respond(self, incoming: Incoming, *, valid=lambda: True,
                      on_sentence=None, on_timing=None) -> Reply | None:
        # Reject stale duplicates by transport ID, not by repeated message text.
        if len(incoming.text) > 1200 or not self.should_reply(incoming):
            return None
        key = incoming.session
        lock = self._acquire_session(key)
        try:
            async with lock:
                if not valid():
                    raise TimeoutError("message expired")
                used = self.seen.setdefault(key, deque(maxlen=512))
                if incoming.message_id and incoming.message_id in used:
                    return None
                history = self.history.setdefault(
                    key, deque(maxlen=self.max_messages))
                user = {"role": "user", "content": (
                    f"{incoming.author} ({incoming.platform}): {incoming.text}")}
                messages = [{"role": "system", "content": self.prompt}, *history, user]
                # Only explicitly opted-in voice callers stream; other backends
                # and clients keep their original complete-response contract.
                stream_complete = getattr(type(self.backend), "stream_complete", None)
                if on_timing is not None:
                    on_timing("llm_start")
                if on_sentence is not None and callable(stream_complete):
                    return await self._stream_response(
                        incoming, messages, user, history, used, stream_complete,
                        on_sentence, valid, on_timing)
                # Failed LLM calls must not corrupt memory or mark a message handled.
                answer = await self.backend.complete(messages)
                if on_timing is not None:
                    on_timing("llm_end")
                if not valid():
                    raise TimeoutError("message expired")
                if not isinstance(answer, str) or not answer.strip():
                    raise ValueError("chat backend returned an empty response")
                result = Reply(incoming, answer.strip())
                history.extend((user, {"role": "assistant", "content": result.text}))
                if incoming.message_id:
                    used.append(incoming.message_id)
                return result
        finally:
            self._users[key] -= 1
            self._last_used[key] = time.monotonic()

    async def _stream_response(self, incoming, messages, user, history, used,
                               stream_complete, on_sentence, valid, on_timing):
        """Overlap LLM generation with bounded, sequential sentence playback.

        The callback confirms complete playback with True. In-flight audio can
        be interrupted, so history keeps only confirmed sentences plus a marker.
        """
        queue = asyncio.Queue(maxsize=2)
        chunker = _SpeechChunks()
        deltas = []
        played = []
        attempted = False
        delivery_failed = False

        async def consume():
            nonlocal attempted, delivery_failed
            while True:
                sentence = await queue.get()
                if sentence is None:
                    return
                if delivery_failed:
                    continue
                if not valid():
                    delivery_failed = True
                    continue
                attempted = True
                try:
                    delivered = await on_sentence(Reply(incoming, sentence))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # Retain the final text but never replay partially heard audio.
                    delivery_failed = True
                    continue
                if delivered is True:
                    played.append(sentence)
                else:
                    delivery_failed = True

        def commit_partial():
            if attempted:
                heard = " ".join(played)
                content = (heard + " " if heard else "") + "[réponse vocale interrompue]"
                history.extend((user, {"role": "assistant", "content": content}))
                if incoming.message_id:
                    used.append(incoming.message_id)

        playback = asyncio.create_task(consume(), name="jade-sentence-playback")
        try:
            first_delta = True
            async with aclosing(stream_complete(self.backend, messages)) as stream:
                async for delta in stream:
                    if not valid():
                        raise TimeoutError("message expired")
                    if not isinstance(delta, str):
                        raise ValueError("invalid streamed text")
                    if first_delta and delta:
                        first_delta = False
                        if on_timing is not None:
                            on_timing("llm_first_token")
                    deltas.append(delta)
                    for sentence in chunker.feed(delta):
                        await queue.put(sentence)
            answer = "".join(deltas).strip()
            if not answer:
                raise ValueError("chat backend returned an empty response")
            if on_timing is not None:
                on_timing("llm_end")
            final = chunker.finish()
            if final:
                await queue.put(final)
            await queue.put(None)
            await playback
            if not valid():
                raise TimeoutError("message expired")
        except BaseException:
            playback.cancel()
            await asyncio.gather(playback, return_exceptions=True)
            commit_partial()
            raise
        if delivery_failed:
            commit_partial()
        else:
            history.extend((user, {"role": "assistant", "content": answer}))
            if incoming.message_id:
                used.append(incoming.message_id)
        return Reply(incoming, answer)
