"""Offline tests for organization costs; no credentials or network needed."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.error import HTTPError

from src.jade_runtime.billing import BillingCosts

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)

def bucket(day, values):
    return {"start_time": int(datetime(2026, 11, day, tzinfo=timezone.utc).timestamp()),
            "results": [{"amount": {"value": value, "currency": currency}}
                        for currency, value in values]}

class Response:
    def __init__(self, data): self.data = json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, limit): return self.data[:limit]

class FetchTests(unittest.TestCase):
    def test_multiple_pages_and_currencies(self):
        pages = [
            {"data": [bucket(1, [("usd", 1.2)])], "has_more": True, "next_page": "next"},
            {"data": [bucket(20, [("usd", 0.34), ("eur", 0.5)])], "has_more": False},
        ]
        with patch("src.jade_runtime.billing.build_opener") as opener:
            opener.return_value.open.side_effect = [Response(p) for p in pages]
            result = BillingCosts("fake")._fetch(NOW)
        self.assertEqual(result["month"], {"usd": "1.54", "eur": "0.5"})
        self.assertEqual(result["today"], {"usd": "0.34", "eur": "0.5"})
        self.assertEqual(opener.return_value.open.call_count, 2)
        self.assertIsNone(result["balance"])

    def test_bad_pagination_fails_closed(self):
        with patch("src.jade_runtime.billing.build_opener") as opener:
            opener.return_value.open.return_value = Response({"data": [], "has_more": True, "next_page": "same"})
            with self.assertRaises(ValueError): BillingCosts("fake")._fetch(NOW)

class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_key_and_cache(self):
        self.assertEqual((await BillingCosts().get())["status"], "not_configured")
        billing = BillingCosts("fake")
        with patch.object(billing, "_fetch", return_value={"status": "ok", "checked_at": NOW.isoformat()}) as fetch:
            with patch("src.jade_runtime.billing.datetime", wraps=datetime) as clock:
                clock.now.return_value = NOW
                self.assertEqual((await billing.get())["status"], "ok")
                self.assertEqual((await billing.get())["status"], "ok")
            fetch.assert_called_once()

    async def test_access_error_does_not_leak_details(self):
        billing = BillingCosts("fake")
        with patch.object(billing, "_fetch", side_effect=HTTPError("secret-url", 403, "secret", {}, None)):
            result = await billing.get()
        self.assertEqual(result["status"], "access_denied")
        self.assertNotIn("secret", str(result))

    async def test_failed_refresh_retains_last_success(self):
        billing = BillingCosts("fake")
        with patch.object(billing, "_fetch", side_effect=[{"status": "ok", "month": {"usd": "1"}, "checked_at": NOW.isoformat()}, RuntimeError()]):
            with patch("src.jade_runtime.billing.datetime", wraps=datetime) as clock:
                clock.now.return_value = NOW
                await billing.get()
                billing._last_attempt -= 31
                result = await billing.get(refresh=True)
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["month"]["usd"], "1")

    async def test_day_change_refreshes_before_normal_cache_expiry(self):
        billing = BillingCosts("fake")
        earlier = datetime(2026, 11, 19, 23, 59, tzinfo=timezone.utc)
        old = {"status": "ok", "checked_at": earlier.isoformat(),
               "today": {"usd": "2"}, "month": {"usd": "10"}}
        fresh = {"status": "ok", "checked_at": NOW.isoformat(),
                 "today": {"usd": "0.1"}, "month": {"usd": "10.1"}}
        with patch.object(billing, "_fetch", side_effect=[old, fresh]) as fetch:
            with patch("src.jade_runtime.billing.datetime", wraps=datetime) as clock:
                clock.now.return_value = earlier
                await billing.get()
                billing._last_attempt -= 31
                clock.now.return_value = NOW
                result = await billing.get()
        self.assertEqual(result, fresh)
        self.assertEqual(fetch.call_count, 2)

    async def test_failed_new_day_hides_only_old_day(self):
        billing = BillingCosts("fake")
        earlier = datetime(2026, 11, 19, 23, 59, tzinfo=timezone.utc)
        old = {"status": "ok", "checked_at": earlier.isoformat(),
               "today": {"usd": "2"}, "month": {"usd": "10"}}
        with patch.object(billing, "_fetch", side_effect=[old, RuntimeError()]):
            with patch("src.jade_runtime.billing.datetime", wraps=datetime) as clock:
                clock.now.return_value = earlier
                await billing.get()
                billing._last_attempt -= 31
                clock.now.return_value = NOW
                result = await billing.get()
                cached = await billing.get()
        for value in (result, cached):
            self.assertEqual(value["status"], "stale")
            self.assertIsNone(value["today"])
            self.assertEqual(value["month"], {"usd": "10"})

    async def test_failed_new_month_hides_both_old_periods(self):
        billing = BillingCosts("fake")
        earlier = datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)
        old = {"status": "ok", "checked_at": earlier.isoformat(),
               "today": {"usd": "2"}, "month": {"usd": "10"}}
        with patch.object(billing, "_fetch", side_effect=[old, RuntimeError()]):
            with patch("src.jade_runtime.billing.datetime", wraps=datetime) as clock:
                clock.now.return_value = earlier
                await billing.get()
                billing._last_attempt -= 31
                clock.now.return_value = NOW
                result = await billing.get()
        self.assertEqual(result["status"], "stale")
        self.assertIsNone(result["today"])
        self.assertIsNone(result["month"])
