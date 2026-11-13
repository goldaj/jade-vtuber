"""Offline regression checks for streamed dialogue and interruption."""
import asyncio
import unittest

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.early_speech import EarlySpeechTurn
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.sentence_stream import SentenceAccumulator


class DialogueStreamingTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def message():
        return Incoming("discord_voice", "local", "un tour", force_reply=True,
                        message_id="synthetic")

    async def test_cancel_after_generation_does_not_record_unheard_response(self):
        delivered = asyncio.Event()
        finish_playback = asyncio.Event()

        class Backend:
            async def complete_stream(self, messages):
                yield "Première phrase. Deuxième phrase encore non entendue."

        class Turn:
            has_submitted = False
            async def emit(self, sentence):
                self.has_submitted = True
            async def finish_input(self):
                pass
            async def wait(self):
                await finish_playback.wait()
                return True
            async def abort(self):
                pass

        async def output(reply):
            self.assertTrue(reply.spoken)
            delivered.set()

        dialogue = Dialogue(Backend(), "Jade")
        runtime = Runtime(dialogue, output, on_stream_start=lambda source: Turn())
        await runtime.start()
        item = await runtime.submit(self.message())
        await asyncio.wait_for(delivered.wait(), 1)
        self.assertEqual(len(dialogue.history[("discord_voice", "default")]), 0)
        runtime.cancel_work(item)
        await asyncio.wait_for(runtime.idle(), 1)
        await runtime.stop()
        history = dialogue.history[("discord_voice", "default")]
        self.assertEqual(history[-1]["content"], "[réponse vocale interrompue ou non diffusée]")
        self.assertNotIn("Deuxième", history[-1]["content"])

    async def test_cancel_during_generation_closes_stream_and_marks_interruption(self):
        emitted = asyncio.Event()
        never = asyncio.Event()
        closed = asyncio.Event()

        class Backend:
            async def complete_stream(self, messages):
                try:
                    yield "Première phrase. "
                    await never.wait()
                finally:
                    closed.set()

        class Turn:
            has_submitted = False
            async def emit(self, sentence):
                self.has_submitted = True
                emitted.set()
            async def abort(self):
                pass

        async def output(reply):
            raise AssertionError("the unfinished reply cannot be delivered")

        dialogue = Dialogue(Backend(), "Jade")
        runtime = Runtime(dialogue, output, on_stream_start=lambda source: Turn())
        await runtime.start()
        item = await runtime.submit(self.message())
        await asyncio.wait_for(emitted.wait(), 1)
        runtime.cancel_work(item)
        await asyncio.wait_for(runtime.idle(), 1)
        await runtime.stop()
        self.assertTrue(closed.is_set())
        self.assertEqual(dialogue.history[("discord_voice", "default")][-1]["content"],
                         "[réponse vocale interrompue ou non diffusée]")

    async def test_consumer_false_with_full_queue_does_not_hang(self):
        release = asyncio.Event()
        original = EarlySpeechTurn._run
        async def finish_false(turn):
            await release.wait()
            return False
        EarlySpeechTurn._run = finish_false
        try:
            turn = EarlySpeechTurn(None, None)
            await turn.emit("Une")
            await turn.emit("Deux")
            release.set()
            self.assertFalse(await turn.wait())
            with self.assertRaises(RuntimeError):
                await asyncio.wait_for(turn.emit("Trois"), 0.5)
            await turn.abort()
        finally:
            EarlySpeechTurn._run = original

    async def test_non_voice_keeps_complete_backend(self):
        class Backend:
            async def complete(self, messages):
                return "Texte entier."
            async def complete_stream(self, messages):
                raise AssertionError("text source must not start the early pipeline")
                yield "unreachable"
        received = []
        async def output(reply):
            received.append(reply)
        runtime = Runtime(Dialogue(Backend(), "Jade"), output,
                          on_stream_start=lambda source: self.fail("unexpected early speech"))
        await runtime.start()
        await runtime.submit(Incoming("console", "local", "Bonjour Jade"))
        await asyncio.wait_for(runtime.idle(), 1)
        await runtime.stop()
        self.assertEqual(received[0].text, "Texte entier.")
        self.assertFalse(received[0].spoken)

    def test_six_segment_limit_and_french_abbreviation(self):
        chunks = SentenceAccumulator()
        emitted = chunks.feed("Nous attendons M. Dupont. " + "Oui. " * 15)
        emitted.extend(chunks.finish())
        self.assertEqual(len(emitted), 6)
        self.assertEqual(emitted[0], "Nous attendons M. Dupont.")
        self.assertEqual(" ".join(emitted).count("Oui."), 15)


if __name__ == "__main__":
    unittest.main()
