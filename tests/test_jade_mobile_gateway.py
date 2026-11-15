"""Offline tests of the owner-only PWA, no OpenAI/Tailscale/live microphone."""
import asyncio
import base64
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
import wave

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.mobile_gateway import (
    MAX_WAV, MobileGateway, WEB_FILES, WEB_ROOT, validate_wav)
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.turn_logging import planned_destinations


def wav16(frames=1600):
    output = BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0\0" * frames)
    return output.getvalue()


class FakeOpenAI:
    def __init__(self):
        self.prompts = []
        self.transcripts = []
        self.speeches = []
        self.settings = SimpleNamespace(tts_pitch_semitones=0.0)

    async def complete(self, messages):
        self.prompts.append(messages)
        return "[INTENT:tender] Bonjour papa, je t'écoute."

    async def transcribe_wav(self, audio):
        self.transcripts.append(audio)
        return "Tu m'entends, Jade ?"

    async def synthesize_speech(self, text, *, intent="neutral"):
        self.speeches.append((text, intent))
        return SimpleNamespace(audio=wav16(), transcript=text)


class MobileBackendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fake = FakeOpenAI()
        self.reply_log = []
        self.mobile = None

        async def on_reply(reply):
            self.reply_log.append(reply)
            self.mobile.deliver(reply)

        self.runtime = Runtime(
            Dialogue(self.fake, "Tu es Jade.", random_reply_rate=0),
            on_reply,
        )
        await self.runtime.start()
        self.mobile = MobileGateway(self.runtime, self.fake,
                                    token="x" * 40,
                                    port=8766)
        self.server = await asyncio.start_server(
            self.mobile._accept, "127.0.0.1", port=0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        if self.mobile.connections:
            await asyncio.gather(*self.mobile.connections, return_exceptions=True)
        await self.runtime.stop(graceful=False)

    async def request(self, method, route, *, body=b"", headers=None):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        extra = headers or {}
        lines = [f"{method} {route} HTTP/1.1", f"Host: 127.0.0.1:{self.port}"]
        if method == "POST" and "Content-Length" not in extra:
            lines.append(f"Content-Length: {len(body)}")
        lines.extend(f"{key}: {value}" for key, value in extra.items())
        packet = ("\r\n".join(lines) + "\r\n\r\n").encode() + body
        writer.write(packet)
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=4)
        writer.close()
        await writer.wait_closed()
        status = int(raw.split(b"\r\n", 1)[0].split()[1])
        payload = raw.split(b"\r\n\r\n", 1)[1]
        return status, payload, raw

    def headers(self, content_type):
        return {"Authorization": "Bearer " + "x" * 40,
                "Content-Type": content_type}

    async def test_chat_response_is_one_goldaj_identity_and_intent(self):
        payload = json.dumps({"text":"Jade, bonjour", "session":"m-123456789012",
                              "speak":False}).encode()
        status, body, raw = await self.request(
            "POST", "/api/chat", body=payload,
            headers=self.headers("application/json"))
        self.assertEqual(status, 200)
        self.assertIn(b"Cache-Control: no-store", raw)
        data = json.loads(body)
        self.assertEqual(data["reply"], "Bonjour papa, je t'écoute.")
        self.assertEqual(data["intent"], "tender")
        self.assertIsNone(data["audio_wav_b64"])
        self.assertEqual(self.reply_log[0].source.platform, "mobile")
        self.assertEqual(self.reply_log[0].source.author, "Goldaj")
        self.assertEqual(self.reply_log[0].source.input_modality, "text")
        self.assertIn("créateur et le père", str(self.fake.prompts[0]))
        self.assertEqual(planned_destinations(self.reply_log[0], mobile=True),
                         ("mobile_text",))

        # Same conversation/session even though next turn comes from the mic.
        voice_status, voice_body, _ = await self.request(
            "POST", "/api/voice", body=wav16(),
            headers={**self.headers("audio/wav"), "X-Jade-Session":"m-123456789012"})
        self.assertEqual(voice_status, 200)
        voice = json.loads(voice_body)
        self.assertEqual(voice["transcript"], "Tu m'entends, Jade ?")
        self.assertEqual(self.reply_log[1].source.platform, "mobile")
        self.assertEqual(self.reply_log[1].source.input_modality, "voice")
        self.assertEqual(self.reply_log[1].source.session,
                         self.reply_log[0].source.session)
        self.assertIn("Jade, bonjour", str(self.fake.prompts[1]))
        self.assertEqual(base64.b64decode(voice["audio_wav_b64"]), wav16())
        self.assertEqual(self.fake.speeches[-1][1], "tender")
        self.assertEqual(planned_destinations(self.reply_log[1], mobile=True),
                         ("mobile_text", "mobile_audio"))

    async def test_chat_optional_audio_and_no_pc_double_play(self):
        payload = json.dumps({"text":"Jade, comment tu vas ?",
                              "session":"m-123456789012", "speak":True}).encode()
        status, body, _ = await self.request(
            "POST", "/api/chat", body=payload, headers=self.headers("application/json"))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["audio_wav_b64"])
        self.assertEqual(len(self.fake.speeches), 1)

    async def test_owner_tailscale_identity_is_checked_for_all_files_and_api(self):
        self.mobile.owner_login = "creator@example.test"
        # The identity header is provided only by trusted Tailscale Serve.
        status, _, _ = await self.request("GET", "/")
        self.assertEqual(status, 403)
        status, _, _ = await self.request("GET", "/model/Jade.model3.json")
        self.assertEqual(status, 403)
        status, _, _ = await self.request(
            "GET", "/", headers={"Tailscale-User-Login":"someone@example.test"})
        self.assertEqual(status, 403)
        status, _, _ = await self.request(
            "GET", "/", headers={"Tailscale-User-Login":"creator@example.test"})
        self.assertEqual(status, 200)
        payload = json.dumps({"text":"Jade, salut", "session":"m-123456789012",
                              "speak":False}).encode()
        status, _, _ = await self.request("POST", "/api/chat", body=payload,
            headers=self.headers("application/json"))
        self.assertEqual(status, 403)
        status, _, _ = await self.request("POST", "/api/chat", body=payload,
            headers={**self.headers("application/json"),
                     "Tailscale-User-Login":"creator@example.test"})
        self.assertEqual(status, 200)

    async def test_tailscale_proxy_rewrites_host_but_browser_origin_is_public(self):
        self.mobile.owner_login = "creator@example.test"
        self.mobile.public_origin = "https://jade-pc.tail123.ts.net"
        payload = json.dumps({"text":"Jade, tu m'entends ?", "session":"m-123456789012",
                              "speak":False}).encode()
        # Host is the Go reverse-proxy backend (localhost), not the HTTPS
        # host seen by Chrome Android. Both owner and bearer are still required.
        status, body, _ = await self.request("POST", "/api/chat", body=payload,
            headers={**self.headers("application/json"),
                     "Tailscale-User-Login":"creator@example.test",
                     "Origin":"https://jade-pc.tail123.ts.net"})
        self.assertEqual(status, 200, body)
        status, _, _ = await self.request("POST", "/api/chat", body=payload,
            headers={**self.headers("application/json"),
                     "Tailscale-User-Login":"creator@example.test",
                     "Origin":"https://attacker.example"})
        self.assertEqual(status, 403)

    async def test_muted_voice_does_not_spend_tts(self):
        status, body, _ = await self.request(
            "POST", "/api/voice", body=wav16(),
            headers={**self.headers("audio/wav"),
                     "X-Jade-Session":"m-123456789012",
                     "X-Jade-Speak":"0"})
        self.assertEqual(status, 200)
        response = json.loads(body)
        self.assertEqual(response["transcript"], "Tu m'entends, Jade ?")
        self.assertIsNone(response["audio_wav_b64"])
        self.assertFalse(self.fake.speeches)
        self.assertEqual(planned_destinations(self.reply_log[-1], mobile=True),
                         ("mobile_text",))
        status, _, _ = await self.request(
            "POST", "/api/voice", body=wav16(),
            headers={**self.headers("audio/wav"),
                     "X-Jade-Session":"m-123456789012",
                     "X-Jade-Speak":"invalid"})
        self.assertEqual(status, 400)

    async def test_authentication_origin_and_bad_routes(self):
        body = json.dumps({"text":"Jade, bonjour", "session":"m-123456789012",
                           "speak":False}).encode()
        status, _, _ = await self.request("POST", "/api/chat", body=body,
            headers={"Content-Type":"application/json"})
        self.assertEqual(status, 401)
        status, _, _ = await self.request("POST", "/api/chat", body=body,
            headers={**self.headers("application/json"),
                     "Origin":"https://evil.example"})
        self.assertEqual(status, 403)
        status, _, _ = await self.request("POST", "/api/chat", body=body,
            headers={**self.headers("application/json"),
                     "Origin":f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)
        status, _, _ = await self.request("GET", "/../.env")
        self.assertEqual(status, 404)
        status, _, _ = await self.request("POST", "/api/unknown", body=b"{}",
                                          headers=self.headers("application/json"))
        self.assertEqual(status, 404)
        status, _, _ = await self.request("GET", "/vendor/live2dcubismcore.min.js")
        self.assertEqual(status, 404)

    async def test_oversized_invalid_microphone_never_calls_stt(self):
        # Announce an oversized body without sending 1MB of unread data;
        # otherwise TCP may reset before the client can read HTTP 413.
        status, _, _ = await self.request(
            "POST", "/api/voice", body=b"",
            headers={**self.headers("audio/wav"), "X-Jade-Session":"m-123456789012",
                     "Content-Length":str(MAX_WAV + 1)})
        self.assertEqual(status, 413)
        status, _, _ = await self.request(
            "POST", "/api/voice", body=b"bad wav header" * 4,
            headers={**self.headers("audio/wav"), "X-Jade-Session":"m-123456789012"})
        self.assertEqual(status, 400)
        self.assertFalse(self.fake.transcripts)

    async def test_png_icons_satisfy_android_install_sizes(self):
        for dimension in (192, 512):
            with self.subTest(size=dimension):
                status, body, response = await self.request(
                    "GET", f"/icon-{dimension}.png")
                self.assertEqual(status, 200)
                self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(int.from_bytes(body[16:20], "big"), dimension)
                self.assertEqual(int.from_bytes(body[20:24], "big"), dimension)
                self.assertIn(b"Content-Type: image/png", response)

    async def test_safe_assets_served_and_r20_idle_is_virtual(self):
        status, page, headers = await self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'id="avatar-container"', page)
        self.assertIn(b"frame-ancestors 'none'", headers)
        status, _, _ = await self.request("GET", "/assets/app.js")
        self.assertEqual(status, 200)
        model_dir = Path(self.temp.name) / "model"
        model_dir.mkdir()
        original = {"Version":3,"FileReferences":{
            "Moc":"Jade.moc3", "Textures":["Jade.4096/texture_00.png"]}}
        (model_dir / "Jade.model3.json").write_text(json.dumps(original), encoding="utf-8")
        (model_dir / "Jade_idle.motion3.json").write_text("{}", encoding="utf-8")
        (model_dir / "Jade.moc3").write_bytes(b"\x00" * 32)
        self.mobile.model_dir = model_dir
        status, doc, _ = await self.request("GET", "/model/Jade.model3.json")
        self.assertEqual(status, 200)
        self.assertIn("Idle", json.loads(doc)["FileReferences"]["Motions"])
        self.assertNotIn("Motions", original["FileReferences"])
        status, raw, _ = await self.request("GET", "/model/Jade.moc3")
        self.assertEqual(status, 200)
        self.assertEqual(raw, b"\x00" * 32)
        status, _, _ = await self.request("GET", "/model/../.env")
        self.assertEqual(status, 404)

    async def test_invalid_token_and_missing_flags(self):
        with self.assertRaises(ValueError):
            Settings(mobile_enabled=True, mobile_token="x" * 40).validate()
        with self.assertRaises(ValueError):
            Settings(mobile_enabled=True, mobile_token="x" * 40,
                     mobile_owner_login="creator@example.test").validate()
        Settings(mobile_enabled=True, mobile_token="x" * 40,
                 mobile_owner_login="creator@example.test",
                 mobile_public_origin="https://jade-pc.tail123.ts.net").validate()
        with self.assertRaises(ValueError):
            MobileGateway(self.runtime, self.fake, token="short")
        with self.assertRaises(ValueError):
            Incoming("mobile", "Goldaj", "Jade", input_modality="unknown")
        with self.assertRaises(ValueError):
            Incoming("mobile", "Goldaj", "Jade", requested_speech="no")
        with self.assertRaises(ValueError):
            validate_wav(wav16(320001))
        validate_wav(wav16(1600))


class MobileAppAssetsTests(unittest.TestCase):
    def test_pwa_assets_exist_and_do_not_store_bearer(self):
        for route, (filename, _) in WEB_FILES.items():
            self.assertTrue((WEB_ROOT / filename).is_file(), route)
        app = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("getUserMedia", app)
        self.assertIn("audio/wav", app)
        self.assertIn("setMouth", app)
        self.assertNotIn("localStorage.", app.replace("localStorage, sessionStorage", ""))
        self.assertNotIn("https://cdn", app)
        web = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("manifest.webmanifest", web)
        self.assertIn("/vendor/live2dcubismcore.min.js", web)

    def test_js_syntax_when_node_is_installed(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js not installed")
        for name in ("avatar.js", "app.js", "sw.js"):
            with self.subTest(name=name):
                process = subprocess.run(
                    [node, "--check", str(WEB_ROOT / name)],
                    capture_output=True, timeout=8)
                self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))


if __name__ == "__main__":
    unittest.main()
