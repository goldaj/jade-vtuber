"""Bounded per-channel conversation. No paid calls in unit tests."""
import asyncio
from collections import deque
import random
import time
from typing import Protocol

from .messages import Incoming, Reply
from .sentence_stream import SentenceAccumulator


class ChatBackend(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> str: ...


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
                      on_sentence=None) -> Reply | None:
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
                # Failed LLM calls must not corrupt memory or mark a message handled.
                if on_sentence is not None and callable(getattr(self.backend, "complete_stream", None)):
                    sentence_buffer = SentenceAccumulator()
                    answer_parts = []
                    stream = self.backend.complete_stream(messages)
                    try:
                        async for fragment in stream:
                            if not valid():
                                raise TimeoutError("message expired")
                            answer_parts.append(fragment)
                            for sentence in sentence_buffer.feed(fragment):
                                await on_sentence(sentence)
                    finally:
                        # Breaking out because Discord disconnected or the
                        # speech consumer failed must close the LLM response
                        # immediately, not wait for generator finalization.
                        close = getattr(stream, "aclose", None)
                        if callable(close):
                            await close()
                    for sentence in sentence_buffer.finish():
                        await on_sentence(sentence)
                    answer = "".join(answer_parts)
                else:
                    answer = await self.backend.complete(messages)
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
