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
from tests.test_demo_realtime_tts import (
    FakeClient, configured, created, delta, transcript, done,
)


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

    def test_second_tag_never_reaches_visible_or_spoken_text(self):
        raw = "[INTENT:playful] Salut ! [INTENT:tender] Bravo."
        wanted = parse_reply(raw)
        self.assertEqual(wanted.intent, "playful")
        self.assertNotIn("INTENT", wanted.text)
        for chunk_size in (1, 2, 3, 5, 11, 128):
            with self.subTest(chunk_size=chunk_size):
                parser = IntentStreamParser()
                fragments = [parser.feed(raw[i:i + chunk_size])
                             for i in range(0, len(raw), chunk_size)]
                fragments.append(parser.finish())
                self.assertEqual("".join(fragments), wanted.text)
                self.assertEqual(parser.intent, "playful")
                self.assertNotIn("INTENT", "".join(fragments))

    def test_second_tag_invalid_label_is_removed_without_changing_intent(self):
        raw = "[INTENT:serious] Voici [INTENT:notreal] la réponse."
        clean = parse_reply(raw)
        self.assertEqual(clean.intent, "serious")
        self.assertNotIn("INTENT", clean.text)
        self.assertIn("la réponse", clean.text)

    def test_later_incomplete_tag_fails_closed(self):
        for raw in ("Bonjour [INTENT:playful", "[INTENT:neutral] Oui. [INTENT:"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_reply(raw)

    def test_literal_brackets_are_preserved_in_stream(self):
        raw = "[INTENT:neutral] Un exemple [entre crochets], rien de plus."
        parser = IntentStreamParser()
        spoken = "".join(parser.feed(char) for char in raw) + parser.finish()
        self.assertEqual(spoken, "Un exemple [entre crochets], rien de plus.")

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

    async def test_actual_realtime_session_receives_static_mood_not_tag(self):
        client = FakeClient([configured(speed=1.25, voice="shimmer"), created(),
                             delta(), transcript(), done()])
        service = OpenAIServices(Settings(), client=client)
        result = await service.synthesize_speech("Bonjour Jade.", intent="playful")
        self.assertTrue(result.audio)
        session = client.connection.session.update.await_args.kwargs["session"]
        self.assertEqual(session["audio"]["output"]["voice"], "shimmer")
        self.assertEqual(session["audio"]["output"]["speed"], 1.25)
        self.assertIn("mischievous", session["instructions"])
        self.assertNotIn("[INTENT", session["instructions"])
        request = client.connection.response.create.await_args.kwargs["response"]
        self.assertEqual(request["input"][0]["content"][0]["text"], "Bonjour Jade.")
        self.assertEqual(client.connection.response.create.await_count, 1)

    async def test_pooled_realtime_session_updates_intention_without_reconnect(self):
        events = [
            configured(speed=1.25, voice="shimmer"), created(), delta(),
            transcript(), done(),
            configured(speed=1.25, voice="shimmer"), created(), delta(),
            transcript(), done(),
        ]
        client = FakeClient(events)
        service = OpenAIServices(Settings(), client=client)
        try:
            first = [chunk async for chunk in service.stream_speech_pcm(
                "Bonjour Jade.", intent="playful")]
            second = [chunk async for chunk in service.stream_speech_pcm(
                "Bonjour Jade.", intent="tender")]
            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 1)
            self.assertEqual(len(client.calls), 1)  # shared WebSocket
            self.assertEqual(client.connection.response.create.await_count, 2)
            sessions = [call.kwargs["session"]
                        for call in client.connection.session.update.await_args_list]
            self.assertEqual(len(sessions), 2)
            self.assertIn("mischievous", sessions[0]["instructions"])
            self.assertIn("slightly shy", sessions[1]["instructions"])
        finally:
            await service._stream_pool.close()

    async def test_realtime_stream_adapter_receives_same_intent(self):
        with patch("src.jade_runtime.openai_services.RealtimeTTS") as adapter:
            service = OpenAIServices(Settings(), client=object())
            service.stream_speech_pcm("Salut.", intent="tender")
            self.assertEqual(adapter.call_args.kwargs["intent"], "tender")
            adapter.return_value.stream_pcm.assert_called_once_with("Salut.")


if __name__ == "__main__":
    unittest.main()
