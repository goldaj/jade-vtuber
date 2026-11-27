from contextlib import asynccontextmanager
import copy
import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx2
from openai.types.live.data_channel_config import DataChannelConfig

from src.jade_runtime.live_config import LiveConfig
from src.jade_runtime.live_provider import LiveProviderError, OpenAILiveProvider, MAX_SDP_BYTES


SDP = "v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=fingerprint:sha-256 00\r\na=ice-ufrag:unit\r\n"


class FakeSocket:
    def __init__(self, events=()):
        self.events = list(events)
        self.sent = []
        self.closed = False

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def close(self):
        self.closed = True

    async def __aiter__(self):
        for event in self.events:
            yield json.dumps(event) if isinstance(event, dict) else event


class LiveProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_uses_exact_live_transport_and_server_selected_config(self):
        captured = []

        def respond(request):
            captured.append(request)
            return httpx2.Response(201, json={"session": {"id": "live_original_123"},
                                             "transport": {"type": "webrtc", "sdp": SDP}})

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as http:
            provider = OpenAILiveProvider("unit-test-key", http_client=http)
            config = LiveConfig().session_config(instructions="private context")
            result = await provider.create_session(SDP, config)
        self.assertEqual(result, {"session_id": "live_original_123", "sdp": SDP, "expires_at": None})
        self.assertEqual(len(captured), 1)
        self.assertEqual(str(captured[0].url), "https://api.openai.com/v1/live/sessions")
        self.assertEqual(captured[0].headers["authorization"], "Bearer unit-test-key")
        body = json.loads(captured[0].content)
        # Validate the actual HTTP payload against the pinned provider SDK,
        # independently of the fake provider and Jade's own configuration.
        DataChannelConfig.model_validate(body["session"]["client"]["data_channel"], strict=True)
        self.assertEqual(body, {"session": config, "transport": {"type": "webrtc", "sdp": SDP}})
        self.assertNotIn("unit-test-key", str(result))

    async def test_resolved_voice_is_logged_without_provider_identifiers(self):
        requested = "voice_test_selected"
        config = LiveConfig(voice_id=requested).session_config()
        for reported, result in (({"id": requested}, "matched"), ("marin", "mismatch")):
            response = httpx2.Response(201, json={
                "session": {"id": "live_original_123", "audio": {"output": {"voice": reported}}},
                "transport": {"type": "webrtc", "sdp": SDP},
            })
            with self.subTest(result=result), self.assertLogs("src.jade_runtime.live_provider") as logged:
                async with httpx2.AsyncClient(transport=httpx2.MockTransport(lambda request: response)) as http:
                    provider = OpenAILiveProvider("unit-test-key", http_client=http)
                    await provider.create_session(SDP, config)
            self.assertEqual(len(logged.output), 1)
            self.assertIn(f"Live voice transport=webrtc kind=custom result={result}", logged.output[0])
            self.assertNotIn(requested, logged.output[0])
            self.assertNotIn("live_original_123", logged.output[0])

    async def test_invalid_server_event_selectors_are_rejected_before_http(self):
        http = AsyncMock()
        provider = OpenAILiveProvider("unit-test-key", http_client=http)
        variants = (
            "all", ["session.started"], [None], [{}], [{"type": ""}],
            [{"type": 1}], [{"type": "x" * 257}],
            [{"type": "session.started", "response_event": "response.completed"}],
            [{"type": "response.event"}],
            [{"type": "response.event", "response_event": ""}],
            [{"type": "response.event", "response_event": "x" * 257}],
            [{"type": "session.started", "unexpected": "value"}],
            [{"type": "session.started"}] * 257,
        )
        for selectors in variants:
            config = LiveConfig().session_config()
            config["client"]["data_channel"]["allowed_server_events"] = selectors
            with self.subTest(selectors=selectors), self.assertRaises(LiveProviderError) as raised:
                await provider.create_session(SDP, config)
            self.assertEqual(raised.exception.code, "live_ui_events_must_be_allowlisted")
        http.post.assert_not_awaited()

    async def test_missing_key_and_invalid_sdp_never_make_requests(self):
        http = AsyncMock()
        provider = OpenAILiveProvider("", http_client=http)
        with self.assertRaises(LiveProviderError) as raised:
            await provider.create_session(SDP, LiveConfig().session_config())
        self.assertEqual(raised.exception.code, "api_key_missing")
        for bad in (None, "not sdp", SDP + "x" * MAX_SDP_BYTES, SDP + "\x00"):
            with self.subTest(bad_type=type(bad)), self.assertRaises(LiveProviderError):
                await provider.create_session(bad, LiveConfig().session_config())
        http.post.assert_not_awaited()

    async def test_weakened_frontend_permissions_and_wrong_api_are_rejected_offline(self):
        http = AsyncMock()
        provider = OpenAILiveProvider("unit-test-key", http_client=http)
        base = LiveConfig().session_config()
        variants = []
        for changes in ({"store": True}, {"model": "gpt-realtime-2.1"},
                        {"delegation": {"type": "responses"}}, {"client": "bad"}):
            variants.append(dict(base, **changes))
        all_events = copy.deepcopy(base)
        all_events["client"]["data_channel"]["allowed_client_events"] = "all"
        variants.append(all_events)
        for config in variants:
            with self.subTest(config=config), self.assertRaises(LiveProviderError):
                await provider.create_session(SDP, config)
        http.post.assert_not_awaited()

    async def test_timeout_never_retries_and_is_ambiguous_without_leaking_body(self):
        http = AsyncMock()
        http.post.side_effect = httpx2.ReadTimeout("sensitive body and credential")
        provider = OpenAILiveProvider("unit-test-key", http_client=http)
        with self.assertRaises(LiveProviderError) as raised:
            await provider.create_session(SDP, LiveConfig().session_config())
        http.post.assert_awaited_once()
        self.assertTrue(raised.exception.ambiguous)
        self.assertNotIn("sensitive", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

    async def test_empty_custom_voice_bad_history_and_paid_triggers_are_rejected_locally(self):
        http = AsyncMock()
        provider = OpenAILiveProvider("unit-test-key", http_client=http)
        base = LiveConfig().session_config()
        invalid_voice = copy.deepcopy(base)
        invalid_voice["audio"]["output"]["voice"] = {"id": ""}
        variants = [invalid_voice, dict(base, triggers=[{"type": "decisions"}])]
        for history in ([{"role": "system", "content": [{"type": "input_text", "text": "bad"}]}],
                        [{"role": "user", "content": "plain string"}],
                        [{"role": "user", "content": [{"type": "input_image", "text": "bad"}]}],
                        [{}] * 129):
            variants.append(dict(base, input=history))
        for config in variants:
            with self.subTest(config=config), self.assertRaises(LiveProviderError):
                await provider.create_session(SDP, config)
        http.post.assert_not_awaited()

    async def test_status_errors_do_not_retry_or_expose_provider_error_bodies(self):
        for status, ambiguous in ((401, False), (422, False), (429, False), (408, True), (500, True), (307, True)):
            count = []

            def respond(request):
                count.append(request)
                return httpx2.Response(status, text="private provider response")

            async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as http:
                provider = OpenAILiveProvider("unit-test-key", http_client=http)
                with self.subTest(status=status), self.assertRaises(LiveProviderError) as raised:
                    await provider.create_session(SDP, LiveConfig().session_config())
                self.assertEqual(raised.exception.ambiguous, ambiguous)
                self.assertEqual(len(count), 1)
                self.assertNotIn("private", str(raised.exception))

    async def test_malformed_success_retains_known_session_id_for_cleanup(self):
        def respond(request):
            return httpx2.Response(201, json={"session": {"id": "live_known"},
                                             "transport": {"type": "webrtc", "sdp": "invalid"}})

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as http:
            provider = OpenAILiveProvider("unit-test-key", http_client=http)
            with self.assertRaises(LiveProviderError) as raised:
                await provider.create_session(SDP, LiveConfig().session_config())
        self.assertTrue(raised.exception.ambiguous)
        self.assertEqual(raised.exception.session_id, "live_known")

    async def test_quota_category_is_allowlisted_without_exposing_provider_details(self):
        for category, expected in (
                ("insufficient_quota", "live_quota_exceeded"),
                ("billing_hard_limit_reached", "live_quota_exceeded"),
                ("rate_limit_exceeded", "session_creation_rejected"),
                ("private-project-identifier", "session_creation_rejected"),
                ({"unexpected": "private"}, "session_creation_rejected")):
            def respond(request):
                return httpx2.Response(429, json={"error": {
                    "code": category, "message": "private provider account details"}})

            async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as http:
                provider = OpenAILiveProvider("unit-test-key", http_client=http)
                with self.subTest(category=category), self.assertRaises(LiveProviderError) as raised:
                    await provider.create_session(SDP, LiveConfig().session_config())
                self.assertEqual(raised.exception.code, expected)
                self.assertFalse(raised.exception.ambiguous)
                self.assertNotIn("private", repr(raised.exception))

    async def test_sideband_exact_url_no_start_replay_preserved_and_audio_discarded(self):
        event = {"type": "session.usage.updated", "event_id": "same", "usage": {"seconds": 12}}
        socket = FakeSocket([event, event, {"type": "future.event", "event_id": "new"},
                             {"type": "session.output_audio.delta", "delta": "private audio"}])
        calls = []

        @asynccontextmanager
        async def connect(url, **options):
            calls.append((url, options))
            yield socket

        provider = OpenAILiveProvider("unit-test-key", websocket_connect=connect)
        async with provider.attach("live_original") as channel:
            events = [item async for item in channel]
            self.assertEqual(socket.sent, [])
            await channel.send({"type": "session.close", "event_id": "stop-1"})
            await channel.close()
        self.assertEqual(events, [event, event, {"type": "future.event", "event_id": "new"}])
        self.assertEqual(calls[0][0], "wss://api.openai.com/v1/live/sessions/live_original/attach")
        self.assertEqual(socket.sent, [{"type": "session.close", "event_id": "stop-1"}])
        self.assertTrue(socket.closed)

    async def test_sideband_rejects_unsupported_commands_and_invalid_events(self):
        socket = FakeSocket(["not json"])

        @asynccontextmanager
        async def connect(url, **options):
            yield socket

        provider = OpenAILiveProvider("unit-test-key", websocket_connect=connect)
        async with provider.attach("live_1") as channel:
            for event_type in ("session.start", "session.input_audio.append", "response.create", "response.cancel"):
                with self.subTest(event=event_type), self.assertRaises(LiveProviderError):
                    await channel.send({"type": event_type})
            with self.assertRaises(LiveProviderError):
                _ = [event async for event in channel]
        self.assertEqual(socket.sent, [])

    async def test_invalid_id_never_enters_transport_and_body_error_is_not_swallowed(self):
        calls = []

        @asynccontextmanager
        async def connect(url, **options):
            calls.append(url)
            yield FakeSocket()

        provider = OpenAILiveProvider("unit-test-key", websocket_connect=connect)
        with self.assertRaises(LiveProviderError):
            async with provider.attach("../another-session?key=x"):
                pass
        self.assertEqual(calls, [])
        with self.assertRaisesRegex(ValueError, "application failure"):
            async with provider.attach("live_1"):
                raise ValueError("application failure")

    async def test_new_http_client_never_uses_ambient_authorization_or_retries(self):
        fake_http = AsyncMock()
        fake_http.post.side_effect = RuntimeError("offline")
        with patch("httpx2.AsyncClient", return_value=fake_http) as factory:
            provider = OpenAILiveProvider("unit-test-key")
            with self.assertRaises(LiveProviderError):
                await provider.create_session(SDP, LiveConfig().session_config())
        self.assertFalse(factory.call_args.kwargs["trust_env"])
        self.assertFalse(factory.call_args.kwargs["follow_redirects"])
        fake_http.aclose.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
