"""Discord vocal: autorisation explicite avant toute donnée ou transcription."""
import asyncio
from array import array
import sys
import threading
import types
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.jade_runtime.discord_voice import DiscordVoiceBridge, PCM_CHUNK_BYTES, _VoiceChunk
from src.jade_runtime.discord_text import DiscordText
from src.jade_runtime.orchestrator import Runtime, Work
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming


def loud():
    return array("h", [1500] * (48000 * 2)).tobytes() + bytes(48000 * 4)


def channel_with_members(members, connect=None):
    channel = SimpleNamespace(id=45, members=members, connect=connect)
    channel.voice_states = {member.id: SimpleNamespace(channel=channel)
                            for member in (members or [])}
    return channel


def client_for(channel):
    return SimpleNamespace(get_channel=lambda _: channel, user=SimpleNamespace(id=100, bot=True))


def attach_connection(bridge, user_ids=(12,)):
    channel = channel_with_members([SimpleNamespace(id=uid, bot=False) for uid in user_ids])
    bridge.connection = SimpleNamespace(channel=channel, stop=Mock(), stop_listening=Mock(),
                                        disconnect=AsyncMock())
    bridge.own_bot_id = 100
    return channel


class DiscordVoiceConsentTests(unittest.IsolatedAsyncioTestCase):
    async def test_frame_authorized_before_session_change_cannot_enter_new_session(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        previous = bridge.session_id
        authorize = bridge._capture_authorized
        def change_session(*args):
            result = authorize(*args)
            bridge.set_session([12], consent_confirmed=True)
            return result
        with patch.object(bridge, "_capture_authorized", side_effect=change_session):
            bridge.receive_pcm(12, "Participant", bytes(4))
        self.assertNotEqual(bridge.session_id, previous)
        self.assertEqual(bridge.buffers, {})
        await bridge.close()

    async def test_frame_authorized_before_playback_transition_is_not_buffered_afterward(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        authorize = bridge._capture_authorized
        def playback_transition(*args):
            result = authorize(*args)
            bridge._begin_playback(bridge.connection, bridge.generation, bridge.session_id)
            bridge._end_playback()
            return result
        with patch.object(bridge, "_capture_authorized", side_effect=playback_transition):
            bridge.receive_pcm(12, "Participant", bytes(4))
        self.assertEqual(bridge.buffers, {})
        await bridge.close()

    async def test_queued_frame_cannot_enter_after_session_changes_during_validation(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.worker = SimpleNamespace(done=lambda: False)
        item = _VoiceChunk(12, "Participant", loud(), bridge.generation,
                           bridge.session_id, bridge._audio_epoch)
        authorize = bridge._capture_authorized
        def change_session(*args):
            result = authorize(*args)
            bridge.set_session([12], consent_confirmed=True)
            return result
        with patch.object(bridge, "_capture_authorized", side_effect=change_session):
            bridge._accept(item)
        self.assertTrue(bridge.pending.empty())
        bridge.worker = None
        await bridge.close()

    async def test_unannounced_unresolved_participant_revokes_before_pcm_storage(self):
        services, runtime = AsyncMock(), AsyncMock()
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        channel = attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        channel.voice_states[13] = SimpleNamespace(channel=channel)  # No Gateway callback.
        await asyncio.to_thread(bridge.receive_pcm, 12, "Participant", loud())
        self.assertFalse(bridge.consent_confirmed)
        self.assertEqual(bridge.buffers, {})
        services.transcribe_wav.assert_not_awaited()
        runtime.submit.assert_not_awaited()
        await asyncio.sleep(0)
        await bridge.close()

    async def test_unannounced_resolved_unauthorized_participant_revokes_before_capture(self):
        services, runtime = AsyncMock(), AsyncMock()
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        channel = attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        channel.members.append(SimpleNamespace(id=13, bot=False))
        channel.voice_states[13] = SimpleNamespace(channel=channel)
        bridge.receive_pcm(13, "Autre", loud())
        self.assertFalse(bridge.consent_confirmed)
        self.assertEqual(bridge.buffers, {})
        services.transcribe_wav.assert_not_awaited()
        await asyncio.sleep(0)
        await bridge.close()

    async def test_snapshot_changed_after_queue_is_rechecked_before_stt(self):
        services, runtime = AsyncMock(), AsyncMock()
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        channel = attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.pending.put_nowait(_VoiceChunk(12, "Participant", loud(), bridge.generation, bridge.session_id))
        channel.voice_states[13] = SimpleNamespace(channel=channel)
        bridge.worker = asyncio.create_task(bridge._consume())
        await asyncio.sleep(.02)
        services.transcribe_wav.assert_not_awaited()
        runtime.submit.assert_not_awaited()
        self.assertFalse(bridge.consent_confirmed)
        await bridge.close()

    async def test_revocation_between_stt_task_creation_and_execution_prevents_provider_call(self):
        services, runtime = AsyncMock(), AsyncMock()
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.pending.put_nowait(_VoiceChunk(12, "Participant", loud(), bridge.generation,
                                             bridge.session_id, bridge._audio_epoch))
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.loop.call_soon(lambda: bridge.set_session([], consent_confirmed=False))
        await asyncio.sleep(.02)
        services.transcribe_wav.assert_not_awaited()
        runtime.submit.assert_not_awaited()
        self.assertFalse(bridge.consent_confirmed)
        await bridge.close()

    async def test_snapshot_read_exception_denies_audio_without_exposing_error(self):
        class UnavailableChannel:
            @property
            def members(self): raise RuntimeError("private diagnostic")
        services, runtime = AsyncMock(), AsyncMock()
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.connection.channel = UnavailableChannel()
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        await asyncio.to_thread(bridge.receive_pcm, 12, "Participant", loud())
        self.assertFalse(bridge.consent_confirmed)
        self.assertEqual(bridge.buffers, {})
        services.transcribe_wav.assert_not_awaited()
        await asyncio.sleep(0)
        await bridge.close()

    async def test_default_and_non_authorized_users_never_store_or_transcribe(self):
        services, runtime = AsyncMock(), AsyncMock()
        bridge = DiscordVoiceBridge(services, runtime, 45)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.receive_pcm(12, "Participant", loud())
        bridge.set_session([12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.receive_pcm(13, "Autre", loud())
        await asyncio.sleep(0)
        self.assertEqual(bridge.buffers, {})
        services.transcribe_wav.assert_not_awaited()
        runtime.submit.assert_not_awaited()
        await bridge.close()

    async def test_connect_without_consent_or_users_fails_before_external_connection(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45)
        client = SimpleNamespace(get_channel=lambda _: self.fail("must not connect"))
        with self.assertRaisesRegex(ValueError, "consent"):
            await bridge.connect(client)
        bridge.set_session([12], consent_confirmed=False)
        with self.assertRaisesRegex(ValueError, "consent"):
            await bridge.connect(client)

    async def test_authorized_turn_has_stable_speaker_and_private_session(self):
        services, runtime = AsyncMock(), AsyncMock()
        services.transcribe_wav.return_value = "Pourquoi ?"
        records = []
        async def save(message): records.append(message)
        runtime.submit.side_effect = save
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.receive_pcm(12, "Participant", loud())
        await asyncio.sleep(.02)
        await bridge.pending.join()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].speaker_id, 12)
        self.assertTrue(records[0].voice_session_id)
        old_session = records[0].voice_session_id
        bridge.set_session([12], consent_confirmed=True)
        bridge.receive_pcm(12, "Participant renommé", loud())
        await asyncio.sleep(.02)
        await bridge.pending.join()
        self.assertEqual(records[1].speaker_id, 12)
        self.assertNotEqual(records[1].voice_session_id, old_session)
        self.assertNotIn(old_session, repr(records[0]))
        await bridge.close()

    async def test_revocation_clears_buffers_cancels_stt_and_drops_queued_audio(self):
        services, runtime = AsyncMock(), AsyncMock()
        started, cancelled = asyncio.Event(), asyncio.Event()
        async def blocked(_):
            started.set()
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        services.transcribe_wav.side_effect = blocked
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.receive_pcm(12, "Participant", loud())
        await asyncio.wait_for(started.wait(), 1)
        bridge.receive_pcm(12, "Participant", loud())
        await asyncio.sleep(0)
        bridge.receive_pcm(12, "Participant", bytes(4))
        bridge.set_session([], consent_confirmed=False)
        await asyncio.wait_for(cancelled.wait(), 1)
        await bridge.pending.join()
        self.assertEqual(bridge.buffers, {})
        runtime.submit.assert_not_awaited()
        self.assertEqual(services.transcribe_wav.await_count, 1)
        await bridge.close()

    async def test_revocation_cancels_already_submitted_runtime_work(self):
        services = AsyncMock()
        services.transcribe_wav.return_value = "Bonjour"
        work = Work(Incoming("discord_voice", "Participant", "Bonjour"))
        runtime = SimpleNamespace(submit=AsyncMock(return_value=work), cancel_work=lambda w: setattr(w, "cancelled", True))
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.receive_pcm(12, "Participant", loud())
        await asyncio.sleep(.02)
        await bridge.pending.join()
        self.assertFalse(work.cancelled)
        bridge.set_session([], consent_confirmed=False)
        await asyncio.sleep(0)
        self.assertTrue(work.cancelled)
        await bridge.close()

    async def test_revocation_cancels_inflight_dialogue_before_any_output(self):
        started, cancelled = asyncio.Event(), asyncio.Event()
        async def complete(_):
            started.set()
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        output = AsyncMock()
        runtime = Runtime(Dialogue(SimpleNamespace(complete=complete), "synthetic"), output)
        await runtime.start()
        services = SimpleNamespace(transcribe_wav=AsyncMock(return_value="Bonjour Jade"))
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        try:
            bridge.receive_pcm(12, "Participant", loud())
            await asyncio.wait_for(started.wait(), 1)
            bridge.set_session([], consent_confirmed=False)
            await asyncio.wait_for(cancelled.wait(), 1)
            await asyncio.sleep(0)
            output.assert_not_awaited()
        finally:
            await bridge.close()
            await runtime.stop(graceful=False)

    async def test_invalid_ids_do_not_enable_session(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45)
        for ids, consent in [([True], True), ([0], True), ("12", True), ([12], 1)]:
            with self.assertRaises(ValueError):
                bridge.set_session(ids, consent_confirmed=consent)
        self.assertFalse(bridge.consent_confirmed)

    async def test_revocation_while_connecting_never_starts_listener(self):
        ready, release = asyncio.Event(), asyncio.Event()
        connection = SimpleNamespace(listen=Mock(), disconnect=AsyncMock())
        async def connect(**kwargs):
            ready.set()
            await release.wait()
            return connection
        channel = channel_with_members([SimpleNamespace(id=12, bot=False)], connect)
        client = client_for(channel)
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        recv = types.ModuleType('discord.ext.voice_recv')
        recv.VoiceRecvClient = object
        recv.AudioSink = type('AudioSink', (), {})
        discord, ext = types.ModuleType('discord'), types.ModuleType('discord.ext')
        discord.ext, ext.voice_recv = ext, recv
        with patch.dict(sys.modules, {'discord': discord, 'discord.ext': ext,
                                      'discord.ext.voice_recv': recv}):
            task = asyncio.create_task(bridge.connect(client))
            await asyncio.wait_for(ready.wait(), 1)
            bridge.set_session([], consent_confirmed=False)
            release.set()
            with self.assertRaisesRegex(ValueError, "authorization changed"):
                await asyncio.wait_for(task, 1)
        connection.listen.assert_not_called()
        connection.disconnect.assert_awaited_once()

    async def test_join_rejects_unknown_or_unauthorized_channel_members(self):
        recv = types.ModuleType('discord.ext.voice_recv')
        recv.VoiceRecvClient = object
        recv.AudioSink = type('AudioSink', (), {})
        discord, ext = types.ModuleType('discord'), types.ModuleType('discord.ext')
        discord.ext, ext.voice_recv = ext, recv
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        connect = AsyncMock()
        for members in (None, [], [SimpleNamespace(id=13, bot=False)],
                        [SimpleNamespace(id=12, bot=False), SimpleNamespace(id=13, bot=False)]):
            channel = channel_with_members(members, connect)
            client = client_for(channel)
            with patch.dict(sys.modules, {'discord': discord, 'discord.ext': ext,
                                          'discord.ext.voice_recv': recv}):
                with self.assertRaisesRegex(ValueError, "participants"):
                    await bridge.connect(client)
        connect.assert_not_awaited()

    async def test_join_rejects_unresolved_member_in_voice_state_cache(self):
        recv = types.ModuleType('discord.ext.voice_recv')
        recv.VoiceRecvClient = object
        recv.AudioSink = type('AudioSink', (), {})
        discord, ext = types.ModuleType('discord'), types.ModuleType('discord.ext')
        discord.ext, ext.voice_recv = ext, recv
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        connect = AsyncMock()
        channel = channel_with_members([SimpleNamespace(id=12, bot=False)], connect)
        channel.voice_states[13] = SimpleNamespace(channel=channel)
        with patch.dict(sys.modules, {'discord': discord, 'discord.ext': ext,
                                      'discord.ext.voice_recv': recv}):
            with self.assertRaisesRegex(ValueError, "participants"):
                await bridge.connect(client_for(channel))
        connect.assert_not_awaited()

    async def test_membership_snapshot_rejects_missing_or_malformed_voice_states(self):
        member = SimpleNamespace(id=12, bot=False)
        channel = channel_with_members([member])
        self.assertTrue(DiscordVoiceBridge._snapshot_allowed(channel, {12}, 100))
        for states in (None, [], {}, {True: SimpleNamespace(channel=channel)},
                       {12: None}, {12: SimpleNamespace(channel=None)},
                       {12: SimpleNamespace(channel=SimpleNamespace(id=46))}):
            channel.voice_states = states
            self.assertFalse(DiscordVoiceBridge._snapshot_allowed(channel, {12}, 100))
        del channel.voice_states
        self.assertFalse(DiscordVoiceBridge._snapshot_allowed(channel, {12}, 100))

    async def test_membership_rejects_other_bots_and_missing_own_identity(self):
        human = SimpleNamespace(id=12, bot=False)
        own_bot = SimpleNamespace(id=100, bot=True)
        other_bot = SimpleNamespace(id=101, bot=True)
        self.assertTrue(DiscordVoiceBridge._snapshot_allowed(channel_with_members([human, own_bot]), {12}, 100))
        self.assertFalse(DiscordVoiceBridge._snapshot_allowed(channel_with_members([human, other_bot]), {12}, 100))
        self.assertFalse(DiscordVoiceBridge._snapshot_allowed(channel_with_members([human]), {12}, None))
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        with self.assertRaisesRegex(ValueError, "identity"):
            await bridge.connect(SimpleNamespace(user=None))

    async def test_new_session_on_active_connection_requires_valid_membership(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        bridge.connection = SimpleNamespace(channel=channel_with_members(
            [SimpleNamespace(id=12, bot=False), SimpleNamespace(id=13, bot=False)]))
        bridge.own_bot_id = 100
        with self.assertRaisesRegex(ValueError, "participants"):
            bridge.set_session([12], consent_confirmed=True)
        self.assertFalse(bridge.consent_confirmed)
        self.assertEqual(bridge.authorized_user_ids, frozenset())

    async def test_playback_rejects_unresolved_participant_before_start(self):
        channel = channel_with_members([SimpleNamespace(id=12, bot=False)])
        channel.voice_states[13] = SimpleNamespace(channel=channel)
        connection = SimpleNamespace(channel=channel, stop=Mock(), play=Mock(),
                                     stop_listening=Mock(), disconnect=AsyncMock())
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        bridge.connection = connection
        bridge.own_bot_id = 100
        with self.assertRaisesRegex(PermissionError, "authorization"):
            await bridge.play(b"synthetic-wav")
        connection.play.assert_not_called()
        connection.disconnect.assert_awaited_once()
        self.assertFalse(bridge.consent_confirmed)

    async def test_playback_rechecks_snapshot_immediately_before_send(self):
        channel = channel_with_members([SimpleNamespace(id=12, bot=False)])
        connection = SimpleNamespace(channel=channel, stop=Mock(), play=Mock(),
                                     stop_listening=Mock(), disconnect=AsyncMock(),
                                     is_playing=lambda: False)
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        bridge.connection = connection
        bridge.own_bot_id = 100
        source = SimpleNamespace(cleanup=Mock())
        def create(_):
            channel.voice_states[13] = SimpleNamespace(channel=channel)
            return source
        with patch.dict(sys.modules, {"discord": SimpleNamespace(FFmpegPCMAudio=create)}):
            with self.assertRaisesRegex(PermissionError, "authorization"):
                await bridge.play(b"synthetic-wav")
        connection.play.assert_not_called()
        source.cleanup.assert_called_once()
        self.assertFalse(bridge.consent_confirmed)

    async def test_stale_wrong_channel_or_missing_session_reply_never_plays(self):
        channel = channel_with_members([SimpleNamespace(id=12, bot=False)])
        connection = SimpleNamespace(channel=channel, stop=Mock(), play=Mock(),
                                     stop_listening=Mock(), disconnect=AsyncMock(),
                                     is_playing=lambda: False)
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        bridge.connection = connection
        bridge.own_bot_id = 100
        session_a = bridge.session_id
        bridge.set_session([12], consent_confirmed=True)
        session_b = bridge.session_id
        sources = [Incoming("discord_voice", "speaker", "hello", channel="45", speaker_id=12,
                            voice_session_id=session_a),
                   Incoming("discord_voice", "speaker", "hello", channel="45", speaker_id=12),
                   Incoming("discord_voice", "speaker", "hello", channel="46", speaker_id=12,
                            voice_session_id=session_b),
                   Incoming("discord_voice", "speaker", "hello", channel="45", speaker_id=13,
                            voice_session_id=session_b),
                   Incoming("twitch", "speaker", "hello", channel="45")]
        for source in sources:
            with self.assertRaises(PermissionError):
                await bridge.play_for_reply(b"synthetic-wav", source)
        connection.play.assert_not_called()
        self.assertTrue(bridge.consent_confirmed)
        self.assertEqual(bridge.session_id, session_b)

    async def test_authorized_reply_from_current_session_is_played(self):
        channel = channel_with_members([SimpleNamespace(id=12, bot=False)])
        source_file = SimpleNamespace(cleanup=Mock())
        def play(source, *, after): after(None)
        connection = SimpleNamespace(channel=channel, stop=Mock(), play=Mock(side_effect=play),
                                     stop_listening=Mock(), disconnect=AsyncMock(),
                                     is_playing=lambda: False)
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        bridge.connection = connection
        bridge.own_bot_id = 100
        source = Incoming("discord_voice", "speaker", "hello", channel="45", speaker_id=12,
                          voice_session_id=bridge.session_id)
        with patch.dict(sys.modules, {"discord": SimpleNamespace(FFmpegPCMAudio=lambda _: source_file)}):
            await asyncio.wait_for(bridge.play_for_reply(b"synthetic-wav", source), 1)
        connection.play.assert_called_once()
        source_file.cleanup.assert_called_once()

    async def test_playback_blocks_audio_clears_partial_and_resumes_after_stop(self):
        services, runtime = AsyncMock(), AsyncMock()
        services.transcribe_wav.return_value = "Salut"
        bridge = DiscordVoiceBridge(services, runtime, 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        channel = attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        callbacks, playing = [], asyncio.Event()
        def play(source, *, after):
            callbacks.append(after)
            playing.set()
        def stop():
            if callbacks: callbacks.pop()(None)
        bridge.connection.play = Mock(side_effect=play)
        bridge.connection.stop = Mock(side_effect=stop)
        bridge.connection.is_playing = lambda: False
        bridge.receive_pcm(12, "Participant", array('h', [1500] * 19200).tobytes())
        self.assertTrue(bridge._segmenter._users)
        source_file = SimpleNamespace(cleanup=Mock())
        with patch.dict(sys.modules, {"discord": SimpleNamespace(FFmpegPCMAudio=lambda _: source_file)}):
            playback = asyncio.create_task(bridge.play(b"synthetic-wav"))
            await asyncio.wait_for(playing.wait(), 1)
            self.assertFalse(bridge._segmenter._users)
            bridge.receive_pcm(12, "Participant", loud())
            await asyncio.sleep(0)
            services.transcribe_wav.assert_not_awaited()
            self.assertFalse(bridge._segmenter._users)
            bridge.connection.stop()
            await asyncio.wait_for(playback, 1)
        bridge.receive_pcm(12, "Participant", loud())
        await asyncio.sleep(.02)
        await bridge.pending.join()
        services.transcribe_wav.assert_awaited_once()
        await bridge.close()

    async def test_playback_cancels_prior_stt_and_ignores_stale_queue(self):
        started, cancelled, playing = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def blocked(_):
            started.set()
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        services = SimpleNamespace(transcribe_wav=AsyncMock(side_effect=blocked))
        bridge = DiscordVoiceBridge(services, AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.receive_pcm(12, "Participant", loud())
        await asyncio.wait_for(started.wait(), 1)
        bridge.receive_pcm(12, "Participant", loud())
        await asyncio.sleep(0)
        callbacks = []
        def play(source, *, after): callbacks.append(after); playing.set()
        def stop():
            if callbacks: callbacks.pop()(None)
        bridge.connection.play = Mock(side_effect=play)
        bridge.connection.stop = Mock(side_effect=stop)
        bridge.connection.is_playing = lambda: False
        with patch.dict(sys.modules, {"discord": SimpleNamespace(FFmpegPCMAudio=lambda _: SimpleNamespace(cleanup=Mock()))}):
            playback = asyncio.create_task(bridge.play(b"synthetic-wav"))
            await asyncio.wait_for(playing.wait(), 1)
            await asyncio.wait_for(cancelled.wait(), 1)
            self.assertTrue(bridge.pending.empty())
            bridge.connection.stop()
            await asyncio.wait_for(playback, 1)
        self.assertEqual(services.transcribe_wav.await_count, 1)
        await bridge.close()

    async def test_cancelled_or_failed_playback_reopens_capture_gate(self):
        for failure in (False, True):
            services, runtime = AsyncMock(), AsyncMock()
            services.transcribe_wav.return_value = "Salut"
            bridge = DiscordVoiceBridge(services, runtime, 45,
                                        authorized_user_ids=[12], consent_confirmed=True)
            attach_connection(bridge)
            bridge.loop = asyncio.get_running_loop()
            bridge.worker = asyncio.create_task(bridge._consume())
            playing = asyncio.Event()
            bridge.connection.is_playing = lambda: False
            bridge.connection.play = Mock(side_effect=lambda source, after: playing.set())
            def create(_):
                if failure: raise RuntimeError("synthetic")
                return SimpleNamespace(cleanup=Mock())
            with patch.dict(sys.modules, {"discord": SimpleNamespace(FFmpegPCMAudio=create)}):
                playback = asyncio.create_task(bridge.play(b"synthetic-wav"))
                if failure:
                    with self.assertRaisesRegex(RuntimeError, "synthetic"): await playback
                else:
                    await asyncio.wait_for(playing.wait(), 1)
                    playback.cancel()
                    with self.assertRaises(asyncio.CancelledError): await playback
            bridge.receive_pcm(12, "Participant", loud())
            await asyncio.sleep(.02)
            await bridge.pending.join()
            services.transcribe_wav.assert_awaited_once()
            await bridge.close()

    async def test_revocation_stops_playback_before_waiting_for_blocked_stt_cleanup(self):
        started, release, playing = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def blocked(_):
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                await release.wait()
        services = SimpleNamespace(transcribe_wav=blocked)
        channel = channel_with_members([SimpleNamespace(id=12, bot=False)])
        callbacks = []
        def play(source, *, after):
            callbacks.append(after)
            playing.set()
        def stop():
            if callbacks:
                callbacks.pop()(None)
        connection = SimpleNamespace(channel=channel, stop=Mock(side_effect=stop), play=Mock(side_effect=play),
                                     stop_listening=Mock(), disconnect=AsyncMock(), is_playing=lambda: False)
        bridge = DiscordVoiceBridge(services, AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        bridge.connection = connection
        bridge.own_bot_id = 100
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        source = SimpleNamespace(cleanup=Mock())
        with patch.dict(sys.modules, {"discord": SimpleNamespace(FFmpegPCMAudio=lambda _: source)}):
            bridge.receive_pcm(12, "Participant", loud())
            await asyncio.wait_for(started.wait(), 1)
            playback = asyncio.create_task(bridge.play(b"synthetic-wav"))
            await asyncio.wait_for(playing.wait(), 1)
            bridge.set_session([], consent_confirmed=False)
            connection.stop.assert_called()
            self.assertFalse(release.is_set())
            with self.assertRaises(PermissionError):
                await asyncio.wait_for(playback, 1)
            self.assertFalse(release.is_set())
            release.set()
            await bridge.close()

    async def test_unauthorized_participant_during_join_prevents_listener(self):
        ready, release = asyncio.Event(), asyncio.Event()
        connection = SimpleNamespace(listen=Mock(), disconnect=AsyncMock())
        async def connect(**kwargs):
            ready.set()
            await release.wait()
            return connection
        members = [SimpleNamespace(id=12, bot=False)]
        channel = channel_with_members(members, connect)
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        recv = types.ModuleType('discord.ext.voice_recv')
        recv.VoiceRecvClient = object
        recv.AudioSink = type('AudioSink', (), {})
        discord, ext = types.ModuleType('discord'), types.ModuleType('discord.ext')
        discord.ext, ext.voice_recv = ext, recv
        with patch.dict(sys.modules, {'discord': discord, 'discord.ext': ext,
                                      'discord.ext.voice_recv': recv}):
            task = asyncio.create_task(bridge.connect(client_for(channel)))
            await asyncio.wait_for(ready.wait(), 1)
            members.append(SimpleNamespace(id=13, bot=False))
            channel.voice_states[13] = SimpleNamespace(channel=channel)
            release.set()
            with self.assertRaisesRegex(ValueError, "authorization changed"):
                await asyncio.wait_for(task, 1)
        connection.listen.assert_not_called()
        connection.disconnect.assert_awaited_once()

    async def test_human_join_revokes_consent_and_disconnects_but_bot_event_is_ignored(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.connection = SimpleNamespace(stop_listening=Mock(), disconnect=AsyncMock())
        connection = bridge.connection
        outside, channel = SimpleNamespace(channel=None), SimpleNamespace(channel=SimpleNamespace(id=45))
        await bridge.voice_state_changed(SimpleNamespace(id=100, bot=True), outside, channel, own_bot_id=100)
        self.assertTrue(bridge.consent_confirmed)
        await bridge.voice_state_changed(SimpleNamespace(id=13, bot=False), outside, channel)
        self.assertFalse(bridge.consent_confirmed)
        self.assertIsNone(bridge.connection)
        connection.stop_listening.assert_called_once()
        connection.disconnect.assert_awaited_once()

    async def test_human_leaves_or_moves_from_another_channel_revokes_only_if_relevant(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        outside = SimpleNamespace(channel=None)
        elsewhere = SimpleNamespace(channel=SimpleNamespace(id=46))
        here = SimpleNamespace(channel=SimpleNamespace(id=45))
        member = SimpleNamespace(id=12, bot=False)
        await bridge.voice_state_changed(member, outside, elsewhere)
        self.assertTrue(bridge.consent_confirmed)
        await bridge.voice_state_changed(member, here, outside)
        self.assertFalse(bridge.consent_confirmed)

    async def test_own_bot_leaving_revokes_and_ignores_own_join(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        outside = SimpleNamespace(channel=None)
        here = SimpleNamespace(channel=SimpleNamespace(id=45))
        bot = SimpleNamespace(id=100, bot=True)
        await bridge.voice_state_changed(bot, outside, here, own_bot_id=100)
        self.assertTrue(bridge.consent_confirmed)
        await bridge.voice_state_changed(bot, here, outside, own_bot_id=100)
        self.assertFalse(bridge.consent_confirmed)

    async def test_other_bot_entering_or_leaving_revokes(self):
        outside = SimpleNamespace(channel=None)
        here = SimpleNamespace(channel=SimpleNamespace(id=45))
        for before, after in ((outside, here), (here, outside)):
            bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                        authorized_user_ids=[12], consent_confirmed=True)
            await bridge.voice_state_changed(SimpleNamespace(id=101, bot=True), before, after, own_bot_id=100)
            self.assertFalse(bridge.consent_confirmed)

    async def test_stale_purge_does_not_remove_new_session_audio(self):
        services, runtime = AsyncMock(), AsyncMock()
        services.transcribe_wav.return_value = "Salut"
        records = []
        async def save(message): records.append(message)
        runtime.submit.side_effect = save
        bridge = DiscordVoiceBridge(services, runtime, 45)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.set_session([12], consent_confirmed=True)
        bridge.set_session([13], consent_confirmed=True)
        attach_connection(bridge, (13,))
        bridge.receive_pcm(13, "Participant", loud())
        await asyncio.sleep(.02)
        await bridge.pending.join()
        self.assertEqual([item.speaker_id for item in records], [13])
        await bridge.close()

    async def test_discord_gateway_delegates_voice_membership_events(self):
        member, before, after = object(), object(), object()
        class Client:
            def __init__(self, **kwargs): pass
            async def start(self, token):
                await self.on_voice_state_update(member, before, after)
            async def close(self): pass
        fake = SimpleNamespace(Client=Client,
            Intents=SimpleNamespace(default=lambda: SimpleNamespace()),
            AllowedMentions=SimpleNamespace(none=lambda: object()))
        bridge = SimpleNamespace(voice_state_changed=AsyncMock(), close=AsyncMock())
        discord = DiscordText("synthetic", AsyncMock(), voice_bridge=bridge)
        with patch.dict(sys.modules, {"discord": fake}):
            await discord.connect_forever()
        bridge.voice_state_changed.assert_awaited_once_with(member, before, after, own_bot_id=None)
        bridge.close.assert_awaited_once()

    async def test_gateway_disconnect_revokes_before_cleanup(self):
        calls = []
        class Client:
            def __init__(self, **kwargs): pass
            async def start(self, token): await self.on_disconnect()
            async def close(self): pass
        fake = SimpleNamespace(Client=Client,
            Intents=SimpleNamespace(default=lambda: SimpleNamespace()),
            AllowedMentions=SimpleNamespace(none=lambda: object()))
        async def close(): calls.append("close")
        async def close_revoked(generation): calls.append("close")
        def revoke(*args, **kwargs):
            calls.append("revoke")
            return True
        bridge = SimpleNamespace(set_session=revoke, close=close,
                                 _close_if_revoked=close_revoked,
                                 buffers_lock=threading.Lock(), generation=1, session_id="old")
        discord = DiscordText("synthetic", AsyncMock(), voice_bridge=bridge)
        with patch.dict(sys.modules, {"discord": fake}):
            await discord.connect_forever()
        self.assertEqual(calls[:2], ["revoke", "close"])

    async def test_gateway_disconnect_does_not_close_replacement_session(self):
        # Hold cleanup on the lifecycle lock, install fresh consent, and then
        # release the old disconnect. The stale callback must not close it.
        started, disconnected, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()
        class Client:
            def __init__(self, **kwargs): pass
            async def start(self, token):
                started.set()
                await self.on_disconnect()
                disconnected.set()
                await finish.wait()
            async def close(self): pass
        fake = SimpleNamespace(Client=Client,
            Intents=SimpleNamespace(default=lambda: SimpleNamespace()),
            AllowedMentions=SimpleNamespace(none=lambda: object()))
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        attach_connection(bridge)
        discord = DiscordText("synthetic", AsyncMock(), voice_bridge=bridge)
        with patch.dict(sys.modules, {"discord": fake}):
            await bridge.lifecycle_lock.acquire()
            task = asyncio.create_task(discord.connect_forever())
            try:
                await asyncio.wait_for(started.wait(), timeout=1)
                self.assertFalse(bridge.consent_confirmed)
                bridge.set_session([12], consent_confirmed=True)
                replacement = bridge.session_id
            finally:
                bridge.lifecycle_lock.release()
            await asyncio.wait_for(disconnected.wait(), timeout=1)
            self.assertTrue(bridge.consent_confirmed)
            self.assertEqual(bridge.session_id, replacement)
            self.assertIsNotNone(bridge.connection)
            finish.set()
            await asyncio.wait_for(task, timeout=2)

    async def test_gateway_reconnect_does_not_reuse_previous_consent(self):
        class Client:
            def __init__(self, **kwargs): self.user = SimpleNamespace(id=100, bot=True)
            async def start(self, token):
                await self.on_disconnect()
                await self.on_ready()
            async def close(self): pass
            def get_channel(self, channel): raise AssertionError("must not rejoin")
        fake = SimpleNamespace(Client=Client,
            Intents=SimpleNamespace(default=lambda: SimpleNamespace()),
            AllowedMentions=SimpleNamespace(none=lambda: object()))
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45,
                                    authorized_user_ids=[12], consent_confirmed=True)
        discord = DiscordText("synthetic", AsyncMock(), voice_bridge=bridge)
        with patch.dict(sys.modules, {"discord": fake}):
            with self.assertRaisesRegex(ValueError, "consent"):
                await discord.connect_forever()
        self.assertFalse(bridge.consent_confirmed)


if __name__ == "__main__":
    unittest.main()
