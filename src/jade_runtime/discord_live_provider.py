"""Primary OpenAI Live WebSocket for Discord, with bounded confirmed shutdown.

The transport carries raw mono PCM16LE at 24 kHz in both directions. Discord
capture is converted separately; playback can reuse DiscordPCMBuffer. No audio,
transcript, credential or provider error body is written to disk or logs.

Protocol: https://developers.openai.com/api/docs/guides/voice-websockets
This is a primary WebSocket: session.start is required here, unlike WebRTC.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
from collections import deque
import copy
import json
import math
import re
import secrets
import struct
import time

from .live_provider import (
    LiveProviderError, MAX_EVENT_BYTES, MAX_SESSION_CONFIG_BYTES, report_live_voice_confirmation,
)
from .live_voice import LiveVoice


PCM_RATE = 24000
PCM_BYTES_PER_SECOND = PCM_RATE * 2
_FRAME_BYTES = 960  # 20 ms, mono PCM16LE at 24 kHz.
_END = object()
_ID = re.compile(r"[A-Za-z0-9_-]{1,256}\Z")
_COMMANDS = frozenset({
    "session.input_audio.mute", "session.input_audio.unmute",
    "session.instructions.append", "session.thinking.append", "session.commentary.append",
})


def build_discord_live_config(live_config, *, instructions="", input=None):
    """Reuse Jade's voice/context, without WebRTC-only wake/data-channel fields."""
    config = live_config.session_config(instructions=instructions, input=input)
    for name in ("client", "wake_policy", "idle_timeout_s"):
        config.pop(name, None)
    config["audio"]["format"] = {"type": "audio/pcm", "rate": PCM_RATE}
    return _validate_config(config)


def _validate_config(config):
    try:
        value = copy.deepcopy(config)
        if (not isinstance(value, dict)
                or set(value) - {"model", "audio", "delegation", "instructions", "input", "store"}
                or len(json.dumps(value, allow_nan=False).encode("utf-8")) > MAX_SESSION_CONFIG_BYTES
                or value.get("model") not in ("gpt-live-1", "gpt-live-1.1")
                or value.get("store") is not False
                or value.get("delegation", {}).get("type") != "client"
                or value.get("audio", {}).get("format") != {"type": "audio/pcm", "rate": PCM_RATE}
                or len(value.get("input", [])) > 128):
            raise ValueError()
        voice = value["audio"]["output"]["voice"]
        if isinstance(voice, str):
            LiveVoice(name=voice).validate()
        elif isinstance(voice, dict) and set(voice) == {"id"} and voice["id"]:
            LiveVoice(custom_id=voice["id"]).validate()
        else:
            raise ValueError()
        # The project pins this SDK. Its schema checks the protocol independently
        # of our transport doubles, including input/history and audio shape.
        from openai.types.live.session_start_event import SessionStartEvent
        SessionStartEvent.model_validate({"type": "session.start", "session": value}, strict=True)
        return value
    except (ValueError, TypeError, KeyError, AttributeError):
        raise LiveProviderError("invalid_discord_live_config") from None


def _consume(task):
    if not task.cancelled():
        task.exception()


def _open_outcome(error, result):
    """Preserve cancellation semantics while exposing paid-attempt finalization.

    This state belongs to this exception/attempt, never a mutable provider-wide
    last result. A caller can durably block another start when it is ambiguous.
    """
    error.close_result = copy.deepcopy(result)
    error.session_id = result["session_id"]
    error.close_confirmed = result["confirmed"]
    error.ambiguous = bool(result.get("started", True) and not result["confirmed"])
    return error


async def _bounded(awaitable, timeout, code):
    """A slow transport cleanup must not turn an application deadline into a wait."""
    task = asyncio.ensure_future(awaitable)
    try:
        done, _ = await asyncio.wait({task}, timeout=max(0.001, timeout))
    except BaseException:
        task.cancel()
        task.add_done_callback(_consume)
        raise
    if not done:
        task.cancel()
        task.add_done_callback(_consume)
        raise LiveProviderError(code, ambiguous=True)
    return task.result()


