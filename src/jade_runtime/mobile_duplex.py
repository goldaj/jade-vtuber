"""Owner-only bounded WebSocket duplex: streaming PCM input, incremental TTS output.

This is a transport, not an additional OpenAI Realtime session. STT remains
one completed utterance per turn. A new start/cancel interrupts the old turn.
No audio, bearer tokens or transcripts are written to disk or application logs.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
from io import BytesIO
import json
import logging
import re
import secrets
import struct
import time
import wave

from .messages import Incoming
from .mobile_audio_stream import speech_events
from .pcm_timing import PCMProgressTiming, log_mobile_progress

LOG = logging.getLogger("jade.mobile.duplex")
_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_SESSION = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_MAX_PCM = 640000
_MAX_FRAME = 32768


class WebSocketPeer:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    async def send(self, event):
        data = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        await self._frame(1, data)

    async def _frame(self, opcode, data=b""):
        size = len(data)
        if size > 8_000_000:
            raise ValueError("oversized socket response")
        head = bytes((0x80 | opcode, size)) if size < 126 else (
            bytes((0x80 | opcode, 126)) + struct.pack("!H", size)
            if size < 65536 else bytes((0x80 | opcode, 127)) + struct.pack("!Q", size))
        self.writer.write(head + data)
        await asyncio.wait_for(self.writer.drain(), timeout=5)

    async def receive(self):
        while True:
            header = await asyncio.wait_for(self.reader.readexactly(2), timeout=90)
            final, opcode = bool(header[0] & 0x80), header[0] & 0x0f
            if not final or opcode not in (1, 2, 8, 9, 10):
                raise ValueError("invalid WS fragment/opcode")
            masked = bool(header[1] & 0x80)
            size = header[1] & 0x7f
            if size == 126:
                size = struct.unpack("!H", await self.reader.readexactly(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", await self.reader.readexactly(8))[0]
            if not masked or size > _MAX_FRAME:
                raise ValueError("unmasked/oversized frame")
            mask = await self.reader.readexactly(4)
            data = bytearray(await self.reader.readexactly(size))
            for n in range(size):
                data[n] ^= mask[n % 4]
            if opcode == 8:
                return None
            if opcode == 9:
                await self._frame(10, bytes(data))
                continue
            if opcode == 10:
                continue
            if opcode == 1:
                try:
                    value = json.loads(data.decode("utf-8"))
                except (UnicodeError, ValueError):
                    raise ValueError("invalid WS JSON") from None
                if not isinstance(value, dict):
                    raise ValueError("invalid WS control")
                return value
            if not data or len(data) % 2:
                raise ValueError("invalid PCM chunk")
            return bytes(data)


async def duplex_session(gateway, reader, writer, headers):
    """Validate upgrade + in-band authentication then process concurrent I/O."""
    if (headers.get("upgrade", "").casefold() != "websocket"
            or "upgrade" not in headers.get("connection", "").casefold().split(",")
            or headers.get("sec-websocket-version") != "13"
            or "jade-v1" not in headers.get("sec-websocket-protocol", "").split(",")):
        await gateway._json(writer, 400, {"error": "websocket required"})
        return
    try:
        secret = base64.b64decode(headers.get("sec-websocket-key", ""),
                                  validate=True)
    except (ValueError, base64.binascii.Error):
        secret = b""
    if len(secret) != 16:
        await gateway._json(writer, 400, {"error": "invalid websocket key"})
        return
    accept = base64.b64encode(hashlib.sha1(
        (headers["sec-websocket-key"] + _GUID).encode("ascii")).digest()).decode("ascii")
    writer.write(("HTTP/1.1 101 Switching Protocols\r\n"
                  "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                  "Sec-WebSocket-Protocol: jade-v1\r\n"
                  "Cache-Control: no-store\r\n"
                  "Sec-WebSocket-Accept: " + accept + "\r\n\r\n").encode("ascii"))
    await writer.drain()
    peer = WebSocketPeer(reader, writer)
    work = None
    pcm = bytearray()
    receiving = False
    session = ""
    speak = True
    try:
        auth = await asyncio.wait_for(peer.receive(), timeout=8)
        if (not isinstance(auth, dict) or auth.get("type") != "auth"
                or not isinstance(auth.get("token"), str)
                or not hmac.compare_digest(auth["token"], gateway.token)
                or not isinstance(auth.get("session"), str)
                or not _SESSION.fullmatch(auth["session"])):
            await peer.send({"type": "error", "error": "authentication required"})
            return
        session = auth["session"]
        await peer.send({"type": "ready"})
        while True:
            frame = await peer.receive()
            if frame is None:
                return
            if isinstance(frame, bytes):
                if not receiving or len(pcm) + len(frame) > _MAX_PCM:
                    raise ValueError("unexpected or oversized audio")
                pcm.extend(frame)
                continue
            cmd = frame.get("type")
            if cmd == "cancel":
                pcm.clear()
                receiving = False
                if work is not None and not work.done():
                    work.cancel()
                    await asyncio.gather(work, return_exceptions=True)
                work = None
                await peer.send({"type": "cancelled"})
            elif cmd == "start":
                if frame.get("speak") not in (True, False):
                    raise ValueError("invalid speech flag")
                if work is not None and not work.done():
                    work.cancel()
                    await asyncio.gather(work, return_exceptions=True)
                work = None
                pcm.clear()
                receiving = True
                speak = frame["speak"]
            elif cmd == "end" and receiving:
                receiving = False
                if not 8000 <= len(pcm) <= _MAX_PCM:
                    await peer.send({"type": "error", "error": "audio too short"})
                else:
                    audio = bytes(pcm)
                    work = asyncio.create_task(
                        _answer(gateway, peer, audio, session, speak),
                        name="jade-mobile-duplex-answer")
                pcm.clear()
            else:
                raise ValueError("invalid voice control")
    except asyncio.CancelledError:
        raise
    except (asyncio.IncompleteReadError, ConnectionError, OSError):
        pass
    except Exception:
        LOG.warning("Mobile duplex session rejected; no contents logged")
        try:
            await peer.send({"type": "error", "error": "invalid audio session"})
        except Exception:
            pass
    finally:
        if work is not None:
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)
        pcm.clear()
        try:
            await peer._frame(8)
        except Exception:
            pass


async def _answer(gateway, peer, pcm, session, speak):
    try:
        async with gateway.semaphore:
            async with asyncio.timeout(gateway.request_timeout):
                output = BytesIO()
                with wave.open(output, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes(pcm)
                text = (await gateway.services.transcribe_wav(output.getvalue())).strip()
                if not text or len(text) > 1200:
                    await peer.send({"type": "error", "error": "transcription unavailable"})
                    return
                source = Incoming(
                    platform="mobile", author="Goldaj", channel=session,
                    message_id=secrets.token_hex(16), text=text,
                    force_reply=True, input_modality="voice",
                    requested_speech=speak)
                reply = await gateway._conversation(source)
                await peer.send({"type": "reply", "transcript": text,
                                 "reply": reply.text, "intent": reply.intent})
                if speak:
                    timing = PCMProgressTiming()
                    first_sent_at = None
                    transfer_completed = False
                    try:
                        async for event in speech_events(
                                gateway.services, reply.text, reply.intent, timing=timing):
                            await peer.send(event)
                            if event["type"] == "pcm" and first_sent_at is None:
                                first_sent_at = time.monotonic()
                        transfer_completed = True
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        await peer.send({"type": "audio_error"})
                    finally:
                        log_mobile_progress(timing, first_sent_at,
                                            transfer_completed=transfer_completed,
                                            transport="websocket")
                await peer.send({"type": "done"})
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError:
        await peer.send({"type": "error", "error": "response timeout"})
    except Exception:
        LOG.warning("Mobile duplex answer unavailable; no contents logged")
        try:
            await peer.send({"type": "error", "error": "Jade unavailable"})
        except Exception:
            pass
