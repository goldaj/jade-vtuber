import asyncio
import types
import unittest
from unittest.mock import AsyncMock, patch

from src.jade_runtime.config import Settings
from src.jade_runtime.discord_text import DiscordText, parse_discord_message
from src.jade_runtime.twitch_irc import TwitchIRC, parse_message


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_twitch_reads_privmsg_and_pings_only(self):
        text = ("@id=hello;mod=0 :viewer!viewer@viewer.tmi.twitch.tv "
                "PRIVMSG #jade :Bonjour Jade 🐈")
        obj = parse_message(text)
        self.assertEqual((obj.author, obj.text, obj.message_id),
                         ("viewer", "Bonjour Jade 🐈", "hello"))
        self.assertIsNone(parse_message("PING :tmi.twitch.tv"))
        self.assertIsNone(parse_message(":server JOIN #jade"))

        replies = []
        async def consume(item):
            replies.append(item)
        reader = asyncio.StreamReader()
        reader.feed_data(("PING :tmi.twitch.tv\r\n" + text + "\r\n"
                          ":server RECONNECT\r\n").encode("utf-8"))
        reader.feed_eof()
        output = []
        class Writer:
            def write(self, raw):
                output.append(raw.decode())
            async def drain(self): pass
            def close(self): pass
            async def wait_closed(self): pass
        async def connect(host, port, ssl=None):
            self.assertEqual(port, 6697)
            return reader, Writer()
        client = TwitchIRC(login="jadebot", token="fake-token", channel="jade",
                           on_message=consume, connector=connect)
        await client.connect_once()
        self.assertEqual(len(replies), 1)
        self.assertIn("PONG :tmi.twitch.tv", "".join(output))
        self.assertNotIn("fake-token", repr(replies))

    def test_discord_skips_bots_dm_and_preserves_channel(self):
        message = types.SimpleNamespace(
            id=101, author=types.SimpleNamespace(id=9, bot=False,
                    display_name="Émilie"),
            guild=types.SimpleNamespace(id=30),
            channel=types.SimpleNamespace(id=70),
            content="Salut Jade")
        self.assertEqual(parse_discord_message(message).channel, "70")
        message.author.bot = True
        self.assertIsNone(parse_discord_message(message))
        message.author.bot = False
        message.guild = None
        self.assertIsNone(parse_discord_message(message))

    def test_extra_connector_flags_are_safe_by_default(self):
        self.assertFalse(Settings().twitch_enabled)
        self.assertFalse(Settings().discord_enabled)
        with self.assertRaises(ValueError):
            Settings(twitch_send=True).validate()
        with self.assertRaises(ValueError):
            Settings(discord_send=True).validate()

    async def test_twitch_queue_full_does_not_stop_pong(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b':viewer!v@host PRIVMSG #jade :hello\r\nPING :server\r\n:server RECONNECT\r\n')
        reader.feed_eof()
        writes = []
        class Writer:
            def write(self, data): writes.append(data)
            async def drain(self): pass
            def close(self): pass
            async def wait_closed(self): pass
        client = TwitchIRC(login='jadebot', token='fake', channel='jade',
                           on_message=AsyncMock(side_effect=asyncio.QueueFull),
                           connector=AsyncMock(return_value=(reader, Writer())))
        await client.connect_once()
        self.assertEqual(client.dropped, 1)
        self.assertIn(b'PONG :server\r\n', writes)

    async def test_discord_sends_with_mentions_explicitly_disabled(self):
        sentinel = object()
        target = types.SimpleNamespace(send=AsyncMock())
        fake = types.SimpleNamespace(AllowedMentions=types.SimpleNamespace(none=lambda: sentinel))
        bridge = DiscordText('fake', AsyncMock(), send_enabled=True)
        bridge.client = types.SimpleNamespace(get_channel=lambda _: target)
        with patch.dict('sys.modules', {'discord': fake}):
            self.assertTrue(await bridge.send_chat('12', '@everyone <@12>'))
        self.assertIs(target.send.await_args.kwargs['allowed_mentions'], sentinel)

    async def test_discord_queue_full_does_not_abort_listener(self):
        sentinel = object()
        message = types.SimpleNamespace(id=1,
            author=types.SimpleNamespace(id=2, bot=False, display_name='User'),
            guild=object(), channel=types.SimpleNamespace(id=3), content='Hello')
        class Client:
            def __init__(self, **kwargs):
                self.user = types.SimpleNamespace(id=10)
                self.kwargs = kwargs
            async def start(self, token):
                await self.on_message(message)
                await self.on_message(message)
            async def close(self): pass
        fake = types.SimpleNamespace(Client=Client,
            Intents=types.SimpleNamespace(default=lambda: types.SimpleNamespace()),
            AllowedMentions=types.SimpleNamespace(none=lambda: sentinel))
        bridge = DiscordText('fake', AsyncMock(side_effect=asyncio.QueueFull))
        with patch.dict('sys.modules', {'discord': fake}):
            await bridge.connect_forever()
        self.assertEqual(bridge.dropped, 2)
        self.assertIs(bridge.client.kwargs['allowed_mentions'], sentinel)
