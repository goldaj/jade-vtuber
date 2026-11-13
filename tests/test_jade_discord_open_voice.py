"""Open Discord voice mode; synthetic PCM, no connection or audio device."""
import asyncio
import struct
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.jade_runtime.discord_voice import OpenVoiceBridge, _ffmpeg_source
from src.jade_runtime.discord_text import DiscordText


def pcm(seconds, level):
    return struct.pack("<hh", level, level) * int(48000 * seconds)


class Channel:
    def __init__(self, channel_id):
        self.id = channel_id
        self.connect = AsyncMock()

    @property
    def members(self):
        raise AssertionError("open voice must not inspect participants")

    @property
    def voice_states(self):
        raise AssertionError("open voice must not validate membership")


class OpenVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        recv = types.ModuleType("discord.ext.voice_recv")
        recv.VoiceRecvClient = object
        recv.AudioSink = type("AudioSink", (), {})
        discord, ext = types.ModuleType("discord"), types.ModuleType("discord.ext")
        discord.ext, ext.voice_recv = ext, recv
        dave = types.ModuleType("src.jade_runtime.discord_dave")
        dave.DaveVoiceRecvClient = type("DaveVoiceRecvClient", (), {})
        self.dave_class = dave.DaveVoiceRecvClient
        self.modules = patch.dict("sys.modules", {"discord": discord, "discord.ext": ext,
            "discord.ext.voice_recv": recv, "src.jade_runtime.discord_dave": dave})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.channel = Channel(45)
        self.connection = types.SimpleNamespace(channel=self.channel, listen=Mock(),
            stop=Mock(), stop_playing=Mock(), stop_listening=Mock(), disconnect=AsyncMock())
        self.channel.connect.return_value = self.connection
        self.client = types.SimpleNamespace(get_channel=lambda _: self.channel,
                                             user=types.SimpleNamespace(id=100, bot=True))
        self.services = types.SimpleNamespace(transcribe_wav=AsyncMock(return_value="Salut !"))
        self.runtime = types.SimpleNamespace(submit=AsyncMock(), cancel_work=Mock())
        self.bridge = OpenVoiceBridge(self.services, self.runtime, 45)
        self.addAsyncCleanup(self.bridge.close)
        await self.bridge.connect(self.client)

    async def utterance(self, uid, text="Salut !"):
        self.services.transcribe_wav.return_value = text
        self.bridge.receive_pcm(uid, "Visiteur", pcm(.25, 1800) + pcm(.8, 0))
        await asyncio.sleep(.04)
        await self.bridge.pending.join()

    async def test_interrupt_while_playing_and_resume_cross_source(self):
        bridge = self.bridge
        bridge._begin_playback(self.connection, bridge.generation, bridge.session_id)
        await self.utterance(12, "parole ordinaire")
        self.assertEqual(self.runtime.submit.await_count, 0)
        await self.utterance(12, "silence")
        self.assertTrue(bridge._decider.is_muted(bridge.session_id))
        self.connection.stop_playing.assert_called()
        self.assertIsNone(bridge.delivery_context())
        with self.assertRaises(PermissionError):
            await bridge._require_playback_authorization(self.connection, bridge.generation, bridge.session_id)
        self.assertIs(bridge.connection, self.connection)
        bridge._end_playback()
        await self.utterance(12, "reprends")
        self.assertFalse(bridge._decider.is_muted(bridge.session_id))
        self.assertIsNotNone(bridge.delivery_context())
        await self.utterance(12, "Comment vas-tu ?")
        self.assertEqual(self.runtime.submit.await_count, 1)

    async def test_interrupt_transcription_finishes_after_playback(self):
        bridge = self.bridge
        started, release = asyncio.Event(), asyncio.Event()
        async def transcribe(_):
            started.set()
            await release.wait()
            return "silence"
        self.services.transcribe_wav.side_effect = transcribe
        bridge._begin_playback(self.connection, bridge.generation, bridge.session_id)
        bridge.receive_pcm(12, "Visiteur", pcm(.25, 1800) + pcm(.8, 0))
        await asyncio.wait_for(started.wait(), 1)
        bridge._end_playback()
        # Streaming sentences can begin a new playback before this STT returns.
        bridge._begin_playback(self.connection, bridge.generation, bridge.session_id)
        release.set()
        await asyncio.sleep(.04)
        await bridge.pending.join()
        self.assertTrue(bridge._decider.is_muted(bridge.session_id))
        bridge._end_playback()

    async def test_stop_turn_crosses_end_of_playback(self):
        bridge = self.bridge
        self.services.transcribe_wav.return_value = "silence"
        bridge._begin_playback(self.connection, bridge.generation, bridge.session_id)
        bridge.receive_pcm(12, "Visiteur", pcm(.25, 1800))
        bridge._end_playback()
        bridge.receive_pcm(12, "Visiteur", pcm(.8, 0))
        await asyncio.sleep(.04)
        await bridge.pending.join()
        self.assertTrue(bridge._decider.is_muted(bridge.session_id))
        self.runtime.submit.assert_not_awaited()

    async def test_ordinary_turn_crossing_end_is_not_sent_to_dialogue(self):
        bridge = self.bridge
        self.services.transcribe_wav.return_value = "parole ordinaire"
        bridge._begin_playback(self.connection, bridge.generation, bridge.session_id)
        bridge.receive_pcm(12, "Visiteur", pcm(.25, 1800))
        bridge._end_playback()
        bridge.receive_pcm(12, "Visiteur", pcm(.8, 0))
        await asyncio.sleep(.04)
        await bridge.pending.join()
        self.services.transcribe_wav.assert_awaited_once()
        self.runtime.submit.assert_not_awaited()

    async def test_queued_stop_survives_end_of_playback(self):
        bridge = self.bridge
        started, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def transcribe(_):
            nonlocal calls
            calls += 1
            if calls == 1:
                started.set()
                await release.wait()
                return "parole ordinaire"
            return "silence"

        self.services.transcribe_wav.side_effect = transcribe
        bridge._begin_playback(self.connection, bridge.generation, bridge.session_id)
        bridge.receive_pcm(12, "Visiteur", pcm(.25, 1800) + pcm(.8, 0))
        await asyncio.wait_for(started.wait(), 1)
        bridge.receive_pcm(13, "Visiteur", pcm(.25, 1800) + pcm(.8, 0))
        await asyncio.sleep(.04)
        self.assertEqual(bridge.pending.qsize(), 1)
        bridge._end_playback()
        release.set()
        await asyncio.wait_for(bridge.pending.join(), 1)
        self.assertTrue(bridge._decider.is_muted(bridge.session_id))
        self.runtime.submit.assert_not_awaited()

    async def test_no_membership_check_and_group_speaks_without_name(self):
        self.channel.connect.assert_awaited_once_with(cls=self.dave_class)
        await self.utterance(12, "Comment vas-tu ?")
        await self.utterance(13, "Et demain ?")
        self.assertEqual(self.runtime.submit.await_count, 2)
        self.assertTrue(all(call.args[0].force_reply for call in self.runtime.submit.await_args_list))
        self.assertIs(self.bridge.connection, self.connection)

    async def test_other_bots_are_received_but_jades_own_voice_is_ignored(self):
        sink = self.connection.listen.call_args.args[0]
        payload = types.SimpleNamespace(pcm=pcm(.25, 1800) + pcm(.8, 0))
        sink.write(types.SimpleNamespace(id=200, bot=True, display_name="Bot"), payload)
        sink.write(types.SimpleNamespace(id=100, bot=True, display_name="Jade"), payload)
        await asyncio.sleep(.04)
        await self.bridge.pending.join()
        self.assertEqual(self.runtime.submit.await_count, 1)
        self.assertEqual(self.runtime.submit.await_args.args[0].speaker_id, 200)

    async def test_other_users_join_and_leave_without_revocation(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def pending(_):
            started.set()
            await release.wait()
            return "Bonjour"
        self.services.transcribe_wav.side_effect = pending
        self.bridge.receive_pcm(12, "A", pcm(.25, 1800) + pcm(.8, 0))
        await asyncio.wait_for(started.wait(), 1)
        generation = self.bridge.generation
        await self.bridge.voice_state_changed(types.SimpleNamespace(id=200, bot=True),
            types.SimpleNamespace(channel=None), types.SimpleNamespace(channel=self.channel), own_bot_id=100)
        await self.bridge.voice_state_changed(types.SimpleNamespace(id=12, bot=False),
            types.SimpleNamespace(channel=self.channel), types.SimpleNamespace(channel=None), own_bot_id=100)
        self.assertEqual(self.bridge.generation, generation)
        self.assertIs(self.bridge.connection, self.connection)
        release.set()
        await asyncio.sleep(.04)
        await self.bridge.pending.join()
        self.assertEqual(self.runtime.submit.await_count, 1)

    async def test_move_invalidates_only_old_transport_and_follows_new_channel(self):
        await self.utterance(12)
        old_source = self.runtime.submit.await_args.args[0]
        old_context = self.bridge.delivery_context()
        target = Channel(46)
        self.connection.channel = target
        self.assertFalse(self.bridge.delivery_context_valid(old_context))
        self.assertFalse(self.bridge.reply_authorized(old_source))
        new_context = self.bridge.delivery_context()
        self.assertIsNotNone(new_context)
        await self.utterance(200)
        self.assertEqual(self.runtime.submit.await_args.args[0].channel, "46")
        self.connection.disconnect.assert_not_awaited()
        with self.assertRaises(PermissionError):
            await self.bridge.play_for_context(b"wav", old_context)

    async def test_bot_move_event_before_cache_update_waits_and_then_continues(self):
        generation = self.bridge.generation
        target = Channel(47)
        await self.bridge.voice_state_changed(types.SimpleNamespace(id=100, bot=True),
            types.SimpleNamespace(channel=self.channel), types.SimpleNamespace(channel=target), own_bot_id=100)
        self.assertGreater(self.bridge.generation, generation)
        await self.utterance(12)
        self.services.transcribe_wav.assert_not_awaited()
        self.connection.channel = target
        await self.utterance(12)
        self.assertEqual(self.runtime.submit.await_args.args[0].channel, "47")

    async def test_reconnect_creates_new_context_without_reauthorization(self):
        old_context = self.bridge.delivery_context()
        await self.bridge.close()
        await self.bridge.connect(self.client)
        self.assertFalse(self.bridge.delivery_context_valid(old_context))
        await self.utterance(12)
        self.assertEqual(self.runtime.submit.await_count, 1)

    async def test_disconnect_during_connect_discards_stale_connection(self):
        await self.bridge.close()
        self.connection.disconnect.reset_mock()
        self.connection.listen.reset_mock()
        started, release = asyncio.Event(), asyncio.Event()

        async def delayed_connect(**kwargs):
            started.set()
            await release.wait()
            return self.connection

        self.channel.connect.side_effect = delayed_connect
        connecting = asyncio.create_task(self.bridge.connect(self.client))
        await started.wait()
        self.bridge.set_session([], consent_confirmed=False)
        release.set()
        with self.assertRaisesRegex(RuntimeError, "changed during startup"):
            await connecting
        self.connection.disconnect.assert_awaited_once()
        self.connection.listen.assert_not_called()
        self.assertIsNone(self.bridge.delivery_context())

    async def test_cross_source_playback_is_bound_to_active_connection(self):
        context = self.bridge.delivery_context()
        with patch.object(self.bridge, "play", new_callable=AsyncMock, return_value=True) as play:
            self.assertTrue(await self.bridge.play_for_context(b"wav", context))
            play.assert_awaited_once_with(b"wav", expected_session=context.session_id)

    async def test_playback_and_move_keep_voice_receiving(self):
        self.connection.is_playing = Mock(return_value=False)
        self.connection.play = Mock(side_effect=lambda source, after: after(None))
        source = types.SimpleNamespace(cleanup=Mock())
        observer = Mock()
        self.bridge.playback_observer = observer
        with patch("src.jade_runtime.discord_voice._ffmpeg_source", return_value=source):
            self.assertTrue(await self.bridge.play(b"synthetic wav"))
        self.connection.stop_playing.assert_called_once()
        self.connection.stop.assert_not_called()
        self.connection.stop_listening.assert_not_called()
        self.assertEqual(observer.call_args_list, [unittest.mock.call("start", b"synthetic wav"),
                                                   unittest.mock.call("end", b"synthetic wav")])
        self.connection.channel = Channel(46)
        self.assertFalse(self.bridge.delivery_context_valid(self.bridge.delivery_context()))
        self.connection.stop.assert_not_called()
        self.connection.stop_listening.assert_not_called()
        await self.utterance(12)
        self.assertEqual(self.runtime.submit.await_count, 1)

    async def test_playback_observer_failure_does_not_break_audio(self):
        self.connection.is_playing = Mock(return_value=False)
        self.connection.play = Mock(side_effect=lambda source, after: after(None))
        self.bridge.playback_observer = Mock(side_effect=RuntimeError("observer failure"))
        with patch("src.jade_runtime.discord_voice._ffmpeg_source", return_value=types.SimpleNamespace(cleanup=Mock())):
            with self.assertLogs("jade.discord.voice", level="WARNING"):
                self.assertTrue(await self.bridge.play(b"synthetic wav"))
        self.assertEqual(self.bridge.playback_observer.call_count, 2)

    async def test_resumed_gateway_reconnects_voice_without_new_ready(self):
        class Client:
            def __init__(self, **kwargs):
                self.user = types.SimpleNamespace(id=100)

            async def start(self, token):
                await self.on_ready()
                await self.on_disconnect()
                await self.on_resumed()

            async def close(self):
                pass

            def get_channel(inner_self, channel_id):
                return self.channel

        fake_discord = __import__("discord")
        fake_discord.Client = Client
        fake_discord.Intents = types.SimpleNamespace(default=lambda: types.SimpleNamespace())
        fake_discord.AllowedMentions = types.SimpleNamespace(none=lambda: None)
        await self.bridge.close()
        connector = DiscordText("synthetic", AsyncMock(), voice_bridge=self.bridge)
        await connector.connect_forever()
        self.assertEqual(self.channel.connect.await_count, 3)  # setup, ready, resume
        self.assertEqual(self.connection.listen.call_count, 3)

    async def test_ffmpeg_child_environment_excludes_credentials(self):
        seen = {}

        class FakeFFmpeg:
            def __init__(self, path):
                self._spawn_process([path], stdin=None)

            def _spawn_process(self, args, **kwargs):
                seen.update(kwargs)

        with patch.dict("sys.modules", {"discord": types.SimpleNamespace(FFmpegPCMAudio=FakeFFmpeg)}):
            with patch.dict("os.environ", {"PATH": "synthetic-path", "OPENAI_API_KEY": "do-not-forward",
                                          "DISCORD_TOKEN": "do-not-forward", "TWITCH_TOKEN": "do-not-forward"}):
                _ffmpeg_source("synthetic.wav")
        self.assertEqual(seen["env"]["PATH"], "synthetic-path")
        for secret in ("OPENAI_API_KEY", "DISCORD_TOKEN", "TWITCH_TOKEN"):
            self.assertNotIn(secret, seen["env"])


if __name__ == "__main__":
    unittest.main()
