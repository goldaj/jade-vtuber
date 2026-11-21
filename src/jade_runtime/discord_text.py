"""Optional Discord text connector using *one* supported discord.py stack.

Discord voice reception requires a separate PCM transport; text support
alone never joins voice channels or records other users.
"""
import asyncio
import logging
import re
from collections import OrderedDict
from dataclasses import replace

from .messages import Incoming
from .discord_text_policy import DiscordTextPolicy

LOG = logging.getLogger("jade.discord")
_VOICE_RECONNECT_DELAYS = (1, 2, 4, 8, 16, 30)


def parse_discord_message(message, *, own_user_id=None) -> Incoming | None:
    author = message.author
    # Prevent another bot from creating a costly autonomous feedback loop.
    if getattr(author, "bot", False) is True:
        return None
    if own_user_id is not None and getattr(author, "id", None) == own_user_id:
        return None
    text = getattr(message, "content", "")
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        return None
    return Incoming(platform="discord",
                    author=getattr(author, "display_name", "") or str(author),
                    text=text,
                    channel=str(message.channel.id),
                    message_id=str(message.id),
                    account_id=(str(author.id) if type(getattr(author, "id", None)) is int
                                and author.id > 0 else ""),
                    private_channel=(getattr(message, "guild", None) is None))


class DiscordText:
    def __init__(self, token: str, on_message, *, send_enabled=False,
                 voice_bridge=None, bot_name="Jade", auto_rate=0.20,
                 cooldown_seconds=180, social_policy=None,
                 initiatives=None):
        if not token or token == "example":
            raise ValueError("Discord token required")
        self.token = token
        self.on_message = on_message
        self.send_enabled = send_enabled
        self.client = None
        self.voice_bridge = voice_bridge
        self.social_policy = social_policy
        self.initiatives = initiatives
        self.dropped = 0
        # A real inbound DM provides an authenticated reply destination.
        # Cache only verified DM channels and bound the reference count.
        self._dm_channels = OrderedDict()
        self.policy = DiscordTextPolicy(bot_name=bot_name, auto_rate=auto_rate,
                                        cooldown_seconds=cooldown_seconds)

    def _remember_dm_channel(self, incoming: Incoming, channel) -> None:
        if (not incoming.private_channel
                or str(getattr(channel, "id", "")) != incoming.channel):
            return
        self._dm_channels[incoming.channel] = channel
        self._dm_channels.move_to_end(incoming.channel)
        while len(self._dm_channels) > 128:
            self._dm_channels.popitem(last=False)

    async def connect_forever(self):
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError("install optional discord.py extra") from exc
        intents = discord.Intents.default()
        intents.message_content = True  # Must also enable Portal privileged intent.
        parent = self

        class JadeClient(discord.Client):
            _gateway_available = False
            _shutting_down = False
            _voice_retry = None

            def _schedule_voice_retry(self, bridge, *, join_now=False):
                if not self._gateway_available:
                    return None
                if self._voice_retry is None or self._voice_retry.done():
                    delays = _VOICE_RECONNECT_DELAYS
                    if join_now:
                        delays = (0, *delays)
                    self._voice_retry = asyncio.create_task(
                        self._reconnect_voice(bridge, delays), name="jade-discord-voice-reconnect")
                return self._voice_retry

            def _cancel_voice_retry(self):
                self._gateway_available = False
                retry, self._voice_retry = self._voice_retry, None
                if retry is not None:
                    retry.cancel()
                return retry

            async def _reconnect_voice(self, bridge, delays):
                # Keep one bounded-backoff retry alive while the Gateway is
                # connected: a short outage can otherwise exhaust all retries
                # and leave voice offline indefinitely. Cancellation on Gateway
                # loss or shutdown interrupts both sleep and connection.
                attempt = 0
                while self._gateway_available and not self._shutting_down:
                    delay = delays[min(attempt, len(delays) - 1)]
                    attempt += 1
                    if delay:
                        await asyncio.sleep(delay)
                    try:
                        await bridge.connect(self)
                    except Exception as exc:
                        LOG.warning("Discord voice reconnect failed: %s; retry scheduled", type(exc).__name__)
                    else:
                        LOG.info("Discord voice reconnected")
                        return

            async def on_ready(self):
                if self._shutting_down:
                    return
                self._gateway_available = True
                bridge = parent.voice_bridge
                if bridge is None:
                    return
                if getattr(bridge, "_open_voice", False) is True:
                    await self._schedule_voice_retry(bridge, join_now=True)
                else:
                    await bridge.connect(self)

            async def on_resumed(self):
                # A resumed Gateway session does not emit on_ready again.
                await self.on_ready()

            async def on_message(self, message):
                incoming = parse_discord_message(
                    message, own_user_id=self.user.id if self.user else None)
                if incoming is not None:
                    parent._remember_dm_channel(incoming, message.channel)
                    if (parent.initiatives is not None
                            and incoming.account_id
                            and getattr(message.author, "bot", True) is False):
                        own_id = self.user.id if self.user else None
                        mentions = getattr(message, "mentions", ()) or ()
                        ref = getattr(message, "reference", None)
                        resolved = getattr(ref, "resolved", None)
                        state = parent.policy.channels.get(incoming.channel)
                        directed = bool(
                            (own_id is not None and
                             (any(getattr(p, "id", None) == own_id for p in mentions)
                              or getattr(getattr(resolved, "author", None), "id", None) == own_id
                              or (state is not None and
                                  getattr(ref, "message_id", None) in state.sent_ids)))
                            or re.search(r"(?<!\w)" + re.escape(parent.policy.bot_name)
                                         + r"(?!\w)", incoming.text, re.I))
                        parent.initiatives.human_replied(
                            incoming.channel, text=incoming.text, directed=directed)
                    selected = parent.policy.observe(
                        message, incoming, own_user_id=self.user.id if self.user else None)
                    # Native text chat of the current voice channel has the
                    # same Discord permissions as that voice channel. We never
                    # merge a different channel, even within the same guild.
                    linked = None
                    bridge = parent.voice_bridge
                    if (bridge is not None and getattr(message.author, "bot", True) is False
                            and incoming.account_id and getattr(message, "guild", None) is not None):
                        guild_id = getattr(message.guild, "id", None)
                        if type(guild_id) is int and type(message.channel.id) is int:
                            linked = bridge.linked_text_conversation_id(
                                guild_id, message.channel.id, message.author.id)
                    if selected is not None and parent.social_policy is not None:
                        state = parent.policy.channels.get(incoming.channel)
                        count = len(state.participants) if state is not None else 0
                        if not await parent.social_policy.allow(
                                message, selected,
                                own_user_id=self.user.id if self.user else None,
                                active_participants=count):
                            parent.policy.forget_pending(selected.channel, selected.message_id)
                            selected = None
                    if selected is not None:
                        if linked:
                            selected = replace(selected, conversation_id=linked)
                        try:
                            await parent.on_message(selected)
                        except (asyncio.QueueFull, RuntimeError):
                            parent.dropped += 1
                            parent.policy.forget_pending(selected.channel, selected.message_id)
                    elif (linked and incoming.message_id and len(incoming.text) <= 1200
                          and not incoming.text.lstrip().startswith(("!", "/", "."))):
                        # No LLM call for passive text. Its owner can resume
                        # verbally moments later without Jade losing the detail.
                        await bridge.runtime.dialogue.observe_linked_text(
                            replace(incoming, conversation_id=linked))

            async def on_voice_state_update(self, member, before, after):
                bridge = parent.voice_bridge
                if bridge is None:
                    return
                own_bot_id = getattr(getattr(self, "user", None), "id", None)
                lost_voice = (
                    getattr(bridge, "_open_voice", False) is True
                    and own_bot_id is not None and getattr(member, "id", None) == own_bot_id
                    and getattr(before, "channel", None) is not None
                    and getattr(after, "channel", None) is None
                )
                try:
                    await bridge.voice_state_changed(member, before, after, own_bot_id=own_bot_id)
                finally:
                    if lost_voice and self._gateway_available:
                        LOG.warning("Discord voice left while Gateway is available; scheduling reconnect")
                        self._schedule_voice_retry(bridge)
                if parent.initiatives is not None:
                    previous = getattr(before, "channel", None)
                    current = getattr(after, "channel", None)
                    if previous is not None and previous != current:
                        members = getattr(previous, "members", None)
                        if isinstance(members, (list, tuple)) and not any(
                                getattr(person, "bot", True) is False
                                for person in members):
                            parent.initiatives.room_emptied(str(previous.id))
                if parent.initiatives is not None and self._gateway_available:
                    source = await parent.initiatives.voice_join(
                        member, before, after, channel_id=bridge.channel_id,
                        own_bot_id=own_bot_id,
                        voice_session_id=(bridge.session_id
                                          if getattr(bridge, "connection", None) is not None
                                          else ""))
                    if source is not None:
                        try:
                            await parent.on_message(source)
                        except (asyncio.QueueFull, RuntimeError):
                            parent.dropped += 1

            async def on_disconnect(self):
                retry = self._cancel_voice_retry()
                bridge = parent.voice_bridge
                try:
                    if bridge is not None:
                        # Revoke immediately, but never let cleanup from this
                        # disconnect close a session established in the meantime.
                        with bridge.buffers_lock:
                            expected = (bridge.generation, bridge.session_id)
                        if bridge.set_session([], consent_confirmed=False, _expected=expected):
                            await bridge._close_if_revoked(expected[0] + 1)
                finally:
                    if retry is not None:
                        await asyncio.gather(retry, return_exceptions=True)

        self.client = JadeClient(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        try:
            await self.client.start(self.token)
        finally:
            self.client._shutting_down = True
            retry = self.client._cancel_voice_retry()
            try:
                if retry is not None:
                    await asyncio.gather(retry, return_exceptions=True)
                if self.voice_bridge is not None:
                    await asyncio.wait_for(self.voice_bridge.close(), timeout=4)
            finally:
                self._dm_channels.clear()
                await self.client.close()

    async def send_chat(self, channel: str, text: str, *,
                        source_message_id: str = "") -> bool:
        if not self.send_enabled or self.client is None or not text.strip():
            return False
        try:
            channel_id = int(channel)
        except ValueError:
            return False
        target = self.client.get_channel(channel_id)
        if target is None:
            target = self._dm_channels.get(str(channel_id))
        if target is None:
            return False  # Never guess a destination or fetch unknown IDs.
        import discord
        remaining = text.strip()
        parts = []
        # Keep full answers where possible within Discord's message limit.
        while remaining and len(parts) < 4:
            if len(remaining) <= 1800:
                parts.append(remaining)
                remaining = ""
                break
            cut = max(remaining.rfind("\n", 0, 1800),
                      remaining.rfind(" ", 0, 1800))
            if cut < 500:
                cut = 1800
            parts.append(remaining[:cut].strip())
            remaining = remaining[cut:].lstrip()
        if remaining:
            parts[-1] = parts[-1][:1775] + " … [suite tronquée]"
        first_sent = False
        for part in parts:
            sent = await target.send(part, allowed_mentions=discord.AllowedMentions.none())
            if not first_sent:
                self.policy.note_sent(channel, source_message_id=source_message_id,
                                      sent_message_id=getattr(sent, "id", None))
                first_sent = True
        return first_sent
