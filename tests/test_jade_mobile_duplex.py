"""Full duplex mobile protocol offline: real local socket, fake STT/LLM."""
import asyncio
import base64
import json
import secrets
import struct
from types import SimpleNamespace
import unittest

from src.jade_runtime.messages import Reply
from src.jade_runtime.mobile_gateway import MobileGateway


def masked(payload: bytes, opcode=1) -> bytes:
    key = b"\x12\x34\x56\x78"
    size = len(payload)
    header = bytes((0x80 | opcode, size | 0x80)) if size < 126 else (
        bytes((0x80 | opcode, 0x80 | 126)) + struct.pack("!H", size)
        if size < 65536 else
        bytes((0x80 | opcode, 0x80 | 127)) + struct.pack("!Q", size))
    return header + key + bytes(v ^ key[i % 4] for i, v in enumerate(payload))


async def read_event(reader):
    head = await asyncio.wait_for(reader.readexactly(2), 3)
    length = head[1] & 0x7f
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]
    data = await reader.readexactly(length)
    return json.loads(data.decode("utf-8"))


class FakeServices:
    def __init__(self):
        self.transcribed = []
        self.synthesized = []
        self.settings = SimpleNamespace(tts_pitch_semitones=0)

    async def transcribe_wav(self, data):
        self.transcribed.append(data)
        return "Bonjour Jade, peux-tu m'entendre ?"

    async def synthesize_speech(self, text, *, intent="neutral"):
        self.synthesized.append((text, intent))
        return SimpleNamespace(audio=b"RIFF" + b"\0" * 40)


class DuplexProtocol(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.services = FakeServices()
        self.mobile = MobileGateway(
            SimpleNamespace(), self.services, token="z" * 40, port=8766)
        self.replies = []

        async def fake_conversation(incoming):
            self.replies.append(incoming)
            return Reply(incoming, "Bonjour, je suis là !")
        self.mobile._conversation = fake_conversation
        self.server = await asyncio.start_server(
            self.mobile._accept, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        tasks = tuple(self.mobile.connections)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def connect(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        request = (
            "GET /api/duplex HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: jade-v1\r\n"
            f"Sec-WebSocket-Key: {key}\r\n\r\n"
        )
        writer.write(request.encode("ascii"))
        await writer.drain()
        header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 3)
        self.assertIn(b"101 Switching Protocols", header)
        return reader, writer

    async def test_voice_stream_stays_one_stt_turn_without_tts_when_muted(self):
        reader, writer = await self.connect()
        try:
            writer.write(masked(json.dumps({
                "type": "auth", "token": "z" * 40, "session": "m-session123"
            }).encode()))
            await writer.drain()
            self.assertEqual((await read_event(reader))["type"], "ready")
            writer.write(masked(b'{"type":"start","speak":false}'))
            writer.write(masked(b"\0\0" * 8000, opcode=2))
            writer.write(masked(b'{"type":"end"}'))
            await writer.drain()
            result = await read_event(reader)
            self.assertEqual(result["type"], "reply")
            self.assertEqual(result["reply"], "Bonjour, je suis là !")
            self.assertEqual((await read_event(reader))["type"], "done")
            self.assertEqual(len(self.services.transcribed), 1)
            self.assertEqual(len(self.replies), 1)
            self.assertEqual(self.services.synthesized, [])
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_invalid_auth_never_reaches_stt(self):
        reader, writer = await self.connect()
        try:
            writer.write(masked(json.dumps({
                "type": "auth", "token": "wrong", "session": "m-session123"
            }).encode()))
            await writer.drain()
            self.assertEqual((await read_event(reader))["type"], "error")
            self.assertEqual(self.services.transcribed, [])
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_cancel_before_end_does_not_call_stt(self):
        reader, writer = await self.connect()
        try:
            writer.write(masked(json.dumps({
                "type": "auth", "token": "z" * 40, "session": "m-session123"
            }).encode()))
            await writer.drain()
            await read_event(reader)
            writer.write(masked(b'{"type":"start","speak":true}'))
            writer.write(masked(b"\0\0" * 8000, opcode=2))
            writer.write(masked(b'{"type":"cancel"}'))
            await writer.drain()
            self.assertEqual((await read_event(reader))["type"], "cancelled")
            self.assertEqual(self.services.transcribed, [])
        finally:
            writer.close()
            await writer.wait_closed()


if __name__ == "__main__":
    unittest.main()
