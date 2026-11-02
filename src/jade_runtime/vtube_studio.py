"""Opt-in loopback-only VTube Studio WebSocket client; no camera needed.

The r20 runtime may have different hotkey IDs. Do not claim visual validity
without real VTube Studio and an installed r20/r21 export.
"""
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
import json


def _validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "ws" or parsed.hostname not in ("127.0.0.1", "localhost")
            or parsed.username or parsed.password or not 1 <= (parsed.port or 0) <= 65535
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("VTube Studio may connect only to local WebSocket API")
    return url


class VTubeStudio:
    def __init__(self, token: str, *, url="ws://127.0.0.1:8001",
                 connector=None):
        if not token or token == "example":
            raise ValueError("VTube Studio permission token missing")
        self.token = token
        self.url = _validate_url(url)
        self.connector = connector
        self.ws = None
        self.sequence = 0

    async def __aenter__(self):
        connector = self.connector
        if connector is None:
            try:
                from websockets.asyncio.client import connect
            except ImportError as exc:
                raise RuntimeError("install the optional VTube Studio extra") from exc
            connector = connect
        self._scope = connector(self.url)
        self.ws = await self._scope.__aenter__()
        try:
            result = await self.request("AuthenticationRequest", {
                "pluginName": "Jade AI", "pluginDeveloper": "Jade Project",
                "authenticationToken": self.token})
            if not result.get("authenticated"):
                raise PermissionError("VTube Studio declined authentication")
        except Exception:
            await self.__aexit__(None, None, None)
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        ws, self.ws = self.ws, None
        if ws is not None:
            await self._scope.__aexit__(exc_type, exc, tb)

    async def request(self, name: str, data=None):
        if self.ws is None:
            raise RuntimeError("VTube Studio not connected")
        self.sequence += 1
        request_id = f"jade-{self.sequence}"
        payload = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": request_id,
            "messageType": name,
            "data": data or {},
        }
        await self.ws.send(json.dumps(payload))
        response = json.loads(await self.ws.recv())
        if (response.get("requestID") != request_id
                or response.get("messageType") not in (name.removesuffix("Request")+"Response", "APIError")):
            raise ValueError("VTube Studio returned unrelated/invalid response")
        if response["messageType"] == "APIError":
            raise RuntimeError("VTube Studio rejected a requested operation")
        return response.get("data") or {}

    async def trigger_hotkey(self, hotkey: str) -> bool:
        if not hotkey:
            return False
        if len(hotkey) > 64 or "\n" in hotkey or "\r" in hotkey:
            raise ValueError("invalid hotkey")
        await self.request("HotkeyTriggerRequest", {"hotkeyID": hotkey})
        return True
