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

    async def play_for_reply(self, data, source):
        self.played.append(data)

    def reply_authorized(self, source):
        return True


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

    async def test_cross_source_broadcast_is_rejected_until_session_routing_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            with self.assertRaises(ValueError):
                SpeechOutput(_Services(), local, Path(directory) / "subtitle.txt",
                             secondary_player=discord, secondary_broadcast=True)

    def test_broadcast_requires_explicit_voice_setup(self):
        with self.assertRaises(ValueError):
            Settings(discord_voice_broadcast=True).validate()
        settings = Settings(discord_enabled=True, discord_token="test",
                            discord_voice_enabled=True, discord_voice_channel=123,
                            discord_voice_consent=True, discord_voice_allowed_users=(1,),
                            discord_voice_broadcast=True)
        with self.assertRaises(ValueError):
            settings.validate()

    def test_setting_is_loaded_and_defaults_off(self):
        with patch("src.jade_runtime.config.environ", side_effect=lambda name, default: {
            "JADE_DISCORD_ENABLED": "1", "DISCORD_TOKEN": "test",
            "JADE_DISCORD_VOICE_ENABLED": "1", "DISCORD_VOICE_CHANNEL": "123",
            "JADE_DISCORD_VOICE_CONSENT": "1", "JADE_DISCORD_VOICE_ALLOWED_USERS": "1",
        }.get(name, default)):
            self.assertFalse(Settings.load().discord_voice_broadcast)
        with patch("src.jade_runtime.config.environ", side_effect=lambda name, default: {
            "JADE_DISCORD_ENABLED": "1", "DISCORD_TOKEN": "test",
            "JADE_DISCORD_VOICE_ENABLED": "1", "DISCORD_VOICE_CHANNEL": "123",
            "JADE_DISCORD_VOICE_CONSENT": "1", "JADE_DISCORD_VOICE_ALLOWED_USERS": "1",
            "JADE_DISCORD_VOICE_BROADCAST": "1",
        }.get(name, default)):
            with self.assertRaises(ValueError):
                Settings.load()

    async def test_main_routes_voice_reply_through_session_aware_bridge(self):
        with tempfile.TemporaryDirectory() as directory:
            received = asyncio.Event()
            config = Settings(api_key="test", discord_enabled=True, discord_token="test",
                              discord_voice_enabled=True, discord_voice_channel=123,
                              discord_voice_consent=True, discord_voice_allowed_users=(1,),
                              subtitle_path=Path(directory) / "subtitle.txt")
            service = SimpleNamespace(client=SimpleNamespace(close=AsyncMock()),
                                      complete=AsyncMock(return_value="synthetic"),
                                      synthesize_wav=AsyncMock(return_value=b"synthetic wav"))

            class Bridge:
                def __init__(self, *_args, **_kwargs):
                    pass

                def reply_authorized(self, _source):
                    return True

                async def play_for_reply(self, _wav, _source):
                    received.set()

            class Connector:
                def __init__(self, _token, on_message, **_kwargs):
                    self.on_message = on_message

                async def connect_forever(self):
                    await self.on_message(Incoming("discord_voice", "test", "question",
                                                   channel="123", speaker_id=1,
                                                   voice_session_id="a" * 32,
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

    async def test_revoked_session_rejected_before_synthesis_or_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            discord.reply_authorized = lambda _source: False
            services = SimpleNamespace(synthesize_wav=AsyncMock(return_value=b"wav"))
            subtitle = Path(directory) / "subtitle.txt"
            output = SpeechOutput(services, local, subtitle, secondary_player=discord)
            source = Incoming("discord_voice", "test", "question", channel="123",
                              speaker_id=1, voice_session_id="a" * 32)
            with self.assertRaises(PermissionError):
                await output.speak(Reply(source, "answer"))
            services.synthesize_wav.assert_not_awaited()
            self.assertFalse(subtitle.exists())
            self.assertEqual(local.played, [])
            self.assertEqual(discord.played, [])

    async def test_revocation_during_playback_stops_local_and_clears_subtitle(self):
        with tempfile.TemporaryDirectory() as directory:
            started, stopped = asyncio.Event(), asyncio.Event()
            class Local:
                async def play(self, _wav):
                    started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        stopped.set()
            class Discord:
                allowed = True
                def reply_authorized(self, _source):
                    return self.allowed
                async def play_for_reply(self, _wav, _source):
                    await asyncio.Event().wait()
            discord = Discord()
            subtitle = Path(directory) / "subtitle.txt"
            output = SpeechOutput(_Services(), Local(), subtitle, secondary_player=discord)
            source = Incoming("discord_voice", "test", "question", channel="123",
                              speaker_id=1, voice_session_id="a" * 32)
            task = asyncio.create_task(output.speak(Reply(source, "answer")))
            await asyncio.wait_for(started.wait(), timeout=1)
            discord.allowed = False
            with self.assertRaises(ExceptionGroup):
                await asyncio.wait_for(task, timeout=1)
            self.assertTrue(stopped.is_set())
            self.assertEqual(subtitle.read_text(encoding="utf-8"), "")

    async def test_revocation_during_synthesis_produces_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            async def synthesize(_text):
                discord.reply_authorized = lambda _source: False
                return b"wav"
            services = SimpleNamespace(synthesize_wav=synthesize)
            subtitle = Path(directory) / "subtitle.txt"
            output = SpeechOutput(services, local, subtitle, secondary_player=discord)
            source = Incoming("discord_voice", "test", "question", channel="123",
                              speaker_id=1, voice_session_id="a" * 32)
            with self.assertRaises(PermissionError):
                await output.speak(Reply(source, "answer"))
            self.assertFalse(subtitle.exists())
            self.assertEqual(local.played, [])
            self.assertEqual(discord.played, [])


if __name__ == "__main__":
    unittest.main()
