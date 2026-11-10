"""Voice session identity must not leak into other channels or representations."""
import unittest
from unittest.mock import AsyncMock

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.config import Settings, _voice_users


class VoiceSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_voice_session_does_not_reuse_previous_history(self):
        backend = type("Backend", (), {})()
        backend.complete = AsyncMock(return_value="réponse")
        dialogue = Dialogue(backend, "personnage")
        first = Incoming("discord_voice", "user", "bonjour", channel="42",
                         force_reply=True, speaker_id=1, voice_session_id="a" * 32)
        second = Incoming("discord_voice", "user", "ensuite", channel="42",
                          force_reply=True, speaker_id=1, voice_session_id="b" * 32)
        await dialogue.respond(first)
        await dialogue.respond(second)
        self.assertNotEqual(first.session, second.session)
        self.assertEqual(len(backend.complete.await_args_list[1].args[0]), 2)
        self.assertNotIn("speaker_id", repr(first))
        self.assertNotIn("voice_session_id", repr(first))

    def test_other_transports_keep_existing_session_key(self):
        self.assertEqual(Incoming("twitch", "user", "hi", channel="chat").session,
                         ("twitch", "chat"))
        with self.assertRaises(ValueError):
            Incoming("discord_voice", "user", "hi", speaker_id=True)
        with self.assertRaises(ValueError):
            Incoming("twitch", "user", "hi", voice_session_id="a" * 32)

    def test_obsolete_participation_fields_do_not_gate_voice(self):
        common = dict(discord_enabled=True, discord_token="test",
                      discord_voice_enabled=True, discord_voice_channel=1)
        for values in ({}, {"discord_voice_consent": True},
                       {"discord_voice_allowed_users": (123,)},
                       {"discord_voice_consent": False, "discord_voice_allowed_users": ()}):
            Settings(**common, **values).validate()
        settings = Settings(**common, discord_voice_consent=True,
                            discord_voice_allowed_users=(123,))
        settings.validate()
        self.assertNotIn("discord_voice_allowed_users", repr(settings))
        self.assertEqual(_voice_users("1, 2"), (1, 2))
        for invalid in ("1,1", "-1", "0", "1,,2"):
            with self.assertRaises(ValueError):
                _voice_users(invalid)

    def test_loading_ignores_even_malformed_legacy_discord_values(self):
        from unittest.mock import patch
        values = {"JADE_DISCORD_ENABLED": "bad", "JADE_DISCORD_SEND": "bad",
                  "JADE_DISCORD_VOICE_ENABLED": "bad", "JADE_DISCORD_VOICE_BROADCAST": "bad",
                  "JADE_DISCORD_VOICE_CONSENT": "bad", "JADE_DISCORD_VOICE_ALLOWED_USERS": "not-a-list"}
        with patch("src.jade_runtime.config.environ", side_effect=lambda name, default: values.get(name, default)):
            Settings.load().validate()


if __name__ == "__main__":
    unittest.main()