class PCM48StereoTo24Mono:
    """Streaming downmix and FIR decimation; boundaries never reset filter state.

    A 31-tap windowed low-pass filters before dropping every second frame, avoiding
    plain decimation's aliasing. The fixed filter delay is 15/48000 seconds.
    """

    def __init__(self):
        taps = []
        for index in range(31):
            distance = index - 15
            ideal = 0.46 if distance == 0 else math.sin(2 * math.pi * 0.23 * distance) / (math.pi * distance)
            taps.append(ideal * (0.54 - 0.46 * math.cos(2 * math.pi * index / 30)))
        scale = sum(taps)
        self._taps = tuple(value / scale for value in taps)
        self.reset()

    def reset(self):
        self._history = deque([0.0] * 31, maxlen=31)
        self._tail = b""
        self._phase = 0

    def feed(self, pcm: bytes) -> bytes:
        if not isinstance(pcm, bytes) or len(pcm) > 3_840_000:
            raise ValueError("invalid Discord PCM input")
        complete = self._tail + pcm
        length = len(complete) - len(complete) % 4
        self._tail = complete[length:]
        output = bytearray()
        for left, right in struct.iter_unpack("<hh", complete[:length]):
            self._history.append((left + right) / 2)
            self._phase ^= 1
            if not self._phase:
                value = round(sum(sample * weight for sample, weight in zip(self._history, self._taps)))
                output.extend(struct.pack("<h", min(32767, max(-32768, value))))
        return bytes(output)


