"""Discord direct messages must never be spoken into another voice channel."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.jade_runtime.discord_text import parse_discord_message
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.output import SpeechOutput
from src.jade_runtime.turn_logging import planned_destinations


class Speech:
    def __init__(self):
        self.calls = 0

    async def synthesize_wav(self, _text):
        self.calls += 1
        return b"synthetic-wav"


class Local:
    def __init__(self, mode="ffplay"):
        self.mode = mode
        self.delivered = []

    async def play(self, wav):
        self.delivered.append(wav)


class Voice:
    def __init__(self):
        self.context_queries = 0
        self.plays = []

    def delivery_context(self):
        self.context_queries += 1
        return self

    def delivery_context_valid(self, context):
        return context is self

    async def play_for_context(self, wav, context):
        self.plays.append(wav)
        return True


class DmVoicePrivacy(unittest.IsolatedAsyncioTestCase):
    async def test_discord_parser_distinguishes_dm_and_guild(self):
        def message(guild):
            return SimpleNamespace(
                author=SimpleNamespace(id=303, display_name="Alice"),
                channel=SimpleNamespace(id=404), id=505, content="Salut Jade",
                guild=guild)
        self.assertTrue(parse_discord_message(message(None)).private_channel)
        self.assertFalse(parse_discord_message(
            message(SimpleNamespace(id=100))).private_channel)

    async def test_dm_never_reaches_voice_bridge(self):
        with tempfile.TemporaryDirectory() as folder:
            services, local, bridge = Speech(), Local(), Voice()
            output = SpeechOutput(services, local, Path(folder)/"subtitle.txt",
                                  secondary_player=bridge)
            source = Incoming("discord", "Alice", "Message privé",
                              private_channel=True, channel="404")
            await output.speak(Reply(source, "Réponse privée"))
            self.assertEqual(local.delivered, [b"synthetic-wav"])
            self.assertEqual(bridge.context_queries, 0)
            self.assertEqual(bridge.plays, [])
            self.assertEqual(planned_destinations(
                Reply(source, "Réponse privée"), has_speech=True,
                audio_output="ffplay", discord_voice=True, discord_text=True),
                ("discord_text", "local_audio"))

    async def test_muted_local_audio_does_not_bill_dm_tts(self):
        with tempfile.TemporaryDirectory() as folder:
            services, local, bridge = Speech(), Local(mode="none"), Voice()
            output = SpeechOutput(services, local, Path(folder)/"subtitle.txt",
                                  secondary_player=bridge)
            source = Incoming("discord", "Alice", "Message privé",
                              private_channel=True)
            await output.speak(Reply(source, "Réponse privée"))
            self.assertEqual(services.calls, 0)
            self.assertEqual(bridge.context_queries, 0)
            self.assertEqual(local.delivered, [])


if __name__ == "__main__":
    unittest.main()
