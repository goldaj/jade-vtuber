"""Offline tests: spontaneous greeting waits for human engagement; dollars are optional."""
import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from zoneinfo import ZoneInfo

from src.jade_runtime.cost_guard import CostGuard
from src.jade_runtime.initiatives import InitiativeScheduler
from src.jade_runtime.personality_evolution import personality_cues
from src.jade_runtime.social_intelligence import HybridSocialPolicy
from src.jade_runtime.messages import Incoming
from src.jade_runtime.memory_store import identity_of


def join(user_id=13, channel_id=77):
    channel = SimpleNamespace(id=channel_id, guild=SimpleNamespace(id=5))
    member = SimpleNamespace(id=user_id, bot=False)
    before = SimpleNamespace(channel=None)
    after = SimpleNamespace(channel=channel)
    return member, before, after


class DollarGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.guard = CostGuard(Path(self.tmp.name) / "guard.sqlite3")

    def test_inactivity_has_no_reservation_and_initiatives_enabled_by_default(self):
        self.assertEqual(self.guard.reserved_usd("initiative"), 0)
        self.assertTrue(self.guard.reserve("initiative", "event-A",
                                           quote_usd=".10", daily_usd=0, monthly_usd=0))
        self.assertFalse(self.guard.reserve("initiative", "event-A",
                                            quote_usd=".10", daily_usd=0, monthly_usd=0))
        self.assertEqual(self.guard.reserved_usd("initiative"), Decimal(".10"))

    def test_financial_limit_if_owner_configures_one(self):
        self.assertTrue(self.guard.reserve("initiative", "first", quote_usd=".1",
                                           daily_usd=".2", monthly_usd="1"))
        second = CostGuard(self.guard.path)
        self.assertTrue(second.reserve("initiative", "second", quote_usd=".1",
                                        daily_usd=".2", monthly_usd="1"))
        self.assertFalse(second.reserve("initiative", "third", quote_usd=".1",
                                         daily_usd=".2", monthly_usd="1"))

    def test_social_llm_disabled_by_default_and_separate(self):
        self.assertFalse(self.guard.reserve("social_review", "one", quote_usd=".03",
                                            daily_usd=0, monthly_usd=0))
        self.assertEqual(self.guard.reserved_usd("social_review"), 0)

    def test_paris_day_changes_at_midnight(self):
        now = datetime(2026, 11, 21, 23, 50, tzinfo=ZoneInfo("Europe/Paris"))
        later = datetime(2026, 11, 22, 0, 10, tzinfo=ZoneInfo("Europe/Paris"))
        self.assertTrue(self.guard.reserve("initiative", "one", quote_usd=".1",
                                           daily_usd=".1", monthly_usd="2", now=now))
        self.assertTrue(self.guard.reserve("initiative", "two", quote_usd=".1",
                                           daily_usd=".1", monthly_usd="2", now=later))


