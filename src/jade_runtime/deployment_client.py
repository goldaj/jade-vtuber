"""Backend-only IPC to Jade's independent localhost deployment supervisor."""
from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DeploymentClient:
    def __init__(self, token: str, *, port: int = 8770):
        if not 32 <= len(token) <= 256 or type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("invalid local deployment credentials")
        self._token = token
        self._url = f"http://127.0.0.1:{port}"

    def _post(self, path: str, data: dict):
        body = json.dumps(data, separators=(",", ":")).encode("utf-8")
        request = Request(self._url + path, data=body, method="POST", headers={
            "Authorization": "Bearer " + self._token,
            "Content-Type": "application/json", "Accept": "application/json",
        })
        try:
            with urlopen(request, timeout=5) as reply:
                return reply.status, json.loads(reply.read(8192))
        except HTTPError as error:
            return error.code, {"error": "supervisor_rejected"}
        except (URLError, OSError, TimeoutError, ValueError):
            return 503, {"error": "supervisor_unavailable"}

    async def request(self, operation: str, **payload):
        if operation not in ("status", "branches", "deploy", "restart"):
            raise ValueError("unsupported supervisor operation")
        return await asyncio.to_thread(self._post, "/" + operation, payload)
