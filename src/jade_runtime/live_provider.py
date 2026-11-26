"""OpenAI Live HTTP/WebRTC signalling and trusted sideband transport.

Official contracts checked 2026-11-26:
https://developers.openai.com/api/docs/guides/voice-webrtc
https://developers.openai.com/api/docs/guides/voice-server-controls

No network or credential lookup on import/construction. The caller owns budget,
authorization, event replay deduplication and observing session.closed. Closing
the transport below is deliberately NOT described as closing the paid session.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import copy
import json
import math
import re
from typing import AsyncContextManager, AsyncIterator, Protocol, TypedDict
from urllib.parse import quote

from .live_voice import LiveVoice


MAX_SDP_BYTES = 64 * 1024
MAX_EVENT_BYTES = 1024 * 1024
MAX_SESSION_CONFIG_BYTES = 128 * 1024


class LiveSession(TypedDict):
    session_id: str
    sdp: str
    expires_at: int | None


class LiveProviderError(RuntimeError):
    def __init__(self, code: str, *, ambiguous: bool = False,
                 session_id: str | None = None, status_code: int | None = None):
        # Never carry HTTP bodies, request objects, transcripts, SDP or secrets.
        super().__init__(code)
        self.code = code
        self.ambiguous = ambiguous
        self.session_id = session_id
        self.status_code = status_code


class LiveChannel(Protocol):
    async def send(self, event: dict) -> None: ...
    def __aiter__(self) -> AsyncIterator[dict]: ...
    async def close(self) -> None: ...


class LiveProvider(Protocol):
    async def create_session(self, sdp: str, session_config: dict) -> LiveSession: ...
    def attach(self, session_id: str) -> AsyncContextManager[LiveChannel]: ...


def validate_sdp(sdp: object) -> str:
    if not isinstance(sdp, str):
        raise LiveProviderError("invalid_sdp")
    try:
        size = len(sdp.encode("utf-8"))
    except UnicodeError:
        raise LiveProviderError("invalid_sdp") from None
    lines = sdp.replace("\r\n", "\n").split("\n")
    if (not 1 <= size <= MAX_SDP_BYTES or "\x00" in sdp
            or not lines or lines[0] != "v=0"
            or not any(line.startswith("m=audio ") for line in lines)
            or not any(line.startswith("a=fingerprint:") for line in lines)
            or not any(line.startswith("a=ice-ufrag:") for line in lines)):
        raise LiveProviderError("invalid_sdp")
    return sdp


def _session_id(value: object) -> str:
    # Treat the ID as opaque; reject URL separators instead of changing its prefix.
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", value):
        raise LiveProviderError("invalid_session_id")
    return value


def _session_config(value: object) -> dict:
    if not isinstance(value, dict):
        raise LiveProviderError("invalid_session_config")
    result = copy.deepcopy(value)
    try:
        if len(json.dumps(result, allow_nan=False).encode()) > MAX_SESSION_CONFIG_BYTES:
            raise LiveProviderError("session_config_too_large")
    except (TypeError, ValueError, UnicodeError):
        raise LiveProviderError("invalid_session_config") from None
    if result.get("model") not in ("gpt-live-1", "gpt-live-1.1"):
        raise LiveProviderError("invalid_live_model")
    if result.get("store") is not False:
        raise LiveProviderError("live_storage_must_be_disabled")
    if not isinstance(result.get("delegation"), dict) or result["delegation"].get("type") != "client":
        raise LiveProviderError("live_requires_client_delegation")
    if result.get("triggers"):
        raise LiveProviderError("unbudgeted_live_triggers_disabled")
    history = result.get("input", [])
    if not isinstance(history, list) or len(history) > 128:
        raise LiveProviderError("invalid_live_history")
    for message in history:
        if (not isinstance(message, dict) or message.get("type", "message") != "message"
                or message.get("role") not in ("developer", "user", "assistant")):
            raise LiveProviderError("invalid_live_history")
        parts = message.get("content")
        if not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], dict):
            raise LiveProviderError("invalid_live_history")
        expected = ("text", "output_text") if message["role"] == "assistant" else ("input_text",)
        if parts[0].get("type", expected[0]) not in expected or not isinstance(parts[0].get("text"), str):
            raise LiveProviderError("invalid_live_history")
    audio = result.get("audio", {})
    if not isinstance(audio, dict) or "format" in audio:
        raise LiveProviderError("invalid_webrtc_audio_config")
    output = audio.get("output")
    if not isinstance(output, dict) or "voice" not in output:
        raise LiveProviderError("live_voice_must_be_explicit")
    voice = output["voice"]
    try:
        if isinstance(voice, str):
            LiveVoice(name=voice).validate()
        elif isinstance(voice, dict) and set(voice) == {"id"} and voice["id"]:
            LiveVoice(custom_id=voice["id"]).validate()
        else:
            raise ValueError("invalid voice")
    except ValueError:
        raise LiveProviderError("invalid_live_voice") from None
    client = result.get("client")
    if not isinstance(client, dict) or not isinstance(client.get("data_channel"), dict):
        raise LiveProviderError("invalid_live_client_permissions")
    permissions = client["data_channel"]
    if permissions.get("allowed_client_events") != []:
        raise LiveProviderError("untrusted_live_commands_must_be_disabled")
    if not isinstance(permissions.get("allowed_server_events"), list):
        raise LiveProviderError("live_ui_events_must_be_allowlisted")
    return result


class _WebSocketChannel:
    def __init__(self, socket):
        self._socket = socket

    async def send(self, event: dict) -> None:
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise LiveProviderError("invalid_live_command")
        if event["type"] not in {
            "session.close", "session.input_audio.mute", "session.input_audio.unmute",
            "session.instructions.append", "session.thinking.append", "session.commentary.append",
        }:
            raise LiveProviderError("unsupported_live_command")
        try:
            payload = json.dumps(event, ensure_ascii=False, allow_nan=False)
            if len(payload.encode("utf-8")) > MAX_EVENT_BYTES:
                raise LiveProviderError("live_command_too_large")
        except (TypeError, ValueError, UnicodeError):
            raise LiveProviderError("invalid_live_command") from None
        try:
            await self._socket.send(payload)
        except Exception:
            raise LiveProviderError("sideband_send_failed", ambiguous=True) from None

    async def __aiter__(self) -> AsyncIterator[dict]:
        try:
            async for message in self._socket:
                if not isinstance(message, str) or len(message.encode("utf-8")) > MAX_EVENT_BYTES:
                    raise LiveProviderError("invalid_sideband_event")
                try:
                    event = json.loads(message)
                except (ValueError, TypeError):
                    raise LiveProviderError("invalid_sideband_event") from None
                if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                    raise LiveProviderError("invalid_sideband_event")
                # Unknown event names are preserved for forward-compatible dispatch.
                # Raw reflected audio never leaves this transport or enters logs.
                if event["type"] not in ("session.input_audio.append", "session.output_audio.delta"):
                    yield event
        except LiveProviderError:
            raise
        except Exception:
            raise LiveProviderError("sideband_receive_failed", ambiguous=True) from None

    async def close(self) -> None:
        try:
            await self._socket.close()
        except Exception:
            raise LiveProviderError("sideband_transport_close_failed", ambiguous=True) from None


class OpenAILiveProvider:
    def __init__(self, api_key: str, *, http_client=None, websocket_connect=None,
                 timeout_seconds: float = 15.0):
        if not isinstance(api_key, str) or any(char in api_key for char in "\r\n"):
            raise ValueError("invalid API credential")
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds)
                or not 1 <= timeout_seconds <= 60):
            raise ValueError("invalid Live transport timeout")
        self._api_key = api_key
        self._http = http_client
        self._websocket_connect = websocket_connect
        self.timeout_seconds = timeout_seconds

    async def create_session(self, sdp: str, session_config: dict) -> LiveSession:
        offer = validate_sdp(sdp)
        config = _session_config(session_config)
        if not self._api_key:
            raise LiveProviderError("api_key_missing")
        # httpx2 is the HTTP dependency of the project's pinned OpenAI 3.42.1.
        import httpx2 as httpx

        client = self._http or httpx.AsyncClient(
            timeout=self.timeout_seconds, follow_redirects=False, trust_env=False,
            transport=httpx.AsyncHTTPTransport(retries=0),
        )
        try:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/live/sessions",
                    headers={"Authorization": f"Bearer {self._api_key}",
                             "Content-Type": "application/json"},
                    json={"session": config, "transport": {"type": "webrtc", "sdp": offer}},
                    timeout=self.timeout_seconds,
                )
            except Exception:
                # Even a timeout can follow a successful upstream creation. Never retry.
                raise LiveProviderError("session_creation_transport_failed", ambiguous=True) from None
            status = response.status_code
            if status != 201:
                # Deterministic validation/auth/quota refusal is safe to distinguish.
                # Server errors and redirects provide no trustworthy creation outcome.
                refused = status in (400, 401, 403, 404, 405, 413, 415, 422, 429)
                raise LiveProviderError("session_creation_rejected",
                                        ambiguous=not refused, status_code=status)
            session_id = None
            try:
                result = response.json()
                session_id = _session_id(result["session"]["id"])
                transport = result["transport"]
                if transport.get("type") != "webrtc":
                    raise ValueError("wrong transport")
                answer = validate_sdp(transport["sdp"])
                expires_at = result["session"].get("expires_at")
                if expires_at is not None and (type(expires_at) is not int or expires_at <= 0):
                    raise ValueError("invalid expiry")
            except (ValueError, TypeError, KeyError, AttributeError, LiveProviderError):
                raise LiveProviderError("invalid_session_creation_response", ambiguous=True,
                                        session_id=session_id) from None
            return {"session_id": session_id, "sdp": answer, "expires_at": expires_at}
        finally:
            if self._http is None:
                try:
                    await client.aclose()
                except Exception:
                    # A local client cleanup failure cannot erase a known session ID.
                    pass

    @asynccontextmanager
    async def attach(self, session_id: str) -> AsyncIterator[LiveChannel]:
        identifier = _session_id(session_id)
        if not self._api_key:
            raise LiveProviderError("api_key_missing")
        connect = self._websocket_connect
        if connect is None:
            # The legacy transport has the same extra_headers contract in websockets
            # 13 through 16 (the project's supported range); no background reconnect.
            from websockets.legacy.client import connect
        try:
            connection = connect(
                f"wss://api.openai.com/v1/live/sessions/{quote(identifier, safe='')}/attach",
                extra_headers={"Authorization": f"Bearer {self._api_key}"},
                open_timeout=self.timeout_seconds, close_timeout=5,
                max_size=MAX_EVENT_BYTES, max_queue=32, ping_interval=20, ping_timeout=20,
            )
            socket = await connection.__aenter__()
        except Exception:
            raise LiveProviderError("sideband_connection_failed", ambiguous=True,
                                    session_id=identifier) from None
        body_failed = False
        try:
            yield _WebSocketChannel(socket)
        except BaseException:
            body_failed = True
            raise
        finally:
            try:
                await connection.__aexit__(None, None, None)
            except Exception:
                if not body_failed:
                    raise LiveProviderError("sideband_transport_close_failed", ambiguous=True,
                                            session_id=identifier) from None
