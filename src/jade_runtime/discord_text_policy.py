"""Bounded, in-memory Discord text participation policy.

Read normal channel traffic without making LLM requests for every message.
Direct requests are always eligible; unsolicited questions are deliberately
rare. This policy is a cheap heuristic, not an LLM relevance classifier.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field, replace
import random
import re
import time

from .messages import Incoming


@dataclass
class _Channel:
    touched: float
    recent: deque[str] = field(default_factory=lambda: deque(maxlen=6))
    pending: OrderedDict[str, int | None] = field(default_factory=OrderedDict)
    sent_ids: deque[int] = field(default_factory=lambda: deque(maxlen=32))
    last_reply_at: float = float("-inf")
    last_reply_author: int | None = None
    last_unsolicited_at: float = float("-inf")


class DiscordTextPolicy:
    """Channel-isolated context, direct addressing and measured participation."""

    def __init__(self, *, bot_name="Jade", auto_rate=0.15, cooldown_seconds=180,
                 followup_seconds=90, max_channels=128, clock=time.monotonic, rng=None):
        if (not isinstance(bot_name, str) or not bot_name.strip()
                or not 0 <= auto_rate <= 1
                or not 30 <= cooldown_seconds <= 3600
                or not 0 <= followup_seconds <= 300
                or not 1 <= max_channels <= 256):
            raise ValueError("invalid Discord text participation settings")
        self.bot_name = bot_name.strip()
        self.auto_rate = auto_rate
        self.cooldown_seconds = cooldown_seconds
        self.followup_seconds = followup_seconds
        self.max_channels = max_channels
        self.clock = clock
        self.rng = rng or random.Random()
        self.channels: OrderedDict[str, _Channel] = OrderedDict()

    def _channel(self, channel: str, now: float) -> _Channel:
        # Context never survives a long idle period, restart or channel change.
        for key, state in list(self.channels.items()):
            if now - state.touched > 1800:
                del self.channels[key]
        if channel not in self.channels:
            if len(self.channels) >= self.max_channels:
                self.channels.popitem(last=False)
            self.channels[channel] = _Channel(now)
        state = self.channels[channel]
        state.touched = now
        self.channels.move_to_end(channel)
        return state

    def observe(self, message, incoming: Incoming, *, own_user_id=None) -> Incoming | None:
        """Return selected messages for the runtime; keep small passive context."""
        now = self.clock()
        state = self._channel(incoming.channel, now)
        text = incoming.text.strip()
        author = message.author
        author_id = getattr(author, "id", None)
        recent = tuple(state.recent)  # Excludes the current message.

        mentions = getattr(message, "mentions", ()) or ()
        ping = own_user_id is not None and (
            any(getattr(user, "id", None) == own_user_id for user in mentions)
            or bool(re.search(r"<@!?" + re.escape(str(own_user_id)) + r">", text)))
        ref = getattr(message, "reference", None)
        resolved = getattr(ref, "resolved", None)
        ref_author = getattr(getattr(resolved, "author", None), "id", None)
        reply_to_jade = (own_user_id is not None and ref_author == own_user_id
                         or getattr(ref, "message_id", None) in state.sent_ids)
        named = bool(re.search(r"(?<!\w)" + re.escape(self.bot_name) + r"(?!\w)",
                               text, flags=re.IGNORECASE))
        command = text.casefold().startswith(("!response", "!rsp"))
        dm = getattr(message, "guild", None) is None
        direct = bool(ping or reply_to_jade or named or command or dm)
        question = text.rstrip().endswith(("?", "？"))
        followup = (not getattr(author, "bot", False)
                    and author_id is not None
                    and state.last_reply_author == author_id
                    and now - state.last_reply_at < self.followup_seconds
                    and (question or text.casefold().startswith(
                        ("et ", "mais ", "donc ", "pourquoi ", "comment ", "sinon "))))
        unsolicited = (not direct and not followup and not getattr(author, "bot", False)
                       and not text.startswith(("!", "/", "."))
                       and question and len(text) <= 500
                       and now - state.last_unsolicited_at >= self.cooldown_seconds
                       and self.rng.random() < self.auto_rate)
        selected = direct or followup or unsolicited
        # Do not bill for very long messages, even when someone pings Jade.
        if len(text) > 1200:
            selected = False

        # Keep the source short, bounded and labelled as untrusted channel text.
        snippet = " ".join(text.split())[:240]
        state.recent.append(f"{incoming.author[:48]} : {snippet}")
        if not selected:
            return None
        if unsolicited:
            # Reserve the cooldown on selection, before a queued response arrives.
            state.last_unsolicited_at = now
        if incoming.message_id:
            state.pending[incoming.message_id] = author_id
            if len(state.pending) > 32:
                state.pending.popitem(last=False)
        return replace(incoming, force_reply=True, context=recent)

    def note_sent(self, channel: str, *, source_message_id: str = "",
                  sent_message_id: int | None = None) -> None:
        state = self.channels.get(channel)
        if state is None:
            return
        author_id = state.pending.pop(source_message_id, None)
        state.last_reply_at = self.clock()
        state.last_reply_author = author_id
        if isinstance(sent_message_id, int):
            state.sent_ids.append(sent_message_id)

    def forget_pending(self, channel: str, message_id: str) -> None:
        state = self.channels.get(channel)
        if state is not None:
            state.pending.pop(message_id, None)
