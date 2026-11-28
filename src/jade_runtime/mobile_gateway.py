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
import sqlite3
from urllib.parse import urlsplit, quote
import wave
import time

from .messages import Incoming
from .incidents import incident_for_client
from .intent_visuals import public_visual_contract
from .mobile_live import LIVE_GET_ROUTES, LIVE_POST_ROUTES, LIVE_SDP_BODY_LIMIT

LOG = logging.getLogger("jade.mobile")
DISCORD_LIVE_ROUTE = "/api/discord/live"
HERE = Path(__file__).resolve().parent
WEB_ROOT = HERE / "mobile_web"
ROOT = HERE.parents[1]
DEFAULT_MODEL = ROOT / "jade-modeling/runtime-installed/Jade_professional_r20_idle_complete"
R21_MODEL = (ROOT / "jade-modeling/assets/live2d/r21_professional_art/livraison"
             / "Jade_r21_v45_1/Jade_r21_v45")
R21_EXPRESSIONS = ("Blink", "WinkL", "WinkR", "Surprised")
SESSION = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
MODEL_FILE = re.compile(r"[A-Za-z0-9_./-]{1,140}\Z")
MAX_WAV = 1_000_000  # 20s of 16kHz mono PCM16, plus a small header.
MAX_RESPONSE_AUDIO = 7_000_000
VENDOR_NAMES = frozenset((
    "pixi.min.js", "pixi-unsafe-eval.min.js", "live2dcubismcore.min.js", "cubism4.min.js",
))
WEB_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/salon.html": ("salon.html", "text/html; charset=utf-8"),
    "/assets/login.css": ("login.css", "text/css; charset=utf-8"),
    "/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/assets/jade-theme.css": ("jade-theme.css", "text/css; charset=utf-8"),
    "/assets/splash.js": ("splash.js", "text/javascript; charset=utf-8"),
    "/assets/login-guard.js": ("login-guard.js", "text/javascript; charset=utf-8"),
    "/assets/splash-jade.png": ("splash-jade.png", "image/png"),
    "/assets/avatar.js": ("avatar.js", "text/javascript; charset=utf-8"),
    "/assets/avatar-gestures.js": ("avatar-gestures.js", "text/javascript; charset=utf-8"),
    "/assets/avatar-shake.js": ("avatar-shake.js", "text/javascript; charset=utf-8"),
    "/assets/avatar-models.js": ("avatar-models.js", "text/javascript; charset=utf-8"),
    "/assets/avatar-model-loader.js": ("avatar-model-loader.js", "text/javascript; charset=utf-8"),
    "/assets/room-motion.js": ("room-motion.js", "text/javascript; charset=utf-8"),
    "/assets/seated-scene.js": ("seated-scene.js", "text/javascript; charset=utf-8"),
    "/assets/portrait-bedroom-motion.js": ("portrait-bedroom-motion.js", "text/javascript; charset=utf-8"),
    "/assets/head-isolation.js": ("head-isolation.js", "text/javascript; charset=utf-8"),
    "/assets/room-bedroom-portrait.avif": ("room-bedroom-portrait.avif", "image/avif"),
    "/assets/jade-seated-body.avif": ("jade-seated-body.avif", "image/avif"),
    "/assets/room-kitchen-portrait.avif": ("room-kitchen-portrait.avif", "image/avif"),
    "/assets/room-living-portrait.avif": ("room-living-portrait.avif", "image/avif"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/assets/preferences.js": ("preferences.js", "text/javascript; charset=utf-8"),
    "/assets/duplex-client.js": ("duplex-client.js", "text/javascript; charset=utf-8"),
    "/assets/live-client.js": ("live-client.js", "text/javascript; charset=utf-8"),
    "/assets/live-audio-worklet.js": ("live-audio-worklet.js", "text/javascript; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
}
# Cubism Web Core may compile WebAssembly at runtime. 'wasm-unsafe-eval' is
# narrower than 'unsafe-eval': permit WASM only, never dynamic JavaScript eval.
CSP = ("default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; "
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
                 second_model_dir: Path | None = None,
                 vendor_dir: Path | None = None, owner_login: str | None = None,
                 public_origin: str | None = None,
                 avatar_intent_enabled: bool = True, billing_admin_key: str = "",
                 reminder_service=None, live_manager=None):
        if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
            raise ValueError("JADE_MOBILE_TOKEN must contain 32-256 characters")
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("invalid mobile port")
        self.runtime, self.services = runtime, services
        self.document_store = getattr(getattr(runtime, "document_service", None), "store", None)
        self.reminders = reminder_service
        self.live_manager = live_manager
        self.discord_live_policy = None
        self.discord_live_adapter = None
        self._discord_live_settings_lock = asyncio.Lock()
        if owner_login is not None and (not isinstance(owner_login, str)
                                         or not 3 <= len(owner_login.strip()) <= 256
                                         or not owner_login.isascii()):
            raise ValueError("invalid Tailscale owner login")
        self.token, self.port = token, port
        self.avatar_intent_enabled = bool(avatar_intent_enabled)
        self.owner_login = owner_login.strip().casefold() if owner_login else None
        if public_origin is not None:
            origin = urlsplit(public_origin)
            if (origin.scheme != "https" or not origin.hostname
                    or not origin.hostname.endswith(".ts.net")
                    or origin.path or origin.query or origin.fragment
                    or origin.username or origin.password
                    or public_origin.endswith("/")):
                raise ValueError("invalid Tailscale HTTPS origin")
        self.public_origin = public_origin
        self.web_root = Path(web_root or WEB_ROOT)
        self.model_dir = Path(model_dir or DEFAULT_MODEL)
        # This slot is opt-in. Never search the repository for newer artwork.
        self.second_model_dir = Path(second_model_dir) if second_model_dir else None
        self.vendor_dir = Path(vendor_dir) if vendor_dir else None
        self.pending: dict[str, asyncio.Future] = {}
        self.connections: set[asyncio.Task] = set()
        self.active_connections = 0
        self.max_connections = 10
        self.semaphore = asyncio.Semaphore(2)
        self.request_timeout = 75
        from .billing import BillingCosts
        self.billing = BillingCosts(billing_admin_key)
        # Remote administration now lives outside Jade, at /control via Tailscale
        # Serve, and stays available while this runtime is restarting.

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
            200: "OK", 202: "Accepted", 400: "Bad Request", 401: "Unauthorized",
            403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
            409: "Conflict",
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

    async def _download_document(self, writer, route: str):
        if self.document_store is None:
            await self._json(writer, 404, {"error": "document unavailable"})
            return
        try:
            record = await asyncio.to_thread(
                self.document_store.read, route[len("/api/documents/"):])
        except ValueError:
            record = None
        if record is None:
            await self._json(writer, 404, {"error": "document expired or unavailable"})
            return
        attachment, payload = record
        disposition = ("Content-Disposition: attachment; filename*=UTF-8''"
                       + quote(attachment.name, safe="") + "\r\n")
        header = self._headers(200, "application/octet-stream", len(payload))
        header = header.replace(b"Connection: close\r\n",
                                disposition.encode("ascii") + b"Connection: close\r\n")
        writer.write(header)
        for start in range(0, len(payload), 65536):
            writer.write(payload[start:start + 65536])
            await asyncio.wait_for(writer.drain(), timeout=5)

    async def _json(self, writer, code: int, value: dict):
        await self._send(writer, code, json.dumps(
            value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    async def _stream_event(self, writer, value):
        payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        writer.write(f"{len(payload):X}\r\n".encode("ascii") + payload + b"\r\n")
        await asyncio.wait_for(writer.drain(), timeout=5)

    async def _stream_reply(self, writer, payload, speak):
        from .mobile_audio_stream import speech_events
        from .pcm_timing import PCMProgressTiming, log_mobile_progress
        headers = self._headers(200, "application/x-ndjson; charset=utf-8", 0)
        headers = headers.replace(b"Content-Length: 0\r\n", b"Transfer-Encoding: chunked\r\n")
        writer.write(headers)
        await self._stream_event(writer, {"type": "reply", **payload})
        if speak:
            timing = PCMProgressTiming()
            first_sent_at = None
            transfer_completed = False
            events = speech_events(self.services, payload["reply"], payload["intent"],
                                   timing=timing)
            try:
                async for event in events:
                    await self._stream_event(writer, event)
                    if event["type"] == "pcm" and first_sent_at is None:
                        first_sent_at = time.monotonic()
                transfer_completed = True
            except asyncio.CancelledError:
                raise
            except (ConnectionError, OSError):
                raise
            except Exception as exc:
                LOG.warning("Mobile streaming voice unavailable; text answer preserved")
                await self._stream_event(writer, {"type": "audio_error",
                                                  **incident_for_client(exc)})
            finally:
                try:
                    await events.aclose()
                finally:
                    log_mobile_progress(timing, first_sent_at,
                                        transfer_completed=transfer_completed,
                                        transport="http_ndjson")
        await self._stream_event(writer, {"type": "done"})
        writer.write(b"0\r\n\r\n")
        await asyncio.wait_for(writer.drain(), timeout=5)

    def _origin_allowed(self, headers: dict[str, str]) -> bool:
        origin = headers.get("origin")
        if not origin:
            return True  # CLI clients still need the bearer token.
        host = headers.get("host", "").lower()
        if self.public_origin is not None:
            if not isinstance(origin, str) or not origin.isascii() or len(origin) > 256:
                return False
            # Go ReverseProxy SetURL() rewrites the backend Host to localhost;
            # the browser Origin remains the HTTPS .ts.net public hostname.
            # Compare to a deliberately configured origin, never that Host.
            return hmac.compare_digest(origin, self.public_origin)
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

    def _second_model_files(self) -> tuple[dict[str, tuple[Path, Path]], dict]:
        """Validate the local r21 and prepare its web manifest without editing the export."""
        built_in = self.second_model_dir is None
        base = self.second_model_dir or R21_MODEL
        manifest_name = "Jade.model3.json"
        if built_in:
            manifest_name = "Jade_r21_mobile.model3.json"
            if not (base / manifest_name).exists():
                manifest_name = "Jade_r21_v45.model3.json"

        def local_asset(name: str, directory: Path = base) -> Path:
            if (not isinstance(name, str) or not MODEL_FILE.fullmatch(name)
                    or any(part in ("", ".", "..") for part in name.split("/"))):
                raise ValueError("invalid model asset reference")
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("model bundle unavailable")
            path = directory
            for part in PurePosixPath(name).parts:
                path = path / part
                if path.is_symlink():
                    raise ValueError("symlink in model bundle")
            if (not path.resolve(strict=True).is_relative_to(directory.resolve())
                    or not path.is_file() or not 0 < path.stat().st_size <= 40_000_000):
                raise ValueError("invalid model asset")
            with path.open("rb") as asset:
                prefix = asset.read(128)
            if prefix.startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise ValueError("model asset not materialized")
            if ((path.suffix.lower() == ".moc3" and not prefix.startswith(b"MOC3"))
                    or (path.suffix.lower() == ".png" and not prefix.startswith(b"\x89PNG\r\n\x1a\n"))):
                raise ValueError("invalid model binary asset")
            return path

        manifest = local_asset(manifest_name)
        if manifest.stat().st_size > 1_000_000:
            raise ValueError("oversized model manifest")
        model = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(model, dict) or model.get("Version") != 3:
            raise ValueError("invalid model manifest")
        refs = model.get("FileReferences")
        if not isinstance(refs, dict):
            raise ValueError("invalid model references")
        allowed = {"Jade.model3.json": (manifest, base)}

        def include(name, suffixes, directory=base):
            if not isinstance(name, str) or PurePosixPath(name).suffix.lower() not in suffixes:
                raise ValueError("invalid model asset type")
            path = local_asset(name, directory)
            if path.suffix.lower() == ".json":
                if path.stat().st_size > 8_000_000 or not isinstance(
                        json.loads(path.read_text(encoding="utf-8")), dict):
                    raise ValueError("invalid model JSON asset")
            allowed[name] = (path, directory)
            if len(allowed) > 256:
                raise ValueError("too many model assets")

        include(refs.get("Moc"), {".moc3"})
        textures = refs.get("Textures")
        if not isinstance(textures, list) or not 1 <= len(textures) <= 64:
            raise ValueError("model requires 1-64 textures")
        for name in textures:
            include(name, {".png"})
        for key in ("DisplayInfo", "Physics", "Pose", "UserData"):
            if key in refs:
                include(refs[key], {".json"})
        expressions = refs.get("Expressions", [])
        motions = refs.get("Motions", {})
        if not isinstance(expressions, list) or not isinstance(motions, dict):
            raise ValueError("invalid model animations")
        groups = [expressions, *motions.values()]
        for group in groups:
            if not isinstance(group, list):
                raise ValueError("invalid model animation group")
            for entry in group:
                if not isinstance(entry, dict):
                    raise ValueError("invalid model animation")
                include(entry.get("File"), {".json"})
                if "Sound" in entry:
                    include(entry["Sound"], {".wav", ".mp3", ".ogg"})
        if built_in:
            for name in R21_EXPRESSIONS:
                filename = f"r21-expressions/{name}.exp3.json"
                include(filename, {".json"}, self.web_root)
                expressions.append({"Name": name, "File": filename})
            refs["Expressions"] = expressions
        return allowed, model

    def _avatar_models(self) -> dict:
        try:
            _, model = self._second_model_files()
            available = True
            idle = "Idle" if model["FileReferences"].get("Motions", {}).get("Idle") else None
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            available, idle = False, None
        return {"version": 1, "defaultId": "next" if available else "classic", "models": [
            {"id": "classic", "label": "Jade classique (r20)", "available": True,
             "manifestUrl": "/model/Jade.model3.json", "presentation": "seated",
             "classicIntents": True, "idleMotion": "Idle"},
            {"id": "next", "label": "Jade actuelle (r21)", "available": available,
             "manifestUrl": "/models/next/Jade.model3.json" if available else None,
             "presentation": "full", "classicIntents": False, "idleMotion": idle},
        ]}

    async def _static(self, writer, route: str):
        if route == "/assets/avatar-models.json":
            await self._json(writer, 200, await asyncio.to_thread(self._avatar_models))
            return
        if route == "/assets/intent-visuals.json":
            try:
                await self._json(writer, 200, public_visual_contract(self.avatar_intent_enabled))
            except (OSError, ValueError, TypeError, KeyError):
                await self._json(writer, 503, {"error": "visual reactions unavailable"})
            return
        if route in ("/icon-192.png", "/icon-512.png"):
            from .mobile_icons import icon_png
            size = 192 if route == "/icon-192.png" else 512
            await self._send(writer, 200, await asyncio.to_thread(icon_png, size),
                             "image/png")
            return
        if route in WEB_FILES:
            filename, mime = WEB_FILES[route]
            path = self.web_root / filename
            base = self.web_root
        elif route.startswith("/vendor/"):
            filename = route[len("/vendor/"):]
            if filename not in VENDOR_NAMES or self.vendor_dir is None:
                await self._json(writer, 404, {"error": "vendor runtime not configured"})
                return
            path, mime = self.vendor_dir / filename, "text/javascript; charset=utf-8"
            base = self.vendor_dir
        elif route.startswith(("/model/", "/models/next/")):
            second = route.startswith("/models/next/")
            prefix = "/models/next/" if second else "/model/"
            filename = route[len(prefix):]
            if (not MODEL_FILE.fullmatch(filename) or
                    ".." in PurePosixPath(filename).parts or
                    filename.startswith("/")):
                await self._json(writer, 404, {"error": "asset not found"})
                return
            try:
                if second:
                    allowed, model = await asyncio.to_thread(self._second_model_files)
                    virtual_model = json.dumps(model, separators=(",", ":")).encode("utf-8")
                else:
                    allowed, virtual_model = await asyncio.to_thread(self._model_files)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                await self._json(writer, 503, {"error": "Live2D model unavailable"})
                return
            if filename not in allowed:
                await self._json(writer, 404, {"error": "asset not found"})
                return
            if filename == "Jade.model3.json":
                await self._send(writer, 200, virtual_model, "application/json; charset=utf-8")
                return
            if second:
                path, base = allowed[filename]
            else:
                base = self.model_dir
                path = base.joinpath(*PurePosixPath(filename).parts)
            mime = {
                ".moc3": "application/octet-stream",
                ".png": "image/png",
                ".json": "application/json; charset=utf-8",
                ".wav": "audio/wav",
                ".mp3": "audio/mpeg",
                ".ogg": "audio/ogg",
            }.get(path.suffix, "application/octet-stream")
        else:
            await self._json(writer, 404, {"error": "unknown route"})
            return
        try:
            # No redirects or symlinks to a private file outside approved roots.
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
        reply_future = loop.create_future()
        # Runtime.result carries the early text acknowledgement OR an error.
        # It cannot carry Reply.intent, so the complete Reply still comes from
        # on_reply -> deliver(). Propagate only failures to fail fast.
        outcome_future = loop.create_future()

        def propagate_failure(outcome):
            if outcome.cancelled():
                if not reply_future.done():
                    reply_future.cancel()
                return
            error = outcome.exception()  # consume exceptions even on shutdown
            if error is not None and not reply_future.done():
                reply_future.set_exception(error)

        outcome_future.add_done_callback(propagate_failure)
        self.pending[incoming.message_id] = reply_future
        work = None
        completed = False
        try:
            deadline = loop.time() + 50
            work = await self.runtime.submit(
                incoming, deadline=deadline, result=outcome_future)
            reply = await asyncio.wait_for(reply_future, timeout=55)
            completed = True
            return reply
        finally:
            # wait_for() cancels reply_future on timeout, making done() True.
            # Checking done() alone would leave the paid LLM work running
            # after the browser abandoned this request.
            if not completed and work is not None:
                self.runtime.cancel_work(work)
            if not reply_future.done():
                reply_future.cancel()
            self.pending.pop(incoming.message_id, None)

    async def _discord_live_settings(self, writer, enabled=None):
        if self.discord_live_policy is None:
            await self._json(writer, 503, {"error": "discord_live_unavailable"})
            return
        async with self._discord_live_settings_lock:
            try:
                status = await self.discord_live_policy.mobile_settings(enabled)
                if enabled is not None and self.discord_live_adapter is not None:
                    await self.discord_live_adapter.apply_owner_preference(enabled)
            except (OSError, sqlite3.Error, ValueError):
                await self._json(writer, 503, {"error": "discord_live_unavailable"})
                return
            if enabled is False and self.discord_live_adapter is not None:
                try:
                    status = await self.discord_live_policy.mobile_settings()
                except (OSError, sqlite3.Error, ValueError):
                    # OFF is already committed and applied. Only the freshly
                    # reported minutes are unavailable for this response.
                    status["partial"] = True
        await self._json(writer, 200, status)

    async def _post(self, writer, route: str, headers: dict, body: bytes, *, streaming=False):
        if route in LIVE_POST_ROUTES:
            from .mobile_live import live_http
            await live_http(self, writer, "POST", route, headers, body)
            return
        if route == DISCORD_LIVE_ROUTE:
            if headers.get("content-type", "").split(";")[0].strip() != "application/json":
                await self._json(writer, 400, {"error": "expected JSON"})
                return
            try:
                request = json.loads(body)
            except (UnicodeDecodeError, ValueError):
                request = None
            if not isinstance(request, dict) or set(request) != {"enabled"} or type(request["enabled"]) is not bool:
                await self._json(writer, 400, {"error": "invalid Discord Live setting"})
                return
            await self._discord_live_settings(writer, request["enabled"])
            return
        if route in ("/api/push", "/api/reminders"):
            if headers.get("content-type", "").split(";")[0].strip() != "application/json":
                await self._json(writer, 400, {"error": "expected JSON"})
                return
            try:
                request = json.loads(body)
            except (UnicodeDecodeError, ValueError):
                await self._json(writer, 400, {"error": "invalid JSON"})
                return
            if not isinstance(request, dict) or not isinstance(request.get("action"), str):
                await self._json(writer, 400, {"error": "invalid action"})
                return
            if self.reminders is None:
                await self._json(writer, 409, {"error": "reminders unavailable"})
                return
            if route == "/api/push":
                action = request["action"]
                if action == "config" and set(request) == {"action"}:
                    await self._json(writer, 200, {
                        "enabled": self.reminders.push.configured,
                        "vapid_public_key": (self.reminders.push.public_key
                                             if self.reminders.push.configured else ""),
                        "reason": ("ready" if self.reminders.push.configured else
                                   "push_not_configured"),
                    })
                    return
                if not self.reminders.push.configured:
                    await self._json(writer, 409, {"error": "push_not_configured"})
                    return
                try:
                    if action == "subscribe" and set(request) == {"action", "subscription"}:
                        await asyncio.to_thread(
                            self.reminders.store.subscribe, request["subscription"])
                    elif (action == "unsubscribe"
                          and set(request) == {"action", "endpoint"}):
                        await asyncio.to_thread(
                            self.reminders.store.unsubscribe, request["endpoint"])
                    else:
                        raise ValueError("invalid push operation")
                except (ValueError, TypeError, KeyError):
                    await self._json(writer, 400, {"error": "invalid push subscription"})
                    return
                await self._json(writer, 200, {"status": "ok"})
                return
            action = request["action"]
            if action == "get" and set(request) == {"action", "id"}:
                try:
                    item = await asyncio.to_thread(
                        self.reminders.store.get, request["id"])
                except (ValueError, TypeError):
                    item = None
                await self._json(writer, 200 if item else 404,
                                 {"status": "ok", "reminder": item} if item
                                 else {"error": "reminder_not_found"})
                return
            if set(request) != {"action", "id", "title", "due_at"}:
                await self._json(writer, 400, {"error": "invalid reminder request"})
                return
            if action == "list":
                items = await asyncio.to_thread(
                    self.reminders.store.list, visible_only=True)
                await self._json(writer, 200, {"status": "ok", "items": items})
                return
            if action == "ack":
                if request["title"] is not None or request["due_at"] is not None:
                    await self._json(writer, 400, {"error": "invalid reminder request"})
                    return
                try:
                    item = await asyncio.to_thread(
                        self.reminders.store.acknowledge, request["id"])
                except (ValueError, TypeError):
                    await self._json(writer, 400, {"error": "reminder_not_sent"})
                    return
                await self._json(writer, 200, {"status": "ok", "reminder": item})
                return
            from .reminders import ReminderAction
            result = await ReminderAction(
                self.reminders, "mobile", "").manage_reminder(
                    json.dumps(request, ensure_ascii=False))
            await self._json(writer, 200 if result["status"] == "ok" else 400, result)
            return
        if route == "/api/auth":
            # Bearer and Tailscale identity are checked at the common gateway.
            if (headers.get("content-type", "").split(";")[0].strip()
                    != "application/json" or body.strip() != b"{}"):
                await self._json(writer, 400, {"error": "expected empty JSON object"})
                return
            await self._json(writer, 200, {"status": "ok"})
            return
        if route == "/api/metrics":
            if (headers.get("content-type", "").split(";")[0].strip() != "application/json"
                    or body.strip() != b"{}"):
                await self._json(writer, 400, {"error": "expected empty JSON object"})
                return
            await self._json(writer, 200, {
                "runtime": self.runtime.state,
                "metrics": self.runtime.metrics.summary(),
                "scope": "server_observed_only",
                "first_audible": "unavailable_without_client_ack",
                "billing": "unavailable_per_turn",
                "live_usage": (await self.live_manager.usage_snapshot()
                               if self.live_manager is not None else None),
            })
            return
        if route == "/api/billing":
            if headers.get("content-type", "").split(";")[0].strip() != "application/json":
                await self._json(writer, 400, {"error": "expected JSON"})
                return
            try:
                request = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                await self._json(writer, 400, {"error": "invalid JSON"})
                return
            if (type(request) is not dict or set(request) - {"refresh"}
                    or type(request.get("refresh", False)) is not bool):
                await self._json(writer, 400, {"error": "invalid billing request"})
                return
            await self._json(writer, 200, await self.billing.get(refresh=request.get("refresh", False)))
            return
        if route == "/api/link":
            # This endpoint is restricted by the same Tailscale owner check and
            # Bearer authorization as chat. Never expose account-linking secrets
            # through a public Discord/Twitch command or an unauthenticated GET.
            if headers.get("content-type", "").split(";")[0].strip() != "application/json":
                await self._json(writer, 400, {"error": "expected JSON"})
                return
            try:
                request = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                await self._json(writer, 400, {"error": "invalid JSON"})
                return
            if (type(request) is not dict or set(request) != {"platform", "account_id"}
                    or request["platform"] not in ("discord", "twitch")
                    or not isinstance(request["account_id"], str)
                    or not re.fullmatch(r"[1-9][0-9]{0,24}", request["account_id"])):
                await self._json(writer, 400, {"error": "invalid target identity"})
                return
            memory = getattr(self.runtime, "memory_service", None)
            if memory is None:
                await self._json(writer, 409, {"error": "memory is disabled"})
                return
            try:
                code = await asyncio.to_thread(
                    memory.store.begin_link, ("microphone", "goldaj"),
                    target=(request["platform"], request["account_id"]))
            except PermissionError:
                await self._json(writer, 409, {"error": "owner memory is not enabled"})
                return
            except ValueError:
                await self._json(writer, 400, {"error": "invalid identity"})
                return
            await self._json(writer, 200, {"code": code, "expires_in_seconds": 300})
            return
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
        if self.live_manager is not None:
            await self.live_manager.stop_owner("Goldaj", "text" if modality == "text" else "classic_voice")
        if self.semaphore.locked():
            await self._json(writer, 429, {"error": "Jade est occupée",
                                          **incident_for_client(asyncio.QueueFull())})
            return
        async with self.semaphore:
            stream_started = False
            try:
                async with asyncio.timeout(self.request_timeout):
                    stt_duration_ms = None
                    if modality == "voice":
                        stt_started_at = time.monotonic()
                        text = (await self.services.transcribe_wav(body)).strip()
                        stt_duration_ms = round(
                            (time.monotonic() - stt_started_at) * 1000, 1)
                        if not text or len(text) > 1200:
                            await self._json(writer, 400, {"error": "transcription unavailable"})
                            return
                    source = Incoming(
                        platform="mobile", author="Goldaj",
                        channel=session, message_id=secrets.token_hex(16),
                        text=text, force_reply=True,
                        input_modality=modality,
                        preprocess_ms=stt_duration_ms,
                        requested_speech=(speak_header == "1" if modality == "voice"
                                          else request["speak"]),
                    )
                    reply = await self._conversation(source)
                    payload = {"reply": reply.text, "intent": reply.intent,
                               "attachments": [item.public() for item in getattr(reply, "attachments", ())],
                               "transcript": text if modality == "voice" else None,
                               "audio_wav_b64": None, "audio_unavailable": False}
                    speak = source.requested_speech
                    if streaming:
                        stream_started = True
                        await self._stream_reply(writer, payload, speak)
                        return
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
                        except Exception as exc:
                            LOG.warning("Mobile voice unavailable; text answer preserved")
                            payload["audio_unavailable"] = True
                            payload["audio_unavailable_reason"] = incident_for_client(exc)
                    await self._json(writer, 200, payload)
            except asyncio.TimeoutError as exc:
                if not stream_started:
                    await self._json(writer, 504, {"error": "Jade n'a pas répondu à temps",
                                                  **incident_for_client(exc)})
            except asyncio.QueueFull as exc:
                if not stream_started:
                    await self._json(writer, 429, {"error": "Jade est occupée",
                                                  **incident_for_client(exc)})
            except Exception as exc:
                LOG.warning("Mobile turn failed; no transcript/secret logged")
                if not stream_started:
                    await self._json(writer, 503, {"error": "Jade indisponible",
                                                  **incident_for_client(exc)})

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
                if route in LIVE_GET_ROUTES or route in ("/api/live/control", DISCORD_LIVE_ROUTE):
                    if not self._origin_allowed(headers) or not headers.get("host"):
                        await self._json(writer, 403, {"error": "invalid_origin"})
                        return
                    if route == "/api/live/control":
                        from .mobile_live import live_control
                        await live_control(self, reader, writer, headers)
                    elif not hmac.compare_digest(headers.get("authorization", ""), "Bearer " + self.token):
                        await self._json(writer, 401, {"error": "authentication_required"})
                    elif route == DISCORD_LIVE_ROUTE:
                        await self._discord_live_settings(writer)
                    else:
                        from .mobile_live import live_http
                        await live_http(self, writer, "GET", route, headers)
                    return
                if route == "/assets/salon.html":
                    # Only deliver the salon document after token validation.
                    if not hmac.compare_digest(
                            headers.get("authorization", ""), "Bearer " + self.token):
                        await self._json(writer, 401, {"error": "authentication required"})
                        return
                if route.startswith("/api/documents/"):
                    if (not self._origin_allowed(headers) or not headers.get("host")):
                        await self._json(writer, 403, {"error": "invalid origin"})
                        return
                    if not hmac.compare_digest(
                            headers.get("authorization", ""), "Bearer " + self.token):
                        await self._json(writer, 401, {"error": "authentication required"})
                        return
                    await self._download_document(writer, route)
                    return
                if route == "/api/duplex":
                    if not self._origin_allowed(headers) or not headers.get("host"):
                        await self._json(writer, 403, {"error": "invalid websocket origin"})
                        return
                    from .mobile_duplex import duplex_session
                    await duplex_session(self, reader, writer, headers)
                    return
                await self._static(writer, route)
                return
            if route not in ("/api/chat", "/api/voice", "/api/link", "/api/billing", "/api/metrics",
                              "/api/push", "/api/reminders", "/api/auth", DISCORD_LIVE_ROUTE) and route not in LIVE_POST_ROUTES:
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
            max_size = MAX_WAV if route == "/api/voice" else (12288 if route == "/api/push" else 4096)
            if route == "/api/live/sessions":
                max_size = LIVE_SDP_BODY_LIMIT
            if not 1 <= size <= max_size:
                await self._json(writer, 413, {"error": "request too large"})
                return
            body = await asyncio.wait_for(reader.readexactly(size), timeout=10)
            streaming = headers.get("x-jade-stream") == "1" and route in ("/api/chat", "/api/voice")
            if route not in ("/api/chat", "/api/voice"):
                await self._post(writer, route, headers, body)
            else:
                # Notice a disconnected phone even while STT/LLM is still
                # running, before a response can be written to the socket.
                work = asyncio.create_task(self._post(writer, route, headers, body, streaming=streaming))
                disconnected = asyncio.create_task(reader.read(1))
                try:
                    done, _ = await asyncio.wait((work, disconnected), return_when=asyncio.FIRST_COMPLETED)
                    if work in done:
                        await work
                    else:
                        work.cancel()
                        await asyncio.gather(work, return_exceptions=True)
                finally:
                    for task in (work, disconnected):
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(work, disconnected, return_exceptions=True)
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
