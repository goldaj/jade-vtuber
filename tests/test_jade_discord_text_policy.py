"""Offline Discord text checks; no bot login or paid API calls."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.discord_text import DiscordText, parse_discord_message
from src.jade_runtime.discord_text_policy import DiscordTextPolicy


def msg(text, *, author_id=7, name="Alice", channel=10, guild=1,
        ident=100, bot=False, mentions=(), reference=None):
    return SimpleNamespace(
        id=ident, content=text,
        author=SimpleNamespace(id=author_id, display_name=name, bot=bot),
        channel=SimpleNamespace(id=channel),
        guild=(None if guild is None else SimpleNamespace(id=guild)),
        mentions=mentions, reference=reference,
    )


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class TextPolicyTests(unittest.IsolatedAsyncioTestCase):
    def test_ignore_chatter_but_pass_context_to_explicit_ping(self):
        policy = DiscordTextPolicy(auto_rate=0)
        idle = msg("On se retrouve demain.", ident=1)
        self.assertIsNone(policy.observe(idle, parse_discord_message(idle), own_user_id=42))
        ping = msg("<@42> Tu en penses quoi ?", ident=2,
                   mentions=[SimpleNamespace(id=42)])
        selected = policy.observe(ping, parse_discord_message(ping), own_user_id=42)
        self.assertTrue(selected.force_reply)
        self.assertEqual(selected.context, ("Alice : On se retrouve demain.",))
        self.assertEqual(selected.text, "<@42> Tu en penses quoi ?")

    def test_other_channels_are_isolated_and_name_requires_word_boundaries(self):
        policy = DiscordTextPolicy(auto_rate=0)
        a = msg("Secret du salon 10", ident=1, channel=10)
        policy.observe(a, parse_discord_message(a), own_user_id=42)
        b = msg("Bonjour Jade !", ident=2, channel=11)
        selected = policy.observe(b, parse_discord_message(b), own_user_id=42)
        self.assertEqual(selected.context, ())
        c = msg("Jadette était là", ident=3, channel=10)
        self.assertIsNone(policy.observe(c, parse_discord_message(c), own_user_id=42))

    def test_dm_and_reply_to_jade_are_direct(self):
        policy = DiscordTextPolicy(auto_rate=0)
        dm = msg("Salut", ident=1, guild=None)
        self.assertTrue(policy.observe(dm, parse_discord_message(dm), own_user_id=42).force_reply)
        quoted = msg("Et là ?", ident=2,
                     reference=SimpleNamespace(resolved=SimpleNamespace(
                         author=SimpleNamespace(id=42)), message_id=999))
        self.assertTrue(policy.observe(quoted, parse_discord_message(quoted), own_user_id=42).force_reply)

    def test_followup_only_after_successful_written_reply_and_same_speaker(self):
        clock = FakeClock()
        policy = DiscordTextPolicy(auto_rate=0, clock=clock)
        direct = msg("Jade, une question", ident=10)
        selected = policy.observe(direct, parse_discord_message(direct), own_user_id=42)
        self.assertTrue(selected.force_reply)
        question = msg("Et ensuite ?", ident=11)
        self.assertIsNone(policy.observe(question, parse_discord_message(question), own_user_id=42))
        policy.note_sent("10", source_message_id="10", sent_message_id=500)
        clock.now += 1
        next_msg = msg("Et ensuite ?", ident=12)
        self.assertTrue(policy.observe(next_msg, parse_discord_message(next_msg), own_user_id=42).force_reply)
        other = msg("Et moi ?", author_id=8, ident=13)
        self.assertIsNone(policy.observe(other, parse_discord_message(other), own_user_id=42))
        clock.now += 91
        later = msg("Et après ?", ident=14)
        self.assertIsNone(policy.observe(later, parse_discord_message(later), own_user_id=42))
        reply = msg("Précise", ident=15, reference=SimpleNamespace(message_id=500, resolved=None))
        self.assertTrue(policy.observe(reply, parse_discord_message(reply), own_user_id=42).force_reply)

    def test_random_questions_are_rate_limited_and_bots_cannot_initiate(self):
        clock = FakeClock()
        policy = DiscordTextPolicy(auto_rate=1, cooldown_seconds=180,
                                   clock=clock, rng=FixedRandom(0))
        a = msg("Comment ça marche ?", ident=1)
        self.assertTrue(policy.observe(a, parse_discord_message(a), own_user_id=42).force_reply)
        b = msg("Pourquoi ?", ident=2)
        self.assertIsNone(policy.observe(b, parse_discord_message(b), own_user_id=42))
        clock.now += 181
        c = msg("Est-ce possible ?", ident=3, bot=True)
        self.assertIsNone(policy.observe(c, parse_discord_message(c), own_user_id=42))
        d = msg("Combien ?", ident=4)
        self.assertTrue(policy.observe(d, parse_discord_message(d), own_user_id=42).force_reply)
        policy0 = DiscordTextPolicy(auto_rate=0)
        self.assertIsNone(policy0.observe(d, parse_discord_message(d), own_user_id=42))

    def test_large_messages_and_state_are_bounded(self):
        policy = DiscordTextPolicy(auto_rate=0, max_channels=2)
        for i in range(8):
            message = msg("Message " + str(i), ident=i, channel=10)
            policy.observe(message, parse_discord_message(message), own_user_id=42)
        ping = msg("Jade ?", ident=9, channel=10)
        selected = policy.observe(ping, parse_discord_message(ping), own_user_id=42)
        self.assertEqual(len(selected.context), 6)
        self.assertTrue(all(len(item) <= 320 for item in selected.context))
        huge = msg("Jade " + "a" * 1201, ident=10)
        self.assertIsNone(policy.observe(huge, parse_discord_message(huge), own_user_id=42))
        for channel in (20, 30):
            m = msg("hello", ident=channel, channel=channel)
            policy.observe(m, parse_discord_message(m), own_user_id=42)
        self.assertEqual(len(policy.channels), 2)
        self.assertNotIn("10", policy.channels)

    async def test_discord_send_is_written_with_no_ping_and_acknowledges_reply(self):
        class Sent:
            id = 700

        sent = SimpleNamespace(send=AsyncMock(return_value=Sent()))
        fake = SimpleNamespace(AllowedMentions=SimpleNamespace(none=lambda: "disabled"))
        connector = DiscordText("test", AsyncMock(), send_enabled=True, auto_rate=0)
        connector.client = SimpleNamespace(get_channel=lambda _: sent)
        message = msg("Salut Jade", ident=101)
        connector.policy.observe(message, parse_discord_message(message), own_user_id=42)
        with patch.dict("sys.modules", {"discord": fake}):
            self.assertTrue(await connector.send_chat("10", "Réponse <@everyone>",
                                                       source_message_id="101"))
        self.assertEqual(sent.send.await_args.kwargs["allowed_mentions"], "disabled")
        self.assertEqual(connector.policy.channels["10"].last_reply_author, 7)
        self.assertIn(700, connector.policy.channels["10"].sent_ids)

    async def test_text_reply_can_span_multiple_discord_messages(self):
        target = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=99)))
        fake = SimpleNamespace(AllowedMentions=SimpleNamespace(none=lambda: "disabled"))
        connector = DiscordText("test", AsyncMock(), send_enabled=True)
        connector.client = SimpleNamespace(get_channel=lambda _: target)
        with patch.dict("sys.modules", {"discord": fake}):
            self.assertTrue(await connector.send_chat("10", "Mot " * 1000))
        self.assertGreater(target.send.await_count, 1)
        for call in target.send.await_args_list:
            self.assertLessEqual(len(call.args[0]), 1800)

    async def test_context_only_appears_for_selected_turn(self):
        class Backend:
            def __init__(self):
                self.calls = []

            async def complete(self, messages):
                self.calls.append(messages)
                return "Une réponse"

        backend = Backend()
        dialogue = Dialogue(backend, "Tu es Jade.")
        direct = msg("Jade, réponds.", ident=1)
        policy = DiscordTextPolicy(auto_rate=0)
        previous = msg("Le sujet était les étoiles", ident=2)
        policy.observe(previous, parse_discord_message(previous), own_user_id=42)
        incoming = policy.observe(direct, parse_discord_message(direct), own_user_id=42)
        reply = await dialogue.respond(incoming)
        self.assertEqual(reply.text, "Une réponse")
        self.assertTrue(any("étoiles" in entry["content"] for entry in backend.calls[0]))


class ConfigTests(unittest.TestCase):
    def test_default_spontaneous_participation_is_thirty_percent(self):
        self.assertEqual(Settings().discord_text_auto_rate, 0.30)
        self.assertEqual(DiscordTextPolicy().auto_rate, 0.30)
        self.assertEqual(DiscordText("test", AsyncMock()).policy.auto_rate, 0.30)

    def test_discord_text_bounds(self):
        Settings(discord_text_auto_rate=0, discord_text_cooldown_seconds=30).validate()
        with self.assertRaises(ValueError):
            Settings(discord_text_auto_rate=1.1).validate()
        with self.assertRaises(ValueError):
            Settings(discord_text_cooldown_seconds=29).validate()
