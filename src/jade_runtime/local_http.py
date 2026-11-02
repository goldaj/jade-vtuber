"""Read-only-by-default local (127.0.0.1) HTTP bridge for a future phone UI.

Bearer authorization, no CORS, strict body limits and a fixed endpoint.
Do NOT bind to 0.0.0.0 or expose plain HTTP on a shared network.
Future mobile access needs an authenticated TLS tunnel/reverse proxy.
"""
import asyncio
import hmac
import json
import logging
import re
import secrets

from .phone_ui import PHONE_HTML

from .messages import Incoming


class LocalHTTP:
    def __init__(self, runtime, *, token: str, port=8765):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("local HTTP token must be 32+ characters")
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("invalid local API port")
        self.runtime, self.token, self.port = runtime, token, port
        self.pending: dict[str, asyncio.Future] = {}
        self.active_connections = 0
        self.connections: set[asyncio.Task] = set()
        self.max_connections = 16
        self.request_timeout = 25.0
        self.log = logging.getLogger("jade.http")

    def deliver(self, reply) -> None:
        if reply.source.platform != "local_http":
            return
        future = self.pending.get(reply.source.message_id)
        if future is not None and not future.done():
            future.set_result(reply.text)

    async def _response(self, writer, status: int, value: dict):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        labels = {200: "OK", 400: "Bad Request", 401: "Unauthorized",
                  413: "Payload Too Large", 429: "Too Many Requests",
                  503: "Service Unavailable", 504: "Gateway Timeout"}
        reason = labels.get(status, "Error")
        writer.write((f"HTTP/1.1 {status} {reason}\r\n"
                      "Content-Type: application/json; charset=utf-8\r\n"
                      "Cache-Control: no-store\r\n"
                      "Connection: close\r\n"
                      "X-Content-Type-Options: nosniff\r\n"
                      f"Content-Length: {len(payload)}\r\n\r\n").encode() + payload)
        await asyncio.wait_for(writer.drain(), timeout=5)

    async def _page(self, writer):
        # The browser interface contains no credentials, and is loopback-only.
        payload = PHONE_HTML.encode("utf-8")
        writer.write((
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            "Cache-Control: no-store\r\n"
            "Connection: close\r\n"
            "X-Content-Type-Options: nosniff\r\n"
            "X-Frame-Options: DENY\r\n"
            "Referrer-Policy: no-referrer\r\n"
            "Content-Security-Policy: default-src 'none'; "
            "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "connect-src 'self'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'none'\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
        ).encode("ascii") + payload)
        await asyncio.wait_for(writer.drain(), timeout=5)

    async def handle(self, reader, writer):
        if self.active_connections >= self.max_connections:
            writer.close()
            return
        self.active_connections += 1
        try:
            await self._handle(reader, writer)
        finally:
            self.active_connections -= 1

    def _accept(self, reader, writer):
        # The callback is synchronous: reject before start_server can create
        # an unbounded number of waiting handler tasks.
        if self.active_connections >= self.max_connections:
            writer.close()
            return
        self.active_connections += 1
        task = asyncio.create_task(self._handle(reader, writer))
        self.connections.add(task)

        def finished(completed):
            self.connections.discard(completed)
            self.active_connections -= 1
            if not completed.cancelled() and completed.exception() is not None:
                self.log.warning("local HTTP handler failed (no content logged)")

        task.add_done_callback(finished)

    async def _handle(self, reader, writer):
        try:
            header_deadline = asyncio.get_running_loop().time() + 5
            first = await asyncio.wait_for(reader.readline(), timeout=5)
            is_page = first == b"GET / HTTP/1.1\r\n"
            if not is_page and first != b"POST /message HTTP/1.1\r\n":
                await self._response(writer, 400, {"error": "invalid request"})
                return
            headers = {}
            size = 0
            while True:
                remaining = max(0, header_deadline - asyncio.get_running_loop().time())
                line = await asyncio.wait_for(reader.readline(), timeout=remaining)
                size += len(line)
                if not line or size > 8192 or len(headers) >= 32:
                    await self._response(writer, 413, {"error": "header limit"})
                    return
                if line == b"\r\n":
                    break
                if b":" not in line:
                    await self._response(writer, 400, {"error": "bad header"})
                    return
                name, value = line.split(b":", 1)
                key = name.decode("ascii", "ignore").strip().lower()
                if key in headers:  # Avoid request smuggling, ambiguous auth.
                    await self._response(writer, 400, {"error": "duplicate header"})
                    return
                headers[key] = value.strip().decode("ascii", "ignore")
            if is_page:
                await self._page(writer)
                return
            authorized = hmac.compare_digest(
                headers.get("authorization", ""), "Bearer " + self.token)
            if not authorized:
                await self._response(writer, 401, {"error": "unauthorized"})
                return
            length_text = headers.get("content-length", "")
            if not length_text.isdecimal():
                await self._response(writer, 400, {"error": "length required"})
                return
            length = int(length_text)
            if not 1 <= length <= 4096:
                await self._response(writer, 413, {"error": "body limit"})
                return
            content = await asyncio.wait_for(reader.readexactly(length), timeout=5)
            try:
                data = json.loads(content)
            except (UnicodeDecodeError, ValueError):
                await self._response(writer, 400, {"error": "invalid JSON"})
                return
            if (type(data) is not dict or "text" not in data
                    or not set(data) <= {"text", "session"}):
                await self._response(writer, 400, {"error": "only text/session permitted"})
                return
            session = data.get("session", "phone")
            if type(session) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session) is None:
                await self._response(writer, 400, {"error": "invalid session"})
                return
            text = data["text"]
            if not isinstance(text, str) or not text.strip() or len(text) > 1200:
                await self._response(writer, 400, {"error": "invalid text"})
                return
            uid = secrets.token_hex(16)
            future = asyncio.get_running_loop().create_future()
            self.pending[uid] = future
            work = None
            try:
                try:
                    deadline = asyncio.get_running_loop().time() + self.request_timeout
                    work = await self.runtime.submit(Incoming(
                        "local_http", "phone", text, session, uid, True),
                        deadline=deadline, result=future)
                except asyncio.QueueFull:
                    await self._response(writer, 429, {"error": "busy"})
                    return
                try:
                    result = await asyncio.wait_for(future, timeout=self.request_timeout)
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        raise
                    await self._response(writer, 503, {"error": "unavailable"})
                    return
                await self._response(writer, 200, {"reply": result})
            finally:
                if work is not None and future.cancelled():
                    self.runtime.cancel_work(work)
                self.pending.pop(uid, None)
        except (TimeoutError, asyncio.IncompleteReadError):
            await self._response(writer, 504, {"error": "timeout"})
        except Exception:
            self.log.warning("local HTTP request failed (no content logged)")
            try:
                await self._response(writer, 503, {"error": "unavailable"})
            except Exception:
                pass
        finally:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=5)
            except (TimeoutError, OSError):
                pass

    async def serve_forever(self):
        server = await asyncio.start_server(
            self._accept, host="127.0.0.1", port=self.port, limit=16384)
        try:
            async with server:
                await server.serve_forever()
        finally:
            pending = set(self.connections)
            for task in pending:
                task.cancel()
            if pending:
                _, pending = await asyncio.wait(pending, timeout=5)
                if pending:
                    self.log.warning("local HTTP handlers did not stop within deadline")
