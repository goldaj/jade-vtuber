from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from src.jade_runtime.live_budget import LiveBudgetLedger, quote_voice, quote_session
from src.jade_runtime.live_config import LiveConfig


UTC = timezone.utc


class LiveBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "budget.sqlite3"
        self.now = datetime(2026, 11, 26, 12, tzinfo=UTC)
        self.ledger = LiveBudgetLedger(self.path, "1", "10", now=lambda: self.now)

    def tearDown(self):
        self.temp.cleanup()

    def test_zero_disables_and_nonfinite_negative_amounts_fail_closed(self):
        disabled = LiveBudgetLedger(self.path, 0, 0)
        self.assertFalse(disabled.reserve("zero", ".01"))
        for amount in ("NaN", "Infinity", "-0.01", True):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.ledger.reserve("invalid", amount)
        self.assertEqual(self.ledger.snapshot()["open_reservations"], 0)

    def test_reservation_consumption_and_release_are_never_added_twice(self):
        self.assertTrue(self.ledger.reserve("voice-1", ".05"))
        self.assertTrue(self.ledger.reserve("voice-1", ".05"))
        self.ledger.reconcile("voice-1", ".03")
        self.assertFalse(self.ledger.release("voice-1"))
        snapshot = self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot["daily"]["spent_usd"]), Decimal(".03"))
        self.assertEqual(Decimal(snapshot["daily"]["exposure_usd"]), Decimal(".03"))
        self.assertEqual(Decimal(snapshot["reserved_usd"]), 0)
        self.assertFalse(self.ledger.reserve("voice-1", ".05"))
        with self.assertRaises(ValueError):
            self.ledger.reserve("voice-1", ".06")

    def test_cumulative_12_15_15_and_old_replay_count_only_15_seconds(self):
        self.ledger.reserve("voice", ".1")
        for seconds in (12, 15, 15, 12):
            self.now += timedelta(seconds=1)
            self.ledger.update_usage("voice", seconds)
        self.ledger.update_usage("voice", 15, final=True)
        row = self.ledger.reservation("voice")
        self.assertEqual(Decimal(row["seconds"]), 15)
        self.assertEqual(Decimal(row["spent_usd"]), quote_voice(15))
        self.assertEqual(row["state"], "closed")
        self.assertEqual(Decimal(self.ledger.snapshot()["reserved_usd"]), 0)

    def test_provider_active_paused_refines_estimate_without_double_counting(self):
        self.ledger.reserve("voice", ".2")
        self.ledger.update_usage("voice", 90)
        row = self.ledger.update_usage("voice", 90, active_seconds=60, paused_seconds=30, final=True)
        self.assertEqual(Decimal(row["spent_usd"]), Decimal(".06"))
        self.assertEqual(row["quality"], "provider_usage")
        self.assertEqual(Decimal(self.ledger.snapshot()["daily"]["spent_usd"]), Decimal(".06"))

    def test_wall_estimate_never_advances_provider_counter_and_final_replaces_it(self):
        self.ledger.reserve("voice", ".2")
        self.ledger.estimate_usage("voice", 90)
        self.assertEqual(Decimal(self.ledger.reservation("voice")["seconds"]), 0)
        self.now += timedelta(seconds=90)
        row = self.ledger.update_usage("voice", 60, active_seconds=30, paused_seconds=30, final=True)
        self.assertEqual(Decimal(row["seconds"]), 60)
        self.assertEqual(Decimal(row["spent_usd"]), Decimal(".035"))
        snapshot = self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot["reserved_usd"]), 0)
        self.assertEqual(Decimal(snapshot["daily"]["spent_usd"]), Decimal(".035"))
        self.ledger.estimate_usage("voice", 120)
        self.assertEqual(Decimal(self.ledger.reservation("voice")["spent_usd"]), Decimal(".035"))

    def test_partial_detail_unknown_seconds_remain_priced_as_active(self):
        self.ledger.reserve("voice", ".2")
        self.ledger.update_usage("voice", 60, active_seconds=30, paused_seconds=30)
        row = self.ledger.update_usage("voice", 90)
        self.assertEqual(Decimal(row["spent_usd"]), Decimal(".06"))
        self.assertEqual(row["quality"], "estimated")
        with self.assertRaises(ValueError):
            self.ledger.update_usage("voice", 90, active_seconds=80, paused_seconds=20)

    def test_voice_and_backend_totals_share_same_atomic_budget(self):
        self.assertTrue(self.ledger.reserve("voice", ".6"))
        self.assertTrue(self.ledger.reserve("backend", ".3", "backend"))
        self.assertFalse(self.ledger.reserve("another", ".2", "backend"))
        self.ledger.reconcile("voice", ".5", confirmed=False)
        self.ledger.reconcile("backend", ".2")
        snapshot = self.ledger.snapshot()["daily"]
        self.assertEqual(Decimal(snapshot["spent_usd"]), Decimal(".7"))
        self.assertEqual(Decimal(snapshot["voice_usd"]), Decimal(".5"))
        self.assertEqual(Decimal(snapshot["backend_usd"]), Decimal(".2"))
        self.assertEqual(Decimal(snapshot["estimated_usd"]), Decimal(".5"))
        self.assertEqual(Decimal(snapshot["confirmed_usd"]), Decimal(".2"))

    def test_concurrent_instances_cannot_overspend_or_duplicate_reservations(self):
        another = LiveBudgetLedger(self.path, "1", "10", now=lambda: self.now)

        def reserve(index):
            ledger = self.ledger if index % 2 else another
            return ledger.reserve(f"parallel-{index}", ".1")

        with ThreadPoolExecutor(max_workers=12) as pool:
            admitted = list(pool.map(reserve, range(30)))
        self.assertEqual(sum(admitted), 10)
        snapshot = self.ledger.snapshot()
        self.assertEqual(Decimal(snapshot["daily"]["exposure_usd"]), 1)
        self.assertFalse(snapshot["available"])
        self.assertFalse(snapshot["over_budget"])

    def test_ambiguous_creation_survives_restart_and_cannot_be_released(self):
        self.ledger.reserve("unknown", ".8")
        self.ledger.mark_unknown("unknown")
        restarted = LiveBudgetLedger(self.path, "1", "10", now=lambda: self.now)
        self.assertFalse(restarted.reserve("retry", ".3"))
        self.assertEqual(restarted.snapshot()["unknown_reservations"], 1)
        with self.assertRaises(ValueError):
            restarted.release("unknown")
        restarted.reconcile("unknown", ".01", invoiced=True)
        self.assertTrue(restarted.reserve("after-reconciliation", ".8"))

    def test_open_reservation_counts_after_midnight_and_month_rollover(self):
        self.now = datetime(2026, 11, 30, 22, 59, tzinfo=UTC)  # 23:59 in Paris.
        self.ledger.reserve("spanning", ".8")
        self.now += timedelta(minutes=2)
        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot["date"], "2026-12-01")
        self.assertEqual(snapshot["month"], "2026-12")
        self.assertEqual(Decimal(snapshot["daily"]["exposure_usd"]), Decimal(".8"))
        self.assertEqual(Decimal(snapshot["monthly"]["exposure_usd"]), Decimal(".8"))
        self.assertFalse(self.ledger.reserve("new-day", ".3"))

    def test_consumed_increment_crossing_midnight_is_split_and_never_lost(self):
        self.now = datetime(2026, 11, 30, 22, 59, 50, tzinfo=UTC)
        self.ledger.reserve("spanning", ".2")
        self.now += timedelta(seconds=20)
        self.ledger.reconcile("spanning", ".1")
        self.assertEqual(Decimal(self.ledger.snapshot()["daily"]["spent_usd"]), Decimal(".05"))
        previous = self.ledger.snapshot(now=self.now - timedelta(seconds=20))
        self.assertEqual(Decimal(previous["daily"]["spent_usd"]), Decimal(".05"))

    def test_dst_dates_and_repeated_hour_do_not_reset_daily_budget(self):
        for before, after, day in (
            (datetime(2026, 3, 29, 0, 30, tzinfo=UTC), datetime(2026, 3, 29, 1, 30, tzinfo=UTC), "2026-03-29"),
            (datetime(2026, 10, 25, 0, 30, tzinfo=UTC), datetime(2026, 10, 25, 1, 30, tzinfo=UTC), "2026-10-25"),
        ):
            with self.subTest(day=day):
                self.now = before
                identifier = "dst-" + day
                self.ledger.reserve(identifier, ".8")
                self.now = after
                self.assertEqual(self.ledger.snapshot()["date"], day)
                self.assertFalse(self.ledger.reserve(identifier + "-new", ".3"))
                self.ledger.release(identifier)

    def test_replayed_equal_usage_does_not_move_observation_boundary(self):
        self.now = datetime(2026, 11, 30, 22, 59, 58, tzinfo=UTC)
        self.ledger.reserve("replayed", ".2")
        self.ledger.update_usage("replayed", 12)
        self.now += timedelta(seconds=2)
        self.ledger.update_usage("replayed", 12)
        self.now += timedelta(seconds=2)
        self.ledger.update_usage("replayed", 24, final=True)
        current = Decimal(self.ledger.snapshot()["daily"]["spent_usd"])
        self.assertEqual(current, Decimal(".005"))

    def test_invoice_replaces_estimate_and_cannot_be_downgraded(self):
        self.ledger.reserve("invoice", ".2")
        self.ledger.update_usage("invoice", 90, final=True)
        self.ledger.reconcile("invoice", ".06", invoiced=True)
        row = self.ledger.reconcile("invoice", ".1", confirmed=False)
        self.assertEqual(row["quality"], "invoice")
        self.assertEqual(Decimal(row["spent_usd"]), Decimal(".06"))
        self.assertEqual(Decimal(self.ledger.snapshot()["daily"]["invoiced_usd"]), Decimal(".06"))

    def test_actual_overrun_is_recorded_and_blocks_new_work(self):
        self.ledger.reserve("overrun", ".1")
        self.ledger.reconcile("overrun", "1.2")
        snapshot = self.ledger.snapshot()
        self.assertTrue(snapshot["over_budget"])
        self.assertEqual(Decimal(snapshot["remaining_usd"]), 0)
        self.assertFalse(self.ledger.reserve("blocked", ".01"))

    def test_quote_covers_whole_connection_without_double_startup_charge(self):
        config = LiveConfig()
        expected = quote_voice(config.max_session_seconds + config.opening_timeout_seconds
                               + config.close_timeout_seconds)
        self.assertEqual(quote_session(config), expected)
        self.assertEqual(quote_voice(90), Decimal(".075"))

    def test_naive_time_and_repo_paths_are_refused(self):
        with self.assertRaises(ValueError):
            self.ledger.snapshot(now=datetime(2026, 11, 26))
        with self.assertRaises(ValueError):
            LiveBudgetLedger(Path(__file__).resolve().parents[1] / "private.sqlite3", 1, 1)


if __name__ == "__main__":
    unittest.main()
