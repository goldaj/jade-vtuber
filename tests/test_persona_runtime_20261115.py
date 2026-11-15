"""Regression checks for opt-in full transcript, new participation and Low/320.

No API, Discord, microphone or other external services are contacted.
"""
import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.discord_text_policy import DiscordTextPolicy
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming
from src.jade_runtime.voice_decision import ConversationTurnDecider


class _Random:
    def __init__(self, value=1.0):
        self.value = value

    def random(self):
        return self.value


class _Backend:
    async def complete(self, messages):
        return "[INTENT:neutral] Réponse de test."


class PersonaRuntimeTests(unittest.TestCase):
    def test_default_model_budget(self):
        settings = Settings()
        self.assertEqual(settings.model, "gpt-6-luna")
        self.assertEqual(settings.reasoning_effort, "low")
        self.assertEqual(settings.max_completion_tokens, 320)
        self.assertEqual(settings.max_history_messages, 48)
        self.assertAlmostEqual(settings.reply_probability, 0.30)

    def test_complete_transcript_is_opt_in_and_can_be_forgotten(self):
        with tempfile.TemporaryDirectory() as temp:
            store = MemoryStore(Path(temp) / "history.sqlite3")
            key = ("microphone", "goldaj")
            turn = dict(source_platform="microphone", message_id="mic-1",
                        user_content="Goldaj (microphone): Salut Jade, raconte notre journée.",
                        assistant_content="On a passé la journée à coder, et j'ai gagné.")
            self.assertFalse(store.append_conversation_turn(key, "person", **turn))
            self.assertEqual(store.recent_conversation_turns(key, "person"), [])
            store.enable(key)
            self.assertTrue(store.append_conversation_turn(key, "person", **turn))
            self.assertFalse(store.append_conversation_turn(key, "person", **turn))
            turns = store.recent_conversation_turns(key, "person")
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["content"], turn["user_content"])
            self.assertEqual(turns[1]["content"], turn["assistant_content"])
            store.forget(key)
            self.assertEqual(store.recent_conversation_turns(key, "person"), [])

    def test_restored_history_keeps_full_messages(self):
        previous = [
            {"role": "user", "content": "Goldaj (microphone): Les détails comptent vraiment."},
            {"role": "assistant", "content": "Alors je les garderai."},
        ]
        chat = Dialogue(_Backend(), "Tu es Jade.", max_messages=48)
        incoming = Incoming("microphone", "Goldaj", "Bonjour.", force_reply=True)
        answer = asyncio.run(chat.respond(incoming, history_messages=previous))
        self.assertEqual(answer.text, "Réponse de test.")
        self.assertEqual(list(chat.history[incoming.history_key])[:2], previous)

    def test_discord_text_solo_responses_and_group_sampling(self):
        policy = DiscordTextPolicy(rng=_Random(1.0), auto_rate=0.30)
        def observe(uid, mid):
            incoming = Incoming("discord", f"User{uid}", "Une intervention intéressante",
                                channel="42", message_id=str(mid), account_id=str(uid))
            member = SimpleNamespace(id=uid, bot=False)
            message = SimpleNamespace(author=member, mentions=[], guild=object(),
                                      reference=None)
            return policy.observe(message, incoming, own_user_id=999)
        first = observe(101, 1)
        self.assertIsNotNone(first)
        self.assertTrue(first.force_reply)
        self.assertIsNone(observe(102, 2))  # More than one current participant.
        policy.rng.value = 0.0
        self.assertIsNotNone(observe(101, 3))

    def test_voice_solo_vs_group_uses_provided_rate(self):
        r = _Random(1.0)
        decider = ConversationTurnDecider(group_reply_probability=0.30, rng=r)
        kwargs = dict(authorized=True, consent_confirmed=True)
        self.assertTrue(decider.decide("1234567890abcdef", 10, "bonjour",
                                        participant_count=1, **kwargs).should_reply)
        self.assertFalse(decider.decide("1234567890abcdef", 20, "bonjour",
                                         participant_count=2, **kwargs).should_reply)
        r.value = 0.0
        self.assertTrue(decider.decide("1234567890abcdef", 20, "bonjour",
                                        participant_count=2, **kwargs).should_reply)


if __name__ == "__main__":
    unittest.main()
