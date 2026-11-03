"""Offline integration of experimental turns: no Discord or provider calls."""
import asyncio
import struct
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.jade_runtime.discord_voice import DiscordVoiceBridge, MAX_TURN_BYTES
from src.jade_runtime.voice_turns import AudioTurn


def pcm(seconds, level):
    return struct.pack('<hh', level, level) * int(48000 * seconds)


class TurnIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def setup_bridge(self, users=(12,), text='Salut', threshold=550):
        services = types.SimpleNamespace(transcribe_wav=AsyncMock(return_value=text))
        runtime = types.SimpleNamespace(submit=AsyncMock(), cancel_work=Mock())
        bridge = DiscordVoiceBridge(services, runtime, 45, authorized_user_ids=users,
                                   consent_confirmed=True, threshold=threshold)
        channel = types.SimpleNamespace(id=45, members=[types.SimpleNamespace(id=u, bot=False) for u in users])
        channel.voice_states = {u: types.SimpleNamespace(channel=channel) for u in users}
        bridge.connection = types.SimpleNamespace(channel=channel, stop=Mock(),
                                                  stop_listening=Mock(), disconnect=AsyncMock())
        bridge.own_bot_id = 100
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge._poller = asyncio.create_task(bridge._poll_turns())
        self.addAsyncCleanup(bridge.close)
        return bridge, services, runtime

    async def test_short_phrase_without_name_finishes_on_silence_and_is_accepted(self):
        bridge, services, runtime = await self.setup_bridge()
        bridge.receive_pcm(12, 'A', pcm(.3, 1500))
        bridge.receive_pcm(12, 'A', pcm(.8, 0))
        await asyncio.sleep(.03)
        await bridge.pending.join()
        services.transcribe_wav.assert_awaited_once()
        msg = runtime.submit.await_args.args[0]
        self.assertEqual(msg.text, 'Salut')
        self.assertTrue(msg.force_reply)
        self.assertEqual(msg.voice_session_id, bridge.session_id)

    async def test_timer_finishes_without_new_packets(self):
        bridge, services, runtime = await self.setup_bridge()
        bridge.receive_pcm(12, 'A', pcm(.2, 1500))
        for _ in range(15):
            if services.transcribe_wav.await_count:
                break
            await asyncio.sleep(.1)
        self.assertEqual(services.transcribe_wav.await_count, 1)
        self.assertEqual(runtime.submit.await_count, 1)

    async def test_configured_threshold_filters_quiet_audio(self):
        bridge, services, runtime = await self.setup_bridge(threshold=2000)
        bridge.receive_pcm(12, 'A', pcm(.2, 1500) + pcm(.8, 0))
        await asyncio.sleep(.03)
        services.transcribe_wav.assert_not_awaited()
        runtime.submit.assert_not_awaited()

    async def test_group_without_trusted_address_is_not_forwarded(self):
        bridge, services, runtime = await self.setup_bridge((12, 13), 'Quelle heure est-il ?')
        bridge.receive_pcm(12, 'A', pcm(.2, 1500) + pcm(.8, 0))
        await asyncio.sleep(.03)
        await bridge.pending.join()
        services.transcribe_wav.assert_awaited_once()
        runtime.submit.assert_not_awaited()

    async def test_reply_ack_is_bound_to_source_and_cannot_survive_revocation(self):
        bridge, _, runtime = await self.setup_bridge()
        bridge.receive_pcm(12, 'A', pcm(.2, 1500) + pcm(.8, 0))
        await asyncio.sleep(.03)
        await bridge.pending.join()
        source = runtime.submit.await_args.args[0]
        self.assertTrue(bridge.mark_voice_reply_played(source))
        self.assertFalse(bridge.mark_voice_reply_played(source))
        bridge.receive_pcm(12, 'A', pcm(.2, 1500) + pcm(.8, 0))
        await asyncio.sleep(.03)
        await bridge.pending.join()
        old_source = runtime.submit.await_args.args[0]
        bridge.set_session([], consent_confirmed=False)
        self.assertFalse(bridge.mark_voice_reply_played(old_source))

    async def test_allowed_participant_arrival_or_departure_revokes_before_capture(self):
        for initial, changed, speaker in (((12,), (12, 13), 12), ((12, 13), (13,), 13)):
            with self.subTest(initial=initial, changed=changed):
                bridge, services, _ = await self.setup_bridge((12, 13))
                channel = bridge.connection.channel
                channel.members = [types.SimpleNamespace(id=u, bot=False) for u in initial]
                channel.voice_states = {u: types.SimpleNamespace(channel=channel) for u in initial}
                bridge.receive_pcm(initial[0], 'A', pcm(.2, 1500))
                self.assertEqual(bridge._participants, frozenset(initial))
                channel.members = [types.SimpleNamespace(id=u, bot=False) for u in changed]
                channel.voice_states = {u: types.SimpleNamespace(channel=channel) for u in changed}
                bridge.receive_pcm(speaker, 'A', pcm(.2, 1500) + pcm(.8, 0))
                self.assertFalse(bridge.consent_confirmed)
                self.assertFalse(bridge._segmenter._users)
                services.transcribe_wav.assert_not_awaited()
                await asyncio.sleep(0)

    async def test_two_phrases_in_one_packet_keep_author(self):
        bridge, services, runtime = await self.setup_bridge()
        phrase = pcm(.2, 1500) + pcm(.7, 0)
        bridge.receive_pcm(12, 'A', phrase + phrase)
        await asyncio.sleep(.03)
        await bridge.pending.join()
        self.assertEqual(services.transcribe_wav.await_count, 2)
        self.assertEqual(runtime.submit.await_count, 2)

    async def test_snapshot_change_detected_on_reply_cannot_recover_old_session(self):
        bridge, _, runtime = await self.setup_bridge()
        bridge.receive_pcm(12, 'A', pcm(.2, 1500) + pcm(.8, 0))
        await asyncio.sleep(.03)
        await bridge.pending.join()
        source = runtime.submit.await_args.args[0]
        channel = bridge.connection.channel
        old_members, old_states = channel.members, channel.voice_states
        channel.members = []
        channel.voice_states = {}
        self.assertFalse(bridge.reply_authorized(source))
        channel.members, channel.voice_states = old_members, old_states
        self.assertFalse(bridge.reply_authorized(source))
        self.assertFalse(bridge.consent_confirmed)

    async def test_stale_rejection_cannot_revoke_replacement_session(self):
        bridge, _, runtime = await self.setup_bridge((12, 13))
        channel = bridge.connection.channel
        channel.members = [types.SimpleNamespace(id=12, bot=False)]
        channel.voice_states = {12: types.SimpleNamespace(channel=channel)}
        bridge.receive_pcm(12, 'A', pcm(.2, 1500) + pcm(.8, 0))
        await asyncio.sleep(.03)
        await bridge.pending.join()
        source = runtime.submit.await_args.args[0]
        channel.members = [types.SimpleNamespace(id=13, bot=False)]
        channel.voice_states = {13: types.SimpleNamespace(channel=channel)}
        old_set = bridge.set_session
        def replace_before_revoke(*args, **kwargs):
            if kwargs.get('_expected') is not None:
                old_set([12, 13], consent_confirmed=True)
            return old_set(*args, **kwargs)
        with patch.object(bridge, 'set_session', side_effect=replace_before_revoke):
            self.assertFalse(bridge.reply_authorized(source))
        self.assertTrue(bridge.consent_confirmed)
        self.assertEqual(bridge._participants, frozenset({13}))
        self.assertNotEqual(bridge.session_id, source.voice_session_id)

    async def test_close_invalidates_before_awaiting_poller_cleanup(self):
        bridge, services, _ = await self.setup_bridge()
        bridge._poller.cancel()
        await asyncio.gather(bridge._poller, return_exceptions=True)
        started, blocked, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def slow_poller():
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                blocked.set()
                await release.wait()
        bridge._poller = asyncio.create_task(slow_poller())
        await started.wait()
        connection = bridge.connection
        closing = asyncio.create_task(bridge.close())
        await asyncio.wait_for(blocked.wait(), 1)
        self.assertFalse(bridge.consent_confirmed)
        connection.stop.assert_called()
        connection.stop_listening.assert_called()
        bridge.receive_pcm(12, 'A', pcm(.2, 1500) + pcm(.8, 0))
        services.transcribe_wav.assert_not_awaited()
        release.set()
        await asyncio.wait_for(closing, 1)

    async def test_revocation_drops_pending_audio_before_timer(self):
        bridge, services, runtime = await self.setup_bridge()
        bridge.receive_pcm(12, 'A', pcm(.2, 1500))
        bridge.set_session([], consent_confirmed=False)
        await asyncio.sleep(.15)
        self.assertFalse(bridge._segmenter._users)
        self.assertFalse(bridge._assemblies)
        services.transcribe_wav.assert_not_awaited()
        runtime.submit.assert_not_awaited()

    async def test_fragments_end_empty_and_oversized_turn_is_dropped(self):
        bridge, _, _ = await self.setup_bridge()
        with bridge.buffers_lock:
            bridge._authors[12] = 'A'
            first = AudioTurn('12', b'a' * 192000, partial=True)
            self.assertEqual(bridge._collect_turns_locked([first], 1), [])
            ready = bridge._collect_turns_locked([AudioTurn('12', b'', partial=False)], 2)
            self.assertEqual(ready[0].pcm, first.pcm)
            bridge._authors[12] = 'A'
            bridge._collect_turns_locked([AudioTurn('12', b'a' * MAX_TURN_BYTES, partial=True)], 3)
            self.assertEqual(bridge._collect_turns_locked([AudioTurn('12', b'bbbb', partial=False)], 4), [])
            self.assertFalse(bridge._assemblies)


if __name__ == '__main__':
    unittest.main()
