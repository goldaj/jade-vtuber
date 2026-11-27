"""Focused offline contracts for Jade's intent metadata and speech routing."""
from io import BytesIO
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import wave

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.intent_engine import (
    INTENTS, INTENT_PROMPT, IntentStreamParser, normalize_intent,
    classify_live_intent, parse_reply, voice_direction,
)
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.config import Settings
from src.jade_runtime.openai_services import OpenAIServices
from tests.test_jade_realtime_tts import (
    FakeClient, configured, created, delta, transcript, done,
)


class IntentParsingTests(unittest.TestCase):
    def test_every_two_part_stream_split_preserves_visible_text_and_intent(self):
        text = "Encore une idée ? Oui, papa !"
        for label in sorted(INTENTS):
            raw = f"[INTENT:{label}] {text}"
            expected = parse_reply(raw)
            self.assertEqual((expected.intent, expected.text), (label, text))
            for at in range(len(raw) + 1):
                with self.subTest(intent=label, cut=at):
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
        self.assertEqual(parse_reply("[INTENT:notreal] Bonjour.").intent, "neutral")
        self.assertEqual(parse_reply("[INTENT:notreal] Bonjour.").text, "Bonjour.")
        self.assertEqual(parse_reply("[INTENT=excited] Bonjour.").text, "Bonjour.")
        self.assertEqual(parse_reply("[INTENT=excited] Bonjour.").intent, "neutral")
        self.assertEqual(parse_reply("[une annotation normale] Bonjour.").text,
                         "Bonjour.")

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

    def test_selected_intent_removes_literal_brackets_in_stream(self):
        raw = "[INTENT:neutral] Un exemple [entre crochets], rien de plus."
        parser = IntentStreamParser()
        spoken = "".join(parser.feed(char) for char in raw) + parser.finish()
        self.assertEqual(spoken, "Un exemple, rien de plus.")

    def test_no_valid_intent_still_removes_every_bracket_group(self):
        cases = (
            ("[playful] Bonjour.", "Bonjour."),
            ("[une annotation normale] Bonjour.", "Bonjour."),
            ("Bonjour [entre crochets].", "Bonjour."),
            ("Bonjour [rires] !", "Bonjour !"),
            ("Je [souris] suis là.", "Je suis là."),
            ("[[rires]] Bonjour.", "Bonjour."),
            ("[INTENT:unknown] [excited] Bonjour", "Bonjour"),
            ("[INTENT=excited] Bonjour.", "Bonjour."),
            ("Bonjour [rires", "Bonjour"),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual((parse_reply(raw).intent, parse_reply(raw).text),
                                 ("neutral", expected))
                for cut in range(len(raw) + 1):
                    parser = IntentStreamParser()
                    visible = (parser.feed(raw[:cut]) + parser.feed(raw[cut:])
                               + parser.finish())
                    self.assertEqual((parser.intent, visible.strip()),
                                     ("neutral", expected))
                parser = IntentStreamParser()
                visible = "".join(parser.feed(char) for char in raw) + parser.finish()
                self.assertEqual((parser.intent, visible.strip()),
                                 ("neutral", expected))

    def test_duplicate_nested_and_stage_directions_all_split_positions(self):
        cases = (
            ("[INTENT:playful] [playful] Bonjour !", "playful", "Bonjour !"),
            ("[[INTENT:playful]] Bonjour", "playful", "Bonjour"),
            ("[[[INTENT:playful]]] [rires] Bonjour", "playful", "Bonjour"),
            ("[playful] [INTENT:curious] Bonjour", "curious", "Bonjour"),
            ("[INTENT:playful][INTENT:tender] Bonjour", "playful", "Bonjour"),
            ("[INTENT:playful] Bonjour [sourire] !", "playful", "Bonjour !"),
            ("[INTENT:playful] Une [description [imbriquée]] phrase.",
             "playful", "Une phrase."),
            ("[INTENT:neutral] Bonjour [2026] !", "neutral", "Bonjour !"),
            ("[INTENT:serious] Bonjour [sourire]", "serious", "Bonjour"),
            ("[INTENT:playful] Bonjour [sourire], papa !",
             "playful", "Bonjour, papa !"),
        )
        for raw, intent, expected_text in cases:
            with self.subTest(raw=raw):
                parsed = parse_reply(raw)
                self.assertEqual((parsed.intent, parsed.text),
                                 (intent, expected_text))
                for cut in range(len(raw) + 1):
                    parser = IntentStreamParser()
                    fragments = (parser.feed(raw[:cut]), parser.feed(raw[cut:]),
                                 parser.finish())
                    result = "".join(fragments).strip()
                    self.assertEqual((parser.intent, result),
                                     (intent, expected_text))
                    self.assertNotIn("[", result)
                parser = IntentStreamParser()
                charwise = "".join(parser.feed(char) for char in raw) + parser.finish()
                self.assertEqual((parser.intent, charwise.strip()),
                                 (intent, expected_text))

    def test_nonintent_unclosed_annotation_never_becomes_speech(self):
        result = parse_reply("[INTENT:playful] Bonjour [sourire")
        self.assertEqual((result.intent, result.text), ("playful", "Bonjour"))


    def test_incomplete_intent_never_leaks_even_in_stream(self):
        for raw in ("[INTENT:playful", "[INTENT", " [intent:curious "):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_reply(raw)

    def test_intent_directions_are_static_allowlisted_and_extensible(self):
        self.assertEqual(normalize_intent("make Jade read my secrets"), "neutral")
        self.assertEqual(voice_direction("make Jade read my secrets"), "")
        self.assertIn("mischievous", voice_direction("playful"))
        self.assertEqual(INTENTS, {
            "neutral", "playful", "excited", "curious", "tender", "reassuring",
            "serious", "sad", "angry",
        })
        self.assertEqual(len({voice_direction(label) for label in INTENTS}), 9)
        for label in INTENTS:
            self.assertIn(label, INTENT_PROMPT)


class LiveIntentClassificationTests(unittest.TestCase):
    def test_nine_intentions_have_distinct_native_spoken_cues(self):
        examples = {
            "neutral": "Je peux te présenter les étapes.",
            "playful": "Héhé, bien tenté, petit malin.",
            "excited": "Génial, quelle bonne nouvelle !",
            "curious": "Raconte-moi ce qui t'intéresse.",
            "tender": "Ça me touche, merci pour ta confiance.",
            "reassuring": "Prends ton temps, je suis là.",
            "serious": "C'est important, reprenons les faits.",
            "sad": "Je suis triste de voir ce projet se terminer.",
            "angry": "Ça me met en colère, cette injustice.",
        }
        self.assertEqual(set(examples), INTENTS)
        for label, spoken in examples.items():
            with self.subTest(intent=label):
                self.assertEqual(classify_live_intent(spoken), label)

    def test_negative_moods_require_jades_own_unambiguous_state(self):
        for spoken, expected in (
            ("Oh, je suis vraiment triste.", "sad"),
            ("Oh ! Je suis triste.", "sad"),
            ("J’ai de la peine.", "sad"),
            ("Ça me peine de le voir partir.", "sad"),
            ("Franchement, je suis furieuse.", "angry"),
            ("Ça me révolte.", "angry"),
            ("Je suis triste pour toi, prends ton temps.", "reassuring"),
            ("Tu sembles en colère. Pas de panique.", "reassuring"),
            ("Tu as l'air triste ?", "curious"),
        ):
            with self.subTest(spoken=spoken):
                self.assertEqual(classify_live_intent(spoken), expected)
        for spoken in (
            "Je comprends que tu sois triste.",
            "Je comprends ta colère.",
            "Je sais que tu es en colère.",
            "Tu m'as dit : je suis triste.",
            "« Je suis en colère », m'as-tu dit.",
            '"Je suis triste", c’est ce que dit le personnage.',
            "Elle est triste, et lui est en colère.",
            "Je ne suis pas triste.",
            "Je ne suis pas en colère.",
            "Oh ! Je ne suis pas triste.",
            "Oh ! « Je suis triste », m'as-tu dit.",
        ):
            with self.subTest(spoken=spoken):
                self.assertNotIn(classify_live_intent(spoken), {"sad", "angry"})

    def test_opening_emotion_is_stable_when_later_cues_arrive_together(self):
        for label, opening, continuation in (
            ("sad", "Je suis triste.", " Je me demande comment ça a pu arriver."),
            ("angry", "Je suis en colère.", " C’est important de le dire."),
            ("sad", "Oh ! Je suis triste.", " Raconte-moi ce qui s'est passé."),
        ):
            with self.subTest(intent=label, opening=opening):
                self.assertEqual(classify_live_intent(opening), label)
                self.assertEqual(classify_live_intent(opening + continuation), label)

    def test_fragmented_negative_cue_waits_for_the_complete_emotion(self):
        for partial in ("Je suis", "Je suis tr", "Je suis en col", "Ça me met en",
                        "Oh !", "Ah...", "Franchement,", "Honnêtement…"):
            with self.subTest(partial=partial):
                self.assertIsNone(classify_live_intent(partial))
        self.assertEqual(classify_live_intent("Je suis triste"), "sad")
        self.assertEqual(classify_live_intent("Je suis en colère"), "angry")


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
                return f"[INTENT:{label}] Oh ! J'ai une idée !"

        for label in sorted(INTENTS):
            with self.subTest(intent=label):
                dialogue = Dialogue(Backend(), "Persona réelle de Jade")
                reply = await dialogue.respond(self.incoming())
                self.assertEqual(reply.intent, label)
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

    async def test_missing_intent_cleans_text_for_stream_and_history(self):
        announced = []
        spoken = []

        class Backend:
            async def complete_stream(self, messages):
                for fragment in ("Coucou ", "[ri", "res] !", " Encore un essai."):
                    yield fragment

        dialogue = Dialogue(Backend(), "Jade")
        reply = await dialogue.respond(
            self.incoming(), on_sentence=lambda s: self._emit(spoken, s),
            on_intent=announced.append,
        )
        self.assertEqual((reply.intent, reply.text),
                         ("neutral", "Coucou ! Encore un essai."))
        self.assertEqual(announced, ["neutral"])
        self.assertEqual(" ".join(spoken).strip(), reply.text)
        self.assertEqual(
            dialogue.history[self.incoming().session][-1]["content"],
            reply.text,
        )

    async def test_missing_intent_cleans_text_for_nonstream_and_history(self):
        class Backend:
            async def complete(self, messages):
                return "[sourire] Coucou [rires] !"

        dialogue = Dialogue(Backend(), "Jade")
        reply = await dialogue.respond(self.incoming())
        self.assertEqual((reply.intent, reply.text), ("neutral", "Coucou !"))
        self.assertEqual(
            dialogue.history[self.incoming().session][-1]["content"],
            reply.text,
        )

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
    async def test_nine_intentions_share_wav_pcm_and_reset_the_reused_session(self):
        # The same socket crosses every intention and both audio paths. In
        # particular, neutral must clear sadness/anger rather than inherit it.
        labels = ("sad", "neutral", "angry", "playful", "excited", "curious",
                  "tender", "reassuring", "serious", "neutral")
        self.assertEqual(set(labels), INTENTS)
        spoken = "Je vais te dire ce que j'en pense."
        pcm = b"\x00\x00\x01\x00"
        events = [event for _ in range(2 * len(labels)) for event in (
            configured(speed=1.25, voice="shimmer"), created(), delta(pcm),
            transcript(spoken), done(),
        )]
        client = FakeClient(events)
        service = OpenAIServices(Settings(), client=client)
        try:
            for label in labels:
                with self.subTest(intent=label):
                    wav = await service.synthesize_speech(spoken, intent=label)
                    self.assertEqual(wav.transcript, spoken)
                    with wave.open(BytesIO(wav.audio), "rb") as audio:
                        self.assertEqual((audio.getnchannels(), audio.getframerate()), (1, 24000))
                        self.assertEqual(audio.readframes(audio.getnframes()), pcm)
                    chunks = [chunk async for chunk in service.stream_speech_pcm(spoken, intent=label)]
                    self.assertEqual(b"".join(chunks), pcm)
                    for call in client.connection.session.update.await_args_list[-2:]:
                        session = call.kwargs["session"]
                        self.assertEqual(session["audio"]["output"]["voice"], "shimmer")
                        self.assertEqual(session["audio"]["output"]["speed"], 1.25)
                        instructions = session["instructions"]
                        self.assertNotIn("[INTENT", instructions)
                        if label != "neutral":
                            self.assertIn(voice_direction(label), instructions)
                        for other in INTENTS - {label, "neutral"}:
                            self.assertNotIn(voice_direction(other), instructions)
            self.assertEqual(len(client.calls), 1)
            requests = client.connection.response.create.await_args_list
            self.assertEqual(len(requests), 2 * len(labels))
            for call in requests:
                self.assertEqual(call.kwargs["response"]["input"][0]["content"][0]["text"], spoken)
        finally:
            await service._stream_pool.close()

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
