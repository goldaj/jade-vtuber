import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from src.jade_runtime.global_spend import (
    ECB_URL, OPENAI_COSTS_URL, TAVILY_USAGE_URL, GlobalSpendCollector, paris_month,
)


class GlobalSpendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "spend.sqlite3"
        self.now = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)
        self.calls = []
        self.costs = [{"amount": {"value": 20, "currency": "usd"}}]
        self.account = {"current_plan": "Researcher", "plan_usage": 100, "paygo_usage": 0,
                        "plan_limit": 1000, "paygo_limit": 0}
        self.errors = set()

    def tearDown(self):
        self.temp.cleanup()

    def get(self, url, key=""):
        self.calls.append((url, key))
        if any(url.startswith(value) for value in self.errors):
            raise OSError("private body must never appear")
        if url.startswith(OPENAI_COSTS_URL):
            query = parse_qs(urlsplit(url).query)
            payload = {"data": [{"start_time": int(query["start_time"][0]),
                                 "end_time": int(query["end_time"][0]), "results": self.costs}],
                       "has_more": False, "next_page": None}
            return json.dumps(payload).encode()
        if url == TAVILY_USAGE_URL:
            # KEY usage intentionally differs: the global total must use account.
            return json.dumps({"key": {"usage": 1}, "account": self.account}).encode()
        if url == ECB_URL:
            return ('<Envelope><Cube><Cube time="' + self.now.date().isoformat() +
                    '"><Cube currency="USD" rate="2"/></Cube></Cube></Envelope>').encode()
        raise AssertionError("unexpected endpoint")

    def collector(self, **kwargs):
        return GlobalSpendCollector(admin_key="offline-admin", tavily_key="offline-tavily", web_enabled=True,
                                    db_path=self.path, now=lambda: self.now, get=self.get, **kwargs)

    async def test_all_openai_products_no_filters_and_account_tavily_are_converted(self):
        collector = self.collector()
        result = await collector.collect()
        self.assertEqual(result["coverage"], "bounded")
        self.assertEqual(result["month"], "2026-11")
        # OpenAI20 + Tavily100 consumed credits *0.008, / USD-per-EUR2.
        self.assertEqual(Decimal(result["spent_eur"]), Decimal("10.4"))
        self.assertEqual(result["sources"]["tavily"]["reported_credits"], "100")
        self.assertNotIn("month_boundary_upper_usd", result["sources"]["tavily"])
        self.assertFalse(result["final_invoice_guaranteed"])
        self.assertIsNone(result["sources"]["openai"]["complete_through"])
        cost_url = next(url for url, _ in self.calls if url.startswith(OPENAI_COSTS_URL))
        query = parse_qs(urlsplit(cost_url).query)
        self.assertEqual(set(query), {"start_time", "end_time", "bucket_width", "limit"})
        self.assertEqual(int(query["start_time"][0]), int(datetime(2026, 10, 31, 23, tzinfo=timezone.utc).timestamp()))
        self.assertNotIn("offline-admin", str(result))
        self.assertNotIn("offline-tavily", str(result))

    async def test_missing_admin_is_unknown_not_zero_even_if_other_provider_works(self):
        collector = GlobalSpendCollector(db_path=self.path, now=lambda: self.now, get=self.get)
        result = await collector.collect()
        self.assertEqual(result["coverage"], "unknown")
        self.assertEqual(result["reason"], "openai_admin_key_missing")
        self.assertIsNone(result["spent_eur"])
        self.assertFalse(any(url.startswith(OPENAI_COSTS_URL) for url, _ in self.calls))

    async def test_no_tavily_when_never_configured(self):
        collector = GlobalSpendCollector(admin_key="offline", db_path=self.path, now=lambda: self.now, get=self.get)
        result = await collector.collect()
        self.assertEqual(result["sources"]["tavily"]["status"], "not_applicable")
        self.assertEqual(Decimal(result["spent_eur"]), Decimal(10))
        self.assertFalse(any(url == TAVILY_USAGE_URL for url, _ in self.calls))

    async def test_disabling_tavily_midmonth_cannot_erase_existing_spend(self):
        await self.collector().collect()
        disabled = GlobalSpendCollector(admin_key="offline", db_path=self.path, now=lambda: self.now, get=self.get)
        result = await disabled.collect()
        self.assertEqual(result["reason"], "tavily_key_missing")
        self.assertEqual(result["coverage"], "unknown")
        self.assertEqual(Decimal(result["last_known_eur"]), Decimal("10.4"))

    async def test_provider_failure_keeps_previous_total_but_is_not_permission(self):
        collector = self.collector()
        previous = await collector.collect()
        self.errors.add(OPENAI_COSTS_URL)
        result = await collector.collect()
        self.assertEqual(result["coverage"], "unknown")
        self.assertIsNone(result["spent_eur"])
        self.assertEqual(result["last_known_eur"], previous["spent_eur"])
        self.assertNotIn("private body", str(result))

    async def test_fx_failure_and_unknown_currency_are_not_zero(self):
        self.errors.add(ECB_URL)
        result = await self.collector().collect()
        self.assertEqual(result["coverage"], "unknown")
        self.assertIn("fx_unavailable", result["issues"])
        self.errors.clear()
        self.costs[0]["amount"]["currency"] = "XYZ"
        result = await self.collector().collect()
        self.assertEqual(result["reason"], "fx_currency_unavailable")
        self.assertIsNone(result["spent_eur"])

    async def test_custom_pricing_is_unknown_and_unused_quota_is_never_spend(self):
        self.account["current_plan"] = "Enterprise"
        result = await self.collector().collect()
        self.assertEqual(result["reason"], "tavily_custom_or_unknown_pricing")
        self.account["current_plan"] = "Researcher"
        self.account["plan_limit"] = 10000
        self.account["paygo_limit"] = None
        result = await self.collector().collect()
        self.assertEqual(result["coverage"], "bounded")
        self.assertEqual(result["sources"]["tavily"]["reported_credits"], "100")
        self.assertEqual(Decimal(result["spent_eur"]), Decimal("10.4"))

    async def test_first_observation_during_ambiguous_month_boundary_waits_for_cycle(self):
        self.now = datetime(2026, 11, 30, 23, 30, tzinfo=timezone.utc)
        collector = self.collector()
        result = await collector.collect()
        self.assertEqual(result["reason"], "tavily_cycle_boundary_unknown")
        self.assertIsNone(result["spent_eur"])
        self.account["plan_usage"] = 1
        self.now += timedelta(hours=2)
        result = await collector.collect()
        self.assertEqual(result["coverage"], "bounded")
        self.assertEqual(result["sources"]["tavily"]["cycle_evidence"]["basis"], "observed_reset")

    async def test_cycle_becomes_identifiable_after_boundary_without_inventing_quota_cost(self):
        self.now = datetime(2026, 11, 30, 23, 30, tzinfo=timezone.utc)
        collector = self.collector()
        self.assertEqual((await collector.collect())["coverage"], "unknown")
        self.now += timedelta(hours=49)
        result = await collector.collect()
        self.assertEqual(result["coverage"], "bounded")
        self.assertEqual(Decimal(result["spent_eur"]), Decimal("10.4"))

    async def test_unexpected_tavily_counter_reset_is_visible(self):
        collector = self.collector()
        await collector.collect()
        self.account["plan_usage"] = 0
        result = await collector.collect()
        self.assertEqual(result["reason"], "tavily_cycle_decreased_unexpectedly")
        self.assertEqual(result["coverage"], "unknown")

    async def test_repeated_cumulative_reports_do_not_add_again_and_fx_is_cached(self):
        collector = self.collector()
        first = await collector.collect()
        second = await collector.collect()
        self.assertEqual(first["spent_eur"], second["spent_eur"])
        self.assertEqual(sum(url == ECB_URL for url, _ in self.calls), 1)

    async def test_old_month_failure_never_supplies_a_new_month_zero_or_total(self):
        collector = self.collector()
        await collector.collect()
        self.now = datetime(2026, 11, 30, 23, tzinfo=timezone.utc)
        self.errors.add(OPENAI_COSTS_URL)
        result = await collector.collect()
        self.assertEqual(result["month"], "2026-12")
        self.assertNotIn("last_known_eur", result)

    def test_month_boundaries_paris_not_utc_in_winter_summer_and_dst(self):
        for instant, month, start in (
            (datetime(2026, 11, 30, 23, tzinfo=timezone.utc), "2026-12", datetime(2026, 11, 30, 23, tzinfo=timezone.utc)),
            (datetime(2026, 6, 30, 22, tzinfo=timezone.utc), "2026-07", datetime(2026, 6, 30, 22, tzinfo=timezone.utc)),
            (datetime(2026, 3, 31, 22, tzinfo=timezone.utc), "2026-04", datetime(2026, 3, 31, 22, tzinfo=timezone.utc)),
        ):
            with self.subTest(month=month):
                actual, lo, hi = paris_month(instant)
                self.assertEqual((actual, lo), (month, start))
                self.assertGreater(hi, lo)


if __name__ == "__main__":
    unittest.main()
