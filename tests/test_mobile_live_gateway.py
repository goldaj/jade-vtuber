"""Live HTTP/WS contract over loopback with a real manager and a fake provider.

All credentials, SDP, identities and ledger entries below are test fixtures.
No external request, account key, audio capture or paid call is performed.
"""
from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import replace
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.jade_runtime.live_usage import LiveUsageLedger
from src.jade_runtime.live_config import LiveConfig
from src.jade_runtime.live_provider import MAX_SDP_BYTES
from src.jade_runtime.live_sessions import LiveSessionManager
from src.jade_runtime.mobile_gateway import MobileGateway
from src.jade_runtime.mobile_duplex import WebSocketPeer
from src.jade_runtime.mobile_live import LIVE_SDP_BODY_LIMIT


TOKEN = "test-owner-token-" + "x" * 32
ORIGIN = "https://jade-private.tailtest.ts.net"
CLIENT = "test-client-12345"
THREAD = "m-test-thread-12345"
SDP = "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=fingerprint:sha-256 TEST\r\na=ice-ufrag:test\r\n"


def masked(payload, opcode=1):
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False).encode()
    mask = b"\x12\x34\x56\x78"
    size = len(payload)
    header = bytes((0x80 | opcode, size | 0x80)) if size < 126 else (
        bytes((0x80 | opcode, 0x80 | 126)) + struct.pack("!H", size)
        if size < 65536 else bytes((0x80 | opcode, 0x80 | 127)) + struct.pack("!Q", size))
    return header + mask + bytes(value ^ mask[index % 4] for index, value in enumerate(payload))


async def read_frame(reader):
    head = await asyncio.wait_for(reader.readexactly(2), 3)
    length = head[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]
    payload = await reader.readexactly(length)
    return head[0] & 0x0F, json.loads(payload) if payload and head[0] & 0x0F == 1 else payload


class FakeChannel:
    def __init__(self):
        self.events = asyncio.Queue()
        self.events.put_nowait({"type": "session.started", "event_id": "started"})
        self.sent = []

    async def send(self, event):
        self.sent.append(event)
        if event["type"] == "session.close":
            self.events.put_nowait({"type": "session.closed", "event_id": "closed",
                                   "reason": "closed", "usage": {"seconds": 0}})

    async def close(self):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.events.get()


class FakeProvider:
    def __init__(self):
        self.created = []
        self.channels = {}

    async def create_session(self, sdp, config):
        self.created.append((sdp, config))
        identifier = "provider-fixture-" + str(len(self.created))
        self.channels[identifier] = FakeChannel()
        return {"session_id": identifier, "sdp": SDP}

    @asynccontextmanager
    async def attach(self, identifier):
        yield self.channels[identifier]


class MobileLiveGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.config = replace(LiveConfig(), usage_db_path=str(root / "usage.sqlite3"),
                              session_db_path=str(root / "sessions.sqlite3"))
        self.provider = FakeProvider()
        self.usage = LiveUsageLedger(root / "usage.sqlite3")
        self.manager = LiveSessionManager(self.config, self.provider, self.usage, api_key_present=True)
        self.mobile = MobileGateway(SimpleNamespace(), SimpleNamespace(), token=TOKEN,
                                    owner_login="owner@example.test", public_origin=ORIGIN,
                                    live_manager=self.manager)
        self.server = await asyncio.start_server(self.mobile._accept, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.writers = []

    async def asyncTearDown(self):
        self.server.close()
        for writer in self.writers:
            writer.close()
        handlers = tuple(self.mobile.connections)
        for task in handlers:
            task.cancel()
        waiters = [*handlers, *(asyncio.create_task(writer.wait_closed()) for writer in self.writers)]
        pending = set()
        try:
            if waiters:
                done, pending = await asyncio.wait(waiters, timeout=3)
                for task in done:
                    if not task.cancelled():
                        task.exception()  # Expected peer resets must still be collected.
        finally:
            for task in pending:
                task.cancel()
            # Do not let an OS close handshake block the remaining fixture
            # cleanup, or await server closure before stopping its handlers.
            for writer in self.writers:
                writer.transport.abort()
            async with asyncio.timeout(3):
                await self.server.wait_closed()
            async with asyncio.timeout(3):
                await self.manager.stop()
        self.assertFalse(pending, "Live gateway fixture left unfinished socket/handler cleanup")

    def headers(self, authenticated=True):
        value = {"Host": f"127.0.0.1:{self.port}", "Origin": ORIGIN,
                 "Tailscale-User-Login": "owner@example.test"}
        if authenticated:
            value["Authorization"] = "Bearer " + TOKEN
        return value

    async def request(self, method, route, payload=None, *, body=None, headers=None, authenticated=True):
        values = self.headers(authenticated)
        if method == "POST":
            body = body if body is not None else json.dumps(payload).encode()
            values.update({"Content-Type": "application/json", "Content-Length": str(len(body))})
        else:
            body = b""
        for name, value in (headers or {}).items():
            if value is None:
                values.pop(name, None)
            else:
                values[name] = value
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.writers.append(writer)
        packet = [f"{method} {route} HTTP/1.1", *(f"{key}: {value}" for key, value in values.items())]
        writer.write(("\r\n".join(packet) + "\r\n\r\n").encode("ascii") + body)
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), 6)
        header, response = raw.split(b"\r\n\r\n", 1)
        status = int(header.split(b" ", 2)[1])
        try:
            response = json.loads(response)
        except (ValueError, UnicodeError):
            pass
        return status, response, header

    async def connect(self, headers=None, route="/api/live/control"):
        values = self.headers(False)
        values.update({"Upgrade": "websocket", "Connection": "Upgrade",
                       "Sec-WebSocket-Version": "13", "Sec-WebSocket-Protocol": "jade-live-v1",
                       "Sec-WebSocket-Key": base64.b64encode(b"test-live-key-12").decode()})
        for name, value in (headers or {}).items():
            if value is None:
                values.pop(name, None)
            else:
                values[name] = value
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        self.writers.append(writer)
        packet = [f"GET {route} HTTP/1.1", *(f"{key}: {value}" for key, value in values.items())]
        writer.write(("\r\n".join(packet) + "\r\n\r\n").encode("ascii"))
        await writer.drain()
        header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 3)
        return reader, writer, header

    async def arm(self):
        status, prefs, _ = await self.request("GET", "/api/voice/preferences")
        self.assertEqual(status, 200)
        if prefs["mode"] != "live":
            status, _, _ = await self.request("POST", "/api/voice/preferences", {"mode": "live", "revision": prefs["revision"]})
            self.assertEqual(status, 200)
        status, result, _ = await self.request("POST", "/api/live/arm", {"client_id": CLIENT, "thread_id": THREAD})
        self.assertEqual(status, 200, result)
        return result["lease_id"]

    async def authenticate(self, lease_id, **changes):
        reader, writer, header = await self.connect()
        self.assertIn(b"101 Switching Protocols", header)
        self.assertIn(b"Sec-WebSocket-Protocol: jade-live-v1", header)
        auth = {"type": "auth", "token": TOKEN, "client_id": CLIENT, "thread_id": THREAD, "lease_id": lease_id, **changes}
        writer.write(masked(auth))
        await writer.drain()
        opcode, event = await read_frame(reader)
        self.assertEqual(opcode, 1)
        return reader, writer, event

    async def until(self, reader, predicate):
        for _ in range(30):
            opcode, event = await read_frame(reader)
            if opcode == 8:
                self.fail("control connection closed before expected event")
            if predicate(event):
                return event
        self.fail("expected control event was not delivered")

    async def test_get_routes_are_private_and_do_not_admit_audio(self):
        for route in ("/api/live/capabilities", "/api/voice/preferences"):
            with self.subTest(route=route):
                status, _, _ = await self.request("GET", route, authenticated=False)
                self.assertEqual(status, 401)
                status, _, _ = await self.request("GET", route, headers={"Origin": "https://attacker.test"})
                self.assertEqual(status, 403)
                status, _, _ = await self.request("GET", route, headers={"Tailscale-User-Login": "other@example.test"})
                self.assertEqual(status, 403)
                status, value, header = await self.request("GET", route)
                self.assertEqual(status, 200)
                self.assertIn(b"Cache-Control: no-store", header)
                self.assertNotIn("api_key", value)
        self.assertEqual(self.provider.created, [])
        self.assertEqual(self.manager.snapshot("Goldaj")["lease_state"], "closed")
        self.assertEqual(self.usage.snapshot()["open_records"], 0)
        status, caps, _ = await self.request("GET", "/api/live/capabilities")
        self.assertEqual(status, 200)
        self.assertTrue(caps["available"])
        self.assertNotIn("budget", caps)
        status, prefs, _ = await self.request("GET", "/api/voice/preferences")
        self.assertEqual((status, prefs["mode"]), (200, "live"))

    async def test_profile_pref_is_revisioned_without_capture_and_conflict_returns_current(self):
        status, value, _ = await self.request("POST", "/api/voice/preferences", {"mode": "live", "revision": 0})
        self.assertEqual(status, 200)
        self.assertEqual(value, {"mode": "live", "revision": 1})
        status, value, _ = await self.request("POST", "/api/voice/preferences", {"mode": "classic", "revision": 0})
        self.assertEqual(status, 200, "OFF is conservative even when the client saw an older revision")
        self.assertEqual(value, {"mode": "classic", "revision": 2})
        status, value, _ = await self.request("POST", "/api/voice/preferences", {"mode": "live", "revision": 1})
        self.assertEqual(status, 409)
        self.assertEqual(value["code"], "preference_conflict")
        self.assertEqual(value["preference"], {"mode": "classic", "revision": 2})
        self.assertEqual(self.manager.snapshot("Goldaj")["lease_state"], "closed")
        self.assertEqual(self.provider.created, [])

    async def test_live_recover_without_lost_session_never_arms_microphone(self):
        status, result, _ = await self.request("POST", "/api/live/recover", {})
        self.assertEqual((status, result["lease_state"], result["session_state"]),
                         (200, "closed", "absent"))
        await self.arm()
        status, result, _ = await self.request("POST", "/api/live/recover", {})
        self.assertEqual((status, result["code"]), (409, "microphone_owned_by_other_client"))
        self.assertEqual(self.provider.created, [])

    async def test_http_payloads_cannot_override_identity_config_or_idle_policy(self):
        requests = (
            ("/api/live/recover", {"owner": "other"}),
            ("/api/voice/preferences", {"mode": "live", "revision": True}),
            ("/api/voice/preferences", {"mode": "live", "revision": 0, "owner": "other"}),
            ("/api/live/arm", {"client_id": CLIENT, "thread_id": THREAD, "channel": "discord"}),
            ("/api/live/arm", {"client_id": [], "thread_id": THREAD}),
            ("/api/live/sessions", {"client_id": CLIENT, "thread_id": THREAD, "lease_id": "none",
                                     "request_id": "request-1", "sdp": SDP, "model": "different"}),
            ("/api/live/sessions/close", {"client_id": CLIENT, "lease_id": "none", "release_arm": False}),
            ("/api/live/sessions/close", {"client_id": CLIENT, "lease_id": "none", "drain": "yes"}),
            ("/api/live/sessions/close", {"client_id": CLIENT, "lease_id": "none", "reason": "x" * 65}),
        )
        for route, payload in requests:
            with self.subTest(route=route, payload=payload):
                status, _, _ = await self.request("POST", route, payload)
                self.assertEqual(status, 400)
        for body in (b"[]", b"null", b"{", b"\xff"):
            status, _, _ = await self.request("POST", "/api/live/arm", body=body)
            self.assertEqual(status, 400)
        status, _, _ = await self.request("POST", "/api/live/arm", {}, headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 400)
        self.assertEqual(self.provider.created, [])

    async def test_post_auth_origin_and_size_are_checked_before_manager(self):
        routes = ("/api/voice/preferences", "/api/live/arm", "/api/live/sessions",
                  "/api/live/sessions/close", "/api/live/recover")
        for route in routes:
            with self.subTest(route=route):
                status, _, _ = await self.request("POST", route, {}, authenticated=False)
                self.assertEqual(status, 401)
                status, _, _ = await self.request("POST", route, {}, headers={"Origin": "https://attacker.test"})
                self.assertEqual(status, 403)
                status, _, _ = await self.request("POST", route, {}, headers={"Host": None})
                self.assertEqual(status, 403)
                status, _, _ = await self.request("POST", route, {}, headers={"Transfer-Encoding": "chunked"})
                self.assertEqual(status, 403)
        status, _, _ = await self.request("POST", "/api/live/sessions", {}, headers={"Content-Length": str(LIVE_SDP_BODY_LIMIT + 1)})
        self.assertEqual(status, 413)
        status, _, _ = await self.request("POST", "/api/live/arm", {}, headers={"Content-Length": "4097"})
        self.assertEqual(status, 413)
        self.assertEqual(self.provider.created, [])

    async def test_decoded_sdp_size_and_structure_are_validated_before_provider(self):
        exact = SDP + "a=x:" + "x" * (MAX_SDP_BYTES - len(SDP.encode()) - 4)
        self.assertEqual(len(exact.encode()), MAX_SDP_BYTES)
        payload = {"client_id": CLIENT, "thread_id": THREAD, "lease_id": "missing-lease", "request_id": "request-1"}
        for sdp in (None, [], "not-sdp", SDP + "\x00", exact + "x"):
            with self.subTest(kind=type(sdp).__name__, size=len(sdp) if isinstance(sdp, str) else None):
                status, value, _ = await self.request("POST", "/api/live/sessions", {**payload, "sdp": sdp})
                self.assertEqual(status, 400)
                self.assertEqual(value["code"], "invalid_sdp")
        status, value, _ = await self.request("POST", "/api/live/sessions", {**payload, "sdp": exact})
        self.assertEqual(status, 409, "a structurally valid 64 KiB SDP must reach the lease gate")
        self.assertEqual(value["code"], "invalid_or_expired_live_lease")
        self.assertEqual(self.provider.created, [])

    async def test_arm_is_exclusive_and_creation_needs_control(self):
        lease = await self.arm()
        status, value, _ = await self.request("POST", "/api/live/arm", {"client_id": "second-client", "thread_id": THREAD})
        self.assertEqual(status, 409)
        self.assertEqual(value["code"], "microphone_owned_by_other_client")
        status, value, _ = await self.request("POST", "/api/live/sessions", {
            "client_id": CLIENT, "thread_id": THREAD, "lease_id": lease, "request_id": "request-1", "sdp": SDP})
        self.assertEqual(status, 409)
        self.assertEqual(value["code"], "live_control_required")
        self.assertEqual(self.provider.created, [])
        self.assertEqual(self.usage.snapshot()["open_records"], 0)

    async def test_websocket_upgrade_validates_origin_owner_protocol_key_and_query(self):
        cases = (
            ({"Origin": "https://attacker.test"}, 403),
            ({"Tailscale-User-Login": "other@example.test"}, 403),
            ({"Sec-WebSocket-Protocol": "jade-v1"}, 400),
            ({"Sec-WebSocket-Key": "invalid"}, 400),
            ({"Sec-WebSocket-Version": "12"}, 400),
        )
        for headers, status in cases:
            with self.subTest(headers=headers):
                _, _, result = await self.connect(headers)
                self.assertIn(f"HTTP/1.1 {status}".encode(), result)
        _, _, result = await self.connect(route="/api/live/control?token=fixture")
        self.assertIn(b"HTTP/1.1 400", result)
        self.assertEqual(self.provider.created, [])

    async def test_websocket_first_frame_auth_and_thread_are_required(self):
        lease = await self.arm()
        for change, code in (({"token": "wrong"}, "authentication_required"),
                             ({"token": "été"}, "authentication_required"),
                             ({"thread_id": "other-thread"}, "invalid_live_thread"),
                             ({"model": "override"}, "authentication_required")):
            with self.subTest(change=change):
                _, _, event = await self.authenticate(lease, **change)
                self.assertEqual(event["type"], "incident")
                self.assertEqual(event["code"], code)
        self.assertEqual(self.provider.created, [])
        self.assertIsNone(self.manager._leases["Goldaj"].control_token)

    async def test_heartbeat_ack_echoes_seq_with_capture_closed_and_projection(self):
        lease = await self.arm()
        reader, writer, event = await self.authenticate(lease)
        self.assertEqual(event["type"], "ready")
        self.assertEqual(event["state"]["lease_id"], lease)
        writer.write(masked({"type": "heartbeat", "seq": 1, "visible": True,
                             "capture": "closed", "playback_active": False, "speech_active": False}))
        await writer.drain()
        event = await self.until(reader, lambda value: value.get("seq") == 1)
        self.assertEqual(event["type"], "state")
        self.assertEqual(event["lease_state"], "armed", "waiting for permission must not revoke the arm lease")
        writer.write(masked({"type": "heartbeat", "seq": 1, "visible": True, "capture": "armed"}))
        await writer.drain()
        event = await self.until(reader, lambda value: value.get("type") == "incident")
        self.assertEqual(event["code"], "stale_live_heartbeat")
        self.assertEqual(self.provider.created, [])

    async def test_real_http_creation_uses_opaque_handle_and_stop_survives_feature_off(self):
        lease = await self.arm()
        reader, writer, event = await self.authenticate(lease)
        self.assertEqual(event["type"], "ready")
        status, value, _ = await self.request("POST", "/api/live/sessions", {
            "client_id": CLIENT, "thread_id": THREAD, "lease_id": lease, "request_id": "request-1", "sdp": SDP})
        self.assertEqual(status, 200, value)
        self.assertEqual(value["sdp"], SDP)
        self.assertNotEqual(value["session_id"], "provider-fixture-1")
        self.assertEqual(len(self.provider.created), 1)
        self.assertEqual(self.provider.created[0][1]["client"]["data_channel"]["allowed_client_events"], [])
        self.manager.config = replace(self.manager.config, enabled=False)
        status, value, _ = await self.request("POST", "/api/live/sessions/close", {
            "client_id": CLIENT, "lease_id": lease, "reason": "sound_off", "drain": False, "release_arm": True})
        self.assertEqual(status, 200)
        self.assertEqual(value["lease_state"], "closed")
        self.assertIn(value["session_state"], ("closed", "absent"), "a provider terminal may precede async handle cleanup")
        self.assertIn({"type": "session.close"}, self.provider.channels["provider-fixture-1"].sent)
        self.assertEqual(len(self.provider.created), 1)

    async def test_disconnect_closes_provider_when_sender_swallows_one_cancellation(self):
        """Reproduce the Python 3.11 wait_for cancellation race deterministically.

        The old finally waited forever in gather(send), before unsubscribe:
        one swallowed cancellation returned the sender to queue.get while the
        owner lease and provider remained active. No wall-clock retry is used.
        """
        lease = await self.arm()
        reader, writer, event = await self.authenticate(lease)
        self.assertEqual(event["type"], "ready")
        original_frame = WebSocketPeer._frame
        entered, swallowed = asyncio.Event(), asyncio.Event()
        sender = None

        async def frame(peer, opcode, data=b""):
            nonlocal sender
            if opcode == 1 and json.loads(data).get("type") == "state" and not entered.is_set():
                sender = asyncio.current_task()
                entered.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    swallowed.set()
                    return  # Simulate wait_for returning a concurrently completed drain.
            await original_frame(peer, opcode, data)

        with patch.object(WebSocketPeer, "_frame", frame):
            status, result, _ = await self.request("POST", "/api/live/sessions", {
                "client_id": CLIENT, "thread_id": THREAD, "lease_id": lease,
                "request_id": "request-cancel-race", "sdp": SDP})
            self.assertEqual(status, 200, result)
            async with asyncio.timeout(1):
                await entered.wait()
            # Close the WS protocol while keeping TCP available to observe the
            # server's close frame. The peer cannot accidentally hide the race
            # by making the next server write fail with a connection reset.
            writer.write(masked(b"", opcode=8))
            await writer.drain()
            async with asyncio.timeout(1):
                await swallowed.wait()
            self.assertEqual(self.manager.snapshot("Goldaj")["lease_state"], "closed",
                             "lease invalidation must precede child-task cleanup")
            session = self.manager._sessions[result["session_id"]]
            async with asyncio.timeout(2):
                await session.closed.wait()
            self.assertIn({"type": "session.close"}, self.provider.channels["provider-fixture-1"].sent)
            async with asyncio.timeout(3):
                while True:
                    opcode, _ = await read_frame(reader)
                    if opcode == 8:
                        break
            self.assertIsNotNone(sender)
            done, _ = await asyncio.wait([sender], timeout=1)
            self.assertIn(sender, done, "sender must not survive in queue.get after connection closure")
            self.assertEqual(len(self.provider.created), 1)

    async def test_forbidden_provider_command_closes_control_without_creation(self):
        lease = await self.arm()
        reader, writer, event = await self.authenticate(lease)
        self.assertEqual(event["type"], "ready")
        writer.write(masked({"type": "session.update", "model": "different", "tools": []}))
        await writer.drain()
        event = await self.until(reader, lambda value: value.get("type") == "incident")
        self.assertEqual(event["code"], "unsupported_live_control")
        opcode, _ = await read_frame(reader)
        self.assertEqual(opcode, 8)
        self.assertEqual(self.manager.snapshot("Goldaj")["lease_state"], "closed")
        self.assertEqual(self.provider.created, [])

    async def test_auth_revocation_closes_the_current_control(self):
        lease = await self.arm()
        reader, writer, event = await self.authenticate(lease)
        self.assertEqual(event["type"], "ready")
        self.mobile.token = "rotated-test-token-" + "z" * 32
        writer.write(masked({"type": "heartbeat", "seq": 1, "visible": True, "capture": "armed"}))
        await writer.drain()
        event = await self.until(reader, lambda value: value.get("type") == "incident")
        self.assertEqual(event["code"], "authentication_revoked")
        opcode, _ = await read_frame(reader)
        self.assertEqual(opcode, 8)
        self.assertEqual(self.manager.snapshot("Goldaj")["lease_state"], "closed")

    async def test_control_rate_is_bounded_and_never_creates_sessions(self):
        lease = await self.arm()
        reader, writer, _ = await self.authenticate(lease)
        for seq in range(1, 22):
            writer.write(masked({"type": "heartbeat", "seq": seq, "visible": True, "capture": "closed"}))
        await writer.drain()
        event = await self.until(reader, lambda value: value.get("type") == "incident")
        self.assertEqual(event["code"], "live_control_rate_limit")
        self.assertEqual(self.provider.created, [])

    async def test_malformed_or_audio_control_frames_close_without_paid_work(self):
        frames = (masked(b"{"), masked(b"\0\0", opcode=2), masked(b"x" * 32769), b"\x81\x02{}")
        for frame in frames:
            with self.subTest(length=len(frame)):
                lease = await self.arm()
                reader, writer, event = await self.authenticate(lease)
                self.assertEqual(event["type"], "ready")
                writer.write(frame)
                await writer.drain()
                opcode, event = await read_frame(reader)
                if opcode == 1:
                    self.assertEqual(event["type"], "incident")
                    opcode, _ = await read_frame(reader)
                self.assertEqual(opcode, 8)
                self.assertEqual(self.manager.snapshot("Goldaj")["lease_state"], "closed")
                self.assertEqual(self.provider.created, [])

    async def test_missing_live_service_preserves_readonly_profile_and_classic(self):
        self.mobile.live_manager = None
        status, value, _ = await self.request("GET", "/api/live/capabilities")
        self.assertEqual(status, 200)
        self.assertFalse(value["available"])
        status, value, _ = await self.request("GET", "/api/voice/preferences")
        self.assertEqual(status, 200)
        self.assertEqual(value, {"mode": "classic", "revision": 0})
        status, _, _ = await self.request("POST", "/api/live/arm", {"client_id": CLIENT, "thread_id": THREAD})
        self.assertEqual(status, 503)
        for route in ("/assets/live-client.js", "/assets/live-audio-worklet.js"):
            status, content, _ = await self.request("GET", route, authenticated=False)
            self.assertEqual(status, 200)
            self.assertIn(b"use strict", content)


if __name__ == "__main__":
    unittest.main()
