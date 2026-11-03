"""Opt-in routing of synthesized replies to the Discord voice bridge."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import main
from src.jade_runtime.config import Settings
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.output import SpeechOutput


class _Services:
    async def synthesize_wav(self, text):
        return b"synthetic wav"


class _Player:
    def __init__(self):
        self.played = []

    async def play(self, data):
        self.played.append(data)


class DiscordVoiceRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_only_sends_discord_voice_replies_to_discord(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            output = SpeechOutput(_Services(), local, Path(directory) / "subtitle.txt",
                                  secondary_player=discord)
            for source in ("discord_voice", "discord", "twitch", "console", "http"):
                await output.speak(Reply(Incoming(source, "test", "question"), "answer"))
            self.assertEqual(len(local.played), 5)
            self.assertEqual(len(discord.played), 1)

    async def test_explicit_broadcast_routes_other_sources_to_discord(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            output = SpeechOutput(_Services(), local, Path(directory) / "subtitle.txt",
                                  secondary_player=discord, secondary_broadcast=True)
            for source in ("discord_voice", "discord", "twitch", "console", "http"):
                await output.speak(Reply(Incoming(source, "test", "question"), "answer"))
            self.assertEqual(len(local.played), 5)
            self.assertEqual(len(discord.played), 5)

    def test_broadcast_requires_explicit_voice_setup(self):
        with self.assertRaises(ValueError):
            Settings(discord_voice_broadcast=True).validate()
        settings = Settings(discord_enabled=True, discord_token="test",
                            discord_voice_enabled=True, discord_voice_channel=123,
                            discord_voice_broadcast=True)
        settings.validate()

    def test_setting_is_loaded_and_defaults_off(self):
        with patch("src.jade_runtime.config.environ", side_effect=lambda name, default: {
            "JADE_DISCORD_ENABLED": "1", "DISCORD_TOKEN": "test",
            "JADE_DISCORD_VOICE_ENABLED": "1", "DISCORD_VOICE_CHANNEL": "123",
        }.get(name, default)):
            self.assertFalse(Settings.load().discord_voice_broadcast)
        with patch("src.jade_runtime.config.environ", side_effect=lambda name, default: {
            "JADE_DISCORD_ENABLED": "1", "DISCORD_TOKEN": "test",
            "JADE_DISCORD_VOICE_ENABLED": "1", "DISCORD_VOICE_CHANNEL": "123",
            "JADE_DISCORD_VOICE_BROADCAST": "1",
        }.get(name, default)):
            self.assertTrue(Settings.load().discord_voice_broadcast)

    async def test_main_routes_discord_text_reply_with_broadcast_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            received = asyncio.Event()
            config = Settings(api_key="test", discord_enabled=True, discord_token="test",
                              discord_voice_enabled=True, discord_voice_channel=123,
                              discord_voice_broadcast=True,
                              subtitle_path=Path(directory) / "subtitle.txt")
            service = SimpleNamespace(client=SimpleNamespace(close=AsyncMock()),
                                      complete=AsyncMock(return_value="synthetic"),
                                      synthesize_wav=AsyncMock(return_value=b"synthetic wav"))

            class Bridge:
                def __init__(self, *_args):
                    pass

                async def play(self, _wav):
                    received.set()

            class Connector:
                def __init__(self, _token, on_message, **_kwargs):
                    self.on_message = on_message

                async def connect_forever(self):
                    await self.on_message(Incoming("discord", "test", "question",
                                                   force_reply=True))
                    await asyncio.Event().wait()

                async def send_chat(self, _channel, _text):
                    return False

            with patch.object(main.Settings, "load", return_value=config), \
                 patch.object(main, "OpenAIServices", return_value=service), \
                 patch("src.jade_runtime.discord_voice.DiscordVoiceBridge", Bridge), \
                 patch("src.jade_runtime.discord_text.DiscordText", Connector):
                task = asyncio.create_task(main.console(live=True, voice=True,
                                                         discord=True, discord_voice=True))
                try:
                    await asyncio.wait_for(received.wait(), timeout=2)
                finally:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task


if __name__ == "__main__":
    unittest.main()
