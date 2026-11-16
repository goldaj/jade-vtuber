"""Offline diagnostics reproducing known connector defects on df544ed.

Successful exit means the documented defects WERE observed, not fixed.
No provider connection, credentials, device, third-party dependency or socket.
"""
import asyncio
from array import array
from pathlib import Path
import sys
import types
from unittest.mock import AsyncMock, patch

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"D:\Codex\projects\jade-migration-20261102")
sys.path.insert(0, str(ROOT))
from src.jade_runtime.discord_voice import DiscordVoiceBridge, PCM_CHUNK_BYTES
from src.jade_runtime.twitch_irc import TwitchIRC
from src.jade_runtime.local_http import LocalHTTP
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.messages import Incoming


class Writer:
    def __init__(self):
        self.writes = []
        self.closed = False
    def write(self, raw):
        self.writes.append(raw)
    async def drain(self):
        pass
    def close(self):
        self.closed = True
    async def wait_closed(self):
        pass


async def voice_user_slots():
    bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45)
    for uid in range(1, 13):
        bridge.receive_pcm(uid, str(uid), bytes(PCM_CHUNK_BYTES))
    assert len(bridge.buffers) == 12
    assert all(not value for value in bridge.buffers.values())
    loud = array('h', [1500] * (PCM_CHUNK_BYTES // 2)).tobytes()
    bridge.receive_pcm(13, 'new-user', loud)
    assert 13 not in bridge.buffers
    print('REPRODUCED: 12 completed silent users permanently exclude user 13')


async def twitch_queue_overflow():
    reader = asyncio.StreamReader()
    reader.feed_data(b'@id=hello :viewer!viewer@viewer.tmi.twitch.tv PRIVMSG #jade :Bonjour Jade\r\nPING :server\r\n')
    reader.feed_eof()
    writer = Writer()
    async def connector(*args, **kwargs):
        return reader, writer
    async def reject(message):
        raise asyncio.QueueFull
    client = TwitchIRC(login='jadebot', token='fake', channel='jade',
                       on_message=reject, connector=connector)
    try:
        await client.connect_once()
    except asyncio.QueueFull:
        pass
    else:
        raise AssertionError('QueueFull no longer propagates')
    assert writer.closed and not any(b'PONG' in raw for raw in writer.writes)
    print('REPRODUCED: a full application queue disconnects Twitch and skips next PING')


async def failed_voice_connect_leaks_workers():
    discord = types.ModuleType('discord')
    ext = types.ModuleType('discord.ext')
    recv = types.ModuleType('discord.ext.voice_recv')
    recv.VoiceRecvClient = object
    ext.voice_recv = recv
    discord.ext = ext
    channel = types.SimpleNamespace(connect=AsyncMock(side_effect=RuntimeError('synthetic failure')))
    client = types.SimpleNamespace(get_channel=lambda channel_id: channel)
    bridge = DiscordVoiceBridge(AsyncMock(), AsyncMock(), 45)
    workers = []
    try:
        with patch.dict(sys.modules, {'discord': discord, 'discord.ext': ext,
                                    'discord.ext.voice_recv': recv}):
            for _ in range(2):
                try:
                    await bridge.connect(client)
                except RuntimeError:
                    workers.append(bridge.worker)
        assert len(workers) == 2 and workers[0] is not workers[1]
        assert all(not worker.done() for worker in workers)
        print('REPRODUCED: two failed voice connects leave two active consumer tasks')
    finally:
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


async def http_timeout_leaves_processing_active():
    gate = asyncio.Event()
    outputs = []
    provider_calls = []
    class Backend:
        async def complete(self, messages):
            provider_calls.append(messages)
            if len(provider_calls) == 1:
                await gate.wait()
            return 'synthetic answer after timeout'
    gateway = None
    async def output(reply):
        outputs.append(reply)
        gateway.deliver(reply)
    runtime = Runtime(Dialogue(Backend(), 'Jade'), output)
    await runtime.start()
    gateway = LocalHTTP(runtime, token='synthetic-token-' * 3)
    await runtime.submit(Incoming('console', 'operator', 'blocker', force_reply=True))
    await asyncio.sleep(0)
    assert len(provider_calls) == 1
    reader = asyncio.StreamReader()
    payload = b'{"text":"Hello","session":"audit"}'
    raw = (b'POST /message HTTP/1.1\r\nAuthorization: Bearer ' +
           gateway.token.encode() + b'\r\nContent-Length: ' +
           str(len(payload)).encode() + b'\r\n\r\n' + payload)
    reader.feed_data(raw)
    reader.feed_eof()
    writer = Writer()
    original_wait_for = asyncio.wait_for
    async def faster_wait_for(awaitable, timeout):
        return await original_wait_for(awaitable, .01 if timeout == 25 else timeout)
    try:
        with patch('src.jade_runtime.local_http.asyncio.wait_for', faster_wait_for):
            await gateway.handle(reader, writer)
        assert any(b'504 Gateway Timeout' in value for value in writer.writes)
        assert not gateway.pending and not outputs and len(provider_calls) == 1
        gate.set()
        await runtime.idle()
        assert len(outputs) == 2 and len(provider_calls) == 2
        print('REPRODUCED: HTTP 504 expires queued requester, then a fresh provider call starts for it')
    finally:
        gate.set()
        await runtime.stop()


async def main():
    await voice_user_slots()
    await twitch_queue_overflow()
    await failed_voice_connect_leaks_workers()
    await http_timeout_leaves_processing_active()
    print('4 defects reproduced using synthetic in-memory inputs; no fixes applied')


if __name__ == '__main__':
    asyncio.run(main())
