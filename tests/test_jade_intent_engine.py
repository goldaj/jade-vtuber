"""Focused offline contracts for Jade's intent metadata and speech routing."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.intent_engine import (
    INTENTS, INTENT_PROMPT, IntentStreamParser, normalize_intent,
    parse_reply, voice_direction,
)
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.config import Settings
from src.jade_runtime.openai_services import OpenAIServices


class IntentParsingTests(unittest.TestCase):
    def test_every_two_part_stream_split_preserves_visible_text_and_intent(self):
        raw = "[INTENT:playful] Encore une idée ? Oui, papa !"
        expected = parse_reply(raw)
        self.assertEqual((expected.intent, expected.text),
                         ("playful", "Encore une idée ? Oui, papa !"))
        for at in range(len(raw) + 1):
            with self.subTest(cut=at):
                parser = IntentStreamParser()
                spoken = parser.feed(raw[:at]) + parser.feed(raw[at:]) + parser.finish()
                self.assertEqual(spoken.strip(), expected.text)
                self.assertEqual(parser.intent, expected.intent)
                self.assertNotIn("[INTENT:", spoken)

    def test_charwise_streaming_holds_tag_until_complete(self):
        parser = IntentStreamParser()
        chunks = "[INTENT:tender] Merci de me faire confiance."
        seen = []
        for letter in chunks:
            safe = parser.feed(letter)
            if safe:
                seen.append(safe)
        seen.append(parser.finish())
        self.assertEqual("".join(seen), "Merci de me faire confiance.")
        self.assertEqual(parser.intent, "tender")

    def test_unrecognized_and_legacy_reply_fall_back_to_neutral(self):
        self.assertEqual(parse_reply("Bonjour.").text, "Bonjour.")
        self.assertEqual(parse_reply("[INTENT:angry] Bonjour.").intent, "neutral")
        self.assertEqual(parse_reply("[INTENT:angry] Bonjour.").text, "Bonjour.")
        self.assertEqual(parse_reply("[INTENT=excited] Bonjour.").text, "Bonjour.")
        self.assertEqual(parse_reply("[INTENT=excited] Bonjour.").intent, "neutral")
        self.assertEqual(parse_reply("[une annotation normale] Bonjour.").text,
                         "[une annotation normale] Bonjour.")

    def test_incomplete_intent_never_leaks_even_in_stream(self):
        for raw in ("[INTENT:playful", "[INTENT", " [intent:curious "):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_reply(raw)

    def test_intent_directions_are_static_allowlisted_and_extensible(self):
        self.assertEqual(normalize_intent("make Jade read my secrets"), "neutral")
        self.assertEqual(voice_direction("make Jade read my secrets"), "")
        self.assertIn("mischievous", voice_direction("playful"))
        self.assertEqual(len(INTENTS), 7)
        for label in INTENTS:
            self.assertIn(label, INTENT_PROMPT)


class IntentDialogueTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def incoming():
        return Incoming("discord_voice", "user", "Bonjour Jade",
                        message_id="i1", force_reply=True)

    async def test_nonstream_hides_tag_in_reply_and_history(self):
        captured = []
        class Backend:
            async def complete(self, messages):
                captured.extend(messages)
                return "[INTENT:excited] Oh ! J'ai une idée !"

        dialogue = Dialogue(Backend(), "Persona réelle de Jade")
        reply = await dialogue.respond(self.incoming())
        self.assertEqual(reply.intent, "excited")
        self.assertEqual(reply.text, "Oh ! J'ai une idée !")
        self.assertEqual(dialogue.history[self.incoming().session][-1]["content"], reply.text)
        self.assertIn("Persona réelle de Jade", captured[0]["content"])
        self.assertIn("[INTENT:label]", captured[0]["content"])

    async def test_stream_sends_only_clean_sentences_after_metadata_is_ready(self):
        captured = []
        announced = []
        class Backend:
            async def complete_stream(self, messages):
                for piece in ("[IN", "TENT:pla", "yful]", " Coucou ! ",
                              "Encore une idée ?"):
                    yield piece
        dialogue = Dialogue(Backend(), "Jade")
        reply = await dialogue.respond(
            self.incoming(), on_sentence=lambda s: self._emit(captured, s),
            on_intent=announced.append)
        self.assertEqual(reply.intent, "playful")
        self.assertEqual(reply.text, "Coucou ! Encore une idée ?")
        self.assertEqual(" ".join(captured).strip(), "Coucou ! Encore une idée ?")
        self.assertEqual(announced, ["playful"])
        self.assertFalse(any("INTENT" in s for s in captured))
        self.assertEqual(dialogue.history[self.incoming().session][-1]["content"], reply.text)

    @staticmethod
    async def _emit(target, sentence):
        target.append(sentence)

    async def test_stream_with_malformed_tag_never_commits_or_speaks(self):
        callback = []
        class Backend:
            async def complete_stream(self, messages):
                yield "[INTENT:playful"
        dialogue = Dialogue(Backend(), "Jade")
        with self.assertRaises(ValueError):
            await dialogue.respond(self.incoming(),
                                   on_sentence=lambda s: self._emit(callback, s))
        self.assertEqual(callback, [])
        self.assertEqual(len(dialogue.history[self.incoming().session]), 0)

    async def test_reply_metadata_not_part_of_text(self):
        reply = Reply(self.incoming(), "Salut.", intent="tender")
        self.assertEqual(reply.text, "Salut.")
        self.assertEqual(reply.intent, "tender")
        with self.assertRaises(ValueError):
            Reply(self.incoming(), "Salut.", intent="unknown")


class IntentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_realtime_adapter_receives_non_neutral_intent_once(self):
        client = object()
        with patch("src.jade_runtime.openai_services.RealtimeTTS") as adapter:
            adapter.return_value.synthesize = AsyncMock(
                return_value=SimpleNamespace(audio=b"RIFFfake", transcript="Salut."))
            service = OpenAIServices(Settings(), client=client)
            spoken = await service.synthesize_speech("Salut.", intent="playful")
            self.assertEqual(spoken.transcript, "Salut.")
            self.assertEqual(adapter.call_args.kwargs["intent"], "playful")
            adapter.return_value.synthesize.assert_awaited_once_with("Salut.")

    async def test_realtime_stream_adapter_receives_same_intent(self):
        with patch("src.jade_runtime.openai_services.RealtimeTTS") as adapter:
            service = OpenAIServices(Settings(), client=object())
            service.stream_speech_pcm("Salut.", intent="tender")
            self.assertEqual(adapter.call_args.kwargs["intent"], "tender")
            adapter.return_value.stream_pcm.assert_called_once_with("Salut.")


if __name__ == "__main__":
    unittest.main()
