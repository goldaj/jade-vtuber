"""Application lifecycle tests with synthetic clients and no network."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import main
from src.jade_runtime.config import Settings
from src.jade_runtime.messages import Incoming


class MainSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_twitch_reply_survives_failed_voice_output(self):
        config = Settings(api_key="test", twitch_enabled=True, twitch_login="jade",
                          twitch_oauth="test", channel="test", audio_output="ffplay")
        spoken = asyncio.Event()
        sent = []
        service = SimpleNamespace(client=SimpleNamespace(close=AsyncMock()),
                                  complete=AsyncMock(return_value="synthetic"))
        class Connector:
            def __init__(self, **kwargs):
                self.on_message = kwargs['on_message']
            async def connect_forever(self):
                await self.on_message(Incoming('twitch', 'user', 'jade', force_reply=True))
                await asyncio.Event().wait()
            async def send_chat(self, text):
                sent.append(text)
        class BrokenSpeech:
            def __init__(self, *args, **kwargs):
                pass
            async def speak(self, reply):
                spoken.set()
                raise RuntimeError('synthetic audio failure')
        with patch.object(main.Settings, 'load', return_value=config), \
             patch.object(main, 'OpenAIServices', return_value=service), \
             patch.object(main, 'SpeechOutput', BrokenSpeech), \
             patch('src.jade_runtime.twitch_irc.TwitchIRC', Connector):
            task = asyncio.create_task(main.console(live=True, twitch=True, voice=True))
            await asyncio.wait_for(spoken.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(sent, ['synthetic'])

    async def test_failed_connector_initialization_cleans_runtime_and_client(self):
        config = Settings(api_key="test", http_enabled=True, http_token="x" * 32)
        client = SimpleNamespace(close=AsyncMock())
        service = SimpleNamespace(client=client)
        with patch.object(main.Settings, "load", return_value=config), \
             patch.object(main, "OpenAIServices", return_value=service), \
             patch("src.jade_runtime.local_http.LocalHTTP", side_effect=ValueError("synthetic")):
            with self.assertRaises(ValueError):
                await main.console(live=True, http=True)
        client.close.assert_awaited_once()
        self.assertFalse(any(t.get_name() == "jade-consumer" and not t.done()
                             for t in asyncio.all_tasks()))

    async def test_shutdown_signal_precedes_connector_cleanup(self):
        config = Settings(api_key="test", twitch_enabled=True, twitch_login="jade",
                          twitch_oauth="test", channel="test")
        started, cleaned = asyncio.Event(), asyncio.Event()
        client = SimpleNamespace(close=AsyncMock())
        class Connector:
            def __init__(self, **kwargs):
                pass
            async def connect_forever(self):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cleaned.set()
        with patch.object(main.Settings, "load", return_value=config), \
             patch.object(main, "OpenAIServices", return_value=SimpleNamespace(client=client)), \
             patch("src.jade_runtime.twitch_irc.TwitchIRC", Connector):
            task = asyncio.create_task(main.console(live=True, twitch=True))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
        self.assertTrue(cleaned.is_set())
        client.close.assert_awaited_once()
        self.assertFalse(any(t.get_name() == "jade-consumer" and not t.done()
                             for t in asyncio.all_tasks()))
