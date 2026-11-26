"""RTE-12: delivery diagnostics are passive, optional and isolated from I/O.

No Discord connection, audio device, model or paid service is used.
"""
import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.jade_runtime.discord_voice import DiscordVoiceBridge
from src.jade_runtime.messages import Incoming
from src.jade_runtime.output import AudioOutput
from src.jade_runtime.session_logging import bind_turn, reset_turn
from src.jade_runtime.turn_logging import observe_delivery, record_delivery


class DeliveryObserverTests(unittest.TestCase):
    def test_structured_event_is_correlated_without_private_content(self):
        source = Incoming("discord", "Nom privé", "Texte confidentiel",
                          channel="confidential-room", message_id="secret-message")
        token = bind_turn(17, source)
        try:
            with patch("src.jade_runtime.turn_logging.summary") as concise, \
                 patch("src.jade_runtime.turn_logging.event") as detailed:
                self.assertIsNone(observe_delivery(
                    "transport_accepted", "discord_text", proof="discord_api"))
        finally:
            reset_turn(token)
        self.assertEqual(concise.call_count, 1)
        self.assertEqual(detailed.call_count, 1)
        for call in (concise.call_args, detailed.call_args):
            self.assertEqual(call.args, ("delivery_evidence",))
            self.assertEqual(call.kwargs, {
                "turn": 17,
                "destination": "discord_text",
                "delivery_stage": "transport_accepted",
                "evidence": "discord_api",
            })
            data = str(call)
            for secret in ("Nom privé", "Texte confidentiel",
                           "confidential-room", "secret-message"):
                self.assertNotIn(secret, data)

    def test_uncorrelated_and_unsupported_proofs_are_silently_discarded(self):
        with patch("src.jade_runtime.turn_logging.summary") as concise, \
             patch("src.jade_runtime.turn_logging.event") as detailed:
            observe_delivery("transport_accepted", "discord_text", proof="discord_api")
            token = bind_turn(23, Incoming("mobile", "Owner", "private"))
            try:
                observe_delivery("transport_accepted", "mobile_text", proof="discord_api")
                observe_delivery("playback_completed", "discord_voice", proof="ffplay_exit_zero")
                observe_delivery("transport_accepted", "discord_text", proof="incorrect")
            finally:
                reset_turn(token)
        concise.assert_not_called()
        detailed.assert_not_called()

    def test_log_sinks_fail_independently_and_can_never_break_output(self):
        token = bind_turn(24, Incoming("discord", "A", "b"))
        try:
            with patch("src.jade_runtime.turn_logging.summary",
                       side_effect=OSError("disk unavailable")), \
                 patch("src.jade_runtime.turn_logging.event") as detailed:
                self.assertIsNone(observe_delivery(
                    "playback_completed", "discord_voice",
                    proof="discord_audio_consumer"))
                record_delivery(24, "handoff_completed", destinations=("discord_voice",))
            self.assertEqual(detailed.call_count, 2)

            with patch("src.jade_runtime.turn_logging.summary",
                       side_effect=RuntimeError("bad console handler")), \
                 patch("src.jade_runtime.turn_logging.event",
                       side_effect=OSError("full disk")):
                self.assertIsNone(observe_delivery(
                    "transport_accepted", "discord_text", proof="discord_api"))
                self.assertIsNone(record_delivery(
                    24, "handoff_completed", destinations=("discord_text",)))
        finally:
            reset_turn(token)


class AudioObserverTests(unittest.IsolatedAsyncioTestCase):
    async def test_ffplay_success_only_and_original_none_return(self):
        for code in (0, 1):
            class Process:
                returncode = code
                async def wait(self):
                    return code

            async def fake_spawn(*args, **kwargs):
                return Process()

            audio = AudioOutput("ffplay")
            with self.subTest(code=code), \
                 patch("src.jade_runtime.output.asyncio.create_subprocess_exec",
                       side_effect=fake_spawn), \
                 patch("src.jade_runtime.output.observe_delivery") as observed:
                if code == 0:
                    self.assertIsNone(await audio.play(b"synthetic wav"))
                    observed.assert_called_once_with(
                        "playback_completed", "local_audio",
                        proof="ffplay_exit_zero")
                else:
                    with self.assertRaisesRegex(RuntimeError, "ffplay could not play"):
                        await audio.play(b"synthetic wav")
                    observed.assert_not_called()

    async def test_disabled_audio_never_claims_a_playback(self):
        with patch("src.jade_runtime.output.observe_delivery") as observed:
            self.assertIsNone(await AudioOutput("none").play(b"synthetic wav"))
        observed.assert_not_called()


class DiscordPlaybackObserverTests(unittest.TestCase):
    def test_acknowledged_playback_only_preserves_existing_return(self):
        source = SimpleNamespace(voice_session_id="session-1", speaker_id=42,
                                 message_id="message-1")
        bridge = SimpleNamespace(
            reply_authorized=lambda incoming: True,
            buffers_lock=threading.Lock(), session_id="session-1",
            _turn_ids={"message-1": ("session-1", 42, "t-1")},
            _decider=SimpleNamespace(mark_replied=Mock(return_value=True)),
        )
        with patch("src.jade_runtime.discord_voice.observe_delivery") as observed:
            self.assertIs(
                DiscordVoiceBridge.mark_voice_reply_played(bridge, source), True)
            observed.assert_called_once_with(
                "playback_completed", "discord_voice",
                proof="discord_audio_consumer")
            self.assertIs(
                DiscordVoiceBridge.mark_voice_reply_played(bridge, source), False)
            self.assertEqual(observed.call_count, 1)

    def test_session_rejection_never_observes_delivery(self):
        source = SimpleNamespace(voice_session_id="session-1", speaker_id=42,
                                 message_id="message-1")
        bridge = SimpleNamespace(reply_authorized=lambda incoming: False)
        with patch("src.jade_runtime.discord_voice.observe_delivery") as observed:
            self.assertIs(
                DiscordVoiceBridge.mark_voice_reply_played(bridge, source), False)
            observed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
