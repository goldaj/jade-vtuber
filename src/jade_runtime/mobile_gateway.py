"""Owner-only mobile PWA gateway: localhost HTTP behind private Tailscale Serve.

No public bind, cookies, CORS, browser token storage, binary uploads on disk,
or secondary AI providers. Mobile text and microphone both enter Jade as the
same trusted "mobile" platform, owned by Goldaj. The HTTP bearer token and
Tailscale identity are independent barriers, not public username assertions.
"""
from __future__ import annotations

import asyncio
import base64
from io import BytesIO
import hmac
import json
import logging
from pathlib import Path, PurePosixPath
import re
import secrets
from urllib.parse import urlsplit
import wave

from .messages import Incoming

LOG = logging.getLogger("jade.mobile")
HERE = Path(__file__).resolve().parent
WEB_ROOT = HERE / "mobile_web"
ROOT = HERE.parents[1]
DEFAULT_MODEL = ROOT / "jade-modeling/runtime-installed/Jade_professional_r20_idle_complete"
SESSION = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
MODEL_FILE = re.compile(r"[A-Za-z0-9_./-]{1,140}\Z")
MAX_WAV = 1_000_000  # 20s of 16kHz mono PCM16, plus a small header.
MAX_RESPONSE_AUDIO = 7_000_000
VENDOR_NAMES = frozenset(("pixi.min.js", "live2dcubismcore.min.js", "cubism4.min.js"))
WEB_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/assets/avatar.js": ("avatar.js", "text/javascript; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
       "connect-src 'self'; img-src 'self' data: blob:; "
       "media-src 'self' blob:; worker-src 'self'; "
       "manifest-src 'self'; base-uri 'none'; form-action 'none'; "
       "frame-ancestors 'none'")


def validate_wav(audio: bytes) -> None:
    """Only short, well-formed mono PCM16 at 16 kHz enters OpenAI STT."""
    if not isinstance(audio, bytes) or not 44 <= len(audio) <= MAX_WAV:
        raise ValueError("invalid mobile microphone upload length")
    try:
        with wave.open(BytesIO(audio), "rb") as sound:
            valid = (sound.getnchannels() == 1 and sound.getsampwidth() == 2
                     and sound.getframerate() == 16000 and sound.getcomptype() == "NONE"
                     and 0 < sound.getnframes() <= 320000)
            if not valid:
                raise ValueError("expected 16kHz mono PCM16, maximum 20 seconds")
            frames = sound.readframes(sound.getnframes())
            if len(frames) != sound.getnframes() * 2:
                raise ValueError("truncated WAV")
    except (wave.Error, EOFError) as exc:
        raise ValueError("invalid WAV header") from exc