class DiscordLiveSession:
    """One non-reconnecting paid session; the receiver owns the terminal event.

    Iteration yields provider events. Audio deltas carry ``pcm: bytes`` instead
    of base64 ``delta``. ``close`` remains effective if the iterator is stalled.
    """

    def __init__(self, socket, connection, *, close_timeout_seconds, send_timeout_seconds,
                 max_events=128, clock=time.monotonic):
        self._socket, self._connection = socket, connection
        self._close_timeout = close_timeout_seconds
        self._send_timeout = send_timeout_seconds
        self._clock = clock
        self._events = asyncio.Queue(maxsize=max_events)
        self._started = asyncio.Event()
        self._finalized = asyncio.Event()
        self._send_lock = asyncio.Lock()
        self._audio_lock = asyncio.Lock()
        self._closing = False
        self._ready = False
        self._requested_voice = None
        self._failure = None
        self._close_task = None
        self._next_audio_at = 0.0
        self.session_id = None
        self.usage = {}
        self.close_confirmed = False
        self.close_reason = ""
        self._receiver = asyncio.create_task(self._receive(), name="jade-discord-live-receive")

    async def _write(self, event, *, closing=False):
        async def write():
            async with self._send_lock:
                if self._closing and not closing:
                    raise LiveProviderError("discord_live_closing", session_id=self.session_id)
                await self._socket.send(json.dumps(event, ensure_ascii=False, allow_nan=False))
        try:
            await _bounded(write(), self._send_timeout, "discord_live_send_timeout")
        except asyncio.CancelledError:
            raise
        except LiveProviderError:
            raise
        except Exception:
            raise LiveProviderError("discord_live_send_failed", ambiguous=True,
                                    session_id=self.session_id) from None

    async def _start(self, config, timeout):
        deadline = self._clock() + timeout
        self._requested_voice = config["audio"]["output"]["voice"]
        await self._write({"type": "session.start", "event_id": "jade-" + secrets.token_hex(12),
                           "session": config})
        await _bounded(self._started.wait(), deadline - self._clock(), "discord_live_open_timeout")
        if self._failure:
            raise self._failure
        if not self._ready or self.close_confirmed:
            raise LiveProviderError("discord_live_start_failed", ambiguous=not self.close_confirmed,
                                    session_id=self.session_id)

    def _fail(self, code):
        if self._failure is None:
            self._failure = LiveProviderError(code, ambiguous=not self.close_confirmed,
                                              session_id=self.session_id)
        self._started.set()
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close(), name="jade-discord-live-close")
            self._close_task.add_done_callback(_consume)

    def _offer(self, event):
        if self._failure and not self.close_confirmed:
            return
        try:
            self._events.put_nowait(event)
        except asyncio.QueueFull:
            # Fail instead of buffering an unbounded amount of private audio.
            # Keep receiving so the independent close can still see its terminal.
            self._fail("discord_live_event_backpressure")

    async def _receive(self):
        try:
            async for message in self._socket:
                if not isinstance(message, str) or len(message.encode("utf-8")) > MAX_EVENT_BYTES:
                    raise ValueError()
                event = json.loads(message)
                if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                    raise ValueError()
                kind = event["type"]
                if kind == "session.started":
                    snapshot = event.get("session", {})
                    identifier = snapshot.get("id")
                    if (not isinstance(identifier, str) or not _ID.fullmatch(identifier)
                            or self.session_id not in (None, identifier)):
                        raise ValueError()
                    self.session_id = identifier
                    fmt = snapshot.get("audio", {}).get("format")
                    if fmt is not None and fmt != {"type": "audio/pcm", "rate": PCM_RATE}:
                        self._fail("discord_live_audio_format_mismatch")
                        continue
                    if not self._ready and self._requested_voice is not None:
                        report_live_voice_confirmation(self._requested_voice, snapshot, transport="discord")
                    self._ready = True
                    self._started.set()
                elif kind == "session.output_audio.delta":
                    encoded = event.get("delta")
                    if not isinstance(encoded, str):
                        raise ValueError()
                    pcm = base64.b64decode(encoded, validate=True)
                    if not pcm or len(pcm) % 2 or len(pcm) > 480_000:
                        raise ValueError()
                    event = {key: value for key, value in event.items() if key != "delta"}
                    event["pcm"] = pcm
                elif kind == "session.closed":
                    identifier = event.get("session", {}).get("id")
                    if (not isinstance(identifier, str) or not _ID.fullmatch(identifier)
                            or self.session_id not in (None, identifier)):
                        raise ValueError()
                    self.session_id = identifier
                    self.close_confirmed = True
                    self.close_reason = event.get("reason", "provider_closed")
                    self._closing = True
                elif kind == "error":
                    # Never expose provider messages, request bodies or account IDs.
                    self._fail("discord_live_provider_error")
                    continue
                if kind in ("session.usage.updated", "session.closed"):
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        self.usage = {key: value for key, value in usage.items()
                                      if isinstance(value, (int, float)) and not isinstance(value, bool)
                                      and math.isfinite(value) and value >= 0}
                self._offer(event)
                if self.close_confirmed:
                    break
        except asyncio.CancelledError:
            raise
        except (ValueError, TypeError, AttributeError, UnicodeError, binascii.Error):
            self._fail("discord_live_invalid_event")
        except Exception:
            self._fail("discord_live_receive_failed")
        finally:
            if not self.close_confirmed and self._failure is None:
                self._fail("discord_live_close_unconfirmed")
            self._started.set()
            self._finalized.set()
            # Always wake the iterator, including when it was not being consumed.
            if self._events.full():
                self._events.get_nowait()
            self._events.put_nowait(_END)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._failure:
            raise self._failure
        if self._finalized.is_set() and self._events.empty():
            raise StopAsyncIteration
        item = await self._events.get()
        if self._failure:
            raise self._failure
        if item is _END:
            raise StopAsyncIteration
        return item

    async def send_audio(self, pcm: bytes):
        """Pace audio at its recorded rate, including buffered opening speech."""
        if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2 or len(pcm) > 960_000:
            raise LiveProviderError("invalid_discord_live_pcm")
        async with self._audio_lock:
            if not self._ready or self._closing or self._failure:
                raise LiveProviderError("discord_live_not_active", session_id=self.session_id)
            for offset in range(0, len(pcm), _FRAME_BYTES):
                chunk = pcm[offset:offset + _FRAME_BYTES]
                delay = self._next_audio_at - self._clock()
                if delay > 0:
                    await asyncio.sleep(delay)
                sent_at = self._clock()
                await self._write({"type": "session.input_audio.append",
                                   "audio": base64.b64encode(chunk).decode("ascii")})
                self._next_audio_at = max(self._next_audio_at, sent_at) + len(chunk) / PCM_BYTES_PER_SECOND

    async def send(self, event):
        if (not isinstance(event, dict) or event.get("type") not in _COMMANDS
                or not self._ready or self._closing or self._failure):
            raise LiveProviderError("unsupported_discord_live_command", session_id=self.session_id)
        try:
            if len(json.dumps(event, allow_nan=False).encode("utf-8")) > 32_768:
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            raise LiveProviderError("invalid_discord_live_command") from None
        await self._write(event)

    async def close(self):
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close(), name="jade-discord-live-close")
            self._close_task.add_done_callback(_consume)
        return await asyncio.shield(self._close_task)

    def close_snapshot(self):
        return {"confirmed": self.close_confirmed, "session_id": self.session_id,
                "usage": dict(self.usage), "reason": self.close_reason or "close_unconfirmed",
                "started": True}

    async def _close(self):
        self._closing = True
        deadline = self._clock() + self._close_timeout
        try:
            if not self.close_confirmed:
                try:
                    if self.session_id is None and not self._finalized.is_set():
                        # A late startup still belongs to this attempt. Wait a
                        # bounded time and close it, never open a replacement.
                        await _bounded(self._started.wait(), deadline - self._clock(),
                                       "discord_live_close_timeout")
                    if self.session_id is not None:
                        await _bounded(self._write({"type": "session.close"}, closing=True),
                                       deadline - self._clock(), "discord_live_close_timeout")
                    if not self._finalized.is_set():
                        await _bounded(self._finalized.wait(), deadline - self._clock(),
                                       "discord_live_close_timeout")
                except (LiveProviderError, OSError):
                    pass
        finally:
            try:
                await _bounded(self._connection.__aexit__(None, None, None), 1.0,
                               "discord_live_transport_close_timeout")
            except Exception:
                transport = getattr(self._socket, "transport", None)
                if transport is not None:
                    try:
                        transport.abort()
                    except Exception:
                        pass
            if not self._receiver.done():
                self._receiver.cancel()
            await asyncio.wait({self._receiver}, timeout=0.1)
            self._receiver.add_done_callback(_consume)
        return self.close_snapshot()


