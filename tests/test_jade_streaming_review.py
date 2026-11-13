"""PO/technical regressions for streaming conversation reliability.

No real network, microphone, Discord token or paid OpenAI call is used.
"""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from src.jade_runtime.config import Settings
from src.jade_runtime.discord_voice import OpenVoiceBridge
from src.jade_runtime.discord_pcm import DiscordPCMBuffer, FRAME_BYTES
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.early_speech import EarlySpeechTurn
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.output import SpeechOutput
from src.jade_runtime.sentence_stream import SentenceAccumulator
from tests.test_jade_streaming_pcm import FakeConnection


def chunk(text=None, finish=None):
    choice = SimpleNamespace(index=0, finish_reason=finish,
                             delta=SimpleNamespace(content=text))
    return SimpleNamespace(choices=[choice])


class MockChat:
    def __init__(self, *events):
        self.events = events
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(
            create=self.create))

    async def create(self, **kwargs):
        self.calls.append(kwargs)

        async def stream():
            for event in self.events:
                yield event
        return stream()


class TruncatedLLMTests(unittest.IsolatedAsyncioTestCase):
    async def test_streaming_llm_requires_successful_terminal_marker(self):
        provider = MockChat(chunk("Réponse partielle"))
        services = OpenAIServices(Settings(), client=provider)
        fragments = []
        with self.assertRaisesRegex(ValueError, "without completion"):
            async for fragment in services.complete_stream([{"role": "user", "content": "Test"}]):
                fragments.append(fragment)
        self.assertEqual(fragments, ["Réponse partielle"])
        self.assertEqual(len(provider.calls), 1)
        self.assertTrue(provider.calls[0]["stream"])

    async def test_length_truncation_is_an_error_not_a_complete_reply(self):
        provider = MockChat(chunk("Partie 1"), chunk(finish="length"))
        services = OpenAIServices(Settings(), client=provider)
        with self.assertRaisesRegex(ValueError, "incompletely"):
            _ = [x async for x in services.complete_stream([{"role": "user", "content": "Test"}])]
        self.assertEqual(len(provider.calls), 1)

    async def test_last_text_and_stop_marker_can_share_one_chunk(self):
        provider = MockChat(chunk("Bonjour ", finish=None), chunk("Jade.", finish="stop"))
        services = OpenAIServices(Settings(), client=provider)
        result = [x async for x in services.complete_stream([{"role": "user", "content": "Test"}])]
        self.assertEqual(result, ["Bonjour ", "Jade."])
        self.assertEqual(len(provider.calls), 1)

    async def test_successful_llm_stream_is_delivered_once(self):
        provider = MockChat(chunk("Bonjour"), chunk(" Jade."), chunk(finish="stop"))
        services = OpenAIServices(Settings(), client=provider)
        result = [x async for x in services.complete_stream([{"role": "user", "content": "Test"}])]
        self.assertEqual(result, ["Bonjour", " Jade."])
        self.assertEqual(len(provider.calls), 1)


class SentenceCostTests(unittest.TestCase):
    def test_french_abbreviation_and_decimal_tokens_are_not_short_calls(self):
        splitter = SentenceAccumulator()
        self.assertEqual(splitter.feed("M."), [])
        self.assertEqual(splitter.feed(" Dupont arrive. Le total est 2."), ["M. Dupont arrive."])
        self.assertEqual(splitter.feed("5 euros."), ["Le total est 2.5 euros."])
        self.assertEqual(splitter.finish(), [])

    def test_tts_call_count_is_bounded_without_losing_remainder(self):
        splitter = SentenceAccumulator(max_segments=4)
        phrases = splitter.feed("Oui. Non. Très bien. Voilà. Encore. Et enfin.")
        phrases.extend(splitter.finish())
        self.assertEqual(len(phrases), 4)
        self.assertEqual(" ".join(phrases), "Oui. Non. Très bien. Voilà. Encore. Et enfin.")

    def test_invalid_billing_cap_is_rejected(self):
        with self.assertRaises(ValueError):
            SentenceAccumulator(max_segments=0)


class SilenceAnimationTests(unittest.IsolatedAsyncioTestCase):
    async def test_prebuffer_and_live_underrun_report_zero_level_to_avatar(self):
        frames = []
        buffer = DiscordPCMBuffer(on_frame=frames.append)
        self.assertEqual(buffer.read(), b"\x00" * FRAME_BYTES)
        await buffer.feed(b"\x10\x00" * 480)
        self.assertNotEqual(buffer.read(), b"\x00" * FRAME_BYTES)
        self.assertEqual(buffer.read(), b"\x00" * FRAME_BYTES)
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0], b"\x00" * FRAME_BYTES)
        self.assertTrue(any(frames[1]))
        self.assertEqual(frames[2], b"\x00" * FRAME_BYTES)
        buffer.abort()


