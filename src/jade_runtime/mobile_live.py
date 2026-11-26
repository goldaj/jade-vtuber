"""Authenticated same-origin HTTP/WS control for the owner's Live microphone."""
from __future__ import annotations

import asyncio
import base64
from collections import deque
import hashlib
import hmac
import json
import time

from .live_sessions import LiveSessionError
from .mobile_duplex import WebSocketPeer

OWNER = "Goldaj"
LIVE_GET_ROUTES = frozenset(("/api/live/capabilities", "/api/voice/preferences"))
LIVE_POST_ROUTES = frozenset(("/api/voice/preferences", "/api/live/arm",
                              "/api/live/sessions", "/api/live/sessions/close"))
LIVE_SDP_BODY_LIMIT = 128 * 1024  # JSON envelope; decoded SDP is separately limited to 64 KiB.
_CONTROL_CLEANUP_SECONDS = 1.0


def _control_task_done(task):
    # Consume failures without logging private control frames or payloads.
    if not task.cancelled():
        task.exception()


async def live_http(gateway, writer, method, route, headers, body=b""):
    manager = gateway.live_manager
    if manager is None:
        if route == "/api/live/capabilities":
            await gateway._json(writer, 200, {"enabled": False, "available": False,
                                             "reason": "live_unavailable"})
        elif route == "/api/voice/preferences" and method == "GET":
            await gateway._json(writer, 200, {"mode": "classic", "revision": 0})
        else:
            await gateway._json(writer, 503, {"error": "live_unavailable", "code": "live_unavailable"})
        return
    try:
        if method == "GET":
            result = (await manager.capabilities(OWNER) if route == "/api/live/capabilities"
                      else await manager.preferences(OWNER))
        else:
            if headers.get("content-type", "").split(";")[0].strip() != "application/json":
                raise LiveSessionError("expected_json", 400)
            try:
                request = json.loads(body)
            except (ValueError, UnicodeError):
                raise LiveSessionError("invalid_json", 400) from None
            if not isinstance(request, dict):
                raise LiveSessionError("invalid_live_request", 400)
            if route == "/api/voice/preferences":
                if set(request) != {"mode", "revision"}:
                    raise LiveSessionError("invalid_voice_preference", 400)
                result = await manager.set_mode(OWNER, request["mode"], request["revision"])
            elif route == "/api/live/arm":
                if set(request) != {"client_id", "thread_id"}:
                    raise LiveSessionError("invalid_live_request", 400)
                # Cancel an unfinished classic turn before admitting a new
                # microphone owner. Its Runtime work is cancelled by _conversation.
                result = await manager.arm(OWNER, request["client_id"], request["thread_id"])
                for future in tuple(gateway.pending.values()):
                    if not future.done():
                        future.cancel()
            elif route == "/api/live/sessions":
                if set(request) != {"client_id", "thread_id", "lease_id", "request_id", "sdp"}:
                    raise LiveSessionError("invalid_live_request", 400)
                result = await manager.create_session(OWNER, **request)
            else:
                if (not {"client_id", "lease_id"}.issubset(request)
                        or set(request) - {"client_id", "lease_id", "reason", "drain", "release_arm"}
                        or type(request.get("drain", False)) is not bool
                        or request.get("release_arm", True) is not True):
                    raise LiveSessionError("invalid_live_close", 400)
                reason = request.get("reason", "user_stop")
                if not isinstance(reason, str) or not 1 <= len(reason) <= 64:
                    raise LiveSessionError("invalid_live_close", 400)
                # The client may request a mute, never extend idle or choose an
                # application/provider identity. Feature OFF still allows close.
                result = await manager.close(OWNER, request["client_id"], request["lease_id"],
                                             reason=reason, drain=request.get("drain", False))
        await gateway._json(writer, 200, result)
    except LiveSessionError as exc:
        result = {"error": exc.code, "code": exc.code, "state": manager.snapshot(OWNER)}
        if exc.code == "preference_conflict":
            result["preference"] = await manager.preferences(OWNER)
        await gateway._json(writer, exc.status, result)


