"""Offline regression tests for cross-media Discord history, no Discord login."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import unittest

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.discord_conversation import conversation_id
from src.jade_runtime.discord_voice import OpenVoiceBridge
from src.jade_runtime.messages import Incoming


class Backend:
    def __init__(self):
        self.prompts = []

    async def complete(self, messages):
        self.prompts.append(messages)
        return "[INTENT:neutral] C'est compris."


class Conversations(unittest.IsolatedAsyncioTestCase):
    async def test_text_and_voice_share_only_explicit_active_key(self):
        key = conversation_id(101, 202, "a" * 32, 303)
        backend = Backend()
        dialogue = Dialogue(backend, "Jade est une assistante.")
        voice = Incoming("discord_voice", "Alice", "Parlons du roman.",
                         channel="202", force_reply=True,
                         voice_session_id="a" * 32, speaker_id=303,
                         message_id="voice-1", conversation_id=key)
        text = Incoming("discord", "Alice", "Le héros s'appelle Akira.",
                        channel="202", force_reply=True, account_id="303",
                        message_id="text-1", conversation_id=key)
        again = replace(voice, text="Son évolution ?", message_id="voice-2")
        await dialogue.respond(voice)
        await dialogue.respond(text)
        await dialogue.respond(again)
        visible = str(backend.prompts[-1])
        self.assertIn("Akira", visible)
        self.assertIn("Parlons du roman", visible)
        self.assertEqual(voice.session, ("discord_voice", "202:" + "a" * 32))
        self.assertEqual(voice.history_key, text.history_key)

    async def test_passive_related_text_survives_until_voice_reply(self):
        key = conversation_id(101, 202, "a" * 32, 303)
        backend = Backend()
        dialogue = Dialogue(backend, "Jade est une assistante.")
        note = Incoming("discord", "Alice", "Le titre sera Lumière.",
                        channel="202", account_id="303",
                        message_id="passive-1", conversation_id=key)
        self.assertTrue(await dialogue.observe_linked_text(note))
        self.assertFalse(await dialogue.observe_linked_text(note))
        self.assertEqual(len(backend.prompts), 0)
        voice = Incoming("discord_voice", "Alice", "Quel titre ?",
                         channel="202", speaker_id=303, voice_session_id="a" * 32,
                         force_reply=True, conversation_id=key, message_id="voice-1")
        await dialogue.respond(voice)
        self.assertIn("Lumière", str(backend.prompts[-1]))

    async def test_isolation_different_person_session_channel_and_dm(self):
        base = conversation_id(101, 202, "a" * 32, 303)
        for other in (conversation_id(101, 202, "a" * 32, 304),
                      conversation_id(101, 202, "b" * 32, 303),
                      conversation_id(101, 999, "a" * 32, 303),
                      conversation_id(999, 202, "a" * 32, 303)):
            self.assertNotEqual(base, other)
        backend = Backend()
        dialogue = Dialogue(backend, "Jade est une assistante.")
        await dialogue.respond(Incoming("discord_voice", "Alice", "Code Aurore.",
                  channel="202", voice_session_id="a"*32, speaker_id=303,
                  force_reply=True, conversation_id=base))
        await dialogue.respond(Incoming("discord", "Alice", "Bonjour en DM.",
                  channel="987", account_id="303", force_reply=True))
        self.assertNotIn("Code Aurore", str(backend.prompts[-1]))

    async def test_bridge_binds_only_authenticated_voice_members_and_native_chat(self):
        voice_channel = SimpleNamespace(id=202, guild=SimpleNamespace(id=101),
            members=[SimpleNamespace(id=303, bot=False)])
        bridge = OpenVoiceBridge(None, None, 202)
        bridge.connection = SimpleNamespace(channel=voice_channel)
        bridge.own_bot_id = 999
        bridge.session_id = "a" * 32
        bridge.consent_confirmed = True
        expected = bridge.voice_conversation_id(303, "a" * 32)
        self.assertEqual(expected, bridge.linked_text_conversation_id(101, 202, 303))
        self.assertIsNone(bridge.linked_text_conversation_id(101, 999, 303))
        self.assertIsNone(bridge.linked_text_conversation_id(101, 202, 304))
        self.assertIsNone(bridge.linked_text_conversation_id(102, 202, 303))
        self.assertIsNone(bridge.linked_text_conversation_id(101, 202, 999))
        bridge.session_id = "b" * 32
        self.assertNotEqual(expected, bridge.linked_text_conversation_id(101, 202, 303))
        bridge.session_id = None
        self.assertIsNone(bridge.linked_text_conversation_id(101, 202, 303))

    async def test_input_rejects_forged_or_malformed_key(self):
        with self.assertRaises(ValueError):
            Incoming("discord", "Alice", "Test", conversation_id="some-other-key")
        with self.assertRaises(ValueError):
            Incoming("twitch", "Alice", "Test", conversation_id="dc-" + "a"*32)
        self.assertIsNone(conversation_id("abc", 202, "a"*32, 303))


if __name__ == "__main__":
    unittest.main()
