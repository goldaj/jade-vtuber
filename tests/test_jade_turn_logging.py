"""Offline tests for selected incoming text, response intent and output modality."""
import asyncio
import json
import logging
import unittest
from unittest.mock import AsyncMock, patch

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.turn_logging import (
    planned_destinations, record_input, record_reply, record_delivery_evidence,
    enable_console_logs,
)


def records(captured):
    return [json.loads(record.message) for record in captured.records]


class TurnLoggingTests(unittest.TestCase):
    def setUp(self):
        # Session logging is process-global; standalone logger tests must not
        # depend on which other test first initialized the session file.
        scope = patch("src.jade_runtime.turn_logging.session_file", return_value=None)
        scope.start()
        self.addCleanup(scope.stop)

    def test_optional_latency_logger_is_configurable_and_private(self):
        with patch("src.jade_runtime.config.environ",
                   side_effect=lambda name, default: "1" if name == "JADE_LATENCY_LOG"
                   else default):
            settings = Settings.load()
        self.assertTrue(settings.latency_logging)
        logger = logging.getLogger("jade.latency")
        previous_level = logger.level
        previous_handlers = list(logger.handlers)
        previous_propagate = logger.propagate
        try:
            enable_console_logs(enable_latency=settings.latency_logging)
            self.assertTrue(logger.isEnabledFor(logging.INFO))
            self.assertFalse(logger.propagate)
        finally:
            logger.handlers[:] = previous_handlers
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
        with self.assertRaises(ValueError):
            Settings(latency_logging="true").validate()


    def test_input_platform_modality_and_single_record(self):
        sources = (
            ("twitch", "text"), ("discord", "text"),
            ("discord_voice", "voice"), ("microphone", "voice"),
            ("local_http", "text"), ("console", "text"),
        )
        for platform, modality in sources:
            with self.subTest(platform=platform), self.assertLogs(
                    "jade.conversation", level="INFO") as captured:
                record_input(42, Incoming(platform, "Éloïse", "Salut\nJade",
                                          channel="room", message_id="123", force_reply=True))
            self.assertEqual(len(captured.records), 1)
            item = records(captured)[0]
            self.assertEqual(item["source_platform"], platform)
            self.assertEqual(item["source_modality"], modality)
            if platform in ("microphone", "local_http"):
                self.assertEqual(item["source_author"], "[privé]")
                self.assertEqual(item["input_text"], "[contenu privé masqué]")
            else:
                self.assertEqual(item["source_author"], "Éloïse")
                self.assertEqual(item["input_text"], "Salut\nJade")
            self.assertNotIn("\n", captured.records[0].message)

    def test_link_confirmation_code_is_masked_in_structured_input_logs(self):
        code = "v1.twitch.6001.oneTimeSecretNotForLogs1234567890"
        incoming = Incoming("twitch", "Alice", "!jade-memoire   CoNfIrMeR " + code,
                            channel="public", account_id="6001")
        with self.assertLogs("jade.conversation", level="INFO") as captured:
            record_input(7, incoming)
        self.assertNotIn(code, captured.records[0].message)
        self.assertEqual(records(captured)[0]["input_text"],
                         "!jade-memoire confirmer [code masqué]")

    def test_reply_canonical_intent_and_multimodal_output(self):
        reply = Reply(Incoming("discord", "Alice", "Jade ?"), "Bonjour !", intent="playful")
        targets = planned_destinations(reply, has_speech=True, audio_output="ffplay",
                                       discord_text=True)
        with self.assertLogs("jade.conversation", level="INFO") as captured:
            record_reply(42, reply, targets)
        item = records(captured)[0]
        self.assertEqual(item["event"], "reply_planned")
        self.assertEqual(item["reply_with_intent"], "[INTENT:playful] Bonjour !")
        self.assertEqual(item["intent"], "playful")
        self.assertEqual(item["output_modalities"], ["text"])
        self.assertEqual(item["output_destinations"], ["discord_text"])
        self.assertEqual(item["delivery_status"], "planned_not_confirmed")
        self.assertEqual(reply.text, "Bonjour !")

    def test_evidence_is_explicit_and_cannot_be_forged_by_other_destinations(self):
        with patch("src.jade_runtime.turn_logging.summary") as summary, \
             patch("src.jade_runtime.turn_logging.event") as event:
            record_delivery_evidence(12, "transport_accepted", "discord_text",
                                     proof="discord_api")
            record_delivery_evidence(12, "playback_completed", "discord_voice",
                                     proof="discord_audio_consumer")
        self.assertEqual(summary.call_count, 2)
        self.assertEqual(event.call_count, 2)
        first = event.call_args_list[0]
        self.assertEqual(first.args[0], "delivery_evidence")
        self.assertEqual(first.kwargs["turn"], 12)
        self.assertEqual(first.kwargs["destination"], "discord_text")
        self.assertEqual(first.kwargs["delivery_stage"], "transport_accepted")
        self.assertNotIn("text", first.kwargs)
        for stage, destination, proof in (
            ("transport_accepted", "mobile_text", "discord_api"),
            ("playback_completed", "discord_voice", "twitch_irc"),
            ("playback_completed", "local_audio", "discord_api"),
        ):
            with self.subTest(stage=stage, destination=destination), self.assertRaises(ValueError):
                record_delivery_evidence(12, stage, destination, proof=proof)

    def test_private_dialogues_never_log_text_or_transport_identifiers(self):
        samples = [
            Incoming("discord", "Alice secrète", "Conversation privée confidentielle",
                     channel="unique-dm", message_id="private-123",
                     account_id="321", private_channel=True),
            Incoming("mobile", "Goldaj", "Un secret personnel",
                     channel="private-mobile", message_id="mobile-123"),
        ]
        for source in samples:
            with self.subTest(platform=source.platform), self.assertLogs(
                    "jade.conversation", level="INFO") as captured:
                record_input(9, source)
                record_reply(9, Reply(source, "Un contenu privé en réponse"),
                             ("discord_text",))
            emitted = "\n".join(rec.message for rec in captured.records)
            for secret in (source.text, source.author, source.channel,
                           source.message_id, "Un contenu privé en réponse"):
                self.assertNotIn(secret, emitted)
            self.assertIn("[contenu privé masqué]", emitted)

    def test_written_channels_never_plan_tts_with_all_voice_outputs_enabled(self):
        for platform, text_flag in (("discord", "discord_text"),
                                    ("twitch", "twitch_text"),
                                    ("local_http", "local_http")):
            with self.subTest(platform=platform):
                reply = Reply(Incoming(platform, "Auteur", "Jade ?"), "Réponse")
                options = dict(has_speech=True, audio_output="ffplay",
                               discord_voice=True, **{text_flag: True})
                self.assertEqual(planned_destinations(reply, **options),
                                 ({"discord": "discord_text", "twitch": "twitch_text",
                                   "local_http": "local_http_text"}[platform],))

    def test_destination_matrix_and_streamed_voice(self):
        cases = (
            ("twitch", {"twitch_text": True}, ("twitch_text",)),
            ("discord", {"discord_text": True}, ("discord_text",)),
            ("discord_voice", {"has_speech": True, "discord_voice": True}, ("discord_voice",)),
            ("microphone", {"has_speech": True, "audio_output": "ffplay"}, ("local_audio",)),
            ("local_http", {"local_http": True}, ("local_http_text",)),
            ("console", {}, ("console_text",)),
        )
        for platform, kwargs, expected in cases:
            with self.subTest(platform=platform):
                reply = Reply(Incoming(platform, "tester", "Jade", force_reply=True), "OK")
                self.assertEqual(planned_destinations(reply, **kwargs), expected)
        streamed = Reply(Incoming("discord_voice", "tester", "Jade", force_reply=True),
                         "OK", spoken=True)
        self.assertEqual(planned_destinations(
            streamed, has_speech=True, audio_output="ffplay", discord_voice=True),
            ("discord_voice",))


