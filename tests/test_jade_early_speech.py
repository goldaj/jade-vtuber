"""Offline early LLM phrase-to-Discord tests; no provider or audio device."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.output import SpeechOutput
from src.jade_runtime.sentence_stream import SentenceAccumulator


class SentenceTests(unittest.TestCase):
    def test_sentences_are_incremental_and_full_text_is_unmodified(self):
        stream = SentenceAccumulator()
        self.assertEqual(stream.feed("Bonjour"), [])
        self.assertEqual(stream.feed(" Jade. Et"), ["Bonjour Jade."])
        self.assertEqual(stream.feed(" encore ?"), ["Et encore ?"])
        self.assertEqual(stream.finish(), [])

    def test_trailing_fragment_is_emitted_once(self):
        stream = SentenceAccumulator()
        self.assertEqual(stream.feed("Bonjour sans ponctuation"), [])
        self.assertEqual(stream.finish(), ["Bonjour sans ponctuation"])
        self.assertEqual(stream.finish(), [])

    def test_bounded_untrusted_fragments(self):
        stream = SentenceAccumulator(max_pending=80, max_total=100)
        with self.assertRaises(ValueError):
            stream.feed("x" * 101)


class EarlySpeechTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_sentence_callback_is_once_and_does_not_block_audio(self):
        class Services:
            settings = SimpleNamespace(tts_model="gpt-realtime-2.1-mini")
            def stream_speech_pcm(self, text):
                async def generate():
                    yield b"\x01\x00" * 480
                return generate()

        class Bridge:
            def reply_authorized(self, source):
                return True
            async def play_pcm_stream_for_reply(self, chunks, source):
                async for _ in chunks:
                    pass
                return True

        class Silent:
            mode = "none"

        started, cancelled = asyncio.Event(), asyncio.Event()
        called = []
        async def hotkey():
            called.append(1)
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        source = Incoming("discord_voice", "A", "Question", voice_session_id="a" * 32,
                          speaker_id=12, force_reply=True)
        with TemporaryDirectory() as folder:
            output = SpeechOutput(Services(), Silent(), Path(folder) / "subtitle.txt",
                                  secondary_player=Bridge())
            turn = output.start_early(source)
            turn.on_first_sentence = hotkey
            await turn.emit("Première phrase.")
            await turn.emit("Deuxième phrase.")
            await turn.finish_input()
            self.assertTrue(await asyncio.wait_for(turn.wait(), 1))
            self.assertTrue(started.is_set())
            self.assertTrue(cancelled.is_set())
            self.assertEqual(called, [1])

    async def test_first_audio_arrives_before_llm_finishes_and_reply_is_delivered_once(self):
        llm_release = asyncio.Event()
        first_audio = asyncio.Event()
        calls, complete_replies, audio_sentences = [], [], []

        class Chat:
            async def complete(self, messages):
                raise AssertionError("non-streaming LLM must not be called")

            async def complete_stream(self, messages):
                calls.append("llm")
                yield "Bonjour."
                await llm_release.wait()
                yield " Et voici la suite."

        class Services:
            settings = SimpleNamespace(tts_model="gpt-realtime-2.1-mini")

            def stream_speech_pcm(self, text):
                audio_sentences.append(text)
                async def generate():
                    yield b"\x12\x00" * 480
                return generate()

        class Bridge:
            def __init__(self):
                self.marked = 0
                self.segments = 0

            def reply_authorized(self, source):
                return True

            async def play_pcm_stream_for_reply(self, stream, source):
                async for chunk in stream:
                    self.segments += 1
                    if self.segments == 1:
                        first_audio.set()
                return True

            def mark_voice_reply_played(self, source):
                self.marked += 1

        class NonePlayer:
            mode = "none"
            async def play(self, audio):
                raise AssertionError("local audio must not play")

        with TemporaryDirectory() as folder:
            bridge = Bridge()
            output = SpeechOutput(Services(), NonePlayer(), Path(folder) / "subtitle.txt",
                                  secondary_player=bridge)
            dialogue = Dialogue(Chat(), "Jade test")
            async def on_reply(reply):
                complete_replies.append(reply)
            runtime = Runtime(dialogue, on_reply, on_stream_start=output.start_early)
            await runtime.start()
            source = Incoming("discord_voice", "Utilisateur", "question", channel="45",
                              voice_session_id="a" * 32, speaker_id=12, force_reply=True)
            try:
                await runtime.submit(source)
                await asyncio.wait_for(first_audio.wait(), 1)
                self.assertEqual(complete_replies, [])
                llm_release.set()
                await asyncio.wait_for(runtime.idle(), 2)
            finally:
                await runtime.stop(graceful=False)
            self.assertEqual(audio_sentences, ["Bonjour.", "Et voici la suite."])
            self.assertEqual(len(complete_replies), 1)
            self.assertEqual(complete_replies[0].text, "Bonjour. Et voici la suite.")
            self.assertTrue(complete_replies[0].spoken)
            self.assertEqual(bridge.marked, 1)
            self.assertEqual(len(dialogue.history[source.session]), 2)
            self.assertEqual((Path(folder) / "subtitle.txt").read_text(encoding="utf-8"), "")

    async def test_each_incremental_subtitle_uses_atomic_replace(self):
        class Services:
            settings = SimpleNamespace(tts_model="gpt-realtime-2.1-mini")

            def stream_speech_pcm(self, text):
                async def generate():
                    yield b"\x01\x00" * 480
                return generate()

        class Bridge:
            def reply_authorized(self, source):
                return True

            async def play_pcm_stream_for_reply(self, chunks, source):
                async for _ in chunks:
                    pass
                return True

        class Silent:
            mode = "none"

        source = Incoming("discord_voice", "A", "Question", voice_session_id="a" * 32,
                          speaker_id=12, force_reply=True)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "subtitle.txt"
            output = SpeechOutput(Services(), Silent(), path, secondary_player=Bridge())
            observed = []
            original = Path.write_text

            def capture(target, data, **kwargs):
                observed.append((target.name, data))
                return original(target, data, **kwargs)

            with patch.object(Path, "write_text", capture):
                turn = output.start_early(source)
                await turn.emit("Première phrase.")
                await turn.emit("Deuxième phrase.")
                await turn.finish_input()
                self.assertTrue(await turn.wait())
            updates = [name for name, value in observed if value]
            self.assertGreaterEqual(len(updates), 3)
            self.assertTrue(all(name.endswith(".tmp") for name in updates))
            self.assertEqual(path.read_text(encoding="utf-8"), "")

    async def test_runtime_legacy_path_remains_unchanged_when_stream_not_enabled(self):
        class Chat:
            async def complete(self, messages):
                return "Classique"
        received = []
        runtime = Runtime(Dialogue(Chat(), "Jade test"), lambda reply: deliver(reply))
        async def deliver(reply):
            received.append(reply)
        await runtime.start()
        try:
            await runtime.submit(Incoming("console", "A", "Question", force_reply=True))
            await asyncio.wait_for(runtime.idle(), 1)
        finally:
            await runtime.stop(graceful=False)
        self.assertEqual(len(received), 1)
        self.assertFalse(received[0].spoken)


if __name__ == "__main__":
    unittest.main()
