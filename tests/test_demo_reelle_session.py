"""Offline tests: no API calls, microphone, speakers or local secret files."""
import asyncio
from io import BytesIO
import os
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import AsyncMock, patch
import wave

if (Path(__file__).resolve().parents[1] / "demo/reelle/session.py").is_file():
    from demo.reelle.session import DemoEvent, DemoSession, _isolated_openai_client, _level, _wav_pcm, play_wav
    from demo.reelle.realtime_tts import SpokenAudio
else:
    # The private export intentionally omits the real-demo sources.
    DemoSession = None


def make_wav():
    buffer = BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes(b"\x00\x10" * 480)
    return buffer.getvalue()


class Services:
    def __init__(self):
        self.complete = AsyncMock(return_value="Bonjour !")
        self.synthesize = AsyncMock(return_value=SpokenAudio(make_wav(), "Bonjour !"))
        self.synthesize_wav = AsyncMock()
        self.transcribe_wav = AsyncMock(return_value="Salut")


@unittest.skipIf(DemoSession is None, "real demo omitted from this export")
class DemoSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_turn_uses_real_dialogue_contract_and_output_events(self):
        services, events, played = Services(), [], []
        def player(audio, stop, emit):
            played.append(audio)
            emit(DemoEvent("audio_level", 0.4))
        session = DemoSession("synthetic", "Jade", events.append, services=services,
                              player=player)
        self.assertTrue(await session.send_text("Bonjour"))
        services.complete.assert_awaited_once()
        services.synthesize.assert_awaited_once_with("Bonjour !")
        services.synthesize_wav.assert_not_awaited()
        services.transcribe_wav.assert_not_awaited()
        self.assertEqual(played, [make_wav()])
        self.assertIn(DemoEvent("reply_text", "Bonjour !"), events)
        self.assertFalse(any(event.kind == "spoken_text" for event in events))
        self.assertIn(DemoEvent("audio_level", 0.4), events)
        self.assertEqual(events[-2:], [DemoEvent("audio_level", 0.0), DemoEvent("state", "idle")])
        await session.close()

    async def test_changed_spoken_text_is_visible_before_audio_playback(self):
        services, events = Services(), []
        services.synthesize.return_value = SpokenAudio(make_wav(), "Bonjour à tous !")
        def player(audio, stop, emit):
            self.assertIn(DemoEvent("spoken_text", "Bonjour à tous !"), events)
        session = DemoSession("synthetic", "Jade", events.append, services=services,
                              player=player)
        self.assertTrue(await session.send_text("Salut"))
        self.assertEqual([event.value for event in events if event.kind == "spoken_text"],
                         ["Bonjour à tous !"])
        await session.close()

    async def test_tts_failure_does_not_retry_or_fall_back_to_speech_api(self):
        services, events, played = Services(), [], []
        services.synthesize.side_effect = RuntimeError("private provider response")
        session = DemoSession("synthetic", "Jade", events.append, services=services,
                              player=lambda *args: played.append(True))
        self.assertFalse(await session.send_text("Salut"))
        services.synthesize.assert_awaited_once()
        services.synthesize_wav.assert_not_awaited()
        self.assertEqual(played, [])
        self.assertNotIn("private provider response", repr(events))
        self.assertTrue(any(event.kind == "error" for event in events))
        await session.close()

    async def test_text_turn_reaches_realtime_transport_and_plays_result(self):
        from demo.reelle.realtime_tts import RealtimeTTS
        from tests.test_demo_realtime_tts import FakeClient, configured, created, delta, transcript, done

        services, events, played = Services(), [], []
        client = FakeClient([configured(), created(), delta(),
                             transcript("Bonjour Jade."), done()])
        synthesizer = RealtimeTTS(client, verify_transcript=False)
        session = DemoSession("synthetic", "Jade", events.append, services=services,
                              synthesizer=synthesizer,
                              player=lambda audio, stop, emit: played.append(audio))
        self.assertTrue(await session.send_text("Salut"))
        self.assertEqual(len(played), 1)
        self.assertEqual(played[0][:4], b"RIFF")
        self.assertIn(DemoEvent("reply_text", "Bonjour !"), events)
        self.assertIn(DemoEvent("spoken_text", "Bonjour Jade."), events)
        self.assertEqual(client.calls[0]["model"], "gpt-realtime-2.1-mini")
        self.assertEqual(client.calls[0]["max_retries"], 0)
        services.synthesize_wav.assert_not_awaited()
        self.assertTrue(client.manager.closed)
        await session.close()

    async def test_mic_is_only_captured_on_explicit_turn(self):
        services, events, captured = Services(), [], []
        def capture(seconds, *, stop_event):
            captured.append((seconds, stop_event.is_set()))
            return make_wav()
        session = DemoSession("synthetic", "Jade", events.append, services=services,
                              player=lambda *args: None, capture=capture)
        self.assertEqual(captured, [])
        self.assertTrue(await session.record_and_reply(1))
        self.assertEqual(captured, [(1, False)])
        services.transcribe_wav.assert_awaited_once_with(make_wav())
        self.assertIn(DemoEvent("user_text", "Salut"), events)
        await session.close()

    async def test_error_messages_never_include_provider_details(self):
        services, events = Services(), []
        marker = "synthetic-provider-private-detail"
        services.complete.side_effect = RuntimeError(marker)
        session = DemoSession("synthetic", "Jade", events.append, services=services)
        self.assertFalse(await session.send_text("Bonjour"))
        self.assertTrue(any(event.kind == "error" for event in events))
        self.assertNotIn(marker, repr(events))
        await session.close()

    async def test_no_second_turn_while_first_is_pending(self):
        services, entered, release = Services(), asyncio.Event(), asyncio.Event()
        async def complete(messages):
            entered.set()
            await release.wait()
            return "Bonjour !"
        services.complete.side_effect = complete
        session = DemoSession("synthetic", "Jade", lambda e: None, services=services,
                              player=lambda *args: None)
        first = asyncio.create_task(session.send_text("Salut"))
        await asyncio.wait_for(entered.wait(), timeout=1)
        with self.assertRaisesRegex(RuntimeError, "busy"):
            await session.send_text("Autre")
        release.set()
        self.assertTrue(await first)
        self.assertEqual(services.complete.await_count, 1)
        await session.close()

    async def test_cancel_capture_waits_for_owned_worker_and_never_transcribes(self):
        services, entered, exited = Services(), threading.Event(), threading.Event()
        def capture(seconds, *, stop_event):
            entered.set()
            stop_event.wait(1)
            exited.set()
            return None
        session = DemoSession("synthetic", "Jade", lambda e: None, services=services,
                              player=lambda *args: None, capture=capture)
        task = asyncio.create_task(session.record_and_reply())
        self.assertTrue(await asyncio.to_thread(entered.wait, 1))
        session.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(exited.is_set())
        services.transcribe_wav.assert_not_awaited()
        await session.close()

    async def test_closed_session_rejects_new_turns(self):
        session = DemoSession("synthetic", "Jade", lambda e: None, services=Services())
        await session.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await session.send_text("Salut")

    async def test_silence_and_empty_transcription_are_not_reported_as_success(self):
        services, events = Services(), []
        session = DemoSession("synthetic", "Jade", events.append, services=services,
                              capture=lambda *args, **kwargs: None)
        self.assertFalse(await session.record_and_reply())
        services.transcribe_wav.assert_not_awaited()
        self.assertTrue(any(event.kind == "error" for event in events))
        session._capture = lambda *args, **kwargs: make_wav()
        services.transcribe_wav.return_value = ""
        self.assertFalse(await session.record_and_reply())
        services.complete.assert_not_awaited()
        await session.close()

    async def test_client_is_created_without_billable_retries_and_released_on_close(self):
        with patch("demo.reelle.session._isolated_openai_client") as factory:
            factory.return_value.close = AsyncMock()
            session = DemoSession("synthetic-key", "Jade", lambda event: None)
            factory.assert_called_once()
            self.assertEqual(factory.call_args.args[0].api_key, "synthetic-key")
            self.assertEqual(factory.call_args.args[0].timeout_seconds, 20.0)
            self.assertIs(session._services.client, factory.return_value)
            self.assertIs(session._synthesizer.client, factory.return_value)
            self.assertEqual(session._services.settings.model, "gpt-6-luna")
            self.assertEqual(session._services.settings.stt_model, "gpt-transcribe")
            self.assertEqual(session._synthesizer.model, "gpt-realtime-2.1-mini")
            self.assertFalse(session._synthesizer.verify_transcript)
            await session.close()
            factory.return_value.close.assert_awaited_once()
            self.assertIsNone(session._services)
            self.assertIsNone(session._synthesizer)
            self.assertIsNone(session._dialogue.backend)

    async def test_sdk_ignores_foreign_endpoint_and_account_environment(self):
        import httpx2
        requests = []

        def respond(request):
            requests.append(request)
            if request.url.path.endswith("/audio/transcriptions"):
                return httpx2.Response(200, json={"text": "Salut"})
            return httpx2.Response(200, json={"choices": [{"message": {"content": "Bonjour"}}]})

        client = httpx2.AsyncClient(transport=httpx2.MockTransport(respond), trust_env=False)
        environment = {"OPENAI_BASE_URL": "https://elsewhere.invalid/v1",
                       "OPENAI_ORG_ID": "foreign-org", "OPENAI_PROJECT_ID": "foreign-project",
                       "OPENAI_ADMIN_KEY": "foreign-admin", "OPENAI_API_KEY": "foreign-key",
                       "OPENAI_CUSTOM_HEADERS": "authorization: Bearer foreign-token\n"
                                                "X-Foreign-Private: private-value\n"
                                                "content-type: text/plain\n"
                                                "OpenAI-Project: foreign-project"}
        with patch.dict(os.environ, environment), patch(
            "demo.reelle.session._isolated_openai_client",
            side_effect=lambda settings: _isolated_openai_client(settings, http_client=client)
        ):
            session = DemoSession("synthetic-key", "Jade", lambda event: None)
            self.assertEqual(await session._services.complete([{"role": "user", "content": "Salut"}]), "Bonjour")
            self.assertEqual(len(requests), 1)
            request = requests[0]
            self.assertEqual(str(request.url), "https://api.openai.com/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"], "Bearer synthetic-key")
            self.assertNotIn("OpenAI-Organization", request.headers)
            self.assertNotIn("OpenAI-Project", request.headers)
            self.assertNotIn("X-Foreign-Private", request.headers)
            self.assertEqual(request.headers["Content-Type"], "application/json")
            self.assertEqual(await session._services.transcribe_wav(make_wav()), "Salut")
            self.assertEqual(len(requests), 2)
            audio_request = requests[1]
            self.assertEqual(audio_request.headers["Authorization"], "Bearer synthetic-key")
            self.assertNotIn("X-Foreign-Private", audio_request.headers)
            self.assertNotIn("OpenAI-Project", audio_request.headers)
            self.assertTrue(audio_request.headers["Content-Type"].startswith("multipart/form-data; boundary="))
            self.assertEqual(session._services.client.admin_api_key, "")
            self.assertEqual(session._services.client.max_retries, 0)
            await session.close()

    async def test_realtime_websocket_ignores_foreign_environment_headers(self):
        from openai.lib import _websocket

        captured = {}
        async def fake_connect(url, **kwargs):
            captured.update(url=url, **kwargs)
            return object()

        environment = {
            "OPENAI_BASE_URL": "https://elsewhere.invalid/v1",
            "OPENAI_ORG_ID": "foreign-org", "OPENAI_PROJECT_ID": "foreign-project",
            "OPENAI_API_KEY": "foreign-key", "OPENAI_ADMIN_KEY": "foreign-admin",
            "OPENAI_CUSTOM_HEADERS": "Authorization: Bearer foreign-token\n"
                                     "X-Foreign-Private: private-value\n"
                                     "OpenAI-Project: foreign-project\n"
                                     "Content-Type: text/plain",
        }
        with patch.dict(os.environ, environment), patch.object(_websocket, "_WebSocketConnect", fake_connect):
            session = DemoSession("synthetic-key", "Jade", lambda event: None)
            manager = session._services.client.realtime.connect(model="gpt-realtime-2.1-mini", max_retries=0)
            await manager._connect_ws({}, {})
            headers = {key.lower(): value for key, value in captured["additional_headers"].items()}
            self.assertTrue(str(captured["url"]).startswith("wss://api.openai.com/v1/realtime?"))
            self.assertEqual(headers["authorization"], "Bearer synthetic-key")
            self.assertNotIn("x-foreign-private", headers)
            self.assertNotIn("openai-organization", headers)
            self.assertNotIn("openai-project", headers)
            self.assertEqual(headers["content-type"], "application/json")
            await session.close()

    async def test_close_releases_credentials_even_if_client_close_fails(self):
        services = Services()
        services.client = type("Client", (), {"close": AsyncMock(side_effect=RuntimeError("failed"))})()
        session = DemoSession("synthetic", "Jade", lambda event: None, services=services)
        with self.assertRaisesRegex(RuntimeError, "failed"):
            await session.close()
        self.assertIsNone(session._services)
        self.assertIsNone(session._dialogue.backend)

    async def test_rejects_key_with_header_control_characters(self):
        for invalid in ("bad\nkey", "bad key", "bad\x7fkey"):
            with self.subTest(value=repr(invalid)), self.assertRaises(ValueError):
                DemoSession(invalid, "Jade", lambda event: None, services=Services())


