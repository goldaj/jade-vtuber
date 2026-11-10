"""Deterministic offline checks: no OpenAI, Discord, Twitch, GPU or audio."""
import asyncio
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import AsyncMock

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.output import SpeechOutput, AudioOutput


class FakeChat:
    def __init__(self):
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return "Réponse à l'accent !"


class CoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_text_different_message_ids_not_discarded_and_unicode_kept(self):
        chat = FakeChat()
        dialogue = Dialogue(chat, "Vous êtes Jade", max_messages=4)
        source = dict(platform="twitch", author="éloïse", text="Bonjour Jade !")
        a = await dialogue.respond(Incoming(**source, message_id="1"))
        b = await dialogue.respond(Incoming(**source, message_id="2"))
        duplicate = await dialogue.respond(Incoming(**source, message_id="2"))
        self.assertEqual(a.text, "Réponse à l'accent !")
        self.assertEqual(b.text, "Réponse à l'accent !")
        self.assertIsNone(duplicate)
        self.assertEqual(len(chat.calls), 2)
        self.assertIn("éloïse", chat.calls[0][-1]["content"])
        self.assertLessEqual(len(dialogue.history[("twitch", "default")]), 4)

    async def test_channel_and_platform_history_isolation(self):
        fake = FakeChat()
        dialogue = Dialogue(fake, "Jade")
        await dialogue.respond(Incoming("twitch", "a", "Jade 1", channel="first"))
        await dialogue.respond(Incoming("discord", "a", "Jade 1", channel="first"))
        self.assertEqual(len(fake.calls[1]), 2)

    async def test_failure_does_not_commit_message_to_history(self):
        failing = AsyncMock()
        failing.complete.side_effect = [ValueError("provider down"), "OK"]
        dialogue = Dialogue(failing, "Jade")
        with self.assertRaises(ValueError):
            await dialogue.respond(Incoming("twitch", "a", "Salut Jade", message_id="abc"))
        self.assertEqual(len(dialogue.history[("twitch", "default")]), 0)
        self.assertEqual((await dialogue.respond(
            Incoming("twitch", "a", "Salut Jade", message_id="abc"))).text, "OK")

    async def test_runtime_processes_fifo_and_stops(self):
        observed = []
        dialogue = Dialogue(FakeChat(), "Jade")
        async def receive(reply):
            observed.append(reply.source.text)
        runner = Runtime(dialogue, receive, max_queue=3)
        await runner.start()
        await runner.submit(Incoming("console", "a", "Jade α"))
        await runner.submit(Incoming("console", "b", "Jade β"))
        await runner.idle()
        await runner.stop()
        self.assertEqual(observed, ["Jade α", "Jade β"])

    async def test_runtime_failure_isolated_without_content_logging(self):
        dialogue = Dialogue(FakeChat(), "Jade")
        async def broken(reply):
            raise RuntimeError("secret context")
        runner = Runtime(dialogue, broken)
        await runner.start()
        await runner.submit(Incoming("console", "a", "Jade test"))
        await runner.idle()
        await runner.stop()
        self.assertEqual(runner.errors, 1)

    async def test_openai_audio_uses_only_openai_models_and_stays_mocked(self):
        import types
        # Explicitly configured legacy models keep their old API contract.
        cfg = Settings(stt_model="gpt-4o-mini-transcribe", tts_model="gpt-4o-mini-tts")
        speech = AsyncMock()
        speech.content = b"RIFFmocked-data"
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=types.SimpleNamespace(
                create=AsyncMock(return_value=types.SimpleNamespace(
                    choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="Salut"))])))),
            audio=types.SimpleNamespace(
                transcriptions=types.SimpleNamespace(create=AsyncMock(
                    return_value=types.SimpleNamespace(text="Texte"))),
                speech=types.SimpleNamespace(create=AsyncMock(
                    return_value=types.SimpleNamespace(content=b"RIFFTEST")))))
        srv = OpenAIServices(cfg, client=client)
        self.assertEqual(await srv.complete([{"role": "user", "content": "a"}]), "Salut")
        self.assertEqual(await srv.transcribe_wav(b"RIFF" + b"0"*50), "Texte")
        self.assertEqual(await srv.synthesize_wav("Bonjour"), b"RIFFTEST")
        self.assertEqual(client.audio.transcriptions.create.call_args.kwargs["model"],
                         "gpt-4o-mini-transcribe")
        self.assertEqual(client.audio.speech.create.call_args.kwargs["model"],
                         "gpt-4o-mini-tts")

    async def test_subtitles_cleared_even_after_player_failure(self):
        from src.jade_runtime.messages import Reply
        with TemporaryDirectory() as folder:
            services = AsyncMock()
            services.synthesize_wav.return_value = b"RIFFTEST"
            player = AudioOutput("none")
            player.play = AsyncMock(side_effect=RuntimeError("missing player"))
            target = Path(folder) / "obs.txt"
            spoken = SpeechOutput(services, player, target)
            with self.assertRaises(RuntimeError):
                await spoken.speak(Reply(Incoming("console", "me", "Jade"), "Bonjour"))
            self.assertEqual(target.read_text(encoding="utf-8"), "")

    def test_credentials_and_permissions_fail_closed(self):
        with self.assertRaises(ValueError):
            Settings(twitch_enabled=True).validate()
        with self.assertRaises(ValueError):
            Settings(discord_enabled=True).validate()
        with self.assertRaises(ValueError):
            Settings().require_openai()


if __name__ == "__main__":
    unittest.main()
