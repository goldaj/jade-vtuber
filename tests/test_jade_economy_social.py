"""Offline checks for reservations, personality cues and social decisions."""
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from datetime import timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError
from src.jade_runtime.paris_clock import paris_date

from src.jade_runtime.cost_guard import CostGuard
from src.jade_runtime.personality_evolution import personality_cues
from src.jade_runtime.social_intelligence import HybridSocialPolicy
from src.jade_runtime.messages import Incoming


class DollarGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.guard = CostGuard(Path(self.tmp.name) / "guard.sqlite3")

    def test_duplicate_event_does_not_increase_reservations(self):
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


    def test_eu_dst_fallback_when_windows_lacks_tzdata(self):
        with patch("src.jade_runtime.paris_clock.ZoneInfo",
                   side_effect=ZoneInfoNotFoundError):
            utc = timezone.utc
            self.assertEqual(paris_date(
                datetime(2026, 3, 29, 0, 30, tzinfo=utc)).isoformat(), "2026-03-29")
            self.assertEqual(paris_date(
                datetime(2026, 3, 29, 23, 30, tzinfo=utc)).isoformat(), "2026-03-30")
            self.assertEqual(paris_date(
                datetime(2026, 10, 25, 0, 30, tzinfo=utc)).isoformat(), "2026-10-25")
            self.assertEqual(paris_date(
                datetime(2026, 10, 25, 23, 30, tzinfo=utc)).isoformat(), "2026-10-26")

    def test_social_llm_disabled_by_default_and_separate(self):
        self.assertFalse(self.guard.reserve("social_review", "one", quote_usd=".03",
                                            daily_usd=0, monthly_usd=0))
        self.assertEqual(self.guard.reserved_usd("social_review"), 0)

    def test_paris_day_changes_at_midnight(self):
        now = datetime(2026, 11, 21, 23, 50, tzinfo=timezone(timedelta(hours=1)))
        later = datetime(2026, 11, 22, 0, 10, tzinfo=timezone(timedelta(hours=1)))
        self.assertTrue(self.guard.reserve("initiative", "one", quote_usd=".1",
                                           daily_usd=".1", monthly_usd="2", now=now))
        self.assertTrue(self.guard.reserve("initiative", "two", quote_usd=".1",
                                           daily_usd=".1", monthly_usd="2", now=later))


class PersonalityMemory(unittest.TestCase):
    def test_uses_curated_style_cues_without_any_model(self):
        cues = personality_cues([
            {"summary": "Jade apprécie un humour discret.",
             "significance": "Évolution de sa personnalité."},
            {"summary": "Alice achète des légumes.", "significance": "Banal."}
        ])
        self.assertIn("humour discret", cues)
        self.assertNotIn("légumes", cues)
        self.assertEqual(personality_cues([
            {"summary": "Alice préfère que Jade parle doucement.",
             "significance": "Préférence personnelle d'Alice."}]), "")
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
