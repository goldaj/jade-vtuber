"""Optional Discord text connector using *one* supported discord.py stack.

Discord voice reception requires a separate consent/PCM transport; text
support alone never joins voice channels or records other users.
"""
import asyncio
import logging

from .messages import Incoming

LOG = logging.getLogger("jade.discord")


def parse_discord_message(message, *, own_user_id=None) -> Incoming | None:
    author = message.author
    if getattr(author, "bot", False) or getattr(author, "id", None) == own_user_id:
        return None
    if not getattr(message, "guild", None):  # no private DMs by default
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
                 voice_bridge=None):
        if not token or token == "example":
            raise ValueError("Discord token required")
        self.token = token
        self.on_message = on_message
        self.send_enabled = send_enabled
        self.client = None
        self.voice_bridge = voice_bridge
        self.dropped = 0

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

            async def on_message(self, message):
                incoming = parse_discord_message(
                    message, own_user_id=self.user.id if self.user else None)
                if incoming is not None:
                    try:
                        await parent.on_message(incoming)
                    except (asyncio.QueueFull, RuntimeError):
                        parent.dropped += 1

            async def on_voice_state_update(self, member, before, after):
                if parent.voice_bridge is not None:
                    own_user = getattr(self, "user", None)
                    await parent.voice_bridge.voice_state_changed(
                        member, before, after, own_bot_id=getattr(own_user, "id", None))

            async def on_disconnect(self):
                if parent.voice_bridge is not None:
                    parent.voice_bridge.set_session([], consent_confirmed=False)
                    await parent.voice_bridge.close()

        self.client = JadeClient(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        try:
            await self.client.start(self.token)
        finally:
            try:
                if self.voice_bridge is not None:
                    await asyncio.wait_for(self.voice_bridge.close(), timeout=4)
            finally:
                await self.client.close()

    async def send_chat(self, channel: str, text: str) -> bool:
        if not self.send_enabled or self.client is None or not text.strip():
            return False
        try:
            channel_id = int(channel)
        except ValueError:
            return False
        target = self.client.get_channel(channel_id)
        if target is None:
            return False  # Never guess a destination/channel or fetch unknown IDs.
        import discord
        await target.send(text[:1500], allowed_mentions=discord.AllowedMentions.none())
        return True
