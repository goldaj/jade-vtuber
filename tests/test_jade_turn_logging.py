"""Offline tests for selected incoming text, response intent and output modality."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.turn_logging import (
    planned_destinations, record_input, record_reply,
)


def records(captured):
    return [json.loads(record.message) for record in captured.records]


class TurnLoggingTests(unittest.TestCase):
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
            self.assertEqual(item["source_author"], "Éloïse")
            self.assertEqual(item["input_text"], "Salut\nJade")
            self.assertNotIn("\n", captured.records[0].message)

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
        self.assertEqual(item["output_modalities"], ["text", "voice"])
        self.assertEqual(item["output_destinations"], ["discord_text", "local_audio"])
        self.assertEqual(item["delivery_status"], "planned_not_confirmed")
        self.assertEqual(reply.text, "Bonjour !")

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


class RuntimeTurnLoggingTests(unittest.IsolatedAsyncioTestCase):
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
                self.assertEqual(events[1]["reply_with_intent"],
                                 "[INTENT:serious] Une réponse vérifiée.")
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