class MobileGateway:
    """Small stdlib HTTPS-proxy backend. The client receives speech as WAV data.

    The app is intended to run behind Tailscale Serve's HTTPS and private ACL.
    This server must NEVER bind to a non-loopback interface.
    """

    def __init__(self, runtime, services, *, token: str, port=8766,
                 web_root: Path | None = None, model_dir: Path | None = None,
                 vendor_dir: Path | None = None, owner_login: str | None = None):
        if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
            raise ValueError("JADE_MOBILE_TOKEN must contain 32-256 characters")
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("invalid mobile port")
        self.runtime, self.services = runtime, services
        if owner_login is not None and (not isinstance(owner_login, str)
                                         or not 3 <= len(owner_login.strip()) <= 256):
            raise ValueError("invalid Tailscale owner login")
        self.token, self.port = token, port
        self.owner_login = owner_login.strip().casefold() if owner_login else None
        self.web_root = Path(web_root or WEB_ROOT)
        self.model_dir = Path(model_dir or DEFAULT_MODEL)
        self.vendor_dir = Path(vendor_dir) if vendor_dir else None
        self.pending: dict[str, asyncio.Future] = {}
        self.connections: set[asyncio.Task] = set()
        self.active_connections = 0
        self.max_connections = 10
        self.semaphore = asyncio.Semaphore(2)
        self.request_timeout = 75

    def deliver(self, reply) -> None:
        """Called on the shared Runtime's response callback, before local TTS."""
        if reply.source.platform != "mobile":
            return
        pending = self.pending.get(reply.source.message_id)
        if pending is not None and not pending.done():
            pending.set_result(reply)

    @staticmethod
    def _headers(code: int, content_type: str, size: int) -> bytes:
        reason = {
            200: "OK", 400: "Bad Request", 401: "Unauthorized",
            403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
            413: "Payload Too Large", 429: "Too Many Requests",
            503: "Service Unavailable", 504: "Gateway Timeout",
        }.get(code, "Error")
        return (f"HTTP/1.1 {code} {reason}\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Length: {size}\r\n"
                "Cache-Control: no-store, max-age=0\r\n"
                "Connection: close\r\n"
                "X-Content-Type-Options: nosniff\r\n"
                "X-Frame-Options: DENY\r\n"
                "Referrer-Policy: no-referrer\r\n"
                f"Content-Security-Policy: {CSP}\r\n\r\n").encode("ascii")

    async def _send(self, writer, code: int, payload: bytes, content_type="application/json; charset=utf-8"):
        writer.write(self._headers(code, content_type, len(payload)))
        for start in range(0, len(payload), 65536):
            writer.write(payload[start:start + 65536])
            await asyncio.wait_for(writer.drain(), timeout=5)
        if not payload:
            await asyncio.wait_for(writer.drain(), timeout=5)

    async def _json(self, writer, code: int, value: dict):
        await self._send(writer, code, json.dumps(
            value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    @staticmethod
    def _origin_allowed(headers: dict[str, str]) -> bool:
        origin = headers.get("origin")
        if not origin:
            return True  # CLI clients still need the bearer token.
        host = headers.get("host", "").lower()
        try:
            parsed = urlsplit(origin)
            return (parsed.scheme in ("https", "http")
                    and parsed.netloc.lower() == host
                    and not parsed.path.strip("/")
                    and not parsed.query and not parsed.fragment
                    and (parsed.scheme == "https"
                         or host.startswith(("127.0.0.1:", "localhost:"))))
        except ValueError:
            return False

    def _model_files(self) -> tuple[set[str], bytes]:
        """Whitelist references from Jade.model3.json; never serve arbitrary files."""
        path = self.model_dir / "Jade.model3.json"
        model = json.loads(path.read_text(encoding="utf-8"))
        refs = model["FileReferences"]
        if not isinstance(refs, dict):
            raise ValueError("invalid model references")
        if not refs.get("Motions"):
            # Exported r20 has a valid idle motion but its model3.json does not
            # declare it. Add a virtual reference without mutating the asset.
            idle = self.model_dir / "Jade_idle.motion3.json"
            if idle.is_file():
                refs["Motions"] = {"Idle": [{"File": idle.name}]}
        allowed = {"Jade.model3.json"}
        for name in ("Moc", "DisplayInfo", "Physics", "Pose", "UserData"):
            if isinstance(refs.get(name), str):
                allowed.add(refs[name])
        for value in refs.get("Textures", []):
            if isinstance(value, str):
                allowed.add(value)
        for group in refs.get("Expressions", []):
            if isinstance(group, dict) and isinstance(group.get("File"), str):
                allowed.add(group["File"])
        for motions in refs.get("Motions", {}).values():
            for motion in motions:
                if isinstance(motion, dict) and isinstance(motion.get("File"), str):
                    allowed.add(motion["File"])
        allowed = {name for name in allowed
                   if MODEL_FILE.fullmatch(name)
                   and ".." not in PurePosixPath(name).parts
                   and not name.startswith("/")}
        return allowed, json.dumps(model, separators=(",", ":")).encode("utf-8")

    async def _static(self, writer, route: str):
        if route in ("/icon-192.png", "/icon-512.png"):
            from .mobile_icons import icon_png
            size = 192 if route == "/icon-192.png" else 512
            await self._send(writer, 200, await asyncio.to_thread(icon_png, size),
                             "image/png")
            return
        if route in WEB_FILES:
            filename, mime = WEB_FILES[route]
            path = self.web_root / filename
        elif route.startswith("/vendor/"):
            filename = route[len("/vendor/"):]
            if filename not in VENDOR_NAMES or self.vendor_dir is None:
                await self._json(writer, 404, {"error": "vendor runtime not configured"})
                return
            path, mime = self.vendor_dir / filename, "text/javascript; charset=utf-8"
        elif route.startswith("/model/"):
            filename = route[len("/model/"):]
            if (not MODEL_FILE.fullmatch(filename) or
                    ".." in PurePosixPath(filename).parts or
                    filename.startswith("/")):
                await self._json(writer, 404, {"error": "asset not found"})
                return
            try:
                allowed, virtual_model = await asyncio.to_thread(self._model_files)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                await self._json(writer, 503, {"error": "Live2D model unavailable"})
                return
            if filename not in allowed:
                await self._json(writer, 404, {"error": "asset not found"})
                return
            if filename == "Jade.model3.json":
                await self._send(writer, 200, virtual_model, "application/json; charset=utf-8")
                return
            path = self.model_dir.joinpath(*PurePosixPath(filename).parts)
            mime = {
                ".moc3": "application/octet-stream",
                ".png": "image/png",
                ".json": "application/json; charset=utf-8",
            }.get(path.suffix, "application/octet-stream")
        else:
            await self._json(writer, 404, {"error": "unknown route"})
            return
        try:
            # No redirects or symlinks to a private file outside approved roots.
            base = (self.web_root if route in WEB_FILES else
                    self.vendor_dir if route.startswith("/vendor/") else self.model_dir)
            if (base is None or not path.resolve().is_relative_to(base.resolve())
                    or path.is_symlink() or not path.is_file()
                    or path.stat().st_size > 40_000_000):
                raise FileNotFoundError()
            data = await asyncio.to_thread(path.read_bytes)
            if data.startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise FileNotFoundError("git lfs pull required")
        except OSError:
            await self._json(writer, 404, {"error": "asset missing or LFS not installed"})
            return
        await self._send(writer, 200, data, mime)

    async def _conversation(self, incoming: Incoming):
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending[incoming.message_id] = future
        work = None
        try:
            deadline = loop.time() + 50
            work = await self.runtime.submit(incoming, deadline=deadline)
            return await asyncio.wait_for(future, timeout=55)
        finally:
            if future.done() is False:
                future.cancel()
                if work is not None:
                    self.runtime.cancel_work(work)
            self.pending.pop(incoming.message_id, None)

    async def _post(self, writer, route: str, headers: dict, body: bytes):
        if route == "/api/chat":
            if headers.get("content-type", "").split(";")[0].strip() != "application/json":
                await self._json(writer, 400, {"error": "expected JSON"})
                return
            try:
                request = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                await self._json(writer, 400, {"error": "invalid JSON"})
                return
            if (type(request) is not dict or set(request) != {"text", "session", "speak"}
                    or not isinstance(request["text"], str)
                    or not request["text"].strip()
                    or len(request["text"]) > 1200 or type(request["speak"]) is not bool):
                await self._json(writer, 400, {"error": "invalid chat payload"})
                return
            text = request["text"].strip()
            session = request["session"]
            modality = "text"
        elif route == "/api/voice":
            if headers.get("content-type", "").split(";")[0].strip() != "audio/wav":
                await self._json(writer, 400, {"error": "expected WAV"})
                return
            try:
                validate_wav(body)
            except ValueError:
                await self._json(writer, 400, {"error": "invalid microphone WAV"})
                return
            session = headers.get("x-jade-session", "")
            speak_header = headers.get("x-jade-speak", "1")
            if speak_header not in ("0", "1"):
                await self._json(writer, 400, {"error": "invalid speech preference"})
                return
            modality = "voice"
            text = None
        else:
            await self._json(writer, 404, {"error": "unknown route"})
            return
        if not isinstance(session, str) or not SESSION.fullmatch(session):
            await self._json(writer, 400, {"error": "invalid session"})
            return
        if self.semaphore.locked():
            await self._json(writer, 429, {"error": "Jade est occupée"})
            return
        async with self.semaphore:
            try:
                async with asyncio.timeout(self.request_timeout):
                    if modality == "voice":
                        text = (await self.services.transcribe_wav(body)).strip()
                        if not text or len(text) > 1200:
                            await self._json(writer, 400, {"error": "transcription unavailable"})
                            return
                    source = Incoming(
                        platform="mobile", author="Goldaj",
                        channel=session, message_id=secrets.token_hex(16),
                        text=text, force_reply=True,
                        input_modality=modality,
                        requested_speech=(speak_header == "1" if modality == "voice"
                                          else request["speak"]),
                    )
                    reply = await self._conversation(source)
                    payload = {"reply": reply.text, "intent": reply.intent,
                               "transcript": text if modality == "voice" else None,
                               "audio_wav_b64": None, "audio_unavailable": False}
                    speak = source.requested_speech
                    if speak:
                        try:
                            speech = await self.services.synthesize_speech(
                                reply.text, intent=reply.intent)
                            audio = speech.audio
                            if not isinstance(audio, bytes) or not 44 <= len(audio) <= MAX_RESPONSE_AUDIO:
                                raise ValueError("invalid synthesized WAV")
                            # Apply the same voice/pitch profile as desktop speech
                            # when supported. Missing FFmpeg is a neutral fallback.
                            settings = getattr(self.services, "settings", None)
                            pitch = getattr(settings, "tts_pitch_semitones", 0)
                            if pitch:
                                from .pitch_shift import shift_wav
                                audio = await shift_wav(audio, pitch)
                            payload["audio_wav_b64"] = base64.b64encode(audio).decode("ascii")
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            LOG.warning("Mobile voice unavailable; text answer preserved")
                            payload["audio_unavailable"] = True
                    await self._json(writer, 200, payload)
            except asyncio.TimeoutError:
                await self._json(writer, 504, {"error": "Jade n'a pas répondu à temps"})
            except asyncio.QueueFull:
                await self._json(writer, 429, {"error": "Jade est occupée"})
            except Exception:
                LOG.warning("Mobile turn failed; no transcript/secret logged")
                await self._json(writer, 503, {"error": "Jade indisponible"})

    async def _handle(self, reader, writer):
        try:
            first = await asyncio.wait_for(reader.readline(), timeout=5)
            if len(first) > 1024 or not first.endswith(b" HTTP/1.1\r\n"):
                await self._json(writer, 400, {"error": "invalid request"})
                return
            try:
                method, route, version = first.decode("ascii").strip().split(" ")
            except (ValueError, UnicodeDecodeError):
                await self._json(writer, 400, {"error": "invalid request"})
                return
            if version != "HTTP/1.1" or method not in ("GET", "POST") or not route.startswith("/") or "?" in route or "%" in route:
                await self._json(writer, 400, {"error": "invalid path"})
                return
            headers = {}
            total = 0
            for _ in range(32):
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                total += len(line)
                if not line or total > 8192:
                    await self._json(writer, 413, {"error": "header limit"})
                    return
                if line == b"\r\n":
                    break
                if b":" not in line:
                    await self._json(writer, 400, {"error": "invalid header"})
                    return
                name, value = line.split(b":", 1)
                key = name.decode("ascii", "ignore").strip().lower()
                if key in headers:
                    await self._json(writer, 400, {"error": "duplicate header"})
                    return
                headers[key] = value.strip().decode("ascii", "ignore")
            else:
                await self._json(writer, 413, {"error": "too many headers"})
                return
            # Tailscale Serve injects the login and strips untrusted versions
            # supplied by remote clients. On the loopback address, another
            # local process could spoof it: the PC itself remains trusted.
            if (self.owner_login is not None and not hmac.compare_digest(
                    headers.get("tailscale-user-login", "").casefold(),
                    self.owner_login)):
                await self._json(writer, 403, {"error": "private owner required"})
                return
            if method == "GET":
                await self._static(writer, route)
                return
            if route not in ("/api/chat", "/api/voice"):
                await self._json(writer, 404, {"error": "unknown route"})
                return
            if (headers.get("transfer-encoding") or not self._origin_allowed(headers)
                    or headers.get("host", "") == ""):
                await self._json(writer, 403, {"error": "request not permitted"})
                return
            if not hmac.compare_digest(
                    headers.get("authorization", ""), "Bearer " + self.token):
                await self._json(writer, 401, {"error": "authentication required"})
                return
            size_str = headers.get("content-length", "")
            if not size_str.isascii() or not size_str.isdecimal():
                await self._json(writer, 400, {"error": "Content-Length required"})
                return
            size = int(size_str)
            max_size = MAX_WAV if route == "/api/voice" else 4096
            if not 1 <= size <= max_size:
                await self._json(writer, 413, {"error": "request too large"})
                return
            body = await asyncio.wait_for(reader.readexactly(size), timeout=10)
            await self._post(writer, route, headers, body)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            try:
                await self._json(writer, 504, {"error": "request timeout"})
            except Exception:
                pass
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.warning("Mobile HTTP handler failed; no personal data logged")
            try:
                await self._json(writer, 503, {"error": "service unavailable"})
            except Exception:
                pass
        finally:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=3)
            except (OSError, asyncio.TimeoutError):
                pass

    def _accept(self, reader, writer):
        if self.active_connections >= self.max_connections:
            writer.close()
            return
        self.active_connections += 1
        task = asyncio.create_task(self._handle(reader, writer), name="jade-mobile-http")
        self.connections.add(task)

        def finished(completed):
            self.connections.discard(completed)
            self.active_connections -= 1
            if not completed.cancelled() and completed.exception() is not None:
                LOG.warning("Mobile connection failed")
        task.add_done_callback(finished)

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
                await asyncio.gather(*pending, return_exceptions=True)
            for future in self.pending.values():
                if not future.done():
                    future.cancel()
            self.pending.clear()
