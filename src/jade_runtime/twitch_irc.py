"""Minimal TLS Twitch IRC text connector; no TwitchIO 2025 dependency.

Twitch recommends EventSub for advanced capabilities; this conservative
chat-read adapter implements only IRC PRIVMSG, PING/PONG and optional text send.
"""
import asyncio
import logging
import re
import ssl
from collections.abc import Awaitable, Callable

from .messages import Incoming

LOG = logging.getLogger("jade.twitch")
CLOSE_TIMEOUT = 1.0
PRIVMSG = re.compile(
    r"^(?:@(?P<tags>[^ ]+) )?:(?P<author>[^! ]+)!\S+ PRIVMSG #"
    r"(?P<channel>[^ ]+) :(?P<text>.*)$")


def parse_message(line: str) -> Incoming | None:
    found = PRIVMSG.match(line.rstrip("\r\n"))
    if not found:
        return None
    tags = found.group("tags") or ""
    message_id = next((item[3:] for item in tags.split(";")
                       if item.startswith("id=")), "")
    text = found.group("text")
    if not text.strip() or len(text) > 4000:
        return None
    return Incoming("twitch", found.group("author"), text,
                    channel=found.group("channel"),
                    message_id=message_id)


class TwitchIRC:
    def __init__(self, *, login: str, token: str, channel: str,
                 on_message: Callable[[Incoming], Awaitable[None]],
                 send_enabled=False, connector=None):
        if (not re.fullmatch(r"[A-Za-z0-9_]{2,25}", login)
                or not re.fullmatch(r"[A-Za-z0-9_]{2,25}", channel)):
            raise ValueError("invalid Twitch bot login or channel name")
        cleaned = token[6:] if token.lower().startswith("oauth:") else token
        if not cleaned or any(char.isspace() for char in cleaned):
            raise ValueError("Twitch access token required")
        self.login = login.lower()
        self.token = cleaned
        self.channel = channel.lower()
        self.on_message = on_message
        self.send_enabled = send_enabled
        self.writer = None
        self.connector = connector or asyncio.open_connection
        self.send_lock = asyncio.Lock()
        self.last_sent = -1e9
        self.dropped = 0

    async def _write(self, line):
        if self.writer is None:
            return False
        self.writer.write((line + "\r\n").encode("utf-8"))
        await self.writer.drain()
        return True

    async def connect_once(self):
        reader, writer = await self.connector(
            "irc.chat.twitch.tv", 6697, ssl=ssl.create_default_context())
        self.writer = writer
        try:
            await self._write("PASS oauth:" + self.token)
            await self._write("NICK " + self.login)
            await self._write("CAP REQ :twitch.tv/tags twitch.tv/commands")
            await self._write("JOIN #" + self.channel)
            while True:
                # wait_for can swallow task cancellation on Python 3.11 when a
                # read finishes in the same event-loop turn as shutdown.
                async with asyncio.timeout(300):
                    data = await reader.readline()
                if not data:
                    raise ConnectionError("Twitch IRC disconnected")
                line = data.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("PING "):
                    await self._write("PONG " + line.removeprefix("PING "))
                    continue
                if "Login authentication failed" in line or "Improperly formatted auth" in line:
                    raise PermissionError("Twitch IRC authentication refused")
                if " RECONNECT" in line:
                    return
                incoming = parse_message(line)
                if incoming is not None and incoming.channel == self.channel:
                    if incoming.author.casefold() != self.login.casefold():
                        try:
                            await self.on_message(incoming)
                        except (asyncio.QueueFull, RuntimeError):
                            # Local overload or shutdown must not break IRC/PING.
                            self.dropped += 1
        finally:
            self.writer = None
            try:
                writer.close()
                # In particular, TLS shutdown may not complete if the peer
                # disconnects during cancellation.  Never let its transport
                # errors mask the cancellation that initiated the shutdown.
                async with asyncio.timeout(CLOSE_TIMEOUT):
                    await writer.wait_closed()
            except (OSError, TimeoutError):
                pass

    async def connect_forever(self):
        delay = 2
        while True:
            try:
                await self.connect_once()
                delay = 2
            except PermissionError:
                LOG.error("Twitch IRC credentials were rejected")
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.warning("Twitch IRC transport disconnected; reconnecting")
            await asyncio.sleep(delay)
            delay = min(60, delay * 2)

    async def send_chat(self, text: str) -> bool:
        if not self.send_enabled or self.writer is None:
            return False
        text = text.replace("\r", " ").replace("\n", " ").strip()[:430]
        if not text:
            return False
        async with self.send_lock:
            loop = asyncio.get_running_loop()
            delay = 2.0 - (loop.time() - self.last_sent)
            if delay > 0:
                await asyncio.sleep(delay)
            result = await self._write("PRIVMSG #" + self.channel + " :" + text)
            if result:
                self.last_sent = loop.time()
            return result
