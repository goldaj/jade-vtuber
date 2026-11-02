import asyncio
import json
import unittest

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.local_http import LocalHTTP
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.messages import Incoming, Reply


class Echo:
    def __init__(self):
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return "Réponse mobile"


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gateway = None
        async def output(reply):
            self.gateway.deliver(reply)
        self.echo = Echo()
        self.runtime = Runtime(Dialogue(self.echo, "Jade"), output)
        await self.runtime.start()
        self.gateway = LocalHTTP(self.runtime, token="token"*9)
        self.server = await asyncio.start_server(
            self.gateway.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        await self.runtime.stop()

    async def request(self, *, key, value):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        payload = json.dumps(value).encode()
        w.write((f"POST /message HTTP/1.1\r\n"
                 f"Authorization: Bearer {key}\r\n"
                 f"Content-Length: {len(payload)}\r\n\r\n").encode() + payload)
        await w.drain()
        result = await r.read()
        w.close()
        await w.wait_closed()
        return result

    async def test_authorized_local_round_trip_and_reject_missing_token(self):
        missing = await self.request(key="bad", value={"text": "Jade"})
        self.assertIn(b"401 Unauthorized", missing)
        result = await self.request(key="token"*9, value={"text": "Salut Jade"})
        self.assertIn(b"200 OK", result)
        self.assertIn("Réponse mobile".encode(), result)
        self.assertFalse(self.gateway.pending)

    async def test_unrecognized_fields_never_enter_our_bot(self):
        result = await self.request(key="token"*9,
                                    value={"text": "Jade", "admin": True})
        self.assertIn(b"400 Bad Request", result)

    async def test_browser_page_served_without_exposing_token(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        page = await reader.read()
        writer.close()
        await writer.wait_closed()
        self.assertIn(b"200 OK", page)
        self.assertIn(b"Content-Security-Policy:", page)
        self.assertIn(b"Cache-Control: no-store", page)
        self.assertIn("Nouvelle discussion".encode(), page)
        self.assertIn(b"textContent=text", page)
        self.assertNotIn(b"tokentokentoken", page)

    async def test_two_browser_sessions_have_separate_histories(self):
        key = "token" * 9
        for session, text in [
            ("alpha", "Bonjour A"),
            ("beta", "Bonjour B"),
            ("alpha", "Suite A"),
        ]:
            response = await self.request(
                key=key, value={"text": text, "session": session})
            self.assertIn(b"200 OK", response)
        self.assertEqual([len(call) for call in self.echo.calls], [2, 2, 4])
        self.assertEqual(
            set(self.runtime.dialogue.history),
            {("local_http", "alpha"), ("local_http", "beta")})
        self.assertFalse(self.gateway.pending)

    async def test_session_validation_and_legacy_request(self):
        key = "token" * 9
        for session in ("../elsewhere", "", "a" * 65, 12, None):
            invalid = await self.request(
                key=key, value={"text": "Salut Jade", "session": session})
            self.assertIn(b"400 Bad Request", invalid)
        legacy = await self.request(key=key, value={"text": "Salut Jade"})
        self.assertIn(b"200 OK", legacy)
        self.assertIn(("local_http", "phone"), self.runtime.dialogue.history)
