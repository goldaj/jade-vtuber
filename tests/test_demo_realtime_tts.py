"""Offline tests for the experimental Realtime speech adapter."""
import asyncio
import base64
from io import BytesIO
import unittest
from unittest.mock import AsyncMock, patch
import wave

try:
    from demo.reelle.realtime_tts import RealtimeTTS, RealtimeTTSError
except ModuleNotFoundError as exc:
    if exc.name not in {"demo", "demo.reelle", "demo.reelle.realtime_tts"}:
        raise
    RealtimeTTS = None


def event(kind, **fields):
    return {"type": kind, **fields}


def configured():
    return event("session.updated", session={"type": "realtime", "output_modalities": ["audio"],
                 "audio": {"output": {"format": {"type": "audio/pcm", "rate": 24000},
                                      "voice": "coral"}}})


def created():
    return event("response.created", response={"id": "response-1", "metadata": {"purpose": "jade_tts"}})


def delta(data=b"\x00\x00\x01\x00", **overrides):
    fields = {"response_id": "response-1", "item_id": "item-1", "output_index": 0,
              "content_index": 0, "delta": base64.b64encode(data).decode("ascii")}
    fields.update(overrides)
    return event("response.output_audio.delta", **fields)


def transcript(text="Bonjour Jade.", **overrides):
    fields = {"response_id": "response-1", "item_id": "item-1", "output_index": 0,
              "content_index": 0, "transcript": text}
    fields.update(overrides)
    return event("response.output_audio_transcript.done", **fields)


def done(status="completed", **overrides):
    response = {"id": "response-1", "status": status}
    response.update(overrides)
    return event("response.done", response=response)


class FakeConnection:
    def __init__(self, events):
        self.events = iter(events)
        self.session = type("Session", (), {})()
        self.session.update = AsyncMock()
        self.response = type("Response", (), {})()
        self.response.create = AsyncMock()
        self.response.cancel = AsyncMock()
        self.blocked = asyncio.Event()

    async def recv(self):
        try:
            value = next(self.events)
        except StopIteration:
            await self.blocked.wait()
            raise AssertionError("unexpected unblock")
        if isinstance(value, BaseException):
            raise value
        return value


class FakeManager:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *args):
        self.closed = True


class FakeClient:
    def __init__(self, events):
        self.connection = FakeConnection(events)
        self.manager = FakeManager(self.connection)
        self.realtime = type("Realtime", (), {})()
        self.calls = []

        def connect(**kwargs):
            self.calls.append(kwargs)
            return self.manager

        self.realtime.connect = connect