class RuntimeTimingTests(unittest.IsolatedAsyncioTestCase):
    async def test_timing_stages_cover_all_entry_channels_without_private_text(self):
        for platform in ("discord", "twitch", "discord_voice",
                         "microphone", "local_http", "mobile", "console"):
            with self.subTest(platform=platform):
                backend = AsyncMock()
                backend.complete.return_value = "[INTENT:neutral] Réponse publique"
                runtime = Runtime(Dialogue(backend, "Jade"), AsyncMock())
                with self.assertLogs("jade.latency", level="INFO") as captured:
                    await runtime.start()
                    await runtime.submit(Incoming(
                        platform, "Nom confidentiel", "Question secrète Jade",
                        force_reply=True))
                    await asyncio.wait_for(runtime.idle(), 2)
                    await runtime.stop()
                events = [record.message for record in captured.records]
                stages = {item.split("stage=", 1)[1].split(" ", 1)[0]
                          for item in events}
                self.assertTrue({"queue_start", "llm_start", "llm_end",
                                 "delivery_start", "delivery_end",
                                 "turn_complete"}.issubset(stages))
                self.assertTrue(all("platform=" + platform in item for item in events))
                self.assertTrue(all("since_queue_ms=" in item for item in events))
                self.assertFalse(any("secrète" in item or "confidentiel" in item
                                     for item in events))


class RuntimeTurnLoggingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        scope = patch("src.jade_runtime.turn_logging.session_file", return_value=None)
        scope.start()
        self.addCleanup(scope.stop)

    async def test_correlated_input_and_reply_with_intent_not_delivered(self):
        backend = AsyncMock()
        backend.complete.return_value = "[INTENT:curious] Intéressant !"
        sent = []
        async def output(reply):
            sent.append(reply.text)

        runtime = Runtime(Dialogue(backend, "Jade"), output,
                          delivery_plan=lambda reply: ("discord_text",))
        with self.assertLogs("jade.conversation", level="INFO") as captured:
            await runtime.start()
            await runtime.submit(Incoming("discord", "Alice", "Jade, bonjour",
                                          "channel", "message", True))
            await asyncio.wait_for(runtime.idle(), 2)
            await runtime.stop()
        events = records(captured)
        self.assertEqual([item["event"] for item in events],
                         ["input_selected", "reply_planned"])
        self.assertEqual(events[0]["turn"], events[1]["turn"])
        self.assertEqual(events[0]["source_modality"], "text")
        self.assertEqual(events[1]["reply_with_intent"],
                         "[INTENT:curious] Intéressant !")
        self.assertEqual(sent, ["Intéressant !"])


    async def test_intent_contract_and_logs_apply_to_every_entry_platform(self):
        """No special-case Discord rule: one Dialogue contract for every source."""
        for platform in ("twitch", "discord", "discord_voice", "microphone",
                         "local_http", "console"):
            with self.subTest(platform=platform):
                model_messages = []
                delivered = []

                class Backend:
                    async def complete(self, messages):
                        model_messages.append(messages)
                        return "[INTENT:serious] Une réponse vérifiée."

                async def on_reply(reply):
                    delivered.append(reply)

                runtime = Runtime(Dialogue(Backend(), "Jade"), on_reply,
                                  delivery_plan=lambda reply: ("console_text",))
                with self.assertLogs("jade.conversation", level="INFO") as captured:
                    await runtime.start()
                    await runtime.submit(Incoming(
                        platform, "Auteur", "Bonjour Jade", channel="test",
                        message_id="fixture", force_reply=True))
                    await asyncio.wait_for(runtime.idle(), 2)
                    await runtime.stop()
                events = records(captured)
                self.assertEqual([event["event"] for event in events],
                                 ["input_selected", "reply_planned"])
                self.assertEqual(events[0]["source_platform"], platform)
                self.assertEqual(events[0]["turn"], events[1]["turn"])
                self.assertIn("[INTENT:label]", model_messages[0][0]["content"])
                self.assertEqual(delivered[0].intent, "serious")
                self.assertEqual(delivered[0].text, "Une réponse vérifiée.")
                expected = ("[contenu privé masqué]"
                            if platform in ("microphone", "local_http")
                            else "[INTENT:serious] Une réponse vérifiée.")
                self.assertEqual(events[1]["reply_with_intent"], expected)
                self.assertEqual(events[1]["intent"], "serious")
                self.assertNotIn("[INTENT:", delivered[0].text)

    async def test_missing_intent_tag_gets_neutral_metadata_even_for_twitch(self):
        """Providers can violate the prompt; public text stays clean and logs complete."""
        backend = AsyncMock()
        backend.complete.return_value = "Réponse sans balise."
        delivered = []
        async def output(reply):
            delivered.append(reply)
        runtime = Runtime(Dialogue(backend, "Jade"), output,
                          delivery_plan=lambda reply: ("twitch_text",))
        with self.assertLogs("jade.conversation", level="INFO") as captured:
            await runtime.start()
            await runtime.submit(Incoming(
                "twitch", "Auteur", "Bonjour Jade", "chat", "fixture", True))
            await asyncio.wait_for(runtime.idle(), 2)
            await runtime.stop()
        response = records(captured)[1]
        self.assertEqual(delivered[0].intent, "neutral")
        self.assertEqual(response["reply_with_intent"],
                         "[INTENT:neutral] Réponse sans balise.")
        self.assertEqual(response["output_destinations"], ["twitch_text"])
        self.assertEqual(delivered[0].text, "Réponse sans balise.")

    async def test_non_replied_message_has_no_planned_output(self):
        backend = AsyncMock()
        output = AsyncMock()
        runtime = Runtime(Dialogue(backend, "Jade", random_reply_rate=0), output)
        with self.assertLogs("jade.conversation", level="INFO") as captured:
            await runtime.start()
            await runtime.submit(Incoming("twitch", "Bob", "Salut", "chat", "x"))
            await asyncio.wait_for(runtime.idle(), 2)
            await runtime.stop()
        events = records(captured)
        self.assertEqual([item["event"] for item in events],
                         ["input_selected", "turn_outcome"])
        self.assertEqual(events[-1]["outcome"], "no_reply")
        backend.complete.assert_not_awaited()
        output.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
