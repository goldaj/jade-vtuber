"""Offline checks for sentence streaming, cancellation, and history."""
import asyncio
import unittest

from src.jade_runtime.dialogue import Dialogue, _SpeechChunks
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime


class DialogueStreamingTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def message():
        return Incoming("discord_voice", "local", "un tour", force_reply=True,
                        message_id="synthetic")

    async def test_first_sentence_plays_before_generation_ends(self):
        started = asyncio.Event()
        release_generation = asyncio.Event()
        generated = asyncio.Event()
        release_playback = asyncio.Event()
        played, final = [], []

        class Backend:
            async def stream_complete(self, messages):
                yield "Bonjour, comment vas-tu aujourd'hui ? "
                await release_generation.wait()
                yield "Voici une autre phrase complète."
                generated.set()

        async def play(reply):
            played.append(reply.text)
            started.set()
            await release_playback.wait()
            return True

        async def deliver(reply):
            final.append((reply.text, runtime.current_streamed()))

        dialogue = Dialogue(Backend(), "Jade")
        runtime = Runtime(dialogue, deliver, on_sentence=play)
        await runtime.start()
        await runtime.submit(self.message())
        await asyncio.wait_for(started.wait(), 1)
        self.assertFalse(generated.is_set())
        release_generation.set()
        await asyncio.wait_for(generated.wait(), 1)
        self.assertFalse(release_playback.is_set())
        self.assertEqual(len(played), 1)
        release_playback.set()
        await asyncio.wait_for(runtime.idle(), 1)
        await runtime.stop()
        self.assertEqual(len(played), 2)
        self.assertEqual(final, [("Bonjour, comment vas-tu aujourd'hui ? Voici une autre phrase complète.", True)])
        self.assertEqual(dialogue.history[("discord_voice", "default")][-1]["content"], final[0][0])

    async def test_cancel_keeps_only_confirmed_speech_and_closes_stream(self):
        second_started = asyncio.Event()
        never = asyncio.Event()
        closed = asyncio.Event()
        final = []

        class Backend:
            async def stream_complete(self, messages):
                try:
                    yield "La première phrase est bien terminée. "
                    yield "La deuxième phrase est interrompue. "
                    await never.wait()
                finally:
                    closed.set()

        async def play(reply):
            if reply.text.startswith("La deuxième"):
                second_started.set()
                await never.wait()
            return True

        async def deliver(reply):
            final.append(reply.text)

        dialogue = Dialogue(Backend(), "Jade")
        runtime = Runtime(dialogue, deliver, on_sentence=play)
        await runtime.start()
        item = await runtime.submit(self.message())
        await asyncio.wait_for(second_started.wait(), 1)
        runtime.cancel_work(item)
        await asyncio.wait_for(runtime.idle(), 1)
        await runtime.stop()
        self.assertTrue(closed.is_set())
        self.assertEqual(final, [])
        history = dialogue.history[("discord_voice", "default")]
        self.assertEqual(history[-1]["content"],
                         "La première phrase est bien terminée. [réponse vocale interrompue]")
        self.assertNotIn("deuxième", history[-1]["content"])

    async def test_delivery_failure_does_not_repeat_sound_and_delivers_text(self):
        class Backend:
            async def stream_complete(self, messages):
                yield "Une première phrase pour entendre la réponse. "
                yield "Une deuxième phrase toujours disponible en texte."

        calls, final = [], []

        async def play(reply):
            calls.append(reply.text)
            return False

        async def deliver(reply):
            final.append((reply.text, runtime.current_streamed()))

        dialogue = Dialogue(Backend(), "Jade")
        runtime = Runtime(dialogue, deliver, on_sentence=play)
        await runtime.start()
        await runtime.submit(self.message())
        await asyncio.wait_for(runtime.idle(), 1)
        await runtime.stop()
        self.assertEqual(len(calls), 1)
        self.assertTrue(final[0][1])
        self.assertIn("deuxième phrase", final[0][0])
        self.assertEqual(dialogue.history[("discord_voice", "default")][-1]["content"],
                         "[réponse vocale interrompue]")

    async def test_non_voice_keeps_complete_backend(self):
        class Backend:
            async def complete(self, messages):
                return "Texte entier."

            async def stream_complete(self, messages):
                raise AssertionError("text source must not stream into voice")
                yield "unreachable"

        received = []

        async def play(reply):
            raise AssertionError("no voice should be played")

        async def deliver(reply):
            received.append((reply.text, runtime.current_streamed()))

        runtime = Runtime(Dialogue(Backend(), "Jade"), deliver, on_sentence=play)
        await runtime.start()
        await runtime.submit(Incoming("console", "local", "Bonjour Jade"))
        await asyncio.wait_for(runtime.idle(), 1)
        await runtime.stop()
        self.assertEqual(received, [("Texte entier.", False)])

    def test_french_abbreviation_and_last_fragment(self):
        chunks = _SpeechChunks()
        self.assertEqual(chunks.feed("Nous demandons à notre cher M. Dupont de patienter. "),
                         ["Nous demandons à notre cher M. Dupont de patienter."])
        self.assertEqual(chunks.feed("Merci"), [])
        self.assertEqual(chunks.finish(), "Merci")


if __name__ == "__main__":
    unittest.main()
