"""Routing synthesized replies to the currently connected Discord voice bridge."""
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

    def delivery_context(self):
        return self

    def delivery_context_valid(self, context):
        return context is self

    async def play_for_context(self, data, context):
        self.played.append(data)
        return True


class DiscordVoiceRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_sends_all_spoken_replies_once_to_connected_voice(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            output = SpeechOutput(_Services(), local, Path(directory) / "subtitle.txt",
                                  secondary_player=discord)
            for source in ("discord_voice", "discord", "twitch", "console", "http"):
                await output.speak(Reply(Incoming(source, "test", "question"), "answer"))
            self.assertEqual(len(local.played), 5)
            self.assertEqual(len(discord.played), 5)

    async def test_legacy_broadcast_flag_has_no_effect(self):
        for legacy in (True, False):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as directory:
                local, discord = _Player(), _Player()
                output = SpeechOutput(_Services(), local, Path(directory) / "subtitle.txt",
                                      secondary_player=discord, secondary_broadcast=legacy)
                await output.speak(Reply(Incoming("twitch", "test", "question"), "answer"))
                self.assertEqual(discord.played, [b"synthetic wav"])

    def test_legacy_broadcast_value_does_not_gate_configuration(self):
        Settings(discord_voice_broadcast=True).validate()
        Settings(discord_voice_broadcast=False).validate()

    def test_old_private_broadcast_value_is_not_loaded(self):
        values = {"JADE_DISCORD_VOICE_BROADCAST": "not-a-boolean"}
        with patch("src.jade_runtime.config.environ", side_effect=lambda name, default: values.get(name, default)):
            Settings.load()

    async def test_no_connection_leaves_local_output_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            discord.delivery_context = lambda: None
            output = SpeechOutput(_Services(), local, Path(directory) / "subtitle.txt",
                                  secondary_player=discord)
            await output.speak(Reply(Incoming("http", "test", "question"), "answer"))
            self.assertEqual(local.played, [b"synthetic wav"])
            self.assertEqual(discord.played, [])

    async def test_changed_destination_during_synthesis_does_not_receive_stale_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            valid = True
            discord.delivery_context_valid = lambda _context: valid
            async def synthesize(_text):
                nonlocal valid
                valid = False
                return b"wav"
            services = SimpleNamespace(synthesize_wav=synthesize)
            output = SpeechOutput(services, local, Path(directory) / "subtitle.txt",
                                  secondary_player=discord)
            await output.speak(Reply(Incoming("twitch", "test", "question"), "answer"))
            self.assertEqual(local.played, [b"wav"])
            self.assertEqual(discord.played, [])

    async def test_changed_destination_stops_discord_but_not_local_playback(self):
        with tempfile.TemporaryDirectory() as directory:
            started, stopped, local_started, local_release = (asyncio.Event() for _ in range(4))
            class Local:
                cancelled = False
                async def play(self, _wav):
                    local_started.set()
                    try:
                        await local_release.wait()
                    except asyncio.CancelledError:
                        self.cancelled = True
                        raise
            class Discord(_Player):
                valid = True
                def delivery_context_valid(self, context):
                    return context is self and self.valid
                async def play_for_context(self, _wav, _context):
                    started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        stopped.set()
            local, discord = Local(), Discord()
            subtitle = Path(directory) / "subtitle.txt"
            output = SpeechOutput(_Services(), local, subtitle, secondary_player=discord)
            task = asyncio.create_task(output.speak(Reply(Incoming("discord", "test", "q"), "answer")))
            await asyncio.wait_for(started.wait(), 1)
            await asyncio.wait_for(local_started.wait(), 1)
            discord.valid = False
            await asyncio.wait_for(stopped.wait(), 1)
            self.assertFalse(local.cancelled)
            self.assertFalse(task.done())
            local_release.set()
            await asyncio.wait_for(task, 1)
            self.assertEqual(subtitle.read_text(encoding="utf-8"), "")

    async def test_discord_failure_does_not_interrupt_local_playback(self):
        with tempfile.TemporaryDirectory() as directory:
            local, discord = _Player(), _Player()
            discord.play_for_context = AsyncMock(side_effect=RuntimeError("synthetic"))
            output = SpeechOutput(_Services(), local, Path(directory) / "subtitle.txt",
                                  secondary_player=discord)
            await output.speak(Reply(Incoming("console", "test", "q"), "answer"))
            self.assertEqual(local.played, [b"synthetic wav"])
            discord.play_for_context.assert_awaited_once()

    async def test_cross_source_uses_real_bridge_context_contract(self):
        from src.jade_runtime.discord_voice import OpenVoiceBridge
        with tempfile.TemporaryDirectory() as directory:
            local = _Player()
            bridge = OpenVoiceBridge(None, None, 123)
            bridge.connection = SimpleNamespace(channel=SimpleNamespace(id=123))
            bridge.consent_confirmed = True  # internal active-connection state
            bridge.own_bot_id = 42
            bridge.session_id = "a" * 32
            bridge.play = AsyncMock(return_value=True)
            output = SpeechOutput(_Services(), local, Path(directory) / "subtitle.txt",
                                  secondary_player=bridge)
            await output.speak(Reply(Incoming("twitch", "test", "q"), "answer"))
            self.assertEqual(local.played, [b"synthetic wav"])
            bridge.play.assert_awaited_once_with(b"synthetic wav", expected_session="a" * 32)

    async def test_cancellation_stops_both_players_and_clears_subtitle(self):
        with tempfile.TemporaryDirectory() as directory:
            started_local, started_discord = asyncio.Event(), asyncio.Event()
            stopped_local, stopped_discord = asyncio.Event(), asyncio.Event()
            class Local:
                async def play(self, _wav):
                    started_local.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        stopped_local.set()
            class Discord(_Player):
                async def play_for_context(self, _wav, _context):
                    started_discord.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        stopped_discord.set()
            subtitle = Path(directory) / "subtitle.txt"
            output = SpeechOutput(_Services(), Local(), subtitle, secondary_player=Discord())
            task = asyncio.create_task(output.speak(Reply(Incoming("http", "test", "q"), "answer")))
            await asyncio.wait_for(asyncio.gather(started_local.wait(), started_discord.wait()), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(stopped_local.is_set())
            self.assertTrue(stopped_discord.is_set())
            self.assertEqual(subtitle.read_text(encoding="utf-8"), "")

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
                 patch("src.jade_runtime.discord_voice.OpenVoiceBridge", Bridge), \
                 patch("src.jade_runtime.discord_text.DiscordText", Connector):
                task = asyncio.create_task(main.console(live=True, voice=True,
                                                         discord=True, discord_voice=True))
                try:
                    await asyncio.wait_for(received.wait(), timeout=2)
                finally:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

    async def test_main_vts_hotkey_starts_with_first_streamed_sentence_once_per_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            submitted, hotkey_started = asyncio.Event(), asyncio.Event()
            speech_calls, runtimes = [], []
            config = Settings(api_key="test", discord_token="test", discord_voice_channel=123,
                              vts_enabled=True, vts_token="test", vts_speak_hotkey="speak",
                              subtitle_path=Path(directory) / "subtitle.txt")

            class Services:
                def __init__(self):
                    self.client = SimpleNamespace(close=AsyncMock())
                    self.close = AsyncMock()

                async def stream_complete(self, _messages):
                    yield "Cette première phrase est assez longue pour être prononcée. "
                    yield "Cette seconde phrase doit aussi être prononcée normalement. "

            class Speech:
                secondary_player = None

                async def speak(self, reply):
                    speech_calls.append(reply.text)
                    if len(speech_calls) == 1:
                        # The hotkey may be slow; speech must already have started.
                        await asyncio.wait_for(hotkey_started.wait(), timeout=3)
                    return True

            async def trigger(_hotkey):
                hotkey_started.set()
                await asyncio.Event().wait()

            vts = SimpleNamespace(trigger_hotkey=AsyncMock(side_effect=trigger))

            class VTSScope:
                def __init__(self, *_args, **_kwargs):
                    pass

                async def __aenter__(self):
                    return vts

                async def __aexit__(self, *_args):
                    pass

            class Bridge:
                def __init__(self, *_args, **_kwargs):
                    pass

            class Connector:
                def __init__(self, _token, on_message, **_kwargs):
                    self.on_message = on_message

                async def connect_forever(self):
                    await self.on_message(Incoming("discord_voice", "test", "question",
                                                   channel="123", speaker_id=1,
                                                   voice_session_id="a" * 32,
                                                   force_reply=True))
                    submitted.set()
                    await asyncio.Event().wait()

            class ObservedRuntime(main.Runtime):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    runtimes.append(self)

            with patch.object(main.Settings, "load", return_value=config), \
                 patch.object(main, "OpenAIServices", return_value=Services()), \
                 patch.object(main, "SpeechOutput", return_value=Speech()), \
                 patch.object(main, "Runtime", ObservedRuntime), \
                 patch("src.jade_runtime.discord_voice.OpenVoiceBridge", Bridge), \
                 patch("src.jade_runtime.discord_text.DiscordText", Connector), \
                 patch("src.jade_runtime.vtube_studio.VTubeStudio", VTSScope):
                task = asyncio.create_task(main.console(live=True, voice=True, vts=True,
                                                         discord=True, discord_voice=True))
                try:
                    await asyncio.wait_for(submitted.wait(), timeout=3)
                    await asyncio.wait_for(runtimes[0].idle(), timeout=3)
                    self.assertEqual(len(speech_calls), 2)
                    vts.trigger_hotkey.assert_awaited_once_with("speak")
                    self.assertTrue(hotkey_started.is_set())
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

    async def test_acknowledges_only_successful_discord_playback(self):
        for result in (True, False, None):
            with self.subTest(result=result), tempfile.TemporaryDirectory() as directory:
                discord = _Player()
                discord.play_for_reply = AsyncMock(return_value=result)
                discord.mark_voice_reply_played = unittest.mock.Mock()
                output = SpeechOutput(_Services(), _Player(), Path(directory) / "subtitle.txt",
                                      secondary_player=discord)
                source = Incoming("discord_voice", "test", "question", channel="123",
                                  speaker_id=1, voice_session_id="a" * 32)
                await output.speak(Reply(source, "answer"))
                if result is True:
                    discord.mark_voice_reply_played.assert_called_once_with(source)
                else:
                    discord.mark_voice_reply_played.assert_not_called()

    async def test_no_acknowledgement_if_session_revoked_during_gate_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            discord = _Player()
            discord.play_for_reply = AsyncMock(return_value=True)
            discord.mark_voice_reply_played = unittest.mock.Mock()
            class Gate:
                async def begin_speech(self):
                    pass
                async def end_speech(self):
                    discord.reply_authorized = lambda _source: False
            subtitle = Path(directory) / "subtitle.txt"
            output = SpeechOutput(_Services(), _Player(), subtitle,
                                  secondary_player=discord, audio_gate=Gate())
            source = Incoming("discord_voice", "test", "question", channel="123",
                              speaker_id=1, voice_session_id="a" * 32)
            with self.assertRaises(PermissionError):
                await output.speak(Reply(source, "answer"))
            discord.mark_voice_reply_played.assert_not_called()
            self.assertEqual(subtitle.read_text(encoding="utf-8"), "")

    async def test_no_acknowledgement_if_local_playback_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            discord = _Player()
            discord.play_for_reply = AsyncMock(return_value=True)
            discord.mark_voice_reply_played = unittest.mock.Mock()
            class FailingLocal:
                async def play(self, _wav):
                    raise RuntimeError("synthetic player failure")
            output = SpeechOutput(_Services(), FailingLocal(), Path(directory) / "subtitle.txt",
                                  secondary_player=discord)
            source = Incoming("discord_voice", "test", "question", channel="123",
                              speaker_id=1, voice_session_id="a" * 32)
            with self.assertRaises(ExceptionGroup):
                await output.speak(Reply(source, "answer"))
            discord.mark_voice_reply_played.assert_not_called()

    async def test_gate_cleanup_failure_still_clears_subtitle(self):
        with tempfile.TemporaryDirectory() as directory:
            discord = _Player()
            discord.play_for_reply = AsyncMock(return_value=True)
            discord.mark_voice_reply_played = unittest.mock.Mock()
            class Gate:
                async def begin_speech(self):
                    pass
                async def end_speech(self):
                    raise RuntimeError("synthetic cleanup failure")
            subtitle = Path(directory) / "subtitle.txt"
            output = SpeechOutput(_Services(), _Player(), subtitle,
                                  secondary_player=discord, audio_gate=Gate())
            source = Incoming("discord_voice", "test", "question", channel="123",
                              speaker_id=1, voice_session_id="a" * 32)
            with self.assertRaises(RuntimeError):
                await output.speak(Reply(source, "answer"))
            self.assertEqual(subtitle.read_text(encoding="utf-8"), "")
            discord.mark_voice_reply_played.assert_not_called()


if __name__ == "__main__":
    unittest.main()
