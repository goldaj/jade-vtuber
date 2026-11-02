"""Mock only; never connect to Discord or upload audio."""
import asyncio
from array import array
import unittest
import types
from unittest.mock import AsyncMock, Mock, patch

from src.jade_runtime.discord_voice import (
    DiscordVoiceBridge, PCM_CHUNK_BYTES, pcm_48k_stereo_wav)


class DiscordVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_pcm_is_bounded_filtered_and_openai_only(self):
        records = []
        runtime = AsyncMock()
        async def save(incoming):
            records.append(incoming)
        runtime.submit.side_effect = save
        services = AsyncMock()
        services.transcribe_wav.return_value = "Bonjour Jade"
        bridge = DiscordVoiceBridge(services, runtime, 45)
        bridge.loop = asyncio.get_running_loop()
        bridge.worker = asyncio.create_task(bridge._consume())
        silent = bytes(PCM_CHUNK_BYTES)
        bridge.receive_pcm(12, "Alpha", silent)
        await asyncio.sleep(0)
        services.transcribe_wav.assert_not_awaited()
        loud = array("h", [1500] * (PCM_CHUNK_BYTES // 2)).tobytes()
        bridge.receive_pcm(12, "Alpha", loud)
        await asyncio.sleep(.01)
        await bridge.pending.join()
        self.assertEqual(records[0].platform, "discord_voice")
        self.assertEqual(records[0].text, "Bonjour Jade")
        self.assertEqual(records[0].channel, "45")
        self.assertEqual(services.transcribe_wav.await_args.args[0][:4], b"RIFF")
        await bridge.close()

    def test_refuse_malformed_chunks(self):
        with self.assertRaises(ValueError):
            pcm_48k_stereo_wav(b"bad")
        self.assertEqual(pcm_48k_stereo_wav(bytes(4))[:4], b"RIFF")

    async def test_completed_and_stale_partial_users_release_slots(self):
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45)
        with patch('src.jade_runtime.discord_voice.time.monotonic', return_value=0):
            for uid in range(1, 13):
                bridge.receive_pcm(uid, str(uid), bytes(4))
        with patch('src.jade_runtime.discord_voice.time.monotonic', return_value=16):
            bridge.receive_pcm(13, 'new', bytes(4))
            self.assertEqual(set(bridge.buffers), {13})
            bridge.receive_pcm(13, 'new', bytes(PCM_CHUNK_BYTES - 4))
        self.assertEqual(bridge.buffers, {})

    async def test_failed_and_concurrent_connect_cleanup(self):
        recv = types.ModuleType('discord.ext.voice_recv')
        recv.VoiceRecvClient = object
        recv.AudioSink = type('AudioSink', (), {})
        discord, ext = types.ModuleType('discord'), types.ModuleType('discord.ext')
        discord.ext, ext.voice_recv = ext, recv
        modules = {'discord': discord, 'discord.ext': ext, 'discord.ext.voice_recv': recv}
        connection = types.SimpleNamespace(listen=Mock(side_effect=ValueError('failed')),
            disconnect=AsyncMock(), stop_listening=Mock())
        channel = types.SimpleNamespace(connect=AsyncMock(return_value=connection))
        client = types.SimpleNamespace(get_channel=lambda _: channel)
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45)
        with patch.dict('sys.modules', modules):
            with self.assertRaises(ValueError):
                await bridge.connect(client)
            self.assertIsNone(bridge.worker)
            self.assertIsNone(bridge.connection)
            connection.disconnect.assert_awaited_once()
            connection.listen.side_effect = None
            await asyncio.gather(bridge.connect(client), bridge.connect(client))
            self.assertEqual(channel.connect.await_count, 2)
            await bridge.close()
            await bridge.close()
            self.assertIsNone(bridge.worker)
            await bridge.pending.join()

    async def test_close_abandons_blocked_transcription(self):
        services = AsyncMock()
        started = asyncio.Event()
        async def blocked(_):
            started.set()
            await asyncio.Event().wait()
        services.transcribe_wav.side_effect = blocked
        bridge = DiscordVoiceBridge(services, AsyncMock(), 45)
        bridge.worker = asyncio.create_task(bridge._consume())
        bridge.pending.put_nowait(('test', bytes(4)))
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.wait_for(bridge.close(), 1)
        await asyncio.wait_for(bridge.pending.join(), 1)

    async def test_cancel_play_stops_and_cleans_source(self):
        source = types.SimpleNamespace(cleanup=Mock())
        discord = types.SimpleNamespace(FFmpegPCMAudio=lambda _: source)
        started = asyncio.Event()
        connection = types.SimpleNamespace(is_playing=lambda: False, stop=Mock())
        def play(src, *, after):
            started.set()
        connection.play = play
        bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45)
        bridge.connection = connection
        with patch.dict('sys.modules', {'discord': discord}):
            task = asyncio.create_task(bridge.play(b'fake-wav'))
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        connection.stop.assert_called_once()
        source.cleanup.assert_called_once()
