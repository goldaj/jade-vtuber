import json
import unittest

from src.jade_runtime.vtube_studio import VTubeStudio, _validate_url


class WebSocket:
    def __init__(self):
        self.request = []
    async def send(self, value):
        self.request.append(json.loads(value))
    async def recv(self):
        last = self.request[-1]
        if last["messageType"] == "AuthenticationRequest":
            data = {"authenticated": True}
        else:
            data = {"hotkeyID": last["data"]["hotkeyID"]}
        return json.dumps({"requestID": last["requestID"],
                          "messageType": last["messageType"].removesuffix("Request")+"Response",
                          "data": data})


class Scope:
    def __init__(self):
        self.ws = WebSocket()
    async def __aenter__(self):
        return self.ws
    async def __aexit__(self, *args):
        pass


class VTSTests(unittest.IsolatedAsyncioTestCase):
    async def test_auth_and_hotkey_without_network_or_camera(self):
        scope = Scope()
        async with VTubeStudio("fake-token", connector=lambda _: scope) as app:
            self.assertTrue(await app.trigger_hotkey("Jade_Smile"))
            self.assertFalse(await app.trigger_hotkey(""))
        self.assertEqual(scope.ws.request[0]["data"]["pluginName"], "Jade AI")
        self.assertEqual(scope.ws.request[1]["data"]["hotkeyID"], "Jade_Smile")

    def test_refuse_nonlocal_api_hosts_and_embedded_secrets(self):
        for url in ["wss://example.com:8001", "ws://evil:8001",
                    "ws://127.0.0.1:8001/path", "ws://a:b@localhost:8001"]:
            with self.assertRaises(ValueError):
                _validate_url(url)
