from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import inspect
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.jade_runtime.live_usage import LiveUsageLedger, quote_voice


UTC = timezone.utc


class LiveUsageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "usage.sqlite3"
        self.now = datetime(2026, 11, 26, 12, tzinfo=UTC)
        self.ledger = LiveUsageLedger(self.path, now=lambda: self.now)

    def tearDown(self):
        self.temp.cleanup()

    def test_zero_and_arbitrary_estimates_never_gate_tracking(self):
        for index, amount in enumerate((0, ".01", 50, 10000000)):
            self.assertTrue(self.ledger.reserve(str(index), amount))
        self.ledger.reconcile("0", "99999.99", invoiced=True)
        self.assertTrue(self.ledger.reserve("after-large-consumption", 0))
        self.assertEqual(self.ledger.snapshot()["open_records"], 4)
        self.assertNotIn("daily_usd", inspect.signature(LiveUsageLedger).parameters)
        self.assertNotIn("monthly_usd", inspect.signature(LiveUsageLedger).parameters)
        self.assertFalse(hasattr(self.ledger, "admission"))

    def test_snapshot_has_only_passive_monthly_observation(self):
        self.ledger.reserve("voice")
        self.ledger.update_usage("voice", 30)
        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot["mode"], "passive")
        self.assertEqual(snapshot["scope"], "live_only")
        self.assertEqual(snapshot["month"], "2026-11")
        forbidden = {"daily", "limit_usd", "available", "available_usd", "admission",
                     "remaining_usd", "over_budget", "over_limit", "reserved_usd", "exposure_usd"}
        self.assertFalse(forbidden.intersection(snapshot))
        self.assertFalse(forbidden.intersection(snapshot["monthly"]))
        self.assertFalse(forbidden.intersection(self.ledger.reservation("voice")))

    def test_nonfinite_negative_amounts_and_blank_identifiers_are_invalid_data(self):
        for amount in ("NaN", "Infinity", "-0.01", True):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.ledger.reserve("invalid", amount)
        for identifier in ("", "   ", "id\n"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.ledger.reserve(identifier)
        self.assertTrue(self.ledger.reserve("valid-after-invalid"))

    def test_idempotent_registration_never_reopens_or_double_counts(self):
        self.assertTrue(self.ledger.reserve("voice-1", ".05"))
        self.assertTrue(self.ledger.reserve("voice-1", ".05"))
        self.ledger.reconcile("voice-1", ".03")
        self.assertFalse(self.ledger.release("voice-1"))
        self.assertTrue(self.ledger.reserve("voice-1", ".05"))
        self.assertEqual(self.ledger.reservation("voice-1")["state"], "closed")
        self.assertEqual(Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"]), Decimal(".03"))
        self.assertEqual(self.ledger.snapshot()["open_records"], 0)
        with self.assertRaises(ValueError):
            self.ledger.reserve("voice-1", ".06")

    def test_cumulative_12_15_15_and_old_replay_count_only_15_seconds(self):
        self.ledger.reserve("voice")
        for seconds in (12, 15, 15, 12):
            self.now += timedelta(seconds=1)
            self.ledger.update_usage("voice", seconds)
        row = self.ledger.update_usage("voice", 15, final=True)
        self.assertEqual(Decimal(row["seconds"]), 15)
        self.assertEqual(Decimal(row["spent_usd"]), quote_voice(15))
        self.assertEqual(row["state"], "closed")
        self.assertEqual(self.ledger.snapshot()["open_records"], 0)

    def test_provider_active_paused_refines_estimate_without_double_counting(self):
        self.ledger.reserve("voice")
        self.ledger.update_usage("voice", 90)
        row = self.ledger.update_usage("voice", 90, active_seconds=60, paused_seconds=30, final=True)
        self.assertEqual(Decimal(row["spent_usd"]), Decimal(".06"))
        self.assertEqual(row["quality"], "provider_usage")
        snapshot = self.ledger.snapshot()["monthly"]
        self.assertEqual(Decimal(snapshot["provider_usage_usd"]), Decimal(".06"))
        self.assertEqual(Decimal(snapshot["invoiced_usd"]), 0)

    def test_wall_estimate_never_advances_provider_counter_and_final_replaces_it(self):
        self.ledger.reserve("voice")
        self.ledger.estimate_usage("voice", 90)
        self.assertEqual(Decimal(self.ledger.reservation("voice")["seconds"]), 0)
        self.now += timedelta(seconds=90)
        row = self.ledger.update_usage("voice", 60, active_seconds=30, paused_seconds=30, final=True)
        self.assertEqual(Decimal(row["seconds"]), 60)
        self.assertEqual(Decimal(row["spent_usd"]), Decimal(".035"))
        self.assertEqual(Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"]), Decimal(".035"))
        self.ledger.estimate_usage("voice", 120)
        self.assertEqual(Decimal(self.ledger.reservation("voice")["spent_usd"]), Decimal(".035"))

    def test_partial_detail_unknown_seconds_remain_estimated(self):
        self.ledger.reserve("voice")
        self.ledger.update_usage("voice", 60, active_seconds=30, paused_seconds=30)
        row = self.ledger.update_usage("voice", 90)
        self.assertEqual(Decimal(row["spent_usd"]), Decimal(".06"))
        self.assertEqual(row["quality"], "estimated")
        with self.assertRaises(ValueError):
            self.ledger.update_usage("voice", 90, active_seconds=80, paused_seconds=20)

    def test_voice_backend_and_evidence_totals_are_distinct(self):
        self.ledger.reserve("voice")
        self.ledger.reserve("backend", kind="backend")
        self.ledger.reconcile("voice", ".5", confirmed=False)
        self.ledger.reconcile("backend", ".2")
        snapshot = self.ledger.snapshot()["monthly"]
        self.assertEqual(Decimal(snapshot["recorded_usd"]), Decimal(".7"))
        self.assertEqual(Decimal(snapshot["voice_usd"]), Decimal(".5"))
        self.assertEqual(Decimal(snapshot["backend_usd"]), Decimal(".2"))
        self.assertEqual(Decimal(snapshot["estimated_usd"]), Decimal(".5"))
        self.assertEqual(Decimal(snapshot["confirmed_usd"]), Decimal(".2"))
        self.assertEqual(Decimal(snapshot["invoiced_usd"]), 0)

    def test_concurrent_instances_register_every_operation_once_without_cap(self):
        another = LiveUsageLedger(self.path, now=lambda: self.now)
        def register(index):
            ledger = self.ledger if index % 2 else another
            return ledger.reserve(f"parallel-{index % 30}", 100)
        with ThreadPoolExecutor(max_workers=12) as pool:
            observed = list(pool.map(register, range(60)))
        self.assertTrue(all(observed))
        self.assertEqual(self.ledger.snapshot()["open_records"], 30)
        self.assertEqual(Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"]), 0)

    def test_unknown_usage_survives_restart_without_blocking_other_records(self):
        self.ledger.reserve("unknown")
        self.ledger.mark_unknown("unknown")
        restarted = LiveUsageLedger(self.path, now=lambda: self.now)
        self.assertTrue(restarted.reserve("another-operation"))
        self.assertEqual(restarted.snapshot()["unknown_records"], 1)
        with self.assertRaises(ValueError):
            restarted.release("unknown")
        restarted.reconcile("unknown", ".01", invoiced=True)
        self.assertEqual(restarted.snapshot()["unknown_records"], 0)

    def test_month_rollover_preserves_uncertainty_without_admission_policy(self):
        self.now = datetime(2026, 11, 30, 22, 59, tzinfo=UTC)
        self.ledger.reserve("spanning")
        self.ledger.mark_unknown("spanning")
        self.now += timedelta(minutes=2)
        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot["month"], "2026-12")
        self.assertEqual(snapshot["unknown_records"], 1)
        self.assertEqual(snapshot["monthly"]["unpriced_records"], 1)
        self.assertTrue(self.ledger.reserve("new-month"))

    def test_consumed_increment_crossing_month_is_split_and_never_lost(self):
        self.now = datetime(2026, 11, 30, 22, 59, 50, tzinfo=UTC)
        self.ledger.reserve("spanning")
        self.now += timedelta(seconds=20)
        self.ledger.reconcile("spanning", ".1")
        self.assertEqual(Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"]), Decimal(".05"))
        previous = self.ledger.snapshot(now=self.now - timedelta(seconds=20))
        self.assertEqual(Decimal(previous["monthly"]["recorded_usd"]), Decimal(".05"))

    def test_dst_changes_preserve_usage_and_allow_more_tracking(self):
        for before, after, month in (
            (datetime(2026, 3, 29, 0, 30, tzinfo=UTC), datetime(2026, 3, 29, 1, 30, tzinfo=UTC), "2026-03"),
            (datetime(2026, 10, 25, 0, 30, tzinfo=UTC), datetime(2026, 10, 25, 1, 30, tzinfo=UTC), "2026-10"),
        ):
            with self.subTest(month=month):
                self.now = before
                identifier = "dst-" + month
                self.ledger.reserve(identifier)
                self.now = after
                self.ledger.update_usage(identifier, 3600, final=True)
                self.assertEqual(self.ledger.snapshot()["month"], month)
                self.assertEqual(Decimal(self.ledger.reservation(identifier)["seconds"]), 3600)
                self.assertTrue(self.ledger.reserve(identifier + "-new"))

    def test_replayed_equal_usage_does_not_move_month_allocation_boundary(self):
        self.now = datetime(2026, 11, 30, 22, 59, 58, tzinfo=UTC)
        self.ledger.reserve("replayed")
        self.ledger.update_usage("replayed", 12)
        self.now += timedelta(seconds=2)
        self.ledger.update_usage("replayed", 12)
        self.now += timedelta(seconds=2)
        self.ledger.update_usage("replayed", 24, final=True)
        current = Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"])
        self.assertEqual(current, Decimal(".005"))

    def test_invoice_replaces_estimate_and_cannot_be_downgraded(self):
        self.ledger.reserve("invoice")
        self.ledger.update_usage("invoice", 90, final=True)
        self.ledger.reconcile("invoice", ".06", invoiced=True)
        row = self.ledger.reconcile("invoice", ".1", confirmed=False)
        self.assertEqual(row["quality"], "invoice")
        self.assertEqual(Decimal(row["spent_usd"]), Decimal(".06"))
        snapshot = self.ledger.snapshot()["monthly"]
        self.assertEqual(Decimal(snapshot["invoiced_usd"]), Decimal(".06"))
        self.assertEqual(Decimal(snapshot["estimated_usd"]), 0)

    def test_backend_completion_keeps_usage_unpriced_and_ignores_injected_cost(self):
        self.ledger.reserve("backend", kind="backend")
        row = self.ledger.record_backend_usage("backend", {
            "input_tokens": 100, "output_tokens": 20, "cost_usd": "0.001", "text": "not persisted"
        }, "completed")
        self.assertEqual(row["state"], "closed")
        self.assertEqual(row["quality"], "unpriced")
        self.assertIsNone(row["cost_usd"])
        self.assertEqual(row["backend_usage"]["input_tokens"], 100)
        self.assertEqual(row["backend_usage"]["output_tokens"], 20)
        self.assertEqual(row["backend_usage"]["quality"], "partial")
        self.assertIsNone(row["backend_usage"]["cost_usd"])
        self.assertNotIn("text", str(self.ledger.reservation("backend")))
        snapshot = self.ledger.snapshot()["monthly"]
        self.assertEqual(snapshot["unpriced_records"], 1)
        self.assertEqual(Decimal(snapshot["backend_usd"]), 0)
        self.assertEqual(Decimal(snapshot["invoiced_usd"]), 0)

    def test_backend_replay_uses_max_counters_and_does_not_downgrade_completion(self):
        self.ledger.reserve("backend", kind="backend")
        self.ledger.record_backend_usage("backend", {"input_tokens": 100}, "unknown")
        self.ledger.record_backend_usage("backend", {"input_tokens": 120, "output_tokens": 20}, "completed")
        self.ledger.record_backend_usage("backend", {"input_tokens": 100, "output_tokens": 10}, "cancelled")
        row = LiveUsageLedger(self.path).reservation("backend")
        self.assertEqual(row["backend_usage"]["input_tokens"], 120)
        self.assertEqual(row["backend_usage"]["output_tokens"], 20)
        self.assertEqual(row["backend_usage"]["status"], "completed")
        self.assertEqual(row["state"], "closed")

    def test_cancelled_or_unknown_backend_remains_uncertain_without_gate(self):
        for status in ("cancelled", "unknown"):
            self.ledger.reserve(status, kind="backend")
            row = self.ledger.record_backend_usage(status, {}, status)
            self.assertEqual(row["state"], "unknown")
            self.assertIsNone(row["cost_usd"])
            self.assertIsNone(row["backend_usage"]["input_tokens"])
        self.assertTrue(self.ledger.reserve("after-unknown", kind="backend"))

    def test_backend_invoice_can_resolve_cost_without_erasing_counters(self):
        self.ledger.reserve("backend", kind="backend")
        self.ledger.record_backend_usage("backend", {"input_tokens": 100}, "completed")
        self.ledger.reconcile("backend", ".02", invoiced=True)
        self.ledger.record_backend_usage("backend", {}, "completed")
        row = self.ledger.reservation("backend")
        self.assertEqual(row["quality"], "invoice")
        self.assertEqual(Decimal(row["cost_usd"]), Decimal(".02"))
        self.assertEqual(row["backend_usage"]["input_tokens"], 100)
        self.assertEqual(self.ledger.snapshot()["monthly"]["unpriced_records"], 0)

    def test_late_invoice_adjusts_original_month_instead_of_receipt_month(self):
        self.now = datetime(2026, 11, 29, 12, tzinfo=UTC)
        self.ledger.reserve("voice")
        self.now += timedelta(seconds=90)
        self.ledger.update_usage("voice", 90, final=True)
        november = self.now
        self.now = datetime(2026, 12, 5, 12, tzinfo=UTC)
        self.ledger.reconcile("voice", ".10", invoiced=True)
        self.assertEqual(Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"]), 0)
        self.assertEqual(Decimal(self.ledger.snapshot(now=november)["monthly"]["invoiced_usd"]), Decimal(".10"))

    def test_first_backend_invoice_uses_recorded_execution_month(self):
        self.now = datetime(2026, 11, 29, 12, tzinfo=UTC)
        self.ledger.reserve("backend", kind="backend")
        self.now += timedelta(seconds=10)
        self.ledger.record_backend_usage("backend", {"input_tokens": 10}, "completed")
        november = self.now
        self.now = datetime(2026, 12, 5, 12, tzinfo=UTC)
        self.ledger.reconcile("backend", ".02", invoiced=True)
        self.assertEqual(Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"]), 0)
        self.assertEqual(Decimal(self.ledger.snapshot(now=november)["monthly"]["invoiced_usd"]), Decimal(".02"))

    def test_invoice_restatement_after_zero_preserves_original_periods(self):
        self.now = datetime(2026, 11, 30, 22, 59, 50, tzinfo=UTC)
        november = self.now
        self.ledger.reserve("voice")
        self.now += timedelta(seconds=20)
        self.ledger.update_usage("voice", 20, final=True)
        december = self.now
        self.now = datetime(2027, 1, 5, 12, tzinfo=UTC)
        self.ledger.reconcile("voice", 0, invoiced=True)
        self.ledger.reconcile("voice", ".10", invoiced=True)
        self.assertEqual(Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"]), 0)
        total = sum(Decimal(self.ledger.snapshot(now=point)["monthly"]["recorded_usd"])
                    for point in (november, december))
        self.assertEqual(total, Decimal(".10"))

    def test_unused_observation_is_zero_evidence_not_unpriced_usage(self):
        self.ledger.reserve("not-started")
        self.assertTrue(self.ledger.release("not-started"))
        self.assertEqual(self.ledger.reservation("not-started")["cost_usd"], "0")
        self.assertEqual(self.ledger.snapshot()["monthly"]["unpriced_records"], 0)

    def test_legacy_sqlite_migration_preserves_data_and_is_repeatable(self):
        path = Path(self.temp.name) / "jade-live-budget.sqlite3"
        stamp = self.now.isoformat()
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE jade_live_budget_reservations(
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, quote_usd TEXT NOT NULL,
                    spent_usd TEXT NOT NULL DEFAULT '0', state TEXT NOT NULL DEFAULT 'reserved',
                    quality TEXT NOT NULL DEFAULT 'estimated', seconds TEXT NOT NULL DEFAULT '0',
                    active_seconds TEXT NOT NULL DEFAULT '0', paused_seconds TEXT NOT NULL DEFAULT '0',
                    created_at TEXT NOT NULL, observed_at TEXT NOT NULL);
                CREATE TABLE jade_live_budget_charges(
                    reservation_id TEXT NOT NULL, day TEXT NOT NULL, month TEXT NOT NULL,
                    usd TEXT NOT NULL, PRIMARY KEY(reservation_id,day));
            """)
            db.executemany("INSERT INTO jade_live_budget_reservations VALUES(?,?,?,?,?,?,?,?,?,?,?)", [
                ("legacy-voice", "voice", ".8", ".1", "closed", "provider_usage", "120", "120", "0", stamp, stamp),
                ("legacy-backend", "backend", ".25", ".25", "closed", "estimated", "0", "0", "0", stamp, stamp),
                ("legacy-unknown", "voice", ".5", "0", "unknown", "estimated", "0", "0", "0", stamp, stamp),
            ])
            db.executemany("INSERT INTO jade_live_budget_charges VALUES(?,?,?,?)", [
                ("legacy-voice", "2026-11-26", "2026-11", ".1"),
                ("legacy-backend", "2026-11-26", "2026-11", ".25"),
            ])
        first = LiveUsageLedger(path, now=lambda: self.now)
        before = first.snapshot()
        self.assertEqual(Decimal(before["monthly"]["recorded_usd"]), Decimal(".35"))
        self.assertEqual(before["unknown_records"], 1)
        self.assertEqual(first.reservation("legacy-voice")["seconds"], "120")
        second = LiveUsageLedger(path, now=lambda: self.now)
        self.assertEqual(second.snapshot(), before)
        self.assertEqual(second.reservation("legacy-backend")["spent_usd"], ".25")
        self.assertTrue(second.reserve("new-with-no-limit"))
        second.reconcile("legacy-backend", ".03", invoiced=True)
        self.assertEqual(Decimal(second.snapshot()["monthly"]["recorded_usd"]), Decimal(".13"))

    def test_naive_time_and_repo_paths_are_refused(self):
        with self.assertRaises(ValueError):
            self.ledger.snapshot(now=datetime(2026, 11, 26))
        with self.assertRaises(ValueError):
            LiveUsageLedger(Path(__file__).resolve().parents[1] / "private.sqlite3")
        self.assertEqual(quote_voice(90), Decimal(".075"))


if __name__ == "__main__":
    unittest.main()