async def live_control(gateway, reader, writer, headers):
    if gateway.live_manager is None:
        await gateway._json(writer, 503, {"error": "live_unavailable"})
        return
    if (headers.get("upgrade", "").lower() != "websocket"
            or "upgrade" not in {v.strip().lower() for v in headers.get("connection", "").split(",")}
            or headers.get("sec-websocket-version") != "13"
            or "jade-live-v1" not in {v.strip() for v in headers.get("sec-websocket-protocol", "").split(",")}):
        await gateway._json(writer, 400, {"error": "live_websocket_required"})
        return
    try:
        key = base64.b64decode(headers.get("sec-websocket-key", ""), validate=True)
    except (ValueError, base64.binascii.Error):
        key = b""
    if len(key) != 16:
        await gateway._json(writer, 400, {"error": "invalid_websocket_key"})
        return
    accept = base64.b64encode(hashlib.sha1((headers["sec-websocket-key"]
        + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
    writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                  "Connection: Upgrade\r\nSec-WebSocket-Protocol: jade-live-v1\r\n"
                  "Cache-Control: no-store\r\nSec-WebSocket-Accept: " + accept + "\r\n\r\n").encode("ascii"))
    async with asyncio.timeout(5):
        await writer.drain()
    peer = WebSocketPeer(reader, writer)
    manager, subscription = gateway.live_manager, None
    tasks = []
    closing = False
    try:
        async with asyncio.timeout(8):
            auth = await peer.receive()
        if (not isinstance(auth, dict) or auth.get("type") != "auth"
                or set(auth) != {"type", "token", "client_id", "thread_id", "lease_id"}
                or not isinstance(auth.get("token"), str)
                or not auth["token"].isascii() or len(auth["token"]) > 4096
                or not hmac.compare_digest(auth["token"], gateway.token)):
            raise LiveSessionError("authentication_required", 401)
        client_id, lease_id = auth["client_id"], auth["lease_id"]
        lease = manager._lease(OWNER, client_id, lease_id)
        if lease.thread_id != auth["thread_id"]:
            raise LiveSessionError("invalid_live_thread", 403)
        subscription, queue = await manager.subscribe(OWNER, client_id, lease_id)
        await peer.send({"type": "ready", "state": manager.snapshot(OWNER)})

        async def receive():
            timestamps = deque()
            while not closing:
                async with asyncio.timeout(manager.config.lease_seconds + 1):
                    frame = await peer.receive()
                if closing or frame is None:
                    return
                now = time.monotonic()
                while timestamps and now - timestamps[0] >= 1:
                    timestamps.popleft()
                if len(timestamps) >= 20 or not isinstance(frame, dict):
                    raise LiveSessionError("live_control_rate_limit", 429)
                timestamps.append(now)
                if not hmac.compare_digest(auth["token"], gateway.token):
                    raise LiveSessionError("authentication_revoked", 401)
                kind = frame.get("type")
                if kind == "heartbeat":
                    await peer.send(await manager.heartbeat(OWNER, client_id, lease_id, frame))
                elif kind == "playback":
                    await manager.observe_playback(OWNER, client_id, lease_id, frame)
                else:
                    raise LiveSessionError("unsupported_live_control", 400)

        async def send():
            while not closing:
                event = await queue.get()
                if closing:
                    return
                await peer.send(event)

        tasks = [asyncio.create_task(receive()), asyncio.create_task(send())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            await task
    except asyncio.CancelledError:
        raise
    except LiveSessionError as exc:
        try:
            await peer.send({"type": "incident", "code": exc.code,
                             "state": manager.snapshot(OWNER)})
        except Exception:
            pass
    except (ConnectionError, OSError, asyncio.TimeoutError, asyncio.IncompleteReadError, ValueError):
        pass
    finally:
        closing = True
        for task in tasks:
            task.cancel()
            task.add_done_callback(_control_task_done)
        try:
            # Release the lease and request provider closure before waiting for
            # socket cleanup: a task swallowing cancel must not keep Live armed.
            if subscription:
                await manager.unsubscribe(OWNER, subscription)
        finally:
            if tasks:
                _, pending = await asyncio.wait(tasks, timeout=_CONTROL_CLEANUP_SECONDS)
                for task in pending:
                    task.cancel()
            try:
                await peer._frame(8)
            except Exception:
                pass
