"""Application lifecycle tests with synthetic clients and no network."""
import asyncio
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import main
from src.jade_runtime.config import Settings
from src.jade_runtime.messages import Incoming


class MainSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_twitch_automatic_mode_uses_managed_connector(self):
        config = Settings(api_key="test", twitch_enabled=True, twitch_oauth="test",
                          channel="test", twitch_auto_refresh=True)
        state = SimpleNamespace(login="derived", access_token="synthetic-access", backup_pending=False)
        manager = SimpleNamespace(check=lambda: state, login="")
        built = []
        class Connector:
            def __init__(self, **kwargs):
                built.append(kwargs)
        async def managed(connector, supplied_manager):
            self.assertIs(supplied_manager, manager)
            raise RuntimeError("synthetic stop")
        client = SimpleNamespace(close=AsyncMock())
        with patch.object(main.Settings, "load", return_value=config), \
             patch.object(main, "OpenAIServices", return_value=SimpleNamespace(client=client)), \
             patch("src.utility.private_config.secrets_file", return_value=Path("unused")), \
             patch("src.jade_runtime.twitch_rotation.TwitchTokenManager", return_value=manager), \
             patch("src.jade_runtime.twitch_irc.TwitchIRC", Connector), \
             patch("src.jade_runtime.twitch_managed.run_managed_twitch", side_effect=managed):
            with self.assertRaisesRegex(RuntimeError, "synthetic stop"):
                await main.console(live=True, twitch=True)
        self.assertEqual(built[0]["login"], "derived")
        self.assertEqual(built[0]["token"], "synthetic-access")
        self.assertEqual(manager.login, "derived")
        client.close.assert_awaited_once()

    async def test_twitch_derives_login_from_verified_token_before_connecting(self):
        config = Settings(api_key="test", twitch_enabled=True, twitch_oauth="test", channel="test")
        seen = []
        class Connector:
            def __init__(self, **kwargs):
                seen.append(kwargs["login"])
            async def connect_forever(self):
                raise RuntimeError("synthetic stop")
        client = SimpleNamespace(close=AsyncMock())
        with patch.object(main.Settings, "load", return_value=config), \
             patch.object(main, "OpenAIServices", return_value=SimpleNamespace(client=client)), \
             patch.object(main, "validate_twitch_token", return_value=SimpleNamespace(login="derived")) as validate, \
             patch("src.jade_runtime.twitch_irc.TwitchIRC", Connector):
            with self.assertRaisesRegex(RuntimeError, "synthetic stop"):
                await main.console(live=True, twitch=True)
        self.assertEqual(seen, ["derived"])
        validate.assert_called_once_with("test", login="", send_enabled=False)
        client.close.assert_awaited_once()

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
             patch.object(main, 'validate_twitch_token', return_value=SimpleNamespace(login='jade')), \
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
             patch.object(main, "validate_twitch_token", return_value=SimpleNamespace(login="jade")), \
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

    async def test_discord_text_reply_is_written_and_spoken_when_voice_is_enabled(self):
        config = Settings(api_key="test", discord_token="synthetic-discord",
                          audio_output="ffplay", vts_enabled=True,
                          vts_token="synthetic-vts", vts_speak_hotkey="speak")
        sent, spoken = asyncio.Event(), asyncio.Event()
        outputs = []
        async def speak(reply):
            spoken.set()
        speech = SimpleNamespace(speak=AsyncMock(side_effect=speak))
        vts = SimpleNamespace(trigger_hotkey=AsyncMock())
        service = SimpleNamespace(
            complete=AsyncMock(return_value="Réponse écrite et vocale"),
            close=AsyncMock())

        class VTSScope:
            def __init__(self, *_args, **_kwargs):
                pass

            async def __aenter__(self):
                return vts

            async def __aexit__(self, *_args):
                pass

        class Connector:
            def __init__(self, token, on_message, **kwargs):
                self.on_message = on_message

            async def connect_forever(self):
                await self.on_message(Incoming(
                    "discord", "Alice", "Jade, bonjour", channel="10",
                    message_id="100", force_reply=True))
                await asyncio.Event().wait()

            async def send_chat(self, channel, text, *, source_message_id=""):
                outputs.append((channel, text, source_message_id))
                sent.set()
                return True

        with patch.object(main.Settings, "load", return_value=config), \
             patch.object(main, "OpenAIServices", return_value=service), \
             patch.object(main, "SpeechOutput", return_value=speech), \
             patch("src.jade_runtime.discord_text.DiscordText", Connector), \
             patch("src.jade_runtime.vtube_studio.VTubeStudio", VTSScope):
            running = asyncio.create_task(main.console(
                live=True, discord=True, voice=True, vts=True))
            try:
                await asyncio.wait_for(sent.wait(), 2)
                await asyncio.wait_for(spoken.wait(), 2)
            finally:
                running.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await running
        self.assertEqual(outputs, [("10", "Réponse écrite et vocale", "100")])
        speech.speak.assert_awaited_once()
        vts.trigger_hotkey.assert_awaited_once_with("speak")
        service.close.assert_awaited_once()