class SpontaneousEngagement(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.guard = CostGuard(Path(self.tmp.name) / "budget.sqlite3")
        self.time = 1000.0
        self.scheduler = InitiativeScheduler(
            self.guard, daily_usd=0, monthly_usd=0, cooldown_seconds=60,
            clock=lambda: self.time)

    async def test_join_triggers_without_prior_speech_then_waits(self):
        event = join(13)
        first = await self.scheduler.voice_join(*event, channel_id=77)
        self.assertIsNotNone(first)
        self.assertTrue(first.force_reply)
        self.assertTrue(self.scheduler.waiting_for_reply("77"))
        self.assertEqual(self.guard.reserved_usd("initiative"), Decimal(".10"))
        self.assertIsNone(await self.scheduler.voice_join(
            *join(14), channel_id=77))
        self.time += 61
        self.assertIsNone(await self.scheduler.voice_join(*join(14), channel_id=77),
                          "Even a new join cannot restart Jade if no one answered")
        self.assertTrue(self.scheduler.human_replied("77", verified=True))
        self.assertFalse(self.scheduler.waiting_for_reply("77"))
        self.assertIsNotNone(await self.scheduler.voice_join(
            *join(14), channel_id=77))
        self.assertEqual(self.guard.reserved_usd("initiative"), Decimal(".20"))

    async def test_room_empty_rearms_new_visit_without_human_reply(self):
        member = join(21)
        first = await self.scheduler.voice_join(*member, channel_id=77)
        self.assertIsNotNone(first)
        self.assertIsNone(await self.scheduler.voice_join(*member, channel_id=77))
        self.scheduler.room_emptied("77")
        self.assertFalse(self.scheduler.waiting_for_reply("77"))
        second = await self.scheduler.voice_join(*member, channel_id=77)
        self.assertIsNotNone(second)
        self.assertEqual(self.guard.reserved_usd("initiative"), Decimal(".20"))

    async def test_connected_vocal_greeting_uses_tts_without_user_memory(self):
        member, before, after = join(19)
        after.channel.members = [member]
        source = await self.scheduler.voice_join(
            member, before, after, channel_id=77, voice_session_id="v" * 24)
        self.assertIsNotNone(source)
        self.assertEqual(source.platform, "discord_voice")
        self.assertEqual(source.speaker_id, 19)
        self.assertTrue(source.system_initiative)
        self.assertIsNone(identity_of(source),
                          "Jade's autonomous greeting is not the entrant's memory")
        self.assertTrue(self.scheduler.waiting_for_reply("77"))

    async def test_no_self_followup_without_response(self):
        await self.scheduler.voice_join(*join(), channel_id=77)
        self.time += 30
        self.assertIsNone(await self.scheduler.voice_join(
            *join(14), channel_id=77))
        self.assertFalse(self.scheduler.human_replied("77", verified=False))
        self.assertTrue(self.scheduler.waiting_for_reply("77"))

    async def test_bots_moving_or_other_voice_channel_do_not_trigger(self):
        m, before, after = join()
        m.bot = True
        self.assertIsNone(await self.scheduler.voice_join(m, before, after,
                                                          channel_id=77))
        self.assertIsNone(await self.scheduler.voice_join(*join(channel_id=99),
                                                          channel_id=77))
        self.assertEqual(self.guard.reserved_usd("initiative"), 0)


class PersonalityMemory(unittest.TestCase):
    def test_uses_curated_style_cues_without_any_model(self):
        cues = personality_cues([
            {"summary": "Jade apprécie un humour discret.",
             "significance": "Évolution de sa personnalité."},
            {"summary": "Alice achète des légumes.", "significance": "Banal."}
        ])
        self.assertIn("humour discret", cues)
        self.assertNotIn("légumes", cues)
        self.assertLess(len(cues), 700)


class SocialHybrid(unittest.IsolatedAsyncioTestCase):
    async def test_paid_only_on_ambiguous_group_turn_when_configured(self):
        class Backend:
            calls = 0
            async def complete(self, messages):
                self.calls += 1
                return '{"reply":false}'
        with tempfile.TemporaryDirectory() as folder:
            guard = CostGuard(Path(folder) / "budget.sqlite3")
            backend = Backend()
            policy = HybridSocialPolicy(backend, guard, daily_usd=".15",
                                        monthly_usd="2")
            message = SimpleNamespace(guild=SimpleNamespace(id=9), mentions=(),
                                      reference=None)
            source = Incoming("discord", "Alice",
                "Est-ce que cette question est pertinente pour tout le salon ?",
                channel="77", message_id="some-human-question")
            self.assertFalse(await policy.allow(message, source, active_participants=3))
            self.assertEqual(backend.calls, 1)
            self.assertEqual(guard.reserved_usd("social_review"), Decimal(".03"))
            direct = Incoming("discord", "Alice", "Jade, tu en penses quoi ?",
                              channel="77", message_id="direct-question")
            self.assertTrue(await policy.allow(message, direct, active_participants=3))
            self.assertEqual(backend.calls, 1)


if __name__ == "__main__":
    unittest.main()
