import asyncio
import copy
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import threading
import unittest

from src.jade_runtime.discord_live_policy import DiscordLiveSpendPolicy


class Collector:
    def __init__(self, path, snapshot):
        self.db_path, self.snapshot = path, snapshot
        self.calls = 0

    async def collect(self):
        self.calls += 1
        return copy.deepcopy(self.snapshot)


class DiscordLiveSpendPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "spend.sqlite3"
        self.now = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)
        self.collector = Collector(self.path, self.snapshot())
        self.policy = DiscordLiveSpendPolicy(self.collector, now=lambda: self.now)

    async def asyncTearDown(self):
        await self.policy.close()
        self.temp.cleanup()

    def snapshot(self, spent="1", coverage="bounded", month="2026-11"):
        return {"month": month, "spent_eur": spent, "coverage": coverage,
                "checked_at": self.now.isoformat(), "complete_through": self.now.isoformat(),
                "sources": {"openai": {"amounts": {"USD": spent}}},
                "fx": {"rates": {"USD": "1"}}}

    async def set_snapshot(self, spent="1", coverage="bounded", month="2026-11"):
        self.collector.snapshot = self.snapshot(spent, coverage, month)
        await self.policy.refresh()

    async def test_owner_preference_persists_and_does_not_override_the_spend_latch(self):
        await self.set_snapshot("1", "complete")
        self.assertTrue((await self.policy.mobile_settings())["enabled"])
        self.assertFalse((await self.policy.mobile_settings(False))["enabled"])
        peer = DiscordLiveSpendPolicy(self.collector, now=lambda: self.now)
        try:
            self.assertFalse((await peer.mobile_settings())["enabled"])
            denied = await peer.reserve_live("manually-disabled", model="gpt-live-1.1",
                                            opening_seconds=8, close_seconds=5, control_seconds=1)
            self.assertEqual(denied["reason"], "manual_classic")
            self.assertNotIn("reservation_id", denied)
            self.assertTrue((await peer.mobile_settings(True))["enabled"])
            self.assertTrue((await self.policy.decision())["allow_live"])
            await peer.mobile_settings(False)
            await self.set_snapshot("51", "complete")
            disabled = await self.policy.decision()
            self.assertEqual(disabled["reason"], "manual_classic")
            self.assertTrue(disabled["latched"])
            await self.set_snapshot("1", "complete")
            await peer.mobile_settings(True)
            self.assertEqual((await self.policy.decision())["reason"], "monthly_threshold_reached")
        finally:
            await peer.close()

    async def test_monthly_minutes_preserve_migration_and_deduplicate_cumulative_usage(self):
        key = self.policy._identifier("retained-live")
        self.policy.store.put("discord_live_usage", {"sessions": {
            key: {"seconds": "60", "month": "2026-11"}
        }})
        self.assertEqual(await self.policy.mobile_settings(),
                         {"enabled": True, "month": "2026-11", "minutes": 1, "partial": True})
        for seconds in (90, 90, 60):
            await self.policy.record_live_usage("retained-live", {"seconds": seconds}, model="gpt-live-1.1")
        await self.set_snapshot()
        self.assertEqual((await self.policy.mobile_settings())["minutes"], 1.5)
        self.now = datetime(2026, 11, 30, 23, tzinfo=timezone.utc)
        self.assertEqual(await self.policy.mobile_settings(),
                         {"enabled": True, "month": "2026-12", "minutes": 0, "partial": False})
        for seconds in (90, 120, 120):
            await self.policy.record_live_usage("retained-live", {"seconds": seconds}, model="gpt-live-1.1")
        self.assertEqual((await self.policy.mobile_settings())["minutes"], .5)

    async def test_exact_boundary_50_with_complete_fresh_coverage(self):
        await self.set_snapshot("49.99", "complete")
        self.assertTrue((await self.policy.decision())["allow_live"])
        await self.set_snapshot("50", "complete")
        decision = await self.policy.decision()
        self.assertFalse(decision["allow_live"])
        self.assertEqual(decision["threshold_eur"], "50")
        self.assertTrue(decision["latched"])

    async def test_exact_boundary_40_with_bounded_coverage(self):
        await self.set_snapshot("39.99")
        self.assertTrue((await self.policy.decision())["allow_live"])
        await self.set_snapshot("40")
        decision = await self.policy.decision()
        self.assertFalse(decision["allow_live"])
        self.assertEqual(decision["threshold_eur"], "40")

    async def test_45_degrades_then_cannot_flip_back_same_month(self):
        await self.set_snapshot("45", "complete")
        self.assertTrue((await self.policy.decision())["allow_live"])
        await self.set_snapshot("45", "bounded")
        self.assertFalse((await self.policy.decision())["allow_live"])
        await self.set_snapshot("45", "complete")
        self.assertTrue((await self.policy.decision())["latched"])

    async def test_fresh_fetch_without_coverage_watermark_cannot_claim_50(self):
        self.collector.snapshot = self.snapshot("41", "complete")
        self.collector.snapshot.pop("complete_through")
        await self.policy.refresh()
        decision = await self.policy.decision()
        self.assertEqual(decision["threshold_eur"], "40")
        self.assertFalse(decision["allow_live"])

    async def test_restarts_and_downward_adjustments_do_not_clear_latch(self):
        await self.set_snapshot("50", "complete")
        await self.policy.decision()
        await self.policy.close()
        self.policy = DiscordLiveSpendPolicy(self.collector, now=lambda: self.now)
        await self.set_snapshot("1")
        result = await self.policy.decision()
        self.assertTrue(result["latched"])
        self.assertFalse(result["allow_live"])

    async def test_month_resets_at_paris_midnight_only_after_new_snapshot(self):
        await self.set_snapshot("50", "complete")
        await self.policy.decision()
        self.now = datetime(2026, 11, 30, 22, 59, 59, tzinfo=timezone.utc)
        self.assertTrue((await self.policy.decision())["latched"])
        self.now += timedelta(seconds=1)
        result = await self.policy.decision()
        self.assertEqual(result["month"], "2026-12")
        self.assertFalse(result["allow_live"])
        await self.set_snapshot("0", month="2026-12")
        result = await self.policy.decision()
        self.assertTrue(result["allow_live"])
        self.assertFalse(result["latched"])

    async def test_unknown_failed_and_stale_collections_remain_classic(self):
        self.collector.snapshot = {"month": "2026-11", "coverage": "unknown", "reason": "openai_admin_key_missing"}
        await self.policy.refresh()
        self.assertEqual((await self.policy.decision())["reason"], "openai_admin_key_missing")
        await self.set_snapshot("1")
        self.now += timedelta(seconds=331)
        self.assertEqual((await self.policy.decision())["reason"], "spend_stale")

    async def test_negative_nan_missing_cost_never_means_zero(self):
        for bad in (None, "nan", "-1", True):
            await self.set_snapshot(bad)
            result = await self.policy.decision()
            self.assertFalse(result["allow_live"])
            self.assertIn(result["reason"], ("spend_state_unavailable", "spend_collection_failed"))

    async def test_concurrent_decisions_observe_same_threshold_and_durable_latch(self):
        await self.set_snapshot("40")
        decisions = await asyncio.gather(*(self.policy.decision() for _ in range(8)))
        self.assertTrue(all(value["latched"] and not value["allow_live"] for value in decisions))

    async def test_active_live_deltas_trigger_switch_without_waiting_five_minutes(self):
        await self.set_snapshot("39.99")
        self.assertTrue((await self.policy.decision())["allow_live"])
        self.now += timedelta(seconds=20)
        await self.policy.record_live_usage("session-1", {"seconds": 20}, model="gpt-live-1.1")
        result = await self.policy.decision()
        self.assertFalse(result["allow_live"])
        self.assertTrue(result["latched"])

    async def test_live_cumulative_replay_not_added_twice_and_report_replaces_overlay(self):
        await self.set_snapshot("1")
        self.now += timedelta(seconds=60)
        for _ in range(2):
            await self.policy.record_live_usage("session-1", {"seconds": 60}, model="gpt-live-1.1")
        result = await self.policy.decision()
        self.assertEqual(result["spent_eur"], "1.050000000000")
        self.now += timedelta(seconds=1)
        await self.set_snapshot("1.05")
        result = await self.policy.decision()
        self.assertEqual(result["spent_eur"], "1.05")
        self.assertNotIn("live_since_report_estimate_usd", result)
        self.now += timedelta(seconds=60)
        await self.policy.record_live_usage("session-1", {"seconds": 120}, model="gpt-live-1.1")
        self.assertEqual((await self.policy.decision())["spent_eur"], "1.100000000000")

    async def test_unknown_live_usage_is_not_zero(self):
        await self.set_snapshot("1")
        await self.policy.record_live_usage("session-1", {}, model="gpt-live-1.1")
        self.assertFalse((await self.policy.decision())["allow_live"])
        self.now += timedelta(seconds=30)
        await self.set_snapshot("1")
        self.assertFalse((await self.policy.decision())["allow_live"], "fresh GET without a watermark cannot erase unknown usage")

    async def test_new_fetch_without_cost_growth_keeps_observed_live_delta(self):
        await self.set_snapshot("1")
        self.now += timedelta(seconds=60)
        await self.policy.record_live_usage("session-1", {"seconds": 60}, model="gpt-live-1.1")
        self.now += timedelta(seconds=1)
        await self.set_snapshot("1")
        self.assertEqual((await self.policy.decision())["spent_eur"], "1.050000000000")
        self.now += timedelta(seconds=30)
        await self.set_snapshot("1")
        self.assertEqual((await self.policy.decision())["spent_eur"], "1.050000000000")

    async def test_unrelated_tavily_or_exchange_growth_does_not_reconcile_openai_live(self):
        await self.set_snapshot("1")
        self.now += timedelta(seconds=60)
        await self.policy.record_live_usage("session-1", {"seconds": 60}, model="gpt-live-1.1")
        self.now += timedelta(seconds=1)
        self.collector.snapshot = self.snapshot("2")
        self.collector.snapshot["sources"]["openai"]["amounts"]["USD"] = "1"
        await self.policy.refresh()
        self.assertEqual((await self.policy.decision())["spent_eur"], "2.050000000000")

    async def test_runtime_start_is_nonblocking_and_cleanup_stops_refresh(self):
        await self.policy.start()
        await asyncio.sleep(.02)
        self.assertEqual(self.collector.calls, 1)
        await self.policy.close()
        self.assertEqual((await self.policy.decision())["reason"], "spend_policy_stopped")

    async def test_close_joins_inflight_sqlite_refresh_before_releasing_private_files(self):
        await self.set_snapshot("1")
        entered, finished = asyncio.Event(), asyncio.Event()
        release = threading.Event()
        loop = asyncio.get_running_loop()
        original = self.policy._reconcile_snapshot_sync

        def slow_sqlite(snapshot):
            # Windows cannot remove this private file while the worker owns it.
            # The barrier makes the same ownership race deterministic on Linux.
            try:
                with closing(self.policy.store.connect()) as db:
                    db.execute("SELECT value FROM global_spend_state LIMIT 1").fetchone()
                    loop.call_soon_threadsafe(entered.set)
                    if not release.wait(2):
                        raise AssertionError("test did not release SQLite worker")
                return original(snapshot)
            finally:
                loop.call_soon_threadsafe(finished.set)

        self.policy._reconcile_snapshot_sync = slow_sqlite
        self.now += timedelta(seconds=331)
        self.assertEqual((await self.policy.decision())["reason"], "spend_stale")
        await asyncio.wait_for(entered.wait(), 1)
        closing_task = asyncio.create_task(self.policy.close())
        try:
            await asyncio.sleep(.02)
            self.assertFalse(closing_task.done(), "close returned while SQLite still owned the private file")
            self.assertFalse(finished.is_set())
        finally:
            release.set()
            await asyncio.wait_for(closing_task, 1)
            await asyncio.wait_for(finished.wait(), 1)

    async def reserve(self, attempt="attempt-1", policy=None):
        return await (policy or self.policy).reserve_live(attempt, model="gpt-live-1.1",
            opening_seconds=8, close_seconds=5, control_seconds=1)

    async def test_reservations_are_atomic_across_independent_policy_instances(self):
        await self.set_snapshot("39.98")
        peer = DiscordLiveSpendPolicy(self.collector, now=lambda: self.now)
        try:
            await peer.refresh()
            decisions = await asyncio.gather(self.reserve("first"), self.reserve("second", peer))
            self.assertEqual(sum(value["allow_live"] for value in decisions), 1)
            denied = next(value for value in decisions if not value["allow_live"])
            self.assertEqual(denied["reason"], "live_reservation_insufficient")
            self.assertFalse(denied["latched"])
            self.assertEqual((await self.policy.decision())["outstanding_live_reservations"], 1)
        finally:
            await peer.close()

    async def test_insufficient_guard_is_not_consumption_and_does_not_latch_month(self):
        await self.set_snapshot("39.995")
        result = await self.reserve()
        self.assertFalse(result["allow_live"])
        self.assertEqual(result["reason"], "live_reservation_insufficient")
        self.assertEqual(result["spent_eur"], "39.995")
        self.assertFalse(result["latched"])
        self.assertEqual(result["outstanding_live_reservations"], 0)
        self.assertEqual((await self.policy.decision())["reason"], "live_reservation_insufficient")
        await self.set_snapshot("39")
        self.assertTrue((await self.policy.decision())["allow_live"])

    async def test_reservation_idempotence_bind_and_unstarted_release(self):
        await self.set_snapshot("1")
        first = await self.reserve()
        second = await self.reserve()
        self.assertEqual(first["reserved_eur"], second["reserved_eur"])
        self.assertEqual(second["outstanding_live_reservations"], 1)
        await self.policy.settle_live("attempt-1", never_started=True, model="gpt-live-1.1")
        self.assertEqual((await self.policy.decision())["outstanding_live_reservations"], 0)
        self.assertEqual((await self.reserve())["reason"], "live_reservation_already_settled")
        await self.reserve("attempt-2")
        await self.policy.bind_live("attempt-2", "session-2")
        self.assertEqual(Decimal((await self.policy.decision())["reserved_eur"]), Decimal("0.005"))

    async def test_outstanding_commitments_survive_restart_and_paris_month_change(self):
        self.now = datetime(2026, 11, 30, 22, 59, 59, tzinfo=timezone.utc)
        await self.set_snapshot("1")
        self.assertTrue((await self.reserve())["allow_live"])
        await self.policy.close()
        self.policy = DiscordLiveSpendPolicy(self.collector, now=lambda: self.now)
        self.now += timedelta(seconds=2)
        await self.set_snapshot("0", month="2026-12")
        result = await self.policy.decision()
        self.assertEqual(result["month"], "2026-12")
        self.assertEqual(result["outstanding_live_reservations"], 1)
        self.assertGreater(Decimal(result["exposure_eur"]), 0)
        self.assertEqual(result["spent_eur"], "0")

    async def test_missing_terminal_remains_unknown_across_restart_month_and_fresh_get(self):
        await self.set_snapshot("1")
        await self.reserve()
        await self.policy.settle_live("attempt-1", confirmed=False, session_id="s1", usage={}, model="gpt-live-1.1")
        await self.policy.close()
        self.policy = DiscordLiveSpendPolicy(self.collector, now=lambda: self.now)
        self.now = datetime(2026, 12, 1, 12, tzinfo=timezone.utc)
        await self.set_snapshot("0", month="2026-12")
        self.assertEqual((await self.policy.decision())["reason"], "live_reservation_unknown")
        await self.policy.settle_live("attempt-1", confirmed=True, session_id="s1",
                                      usage={"seconds": 2}, model="gpt-live-1.1")
        self.assertTrue((await self.policy.decision())["allow_live"])

    async def test_wall_clock_exposure_closes_headroom_without_usage_event_cadence(self):
        await self.set_snapshot("39.98")
        self.assertTrue((await self.reserve())["allow_live"])
        await self.policy.bind_live("attempt-1", "s1")
        self.now += timedelta(seconds=20)
        result = await self.policy.decision()
        self.assertFalse(result["allow_live"])
        self.assertEqual(result["reason"], "live_reservation_insufficient")
        self.assertEqual(result["spent_eur"], "39.98")
        self.assertGreater(Decimal(result["unreported_live_exposure_eur"]), 0)
        self.assertFalse(result["latched"])

    async def test_confirmed_zero_usage_replaces_wall_exposure_without_fabricated_charge(self):
        await self.set_snapshot("39.98")
        await self.reserve()
        await self.policy.bind_live("attempt-1", "s1")
        self.now += timedelta(seconds=20)
        self.assertFalse((await self.policy.decision())["allow_live"])
        await self.policy.settle_live("attempt-1", confirmed=True, session_id="s1",
                                      usage={"seconds": 0}, model="gpt-live-1.1")
        result = await self.policy.decision()
        self.assertEqual(result["spent_eur"], "39.98")
        self.assertEqual(result["reserved_eur"], "0")
        self.assertEqual(result["unreported_live_exposure_eur"], "0")
        self.assertFalse(result["latched"])
        self.assertTrue(result["allow_live"])

    async def test_terminal_usage_settlement_is_atomic_and_idempotent_after_restart(self):
        await self.set_snapshot("1")
        await self.reserve()
        await self.policy.bind_live("attempt-1", "s1")
        await self.policy.record_live_usage("s1", {"seconds": 20}, model="gpt-live-1.1")
        self.now += timedelta(seconds=60)
        await self.policy.settle_live("attempt-1", confirmed=True, session_id="s1",
                                      usage={"seconds": 60}, model="gpt-live-1.1")
        expected = (await self.policy.decision())["spent_eur"]
        self.assertLessEqual(abs(Decimal(expected) - Decimal("1.05")), Decimal("0.000000000002"))
        await self.policy.close()
        self.policy = DiscordLiveSpendPolicy(self.collector, now=lambda: self.now)
        await self.set_snapshot("1")
        await self.policy.settle_live("attempt-1", confirmed=True, session_id="s1",
                                      usage={"seconds": 60}, model="gpt-live-1.1")
        self.assertEqual((await self.policy.decision())["spent_eur"], expected)
        self.assertEqual((await self.policy.decision())["outstanding_live_reservations"], 0)

    async def test_confirmed_close_without_usage_never_invents_zero_consumption(self):
        await self.set_snapshot("1")
        await self.reserve()
        await self.policy.bind_live("attempt-1", "s1")
        await self.policy.settle_live("attempt-1", confirmed=True, session_id="s1",
                                      usage={}, model="gpt-live-1.1")
        result = await self.policy.decision()
        self.assertFalse(result["allow_live"])
        await self.set_snapshot("1")
        self.assertFalse((await self.policy.decision())["allow_live"])

    async def test_unstarted_claim_cannot_release_already_bound_session(self):
        await self.set_snapshot("1")
        await self.reserve()
        await self.policy.bind_live("attempt-1", "s1")
        await self.policy.settle_live("attempt-1", never_started=True, model="gpt-live-1.1")
        result = await self.policy.decision()
        self.assertEqual(result["outstanding_live_reservations"], 1)
        self.assertEqual(result["reason"], "live_reservation_unknown")

    async def test_unknown_price_or_missing_fx_never_reserves_or_starts(self):
        await self.set_snapshot("1")
        result = await self.policy.reserve_live("bad", model="future-live", opening_seconds=8,
                                                close_seconds=5, control_seconds=1)
        self.assertFalse(result["allow_live"])
        self.collector.snapshot["fx"] = {}
        await self.policy.refresh()
        self.assertFalse((await self.reserve())["allow_live"])

    async def test_peer_refresh_does_not_erase_another_instances_observed_usage(self):
        await self.set_snapshot("1")
        peer = DiscordLiveSpendPolicy(self.collector, now=lambda: self.now)
        try:
            await peer.refresh()
            self.now += timedelta(seconds=60)
            await self.policy.record_live_usage("s1", {"seconds": 60}, model="gpt-live-1.1")
            self.collector.snapshot = self.snapshot("1")
            await peer.refresh()
            self.assertEqual(Decimal((await self.policy.decision())["spent_eur"]), Decimal("1.05"))
        finally:
            await peer.close()

    async def test_peer_admission_uses_same_shared_base_as_reconciled_overlay(self):
        await self.set_snapshot("39.96")
        old_collector = Collector(self.path, self.snapshot("39.96"))
        peer = DiscordLiveSpendPolicy(old_collector, now=lambda: self.now)
        try:
            await peer.refresh()
            self.now += timedelta(seconds=60)
            await self.policy.record_live_usage("s1", {"seconds": 60}, model="gpt-live-1.1")
            self.now += timedelta(seconds=1)
            await self.set_snapshot("40.01")
            # Even an older GET completing later cannot restore the old base.
            await peer.refresh()
            decision = await self.reserve("second-instance", peer)
            self.assertFalse(decision["allow_live"])
            self.assertEqual(decision["reason"], "monthly_threshold_reached")
            self.assertTrue(decision["latched"])
        finally:
            await peer.close()

    async def test_pending_session_counters_survive_other_sessions_month_rollover(self):
        self.now = datetime(2026, 11, 30, 22, 59, 59, tzinfo=timezone.utc)
        await self.set_snapshot("1")
        for index in (1, 2):
            await self.reserve(f"attempt-{index}")
            await self.policy.bind_live(f"attempt-{index}", f"s{index}")
            await self.policy.record_live_usage(f"s{index}", {"seconds": 60}, model="gpt-live-1.1")
        self.now += timedelta(seconds=2)
        await self.set_snapshot("0", month="2026-12")
        for index in (1, 2):
            await self.policy.record_live_usage(f"s{index}", {"seconds": 61}, model="gpt-live-1.1")
        result = await self.policy.decision()
        self.assertLess(Decimal(result["spent_eur"]), Decimal("0.002"))
        self.assertEqual(result["outstanding_live_reservations"], 2)


if __name__ == "__main__":
    unittest.main()
