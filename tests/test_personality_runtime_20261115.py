"""Focused offline checks for approved Jade personality runtime changes."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.discord_text_policy import DiscordTextPolicy
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming
from src.jade_runtime.openai_services import OpenAIServices
from src.jade_runtime.twitch_irc import TwitchIRC
from src.jade_runtime.voice_decision import ConversationTurnDecider


class _Backend:
    async def complete(self, messages):
        return "[INTENT:neutral] D'accord, mais je garde mon avis."


class _Random:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class _Completions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if not kwargs.get("stream"):
            return SimpleNamespace(choices=[
                SimpleNamespace(message=SimpleNamespace(content="Réponse"))
            ])

        async def chunks():
            yield SimpleNamespace(choices=[SimpleNamespace(
                index=0, finish_reason=None,
                delta=SimpleNamespace(content="[INTENT:neutral] Réponse"))])
            yield SimpleNamespace(choices=[SimpleNamespace(
                index=0, finish_reason="stop",
                delta=SimpleNamespace(content=None))])
        return chunks()


class TestJadeRuntime20261115(unittest.TestCase):
    def test_low_320_are_explicit_on_chat_and_stream(self):
        self.assertEqual(Settings().reasoning_effort, "low")
        self.assertEqual(Settings().max_completion_tokens, 320)
        backend = _Completions()
        services = object.__new__(OpenAIServices)
        services.settings = Settings()
        services.client = SimpleNamespace(
            chat=SimpleNamespace(completions=backend))
        async def run():
            self.assertEqual(await services.complete([{"role": "user", "content": "salut"}]),
                             "Réponse")
            self.assertEqual(
                "".join([chunk async for chunk in services.complete_stream(
                    [{"role": "user", "content": "salut"}])]),
                "[INTENT:neutral] Réponse")
        asyncio.run(run())
        self.assertEqual(len(backend.calls), 2)
        for call in backend.calls:
            self.assertEqual(call["model"], "gpt-6-luna")
            self.assertEqual(call["reasoning_effort"], "low")
            self.assertEqual(call["max_completion_tokens"], 320)

    def test_exact_history_is_kept_and_replayed_only_after_opt_in(self):
        with TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "dialogue.sqlite3")
            key = ("microphone", "goldaj")
            self.assertEqual(store.recent_conversation_turns(key, "person"), [])
            self.assertFalse(store.append_conversation_turn(
                key, "person", source_platform="microphone", message_id="x1",
                user_content="Goldaj (microphone): Salut", assistant_content="Coucou"))
            store.enable(key)
            text = "Texte intégral de mon message, sans résumé et avec les détails."
            self.assertTrue(store.append_conversation_turn(
                key, "person", source_platform="microphone", message_id="x1",
                user_content=text, assistant_content="Réponse complète."))
            self.assertFalse(store.append_conversation_turn(
                key, "person", source_platform="microphone", message_id="x1",
                user_content=text, assistant_content="Réponse complète."))
            expected = [{"role": "user", "content": text},
                        {"role": "assistant", "content": "Réponse complète."}]
            self.assertEqual(store.recent_conversation_turns(key, "person"), expected)
            self.assertTrue(store.forget(key))
            self.assertEqual(store.recent_conversation_turns(key, "person"), [])

    def test_dialogue_uses_restored_history_without_summarization(self):
        previous = [{"role": "user", "content": "Un message précis : 123456"},
                    {"role": "assistant", "content": "Je m'en souviens exactement."}]
        dialogue = Dialogue(_Backend(), "Tu es Jade.", max_messages=48)
        incoming = Incoming(platform="microphone", author="Goldaj", text="Coucou",
                            channel="mic", force_reply=True, message_id="new")
        answer = asyncio.run(dialogue.respond(incoming, history_messages=previous))
        self.assertIn("je garde mon avis", answer.text)
        self.assertEqual(list(dialogue.history[incoming.history_key])[:2], previous)

    def test_discord_text_solo_100_percent_group_30_percent(self):
        policy = DiscordTextPolicy(auto_rate=0.30, rng=_Random(0.99))
        def observe(uid, mid):
            message = SimpleNamespace(
                author=SimpleNamespace(id=uid, bot=False),
                mentions=(), reference=None, guild=SimpleNamespace(id=99))
            incoming = Incoming(platform="discord", author=f"user-{uid}",
                                channel="123", text="Salut",
                                message_id=str(mid), account_id=str(uid))
            return policy.observe(message, incoming, own_user_id=999)
        self.assertIsNotNone(observe(1, 1))
        self.assertIsNone(observe(2, 2))

    def test_twitch_solo_forced_but_group_is_sampled_by_dialogue(self):
        seen = []
        async def callback(msg):
            seen.append(msg)
            return None
        bridge = TwitchIRC(login="jadebot", token="not-a-real-token",
                           channel="example", on_message=callback)
        bridge.participants["person1"] = 1.0
        incoming = Incoming("twitch", "person1", "Salut", channel="example")
        asyncio.run(bridge._offer_message(incoming))
        self.assertTrue(seen[-1].force_reply)
        bridge.participants["person2"] = 2.0
        asyncio.run(bridge._offer_message(incoming))
        self.assertFalse(seen[-1].force_reply)

    def test_discord_voice_solo_always_group_sampled(self):
        decider = ConversationTurnDecider(
            group_reply_probability=0.30, rng=_Random(0.99))
        solo = decider.decide(
            "abcdefghijklmnop", 13, "Salut",
            authorized=True, consent_confirmed=True,
            participant_count=1)
        group = decider.decide(
            "qrstuvwxyzabcdef", 13, "Salut",
            authorized=True, consent_confirmed=True,
            participant_count=2)
        self.assertTrue(solo.should_reply)
        self.assertFalse(group.should_reply)
        self.assertEqual(group.reason, "group_sampled_out")
        self.assertTrue(decider.mark_replied("abcdefghijklmnop", solo.turn_id))
        # Even a recent conversational follow-up is sampled in a group.
        followup = decider.decide(
            "abcdefghijklmnop", 13, "Et donc ?",
            authorized=True, consent_confirmed=True, participant_count=2)
        self.assertFalse(followup.should_reply)
        # Being directly addressed in the group remains an exception.
        direct = decider.decide(
            "qrstuvwxyzabcdef", 13, "Jade, tu en penses quoi ?",
            authorized=True, consent_confirmed=True,
            participant_count=2, direct_address=True)
        self.assertTrue(direct.should_reply)


if __name__ == "__main__":
    unittest.main()
