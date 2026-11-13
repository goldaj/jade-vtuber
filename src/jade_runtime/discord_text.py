"""Optional Discord text connector using *one* supported discord.py stack.

Discord voice reception requires a separate PCM transport; text support
alone never joins voice channels or records other users.
"""
import asyncio
import logging

from .messages import Incoming
from .discord_text_policy import DiscordTextPolicy

LOG = logging.getLogger("jade.discord")


def parse_discord_message(message, *, own_user_id=None) -> Incoming | None:
    author = message.author
    if own_user_id is not None and getattr(author, "id", None) == own_user_id:
        return None
    text = getattr(message, "content", "")
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        return None
    return Incoming(platform="discord",
                    author=getattr(author, "display_name", "") or str(author),
                    text=text,
                    channel=str(message.channel.id),
                    message_id=str(message.id))


class DiscordText:
    def __init__(self, token: str, on_message, *, send_enabled=False,
                 voice_bridge=None, bot_name="Jade", auto_rate=0.15,
                 cooldown_seconds=180):
        if not token or token == "example":
            raise ValueError("Discord token required")
        self.token = token
        self.on_message = on_message
        self.send_enabled = send_enabled
        self.client = None
        self.voice_bridge = voice_bridge
        self.dropped = 0
        self.policy = DiscordTextPolicy(bot_name=bot_name, auto_rate=auto_rate,
                                        cooldown_seconds=cooldown_seconds)

    async def connect_forever(self):
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError("install optional discord.py extra") from exc
        intents = discord.Intents.default()
        intents.message_content = True  # Must also enable Portal privileged intent.
        parent = self

        class JadeClient(discord.Client):
            async def on_ready(self):
                if parent.voice_bridge is not None:
                    await parent.voice_bridge.connect(self)

            async def on_resumed(self):
                # A resumed Gateway session does not emit on_ready again.
                if parent.voice_bridge is not None:
                    await parent.voice_bridge.connect(self)

            async def on_message(self, message):
                incoming = parse_discord_message(
                    message, own_user_id=self.user.id if self.user else None)
                if incoming is not None:
                    selected = parent.policy.observe(
                        message, incoming, own_user_id=self.user.id if self.user else None)
                    if selected is not None:
                        try:
                            await parent.on_message(selected)
                        except (asyncio.QueueFull, RuntimeError):
                            parent.dropped += 1
                            parent.policy.forget_pending(selected.channel, selected.message_id)

            async def on_voice_state_update(self, member, before, after):
                if parent.voice_bridge is not None:
                    own_user = getattr(self, "user", None)
                    await parent.voice_bridge.voice_state_changed(
                        member, before, after, own_bot_id=getattr(own_user, "id", None))

            async def on_disconnect(self):
                bridge = parent.voice_bridge
                if bridge is not None:
                    # Revoke immediately, but never let cleanup from this
                    # disconnect close a session established in the meantime.
                    with bridge.buffers_lock:
                        expected = (bridge.generation, bridge.session_id)
                    if bridge.set_session([], consent_confirmed=False, _expected=expected):
                        await bridge._close_if_revoked(expected[0] + 1)

        self.client = JadeClient(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        try:
            await self.client.start(self.token)
        finally:
            try:
                if self.voice_bridge is not None:
                    await asyncio.wait_for(self.voice_bridge.close(), timeout=4)
            finally:
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