@unittest.skipIf(DemoSession is None, "real demo omitted from this export")
class WavTests(unittest.TestCase):
    def test_valid_pcm_and_streaming_header_are_bounded(self):
        wav = bytearray(make_wav())
        wav[4:8] = (0x7fffffff).to_bytes(4, "little")
        wav[40:44] = (0x7fffffff).to_bytes(4, "little")
        pcm, rate, channels = _wav_pcm(bytes(wav))
        self.assertEqual((len(pcm), rate, channels), (960, 24000, 1))
        self.assertGreater(_level(pcm), 0)

    def test_invalid_and_oversized_data_rejected(self):
        for data in (b"x" * 50, b"x" * 20_000_001):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                _wav_pcm(data)

    def test_pcm_playback_emits_audio_levels_and_resets(self):
        writes, levels = [], []
        class Output:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def write(self, samples):
                writes.append(samples)
            def abort(self):
                raise AssertionError("unexpected abort")
        fake = types.SimpleNamespace(RawOutputStream=lambda **kwargs: Output())
        with patch.dict(sys.modules, {"sounddevice": fake}):
            play_wav(make_wav(), threading.Event(), levels.append)
        self.assertEqual(len(writes), 1)
        self.assertEqual(sum(map(len, writes)), 960)
        self.assertGreater(levels[0].value, 0)
        self.assertEqual(levels[-1], DemoEvent("audio_level", 0.0))

    def test_pcm_playback_cancellation_aborts_and_resets(self):
        events, stop = [], threading.Event()
        stop.set()
        class Output:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def write(self, samples):
                events.append("unexpected write")
            def abort(self):
                events.append("abort")
        fake = types.SimpleNamespace(RawOutputStream=lambda **kwargs: Output())
        with patch.dict(sys.modules, {"sounddevice": fake}):
            play_wav(make_wav(), stop, events.append)
        self.assertEqual(events, ["abort", DemoEvent("audio_level", 0.0)])


if __name__ == "__main__":
    unittest.main()