@unittest.skipIf(RealtimeTTS is None, "real demo omitted from this preview")
class RealtimeTTSTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_wav_and_request_contract(self):
        client = FakeClient([event("session.created"), configured(), created(), delta(),
                             transcript("bonjour, Jade !"), done()])
        audio = await RealtimeTTS(client).synthesize_wav("Bonjour Jade.")
        with wave.open(BytesIO(audio), "rb") as result:
            self.assertEqual((result.getnchannels(), result.getsampwidth(), result.getframerate()),
                             (1, 2, 24000))
            self.assertEqual(result.readframes(2), b"\x00\x00\x01\x00")
        self.assertTrue(client.manager.closed)
        self.assertEqual(client.calls[0]["model"], "gpt-realtime-2.1-mini")
        self.assertEqual(client.calls[0]["max_retries"], 0)
        sent_session = client.connection.session.update.await_args.kwargs["session"]
        self.assertIsNone(sent_session["audio"]["input"]["turn_detection"])
        self.assertEqual(sent_session["audio"]["output"]["format"]["rate"], 24000)
        sent_response = client.connection.response.create.await_args.kwargs["response"]
        self.assertEqual(sent_response["conversation"], "none")
        self.assertEqual(sent_response["max_output_tokens"], 4096)
        self.assertEqual(sent_response["input"][0]["content"][0]["text"], "Bonjour Jade.")
        client.connection.response.cancel.assert_not_awaited()

    async def test_transcript_may_arrive_before_first_audio(self):
        client = FakeClient([configured(), created(), transcript(), delta(), done()])
        self.assertTrue(await RealtimeTTS(client).synthesize_wav("Bonjour Jade."))

    async def test_relaxed_transcript_option_is_explicit(self):
        client = FakeClient([configured(), created(), delta(), transcript("Bonjour chère Jade"), done()])
        result = await RealtimeTTS(client, verify_transcript=False).synthesize("Bonjour Jade.")
        self.assertTrue(result.audio)
        self.assertEqual(result.transcript, "Bonjour chère Jade")
        self.assertNotIn("Jade", repr(result))

    async def test_transcript_still_required_when_comparison_is_relaxed(self):
        client = FakeClient([configured(), created(), delta(), done()])
        with self.assertRaises(RealtimeTTSError):
            await RealtimeTTS(client, verify_transcript=False).synthesize("Bonjour Jade.")

    async def test_rejects_failed_incomplete_and_mismatched_transcripts(self):
        scenarios = [
            [configured(), created(), delta(), transcript(), done("failed")],
            [configured(), created(), delta(), transcript(), done("cancelled")],
            [configured(), created(), delta(), transcript(), done("incomplete")],
            [configured(), created(), delta(), transcript("Autre phrase"), done()],
            [configured(), created(), delta(), done()],
            [configured(), created(), delta(b"x"), transcript(), done()],
        ]
        for events in scenarios:
            with self.subTest(events=events[-1]["type"]):
                client = FakeClient(events)
                with self.assertRaises(RealtimeTTSError) as caught:
                    await RealtimeTTS(client).synthesize_wav("Bonjour Jade.")
                self.assertNotIn("Bonjour", str(caught.exception))
                self.assertTrue(client.manager.closed)

    async def test_corrupt_oversized_and_foreign_audio_fails_closed(self):
        invalid = [delta(delta="???"), delta(b"a" * 101),
                   delta(response_id="other"), delta(item_id="")]
        for bad in invalid:
            client = FakeClient([configured(), created(), bad])
            with self.subTest(bad=bad):
                with self.assertRaises(RealtimeTTSError):
                    await RealtimeTTS(client, max_audio_bytes=100).synthesize_wav("Bonjour Jade.")
                client.connection.response.cancel.assert_awaited_once_with(response_id="response-1")
                self.assertTrue(client.manager.closed)

    async def test_different_content_parts_are_not_joined(self):
        client = FakeClient([configured(), created(), delta(), delta(item_id="other")])
        with self.assertRaises(RealtimeTTSError):
            await RealtimeTTS(client).synthesize_wav("Bonjour Jade.")
        client.connection.response.cancel.assert_awaited_once_with(response_id="response-1")

    async def test_configuration_error_never_starts_a_response(self):
        bad = configured()
        bad["session"]["audio"]["output"]["format"]["rate"] = 16000
        for first in (bad, event("error", error={"message": "sensitive provider text"})):
            client = FakeClient([first])
            with self.assertRaises(RealtimeTTSError) as caught:
                await RealtimeTTS(client).synthesize_wav("Bonjour Jade.")
            self.assertNotIn("sensitive", str(caught.exception))
            client.connection.response.create.assert_not_awaited()

    async def test_cancellation_sends_cancel_and_closes(self):
        client = FakeClient([configured(), created(), delta()])
        task = asyncio.create_task(RealtimeTTS(client).synthesize_wav("Bonjour Jade."))
        for _ in range(100):
            await asyncio.sleep(0)
            if client.connection.response.create.await_count:
                break
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        client.connection.response.cancel.assert_awaited_once_with(response_id="response-1")
        self.assertTrue(client.manager.closed)

    async def test_timeout_cancels_and_closes(self):
        client = FakeClient([configured(), created()])
        with self.assertRaises(RealtimeTTSError):
            await RealtimeTTS(client, timeout_seconds=1).synthesize_wav("Bonjour Jade.")
        client.connection.response.cancel.assert_awaited_once_with(response_id="response-1")
        self.assertTrue(client.manager.closed)

    async def test_actual_sdk_serializes_requests_without_network(self):
        from openai.resources.realtime.realtime import (
            AsyncRealtimeConnection, AsyncRealtimeSessionResource, AsyncRealtimeResponseResource,
        )
        from openai._websocket_connection import AsyncWebSocketConnectionBase

        connection = object.__new__(AsyncRealtimeConnection)
        connection.session = AsyncRealtimeSessionResource(connection)
        connection.response = AsyncRealtimeResponseResource(connection)
        fake = FakeConnection([configured(), created(), delta(), transcript(), done()])
        connection.recv = fake.recv
        client = FakeClient([])
        client.manager = FakeManager(connection)
        with patch.object(AsyncWebSocketConnectionBase, "send_raw", new_callable=AsyncMock) as sent:
            await RealtimeTTS(client).synthesize_wav("Bonjour Jade.")
        import json
        messages = [json.loads(call.args[1]) for call in sent.await_args_list]
        self.assertEqual([item["type"] for item in messages], ["session.update", "response.create"])
        self.assertEqual(messages[1]["response"]["input"][0]["content"][0]["text"], "Bonjour Jade.")


if __name__ == "__main__":
    unittest.main()