class DiscordLiveProvider:
    """No connection on construction; one explicit session.start per open call."""

    def __init__(self, api_key, *, opening_timeout_seconds=8.0, close_timeout_seconds=5.0,
                 websocket_connect=None, max_events=128):
        if not isinstance(api_key, str) or any(char in api_key for char in "\r\n"):
            raise ValueError("invalid API credential")
        for timeout in (opening_timeout_seconds, close_timeout_seconds):
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0.01 <= timeout <= 30:
                raise ValueError("invalid Discord Live timeout")
        if type(max_events) is not int or not 4 <= max_events <= 256:
            raise ValueError("invalid Discord Live event capacity")
        self._api_key = api_key
        self._connect = websocket_connect
        self._opening_timeout = opening_timeout_seconds
        self._close_timeout = close_timeout_seconds
        self._max_events = max_events

    async def _transport(self, url):
        connect = self._connect
        if connect is None:
            from websockets.legacy.client import connect
        connection = connect(
            url, extra_headers={"Authorization": f"Bearer {self._api_key}"},
            open_timeout=self._opening_timeout, close_timeout=1,
            max_size=MAX_EVENT_BYTES, max_queue=32, ping_interval=10, ping_timeout=10,
        )
        entering = asyncio.ensure_future(connection.__aenter__())

        def discard_late(task):
            if task.cancelled():
                return
            try:
                socket = task.result()
            except BaseException:
                return

            async def cleanup():
                try:
                    await _bounded(connection.__aexit__(None, None, None), 1.0,
                                   "discord_live_transport_close_timeout")
                except Exception:
                    transport = getattr(socket, "transport", None)
                    if transport is not None:
                        try:
                            transport.abort()
                        except Exception:
                            pass

            cleanup_task = asyncio.create_task(cleanup(), name="jade-discord-live-late-transport")
            cleanup_task.add_done_callback(_consume)

        try:
            socket = await _bounded(entering, self._opening_timeout,
                                    "discord_live_connection_timeout")
        except BaseException:
            # A third-party transport may ignore task cancellation and finish
            # connecting later. Its unused socket must not escape our cleanup.
            entering.add_done_callback(discard_late)
            raise
        return connection, socket

    async def open(self, session_config):
        config = _validate_config(session_config)
        if not self._api_key:
            raise LiveProviderError("api_key_missing")
        try:
            connection, socket = await self._transport("wss://api.openai.com/v1/live/sessions")
        except asyncio.CancelledError as error:
            _open_outcome(error, {"confirmed": False, "session_id": None, "usage": {},
                                  "reason": "cancelled_before_start", "started": False})
            raise
        except Exception:
            # No session.start was sent, so this is not an ambiguous creation.
            raise LiveProviderError("discord_live_connection_failed") from None
        session = DiscordLiveSession(socket, connection, close_timeout_seconds=self._close_timeout,
                                     send_timeout_seconds=min(self._opening_timeout, 3.0),
                                     max_events=self._max_events)
        try:
            await session._start(config, self._opening_timeout)
            return session
        except BaseException as error:
            _open_outcome(error, session.close_snapshot())
            try:
                result = await session.close()
            except asyncio.CancelledError as interrupted:
                # A second cancellation cannot erase the first paid attempt.
                # The shielded, bounded close task keeps running independently.
                _open_outcome(interrupted, session.close_snapshot())
                raise
            _open_outcome(error, result)
            raise

    async def reconcile_close(self, session_id):
        """One close-only attachment to a saved ID; never start or replay audio.

        Attachment only replays recent events. A failed connection, expired ID,
        or absent terminal is therefore still unknown, never proof of closure.
        """
        if not isinstance(session_id, str) or not _ID.fullmatch(session_id):
            raise LiveProviderError("invalid_discord_live_session_id")
        result = {"confirmed": False, "session_id": session_id, "usage": {},
                  "reason": "close_unconfirmed", "started": True}
        if not self._api_key:
            return result
        try:
            connection, socket = await self._transport(
                f"wss://api.openai.com/v1/live/sessions/{session_id}/attach")
        except asyncio.CancelledError as error:
            _open_outcome(error, result)
            raise
        except Exception:
            return result
        session = DiscordLiveSession(socket, connection, close_timeout_seconds=self._close_timeout,
                                     send_timeout_seconds=min(self._opening_timeout, 3.0),
                                     max_events=self._max_events)
        session.session_id = session_id
        session._started.set()
        try:
            return await session.close()
        except asyncio.CancelledError as error:
            _open_outcome(error, session.close_snapshot())
            raise
