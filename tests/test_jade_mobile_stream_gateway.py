"""Streaming protocol and disconnect tests, with no external services."""
import asyncio
import base64
from io import BytesIO
import json
from types import SimpleNamespace
import unittest
import wave

from src.jade_runtime.mobile_gateway import MobileGateway


def microphone_wav():
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)
    return output.getvalue()


class MobileStreamingGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.release = asyncio.Event()
        self.closed = asyncio.Event()
        self.fake = SimpleNamespace(settings=SimpleNamespace(tts_pitch_semitones=0))
        self.mobile = MobileGateway(SimpleNamespace(), self.fake, token="x" * 40)
        async def conversation(_incoming):
            return SimpleNamespace(text="Bonjour !", intent="neutral")
        self.mobile._conversation = conversation
        self.server = await asyncio.start_server(self.mobile._accept, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.release.set()
        self.server.close()
        await self.server.wait_closed()
        if self.mobile.connections:
            await asyncio.wait_for(asyncio.gather(*self.mobile.connections), timeout=3)

    async def request(self, route, body, content_type, extra="", *, streaming=True):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        stream_header = "X-Jade-Stream: 1\r\n" if streaming else ""
        head = (f"POST {route} HTTP/1.1\r\nHost: localhost:{self.port}\r\n"
                f"Authorization: Bearer {'x' * 40}\r\nContent-Type: {content_type}\r\n"
                f"Content-Length: {len(body)}\r\n{stream_header}{extra}\r\n")
        writer.write(head.encode() + body)
        await writer.drain()
        return reader, writer

    async def read_event(self, reader):
        length = int((await asyncio.wait_for(reader.readline(), 2)).strip(), 16)
        if not length:
            await reader.readexactly(2)
            return None
        data = await reader.readexactly(length)
        self.assertEqual(await reader.readexactly(2), b"\r\n")
        return json.loads(data)

    async def test_first_pcm_arrives_before_provider_finishes(self):
        async def speech():
            try:
                yield b"\x00\x01\x02\x03"
                await self.release.wait()
                yield b"\x04\x05"
            finally:
                self.closed.set()
        self.fake.stream_speech_pcm = lambda text, *, intent: speech()
        body = json.dumps({"text":"Salut", "session":"mobile-1234", "speak":True}).encode()
        reader, writer = await self.request("/api/chat", body, "application/json")
        headers = await reader.readuntil(b"\r\n\r\n")
        self.assertIn(b"Transfer-Encoding: chunked", headers)
        self.assertEqual((await self.read_event(reader))["type"], "reply")
        first = await self.read_event(reader)
        self.assertEqual(first["type"], "pcm")
        self.assertEqual(base64.b64decode(first["pcm_b64"]), b"\x00\x01\x02\x03")
        self.assertFalse(self.closed.is_set())
        self.release.set()
        self.assertEqual((await self.read_event(reader))["type"], "pcm")
        self.assertEqual((await self.read_event(reader))["type"], "done")
        self.assertIsNone(await self.read_event(reader))
        writer.close()
        await writer.wait_closed()

    async def test_text_only_uses_no_synthesis(self):
        body = json.dumps({"text":"Salut", "session":"mobile-1234", "speak":False}).encode()
        reader, writer = await self.request("/api/chat", body, "application/json")
        await reader.readuntil(b"\r\n\r\n")
        self.assertEqual((await self.read_event(reader))["type"], "reply")
        self.assertEqual((await self.read_event(reader))["type"], "done")
        self.assertIsNone(await self.read_event(reader))
        writer.close()
        await writer.wait_closed()

    async def test_disconnect_closes_active_synthesis(self):
        async def speech():
            try:
                yield b"\x00\x01"
                await self.release.wait()
                yield b"\x02\x03"
            finally:
                self.closed.set()
        self.fake.stream_speech_pcm = lambda text, *, intent: speech()
        body = json.dumps({"text":"Salut", "session":"mobile-1234", "speak":True}).encode()
        reader, writer = await self.request("/api/chat", body, "application/json")
        await reader.readuntil(b"\r\n\r\n")
        await self.read_event(reader)
        await self.read_event(reader)
        writer.close()
        await writer.wait_closed()
        await asyncio.wait_for(self.closed.wait(), 2)

    async def test_disconnect_cancels_transcription_before_reply(self):
        started = asyncio.Event()
        async def transcribe(_body):
            started.set()
            try:
                await self.release.wait()
            finally:
                self.closed.set()
        self.fake.transcribe_wav = transcribe
        reader, writer = await self.request("/api/voice", microphone_wav(), "audio/wav",
                                           "X-Jade-Session: mobile-1234\r\n")
        await asyncio.wait_for(started.wait(), 2)
        writer.close()
        await writer.wait_closed()
        await asyncio.wait_for(self.closed.wait(), 2)

    async def test_disconnect_cancels_nonstreaming_chat_before_reply(self):
        started = asyncio.Event()

        async def conversation(_incoming):
            started.set()
            try:
                await self.release.wait()
            finally:
                self.closed.set()

        self.mobile._conversation = conversation
        body = json.dumps({"text": "Salut", "session": "mobile-1234", "speak": False}).encode()
        _, writer = await self.request("/api/chat", body, "application/json", streaming=False)
        await asyncio.wait_for(started.wait(), 2)
        writer.close()
        await writer.wait_closed()
        await asyncio.wait_for(self.closed.wait(), 2)
