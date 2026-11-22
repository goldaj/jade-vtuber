"""Bounded no-LLM prefetch cache for opted-in, transport-verified identities."""
from __future__ import annotations

from collections import OrderedDict
import asyncio
import time


class PresenceMemoryCache:
    def __init__(self, store, *, ttl_seconds=600, max_entries=64, clock=time.monotonic):
        self.store = store
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock
        self._entries = OrderedDict()
        self._locks = {}

    async def candidates(self, key, scope: str, *, linked=False):
        # Consent and revision are checked on *every* read, including cache hits.
        person = await asyncio.to_thread(self.store.account, key)
        if not person:
            self.invalidate(key)
            return []
        revision = await asyncio.to_thread(self.store.revision)
        cache_key = (key, scope, bool(linked), person)
        now = self.clock()
        stored = self._entries.get(cache_key)
        if stored and stored[0] > now and stored[1] == revision:
            self._entries.move_to_end(cache_key)
            return [dict(item) for item in stored[2]]
        lock = self._locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            person_again = await asyncio.to_thread(self.store.account, key)
            revision_again = await asyncio.to_thread(self.store.revision)
            if person_again != person:
                self.invalidate(key)
                return []
            stored = self._entries.get(cache_key)
            if stored and stored[0] > self.clock() and stored[1] == revision_again:
                return [dict(item) for item in stored[2]]
            rows = await asyncio.to_thread(self.store.recall_candidates, key, scope,
                                           linked=linked)
            # Abort a stale load after unlink, erasure, new writes or opt-out.
            if (await asyncio.to_thread(self.store.account, key) != person
                    or await asyncio.to_thread(self.store.revision) != revision_again):
                self.invalidate(key)
                return []
            self._entries[cache_key] = (self.clock() + self.ttl_seconds,
                                        revision_again, tuple(dict(x) for x in rows))
            self._entries.move_to_end(cache_key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            return [dict(item) for item in rows]

    def invalidate(self, key=None):
        for candidate in list(self._entries):
            if key is None or candidate[0] == key:
                self._entries.pop(candidate, None)

    def clear(self):
        self._entries.clear()
        self._locks.clear()