class GateFailureTests(unittest.IsolatedAsyncioTestCase):
    class Services:
        settings = SimpleNamespace(tts_model="gpt-realtime-2.1-mini")

        def stream_speech_pcm(self, text):
            async def generator():
                yield b"\x01\x00" * 480
            return generator()

    class Gate:
        async def begin_speech(self):
            pass

        async def end_speech(self):
            raise RuntimeError("failed to release gate")

    class Bridge:
        def __init__(self):
            self.ack = 0

        def reply_authorized(self, source):
            return True

        async def play_pcm_stream_for_reply(self, stream, source):
            async for _ in stream:
                pass
            return True

        def mark_voice_reply_played(self, source):
            self.ack += 1

    class SilentPlayer:
        mode = "none"

    def source(self):
        return Incoming("discord_voice", "Visiteur", "bonjour", channel="45",
                        speaker_id=12, voice_session_id="a" * 32, force_reply=True)

    async def test_progressive_stream_ack_requires_successful_gate_cleanup(self):
        with TemporaryDirectory() as folder:
            bridge = self.Bridge()
            path = Path(folder) / "subtitle.txt"
            output = SpeechOutput(self.Services(), self.SilentPlayer(), path,
                                  secondary_player=bridge, audio_gate=self.Gate())
            with self.assertRaisesRegex(RuntimeError, "failed to release gate"):
                await output.speak(Reply(self.source(), "Bonjour."))
            self.assertEqual(bridge.ack, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), "")

    async def test_early_stream_ack_requires_successful_gate_cleanup(self):
        with TemporaryDirectory() as folder:
            bridge = self.Bridge()
            path = Path(folder) / "subtitle.txt"
            output = SpeechOutput(self.Services(), self.SilentPlayer(), path,
                                  secondary_player=bridge, audio_gate=self.Gate())
            turn = output.start_early(self.source())
            await turn.emit("Bonjour.")
            await turn.finish_input()
            with self.assertRaisesRegex(RuntimeError, "failed to release gate"):
                await asyncio.wait_for(turn.wait(), 1)
            self.assertEqual(bridge.ack, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), "")

    async def test_early_stream_deadline_stops_stalled_discord_player(self):
        class StalledBridge(self.Bridge):
            async def play_pcm_stream_for_reply(self, stream, source):
                await asyncio.Event().wait()

        with TemporaryDirectory() as folder:
            bridge = StalledBridge()
            path = Path(folder) / "subtitle.txt"
            output = SpeechOutput(self.Services(), self.SilentPlayer(), path,
                                  secondary_player=bridge)
            turn = output.start_early(self.source())
            turn.max_seconds = 1
            await turn.emit("Bonjour.")
            await turn.finish_input()
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(turn.wait(), 2)
            self.assertEqual(bridge.ack, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), "")


class LLMStreamDisposalTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_voice_consumer_closes_llm_stream_and_leaves_history_clean(self):
        class Backend:
            closed = False

            async def complete_stream(self, messages):
                try:
                    yield "Bonjour."
                    await asyncio.Event().wait()
                finally:
                    self.closed = True

        backend = Backend()
        dialogue = Dialogue(backend, "Jade test")
        source = Incoming("discord_voice", "Visiteur", "Salut", channel="45",
                          voice_session_id="a" * 32, speaker_id=12, force_reply=True)

        async def consumer(_sentence):
            raise RuntimeError("voice destination unavailable")

        with self.assertRaisesRegex(RuntimeError, "voice destination unavailable"):
            await dialogue.respond(source, on_sentence=consumer)
        self.assertTrue(backend.closed)
        self.assertEqual(len(dialogue.history[source.session]), 0)


class CancellationCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_discord_playback_state_is_released_if_stream_aclose_cancels(self):
        class BadStream:
            def __init__(self):
                self.sent = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.sent:
                    raise RuntimeError("synthetic provider error")
                self.sent = True
                return b"\x01\x00" * 480

            async def aclose(self):
                raise asyncio.CancelledError()

        bridge = OpenVoiceBridge(None, None, 45)
        connection = FakeConnection()
        bridge.connection = connection
        bridge.consent_confirmed = True
        bridge.own_bot_id = 100
        bridge.session_id = "a" * 32
        with patch.dict("sys.modules", {"discord": SimpleNamespace(AudioSource=object)}):
            with self.assertRaises(asyncio.CancelledError):
                await bridge.play_pcm_stream(BadStream())
        self.assertFalse(bridge._playback_active)
        self.assertGreater(connection.stops, 0)

    async def test_subtitles_and_mic_release_even_when_stream_aclose_cancels(self):
        class BadStream:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration()

            async def aclose(self):
                raise asyncio.CancelledError()

        class Services:
            def stream_speech_pcm(self, text):
                return BadStream()

        class Gate:
            def __init__(self):
                self.started = 0
                self.ended = 0

            async def begin_speech(self):
                self.started += 1

            async def end_speech(self):
                self.ended += 1

        class Bridge:
            def reply_authorized(self, source):
                return True

            async def play_pcm_stream_for_reply(self, stream, source):
                return True

        source = Incoming("discord_voice", "Visiteur", "bonjour", channel="45",
                          speaker_id=12, voice_session_id="a" * 32, force_reply=True)
        with TemporaryDirectory() as folder:
            gate = Gate()
            path = Path(folder) / "subtitle.txt"
            output = SpeechOutput(Services(), GateFailureTests.SilentPlayer(), path,
                                  secondary_player=Bridge(), audio_gate=gate)
            with self.assertRaises(asyncio.CancelledError):
                await output.speak(Reply(source, "Bonjour."))
            self.assertEqual((gate.started, gate.ended), (1, 1))
            self.assertEqual(path.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
