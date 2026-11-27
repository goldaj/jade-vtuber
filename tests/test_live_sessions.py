"""Offline lifecycle acceptance tests: real private ledgers, fake media/provider.

These tests prove software admission and cleanup contracts. They do not prove
Android microphone behavior, the provider's shutdown delay or invoice totals.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from src.jade_runtime.live_usage import LiveUsageLedger, quote_voice
from src.jade_runtime.live_config import LiveConfig
from src.jade_runtime.live_provider import LiveProviderError
from src.jade_runtime.live_sessions import LiveSessionError, LiveSessionManager, ProviderSession


OWNER = "verified-mobile-owner"
CLIENT = "client_primary"
THREAD = "thread_primary"
SDP = ("v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
       "a=fingerprint:sha-256 00\r\na=ice-ufrag:unit\r\n")


class FakeClock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds

    def utc(self):
        return datetime(2026, 11, 26, 12, tzinfo=timezone.utc) + timedelta(seconds=self.value - 1000)


class FakeChannel:
    def __init__(self, provider, session_id):
        self.provider, self.session_id = provider, session_id
        self.queue = asyncio.Queue()
        self.transport_closed = False

    async def send(self, event):
        self.provider.commands.append((self.session_id, dict(event)))
        if event["type"] == "session.close":
            self.provider.close_requested.set()
            await self.provider.send_gate.wait()
            if self.provider.close_ack:
                terminal = {"type": "session.closed", "event_id": f"closed-{self.session_id}",
                            "reason": "close_requested"}
                if self.provider.final_usage is not None:
                    terminal["usage"] = dict(self.provider.final_usage)
                await self.queue.put(terminal)

    async def close(self):
        self.transport_closed = True
        await self.queue.put(None)

    async def __aiter__(self):
        while True:
            event = await self.queue.get()
            if event is None:
                return
            yield event


class FakeLiveProvider:
    def __init__(self):
        self.creations = []
        self.commands = []
        self.channels = {}
        self.create_entered = asyncio.Event()
        self.create_gate = asyncio.Event()
        self.create_gate.set()
        self.send_gate = asyncio.Event()
        self.send_gate.set()
        self.cleanup_gate = asyncio.Event()
        self.cleanup_gate.set()
        self.cleanup_entered = asyncio.Event()
        self.close_requested = asyncio.Event()
        self.create_error = None
        self.emit_started = True
        self.close_ack = True
        self.final_usage = {"seconds": 15, "active_seconds": 15, "paused_seconds": 0}

    async def create_session(self, sdp, session_config):
        self.creations.append((sdp, session_config))
        self.create_entered.set()
        await self.create_gate.wait()
        if self.create_error is not None:
            raise self.create_error
        return {"session_id": f"live_fake_{len(self.creations)}", "sdp": SDP, "expires_at": None}

    @asynccontextmanager
    async def attach(self, session_id):
        channel = FakeChannel(self, session_id)
        self.channels.setdefault(session_id, []).append(channel)
        if self.emit_started:
            await channel.queue.put({"type": "session.started", "event_id": f"started-{session_id}",
                                     "session": {"id": session_id}})
        try:
            yield channel
        finally:
            self.cleanup_entered.set()
            await self.cleanup_gate.wait()
            await channel.close()

    async def emit(self, session_id, event):
        await self.channels[session_id][-1].queue.put(event)


class DelayedContextBridge:
    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def prepare_context(self, owner, thread_id):
        self.entered.set()
        await self.release.wait()
        return {}


class LiveSessionManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.provider = FakeLiveProvider()
        self.config = replace(
            LiveConfig(), usage_db_path=str(Path(self.temp.name) / "usage.sqlite3"),
            session_db_path=str(Path(self.temp.name) / "sessions.sqlite3"),
            heartbeat_seconds=0.5, lease_seconds=2.0,
            opening_timeout_seconds=1.0, close_timeout_seconds=1.0,
            idle_standby_seconds=5, idle_close_seconds=6.0,
            muted_drain_seconds=3.0, max_session_seconds=15.0,
        )
        self.ledger = LiveUsageLedger(self.config.usage_db_path, now=self.clock.utc)
        self.manager = LiveSessionManager(self.config, self.provider, self.ledger, clock=self.clock)
        self.managers = [self.manager]
        self.original_save = self.manager.registry.save
        self.seq = 0

    async def asyncTearDown(self):
        self.provider.create_gate.set()
        self.provider.send_gate.set()
        self.provider.cleanup_gate.set()
        self.provider.close_ack = True
        self.manager.registry.save = self.original_save
        if isinstance(self.manager.bridge, DelayedContextBridge):
            self.manager.bridge.release.set()
        for manager in reversed(self.managers):
            await asyncio.wait_for(manager.stop(), 5)
        self.temp.cleanup()

    async def until(self, predicate, *, timeout=2):
        deadline = asyncio.get_running_loop().time() + timeout
        while not predicate():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail("Expected Live state was not reached within the test deadline")
            await asyncio.sleep(0.005)

    async def enable(self):
        preference = await self.manager.preferences(OWNER)
        return await self.manager.set_mode(OWNER, "live", preference["revision"])

    async def arm(self, *, subscribe=True):
        await self.enable()
        state = await self.manager.arm(OWNER, CLIENT, THREAD)
        self.lease_id = state["lease_id"]
        if subscribe:
            self.control_token, self.control_queue = await self.manager.subscribe(OWNER, CLIENT, self.lease_id)
        return state

    async def create(self, request_id="request_primary"):
        result = await self.manager.create_session(OWNER, CLIENT, THREAD, self.lease_id, request_id, SDP)
        self.session = self.manager._sessions[result["session_id"]]
        return result

    async def heartbeat(self, *, capture="armed", visible=True, speech=False, playback=False):
        event = {"seq": self.seq, "visible": visible, "capture": capture,
                 "speech_active": speech, "playback_active": playback}
        self.seq += 1
        return await self.manager.heartbeat(OWNER, CLIENT, self.lease_id, event)

    async def test_default_live_and_profile_preference_open_no_session_or_microphone(self):
        self.assertEqual(await self.manager.preferences(OWNER), {"mode": "live", "revision": 0})
        await self.manager.start()
        result = await self.enable()
        self.assertEqual(result, {"mode": "live", "revision": 1})
        self.assertEqual(self.provider.creations, [])
        self.assertEqual(self.ledger.snapshot()["open_records"], 0)
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")

    async def test_admission_checks_explicit_off_flags_and_key_before_arming(self):
        await self.manager.set_mode(OWNER, "classic", 0)
        with self.assertRaises(LiveSessionError) as raised:
            await self.manager.arm(OWNER, CLIENT, THREAD)
        self.assertEqual(raised.exception.code, "live_mode_off")
        await self.enable()
        self.manager.config = replace(self.config, enabled=False)
        with self.assertRaises(LiveSessionError):
            await self.manager.arm(OWNER, CLIENT, THREAD)
        self.manager.config = self.config
        self.manager.api_key_present = False
        with self.assertRaises(LiveSessionError):
            await self.manager.arm(OWNER, CLIENT, THREAD)
        self.manager.api_key_present = True
        self.assertEqual(self.provider.creations, [])
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")

    async def test_saved_classic_preference_survives_restart_despite_live_default(self):
        await self.manager.set_mode(OWNER, "classic", 0)
        await self.manager.stop()
        restarted = LiveSessionManager(self.config, self.provider, self.ledger, clock=self.clock)
        self.managers.append(restarted)
        await restarted.start()
        self.assertEqual(await restarted.preferences(OWNER), {"mode": "classic", "revision": 1})
        with self.assertRaises(LiveSessionError) as raised:
            await restarted.arm(OWNER, CLIENT, THREAD)
        self.assertEqual(raised.exception.code, "live_mode_off")
        self.assertEqual(self.provider.creations, [])

    async def test_exclusive_arming_and_foreign_lease_refusal(self):
        await self.enable()
        outcomes = await asyncio.gather(
            self.manager.arm(OWNER, "client_first", THREAD),
            self.manager.arm(OWNER, "client_second", THREAD), return_exceptions=True)
        self.assertEqual(sum(isinstance(value, dict) for value in outcomes), 1)
        self.assertEqual(sum(isinstance(value, LiveSessionError) for value in outcomes), 1)
        lease = self.manager._leases[OWNER]
        with self.assertRaises(LiveSessionError):
            await self.manager.subscribe("different-owner", lease.client_id, lease.lease_id)
        with self.assertRaises(LiveSessionError):
            await self.manager.subscribe(OWNER, "client_foreign", lease.lease_id)
        self.assertEqual(self.provider.creations, [])

    async def test_heartbeat_replay_is_rejected_and_expiry_closes_arm(self):
        await self.arm()
        await self.heartbeat()
        with self.assertRaises(LiveSessionError) as raised:
            await self.manager.heartbeat(OWNER, CLIENT, self.lease_id,
                                         {"seq": 0, "visible": True, "capture": "armed"})
        self.assertEqual(raised.exception.code, "stale_live_heartbeat")
        self.clock.advance(self.config.lease_seconds)
        await self.manager.tick()
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")
        with self.assertRaises(LiveSessionError):
            await self.create()
        self.assertEqual(self.provider.creations, [])

    async def test_creation_requires_control_subscription_and_valid_sdp(self):
        await self.arm(subscribe=False)
        with self.assertRaises(LiveSessionError) as raised:
            await self.create()
        self.assertEqual(raised.exception.code, "live_control_required")
        await self.manager.subscribe(OWNER, CLIENT, self.lease_id)
        with self.assertRaises(LiveSessionError) as raised:
            await self.manager.create_session(OWNER, CLIENT, THREAD, self.lease_id,
                                              "request_invalid", "not sdp")
        self.assertEqual(raised.exception.code, "invalid_sdp")
        self.assertEqual(self.ledger.snapshot()["open_records"], 0)
        self.assertEqual(self.provider.creations, [])

    async def test_concurrent_duplicate_create_shares_one_billable_call(self):
        await self.arm()
        self.provider.create_gate.clear()
        first = asyncio.create_task(self.create())
        await self.provider.create_entered.wait()
        second = asyncio.create_task(self.create())
        await asyncio.sleep(0.01)
        self.provider.create_gate.set()
        results = await asyncio.gather(first, second)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.provider.creations), 1)
        self.assertEqual(self.ledger.snapshot()["open_records"], 1)
        self.assertNotEqual(results[0]["session_id"], self.session.provider_id)
        with self.assertRaises(LiveSessionError):
            await self.manager.create_session(OWNER, CLIENT, THREAD, self.lease_id,
                                              "request_primary", SDP + "a=sendrecv\r\n")
        self.assertEqual(len(self.provider.creations), 1)

    async def test_off_during_creation_closes_late_result_without_returning_live_answer(self):
        await self.arm()
        self.provider.create_gate.clear()
        opening = asyncio.create_task(self.create())
        await self.provider.create_entered.wait()
        await self.manager.set_mode(OWNER, "classic", 1)
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")
        self.provider.create_gate.set()
        with self.assertRaises(LiveSessionError):
            await opening
        session = next(iter(self.manager._sessions.values()))
        await asyncio.wait_for(session.closed.wait(), 2)
        self.assertTrue(self.provider.close_requested.is_set())
        self.assertEqual(len(self.provider.creations), 1)
        self.assertEqual(self.manager.snapshot(OWNER)["mode"], "classic")
        with self.assertRaises(LiveSessionError):
            await self.manager.set_mode(OWNER, "live", 0)

    async def test_timed_out_creation_is_not_retried_and_late_id_is_closed(self):
        await self.arm()
        self.provider.create_gate.clear()
        with self.assertRaises(LiveSessionError) as raised:
            await self.create()
        self.assertEqual(raised.exception.code, "live_opening_timeout")
        self.assertEqual(self.manager.snapshot(OWNER)["session_state"], "opening_unknown")
        self.provider.create_gate.set()
        session = next(iter(self.manager._sessions.values()))
        await asyncio.wait_for(session.closed.wait(), 2)
        self.assertTrue(self.provider.close_requested.is_set())
        self.assertEqual(len(self.provider.creations), 1)

    async def test_lease_expired_during_context_preparation_prevents_provider_creation(self):
        bridge = DelayedContextBridge()
        self.manager.bridge = bridge
        await self.arm()
        opening = asyncio.create_task(self.create())
        await bridge.entered.wait()
        self.clock.advance(self.config.lease_seconds + 0.1)
        bridge.release.set()
        with self.assertRaises(LiveSessionError):
            await opening
        self.assertEqual(self.provider.creations, [])
        self.assertEqual(self.ledger.snapshot()["open_records"], 0)

    async def test_usage_replay_and_finalization_keep_cumulative_total(self):
        await self.arm()
        await self.create()
        for event_id, seconds in (("usage_12", 12), ("usage_15", 15), ("usage_15", 15), ("usage_old", 12)):
            await self.provider.emit(self.session.provider_id,
                                     {"type": "session.usage.updated", "event_id": event_id,
                                      "usage": {"seconds": seconds}})
        await self.until(lambda: self.session.usage_seconds == 15)
        await self.manager.close(OWNER, CLIENT, self.lease_id)
        await self.until(lambda: self.ledger.reservation(self.session.reservation_id)["state"] == "closed")
        row = self.ledger.reservation(self.session.reservation_id)
        self.assertEqual(Decimal(row["seconds"]), 15)
        self.assertEqual(Decimal(row["spent_usd"]), quote_voice(15))
        self.assertEqual(self.ledger.snapshot()["open_records"], 0)

    async def test_background_heartbeat_stops_capture_and_provider(self):
        await self.arm()
        await self.create()
        await self.heartbeat(visible=False)
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")
        self.assertTrue(self.provider.close_requested.is_set())
        self.assertTrue(self.session.closed.is_set())

    async def test_closure_works_after_flags_are_disabled_and_usage_is_unavailable(self):
        await self.arm()
        await self.create()
        self.manager.config = replace(self.config, enabled=False, mobile_enabled=False)
        self.manager.usage = None
        await self.manager.close(OWNER, CLIENT, self.lease_id)
        self.assertTrue(self.provider.close_requested.is_set())
        self.assertTrue(self.session.closed.is_set())

    async def test_idle_closes_provider_but_preserves_armed_lease_for_new_speech(self):
        await self.arm()
        await self.create()
        await self.until(lambda: self.session.started.is_set())
        previous = self.session
        for _ in range(6):
            self.clock.advance(1)
            await self.heartbeat()
            await self.manager.tick()
        await asyncio.wait_for(previous.closed.wait(), 2)
        await self.until(lambda: self.manager.snapshot(OWNER)["session_state"] == "absent")
        state = self.manager.snapshot(OWNER)
        self.assertEqual(state["lease_state"], "armed")
        self.assertEqual(state["lease_id"], self.lease_id)
        await self.create("request_after_idle")
        self.assertEqual(len(self.provider.creations), 2)
        self.assertNotEqual(self.session.provider_id, previous.provider_id)

    async def test_mute_drain_deadline_never_extends_with_repeat_or_heartbeat(self):
        await self.arm()
        await self.create()
        await self.heartbeat(speech=True)
        await self.manager.close(OWNER, CLIENT, self.lease_id, reason="mute", drain=True)
        deadline = self.manager._leases[OWNER].drain_deadline
        self.clock.advance(1)
        await self.heartbeat(capture="closed")
        await self.manager.close(OWNER, CLIENT, self.lease_id, reason="mute", drain=True)
        self.assertEqual(self.manager._leases[OWNER].drain_deadline, deadline)
        self.clock.advance(1)
        await self.heartbeat(capture="closed")
        self.clock.advance(1)
        await self.heartbeat(capture="closed")
        await self.manager.tick()
        await asyncio.wait_for(self.session.closed.wait(), 2)
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")

    async def test_missing_started_replay_does_not_prevent_cleanup(self):
        self.provider.emit_started = False
        await self.arm()
        await self.create()
        self.assertFalse(self.session.started.is_set())
        await self.manager.close(OWNER, CLIENT, self.lease_id)
        self.assertTrue(self.session.closed.is_set())
        self.assertTrue(self.provider.close_requested.is_set())

    async def test_resumed_without_started_replay_allows_backend_context_delivery(self):
        self.provider.emit_started = False
        await self.arm()
        await self.create()
        self.assertFalse(self.session.started.is_set())
        await self.provider.emit(self.session.provider_id,
                                 {"type": "session.resumed", "event_id": "resumed_after_attach"})
        await self.until(lambda: self.session.phase == "active")
        event = {"type": "session.thinking.append", "event_id": "backend_context",
                 "delegation_id": None, "content": "The verified result is ready."}
        await self.manager.send(self.session.handle, event)
        self.assertIn((self.session.provider_id, event), self.provider.commands)

    async def test_off_stops_active_live_even_when_preference_persistence_fails(self):
        await self.arm()
        await self.create()
        with patch.object(self.manager.registry, "set_mode",
                          side_effect=sqlite3.OperationalError("test preference disk failure")):
            with self.assertRaises(LiveSessionError) as raised:
                await self.manager.set_mode(OWNER, "classic", 1)
        self.assertEqual(raised.exception.status, 503)
        self.assertTrue(self.provider.close_requested.is_set())
        self.assertTrue(self.session.closed.is_set())
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")
        self.assertFalse((await self.manager.capabilities(OWNER))["available"])

    async def test_missing_terminal_blocks_reopening_for_session_safety_not_cost(self):
        self.provider.close_ack = False
        await self.arm()
        await self.create()
        await self.manager.close(OWNER, CLIENT, self.lease_id)
        self.assertEqual(self.session.phase, "close_unconfirmed")
        self.assertFalse(self.session.closed.is_set())
        self.assertEqual(self.ledger.reservation(self.session.reservation_id)["state"], "unknown")
        self.assertEqual(self.ledger.snapshot()["unknown_records"], 1)
        with self.assertRaises(LiveSessionError):
            await self.manager.arm(OWNER, CLIENT, THREAD)
        self.assertEqual(len(self.provider.creations), 1)

    async def test_explicit_recovery_retires_lost_generation_and_keeps_usage_unknown(self):
        self.provider.close_ack = False
        await self.arm()
        await self.create()
        old_session = self.session
        await self.manager.close(OWNER, CLIENT, self.lease_id)
        await self.until(lambda: self.manager.snapshot(OWNER)["recovery_allowed"])
        provider_calls = list(self.provider.commands)

        # Toggling OFF need not relaunch reconciliation already exhausted for
        # this connection. Recovery itself does not change the preference.
        saved = await self.manager.set_mode(OWNER, "classic", 1)
        self.assertEqual(self.provider.commands, provider_calls)
        state = await self.manager.recover(OWNER)
        self.assertEqual(state["mode"], "classic")
        self.assertEqual(state["session_state"], "absent")
        self.assertEqual(state["lease_state"], "closed")
        self.assertEqual(old_session.phase, "retired_unconfirmed")
        self.assertFalse(old_session.closed.is_set())
        self.assertEqual(self.ledger.reservation(old_session.reservation_id)["state"], "unknown")
        self.assertFalse(self.manager.registry.pending())
        with closing(sqlite3.connect(self.config.session_db_path)) as db:
            self.assertEqual(db.execute("SELECT phase FROM live_sessions WHERE handle=?",
                                        (old_session.handle,)).fetchone(), ("retired_unconfirmed",))
        self.assertEqual(len(self.provider.creations), 1)

        self.provider.close_ack = True
        await self.manager.set_mode(OWNER, "live", saved["revision"])
        lease = await self.manager.arm(OWNER, CLIENT, THREAD)
        await self.manager._provider_event(old_session, {"type": "error"})
        self.assertEqual(self.manager.snapshot(OWNER)["lease_id"], lease["lease_id"])
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "armed")
        await self.manager.stop()

        restarted = LiveSessionManager(self.config, self.provider, self.ledger, clock=self.clock)
        self.managers.append(restarted)
        await restarted.start()
        self.assertTrue((await restarted.capabilities(OWNER))["available"])
        self.assertEqual(self.provider.commands, provider_calls)

    async def test_close_in_flight_is_reported_and_cannot_be_retired(self):
        await self.arm()
        await self.create()
        self.provider.send_gate.clear()
        close = asyncio.create_task(self.manager.close(OWNER, CLIENT, self.lease_id))
        try:
            await asyncio.wait_for(self.provider.close_requested.wait(), timeout=1)
            caps = await self.manager.capabilities(OWNER)
            self.assertEqual(caps["state"]["session_state"], "closing")
            self.assertFalse(caps["state"]["recovery_allowed"])
            self.assertEqual(caps["reason"], "previous_session_not_closed")
            with self.assertRaises(LiveSessionError) as raised:
                await self.manager.recover(OWNER)
            self.assertEqual(raised.exception.code, "previous_session_not_closed")
        finally:
            self.provider.send_gate.set()
            await close

    async def test_missing_final_usage_preserves_cost_uncertainty_after_confirmed_close(self):
        self.provider.final_usage = None
        await self.arm()
        await self.create()
        await self.manager.close(OWNER, CLIENT, self.lease_id)
        await self.until(lambda: self.ledger.reservation(self.session.reservation_id)["state"] == "unknown")
        self.assertTrue(self.session.closed.is_set())
        self.assertEqual(self.session.phase, "closed")
        self.assertEqual(self.ledger.snapshot()["unknown_records"], 1)
        self.assertTrue((await self.manager.capabilities(OWNER))["available"])
        await self.arm()
        await self.create("request_without_known_cost")
        self.assertEqual(len(self.provider.creations), 2)

    async def test_unknown_creation_survives_restart_without_automatic_retry(self):
        self.provider.create_error = LiveProviderError("offline_timeout", ambiguous=True)
        await self.arm()
        with self.assertRaises(LiveSessionError):
            await self.create()
        self.assertEqual(self.manager.snapshot(OWNER)["session_state"], "opening_unknown")
        await self.manager.stop()
        restarted = LiveSessionManager(self.config, self.provider, self.ledger, clock=self.clock)
        self.managers.append(restarted)
        await restarted.start()
        self.assertFalse((await restarted.capabilities(OWNER))["available"])
        with self.assertRaises(LiveSessionError):
            await restarted.arm(OWNER, CLIENT, THREAD)
        with self.assertRaises(LiveSessionError) as raised:
            await restarted.recover(OWNER)
        self.assertEqual(raised.exception.code, "close_unconfirmed")
        self.assertEqual(len(self.provider.creations), 1)
        self.assertEqual(self.ledger.snapshot()["unknown_records"], 1)

    async def test_concurrent_start_waits_for_persistent_reconciliation(self):
        await self.enable()
        self.ledger.reserve("voice:previous", ".1")
        previous = ProviderSession("previous_handle", OWNER, CLIENT, THREAD,
                                   "previous_lease", "previous_generation", "voice:previous",
                                   self.clock(), self.clock(), phase="opening_unknown")
        self.manager.registry.save(previous)
        entered, release = threading.Event(), threading.Event()
        original_pending = self.manager.registry.pending

        def delayed_pending():
            entered.set()
            if not release.wait(2):
                raise TimeoutError("test recovery gate")
            return original_pending()

        self.manager.registry.pending = delayed_pending
        first = asyncio.create_task(self.manager.arm(OWNER, CLIENT, THREAD))
        try:
            await self.until(entered.is_set)
            second = asyncio.create_task(self.manager.arm(OWNER, "client_other", THREAD))
            await asyncio.sleep(0.02)
            self.assertFalse(first.done())
            self.assertFalse(second.done())
        finally:
            release.set()
        outcomes = await asyncio.gather(first, second, return_exceptions=True)
        self.assertTrue(all(isinstance(value, LiveSessionError) for value in outcomes))
        self.assertEqual(self.provider.creations, [])

    async def test_registry_save_failure_never_blocks_provider_close(self):
        await self.arm()
        await self.create()
        self.manager.registry.save = Mock(side_effect=sqlite3.OperationalError("test disk failure"))
        await self.manager.close(OWNER, CLIENT, self.lease_id)
        await self.until(self.provider.close_requested.is_set)
        self.assertTrue(self.session.closed.is_set())
        self.assertFalse((await self.manager.capabilities(OWNER))["available"])

    async def test_registry_failure_after_http_success_still_closes_known_provider_id(self):
        await self.arm()

        def fail_after_http(session):
            if session.provider_id:
                raise sqlite3.OperationalError("test post-create disk failure")
            self.original_save(session)

        self.manager.registry.save = fail_after_http
        with self.assertRaises(LiveSessionError):
            await self.create()
        session = next(iter(self.manager._sessions.values()))
        await asyncio.wait_for(session.closed.wait(), 2)
        self.assertEqual(session.provider_id, "live_fake_1")
        self.assertTrue(self.provider.close_requested.is_set())
        self.assertFalse((await self.manager.capabilities(OWNER))["available"])

    async def test_duration_limit_closes_even_with_fresh_heartbeat_and_audio_activity(self):
        await self.arm()
        await self.create()
        await self.until(lambda: self.session.started.is_set())
        for _ in range(15):
            self.clock.advance(1)
            await self.heartbeat(playback=True)
            await self.manager.tick()
        await asyncio.wait_for(self.session.closed.wait(), 2)
        self.assertEqual(self.session.reason, "live_duration_limit")
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")
        self.assertEqual(len(self.provider.creations), 1)

    async def test_creation_rate_limit_suspends_the_arm_without_a_fourth_call(self):
        for index in range(3):
            await self.arm()
            await self.create(f"request_loop_{index}")
            await self.manager.close(OWNER, CLIENT, self.lease_id)
            await self.until(lambda: self.manager.snapshot(OWNER)["session_state"] == "absent")
        await self.arm()
        with self.assertRaises(LiveSessionError) as raised:
            await self.create("request_loop_four")
        self.assertEqual(raised.exception.code, "live_start_rate_limit")
        self.assertEqual(len(self.provider.creations), 3)
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")
        self.assertEqual(self.ledger.snapshot()["open_records"], 0)

    async def test_control_disconnect_closes_without_waiting_for_heartbeat_expiry(self):
        await self.arm()
        await self.create()
        await self.manager.unsubscribe(OWNER, self.control_token)
        self.assertTrue(self.session.closed.is_set())
        self.assertEqual(self.session.reason, "control_disconnected")
        self.assertEqual(self.manager.snapshot(OWNER)["lease_state"], "closed")

    async def test_receiver_cleanup_is_bounded_when_terminal_is_missing(self):
        self.provider.close_ack = False
        await self.arm()
        await self.create()
        self.provider.cleanup_gate.clear()
        started = asyncio.get_running_loop().time()
        try:
            await asyncio.wait_for(self.manager.close(OWNER, CLIENT, self.lease_id), 2)
            self.assertEqual(self.session.phase, "close_unconfirmed")
            self.assertLess(asyncio.get_running_loop().time() - started, 2)
        finally:
            self.provider.cleanup_gate.set()

    async def test_backend_operations_are_allowed_without_any_financial_configuration(self):
        await self.arm()
        await self.create()
        context = self.manager._context(self.session)
        self.assertTrue(self.manager._valid(self.session))
        self.assertEqual(self.ledger.snapshot()["open_records"], 1)
        reservation = await self.manager.reserve_delegation(context, "delegation_allowed")
        self.assertIsInstance(reservation, str)
        self.assertEqual(self.ledger.reservation(reservation)["kind"], "backend")
        self.assertEqual(self.ledger.reservation(self.session.reservation_id)["kind"], "voice")
        self.assertEqual(self.ledger.snapshot()["open_records"], 2)

    async def test_completed_delegation_retains_tokens_without_inventing_a_full_price(self):
        await self.arm()
        await self.create()
        context = self.manager._context(self.session)
        reservation = await self.manager.reserve_delegation(context, "delegation_completed")
        usage = {"input_tokens": 100, "output_tokens": 20, "cost_usd": "0.001"}
        await self.manager.settle_delegation(context, "delegation_completed", reservation, usage, "completed")
        await self.manager.settle_delegation(context, "delegation_completed", reservation, usage, "completed")
        row = self.ledger.reservation(reservation)
        self.assertEqual(row["state"], "closed")
        self.assertEqual(row["quality"], "unpriced")
        self.assertIsNone(row["cost_usd"])
        self.assertEqual(row["backend_usage"]["input_tokens"], 100)
        self.assertEqual(row["backend_usage"]["output_tokens"], 20)
        self.assertEqual(row["backend_usage"]["quality"], "partial")
        # Voice is also unpriced until its first duration observation arrives.
        self.assertGreaterEqual(self.ledger.snapshot()["monthly"]["unpriced_records"], 1)
        self.assertNotIn("delegation_completed", self.session.pending_delegations)

    async def test_high_recorded_usage_never_blocks_mobile_or_stops_its_session(self):
        self.ledger.reserve("historical-usage", 0, "backend")
        self.ledger.reconcile("historical-usage", "1000", confirmed=True)
        self.assertTrue((await self.manager.capabilities(OWNER))["available"])
        await self.arm()
        await self.create()
        await self.until(lambda: self.session.started.is_set())
        context = self.manager._context(self.session)
        reservation = await self.manager.reserve_delegation(context, "delegation_after_high_usage")
        self.assertTrue(reservation)
        await self.manager.settle_delegation(context, "delegation_after_high_usage", reservation, {}, "completed")
        self.clock.advance(1)
        await self.heartbeat()
        await self.manager.tick()
        self.assertFalse(self.session.closed.is_set())
        self.assertFalse(self.provider.close_requested.is_set())
        self.assertTrue((await self.manager.capabilities(OWNER))["available"])
        self.assertGreaterEqual(Decimal(self.ledger.snapshot()["monthly"]["recorded_usd"]), 1000)

    async def test_every_usage_failure_is_informational_and_never_disables_live(self):
        unavailable = Mock()
        for name in ("snapshot", "reserve", "estimate_usage", "update_usage", "reconcile",
                     "mark_unknown", "record_backend_usage"):
            getattr(unavailable, name).side_effect = sqlite3.OperationalError("usage unavailable")
        self.manager.usage = unavailable
        caps = await self.manager.capabilities(OWNER)
        self.assertTrue(caps["available"])
        self.assertEqual(caps["usage"], {"available": False, "reason": "usage_unavailable"})
        await self.arm()
        await self.create()
        await self.until(lambda: self.session.started.is_set())
        self.clock.advance(1)
        await self.heartbeat()
        await self.manager.tick()
        self.assertFalse(self.provider.close_requested.is_set())
        await self.provider.emit(self.session.provider_id, {
            "type": "session.usage.updated", "event_id": "unrecordable_usage", "usage": {"seconds": 1}})
        await self.until(lambda: self.session.usage_seconds == 1)
        context = self.manager._context(self.session)
        reservation = await self.manager.reserve_delegation(context, "delegation_without_usage")
        self.assertTrue(reservation)
        await self.manager.settle_delegation(context, "delegation_without_usage", reservation,
                                             {"input_tokens": 100, "output_tokens": 20}, "completed")
        self.assertFalse(await self.manager.reserve_delegation(context, "delegation_without_usage"))
        self.assertEqual(self.session.pending_delegations, set())
        await self.manager.close(OWNER, CLIENT, self.lease_id)
        self.assertTrue(self.session.closed.is_set())
        self.assertFalse(self.manager._storage_failed)
        self.assertTrue((await self.manager.capabilities(OWNER))["available"])
        await self.arm()
        await self.create("second_without_usage")
        self.assertEqual(len(self.provider.creations), 2)
        for name in ("reserve", "estimate_usage", "update_usage", "record_backend_usage"):
            self.assertTrue(getattr(unavailable, name).called, name)

    async def test_provider_refusals_have_public_codes_without_response_contents(self):
        self.manager.config = replace(self.config, max_starts_per_minute=10)
        cases = ((401, "session_creation_rejected", "live_auth_failed"),
                 (403, "session_creation_rejected", "live_access_denied"),
                 (404, "session_creation_rejected", "live_model_unavailable"),
                 (429, "session_creation_rejected", "live_rate_limited"),
                 (429, "live_quota_exceeded", "live_quota_exceeded"))
        for status, provider_code, expected in cases:
            with self.subTest(status=status, code=provider_code):
                self.provider.create_error = LiveProviderError(provider_code, status_code=status)
                await self.arm()
                with self.assertRaises(LiveSessionError) as raised:
                    await self.create()
                self.assertEqual(raised.exception.code, expected)
                self.assertEqual(self.manager.snapshot(OWNER)["session_state"], "absent")

    async def test_network_failure_keeps_unknown_creation_safety_with_readable_error(self):
        self.provider.create_error = LiveProviderError("session_creation_transport_failed", ambiguous=True)
        await self.arm()
        with self.assertRaises(LiveSessionError) as raised:
            await self.create()
        self.assertEqual(raised.exception.code, "live_connection_failed")
        self.assertEqual(self.manager.snapshot(OWNER)["session_state"], "opening_unknown")
        with self.assertRaises(LiveSessionError):
            await self.manager.arm(OWNER, CLIENT, THREAD)
        self.assertEqual(len(self.provider.creations), 1)

    async def test_cancelled_and_unknown_delegations_keep_uncertainty_without_a_price(self):
        await self.arm()
        await self.create()
        context = self.manager._context(self.session)
        for status in ("cancelled", "unknown"):
            with self.subTest(status=status):
                delegation_id = "delegation_" + status
                reservation = await self.manager.reserve_delegation(context, delegation_id)
                await self.manager.settle_delegation(context, delegation_id, reservation,
                                                     {"input_tokens": 0, "output_tokens": 0}, status)
                row = self.ledger.reservation(reservation)
                self.assertEqual(row["state"], "unknown")
                self.assertIsNone(row["cost_usd"])
                self.assertEqual(row["backend_usage"]["status"], status)
                self.assertNotIn(delegation_id, self.session.pending_delegations)
        self.assertEqual(self.ledger.snapshot()["unknown_records"], 2)
        self.assertTrue((await self.manager.capabilities(OWNER))["available"])

    async def test_delegation_quota_and_duplicate_ids_are_enforced_after_completed_work(self):
        self.manager.config = replace(self.config, max_delegations_per_session=2)
        self.manager.usage = None  # Business deduplication cannot rely on telemetry.
        await self.arm()
        await self.create()
        context = self.manager._context(self.session)
        first = await self.manager.reserve_delegation(context, "delegation_first")
        self.assertTrue(first)
        self.assertFalse(await self.manager.reserve_delegation(context, "delegation_first"))
        await self.manager.settle_delegation(context, "delegation_first", first, {}, "completed")
        self.assertFalse(await self.manager.reserve_delegation(context, "delegation_first"))
        second = await self.manager.reserve_delegation(context, "delegation_second")
        self.assertTrue(second)
        self.assertFalse(await self.manager.reserve_delegation(context, "delegation_third"))
        self.assertEqual(self.session.total_delegations, 2)

    async def test_stale_generation_and_invalid_ids_refuse_delegations(self):
        await self.arm()
        await self.create()
        context = self.manager._context(self.session)
        stale = {**context, "generation": "old_generation"}
        self.assertFalse(await self.manager.reserve_delegation(stale, "delegation_stale"))
        for invalid in (None, "", " " * 3, "x" * 257):
            with self.subTest(delegation_id=invalid):
                self.assertFalse(await self.manager.reserve_delegation(context, invalid))
        self.assertEqual(self.session.total_delegations, 0)
        self.assertEqual(self.ledger.snapshot()["open_records"], 1)
        self.assertTrue(self.manager._valid(self.session))

    async def test_stale_generation_and_wrong_reservation_cannot_settle_another_job(self):
        await self.arm()
        await self.create()
        context = self.manager._context(self.session)
        reservation = await self.manager.reserve_delegation(context, "delegation_current")
        await self.manager.settle_delegation({**context, "generation": "old_generation"},
                                             "delegation_current", reservation, {}, "completed")
        self.assertEqual(self.ledger.reservation(reservation)["state"], "reserved")
        await self.manager.settle_delegation(context, "delegation_current", self.session.reservation_id,
                                             {}, "completed")
        self.assertEqual(self.ledger.reservation(reservation)["state"], "reserved")
        self.assertIn("delegation_current", self.session.pending_delegations)

    async def test_lease_expiry_during_backend_tracking_still_prevents_dispatch(self):
        await self.arm()
        await self.create()
        context = self.manager._context(self.session)
        entered, release = threading.Event(), threading.Event()
        original_reserve = self.ledger.reserve
        reservations = []

        def delayed_reserve(identifier, quote, kind="voice", **kwargs):
            if kind == "backend":
                reservations.append(identifier)
                entered.set()
                if not release.wait(2):
                    raise TimeoutError("test observation barrier")
            return original_reserve(identifier, quote, kind, **kwargs)

        self.ledger.reserve = delayed_reserve
        pending = asyncio.create_task(self.manager.reserve_delegation(context, "delegation_expired"))
        try:
            await self.until(entered.is_set)
            self.clock.advance(self.config.lease_seconds + 0.1)
            release.set()
            self.assertFalse(await pending)
        finally:
            release.set()
            self.ledger.reserve = original_reserve
        self.assertEqual(self.ledger.reservation(reservations[0])["state"], "released")
        self.assertEqual(self.session.total_delegations, 0)
        self.assertEqual(self.session.pending_delegations, set())

    async def test_idle_does_not_close_while_delegation_is_pending_then_restarts_idle_clock(self):
        await self.arm()
        await self.create()
        await self.until(lambda: self.session.started.is_set())
        context = self.manager._context(self.session)
        reservation = await self.manager.reserve_delegation(context, "delegation_slow")
        for _ in range(8):
            self.clock.advance(1)
            await self.heartbeat()
            await self.manager.tick()
        self.assertFalse(self.session.closed.is_set())
        self.assertFalse(self.provider.close_requested.is_set())
        await self.manager.settle_delegation(context, "delegation_slow", reservation, {}, "completed")
        for _ in range(6):
            self.clock.advance(1)
            await self.heartbeat()
            await self.manager.tick()
        await asyncio.wait_for(self.session.closed.wait(), 2)
        self.assertEqual(self.session.reason, "idle")

    async def test_lifecycle_telemetry_omits_private_content_and_does_not_claim_heard_audio(self):
        canary = "PRIVATE_TRANSCRIPT_CANARY"
        with patch("src.jade_runtime.live_sessions.audit_event") as audit:
            await self.arm()
            await self.create()
            await self.provider.emit(self.session.provider_id, {
                "type": "session.input_transcript.delta", "event_id": "private_fragment",
                "delta": canary, "start_ms": 0, "end_ms": 100,
            })
            await self.until(lambda: self.session.ever_input)
            self.clock.advance(0.25)
            await self.manager.observe_playback(OWNER, CLIENT, self.lease_id,
                                                {"session_id": self.session.handle,
                                                 "state": "playing", "offset_ms": 100})
            self.manager._trace(self.session, "technical_test", transcript=canary,
                                sdp=SDP, owner=OWNER, measured_ms=25)
            await self.manager.close(OWNER, CLIENT, self.lease_id)
            await self.until(lambda: bool(self.manager.metrics.summary()))
            records = [{"event": call.args[0], **call.kwargs} for call in audit.call_args_list]
        encoded = json.dumps(records) + json.dumps(self.manager.metrics.summary())
        for private in (canary, OWNER, CLIENT, THREAD, SDP, self.session.provider_id, self.session.handle):
            self.assertNotIn(private, encoded)
        stages = {record["stage"] for record in records}
        self.assertTrue({"live_opening", "live_sdp_ready", "live_close_requested", "live_terminal",
                         "live_playback_reported"}.issubset(stages))
        summary = self.manager.metrics.summary()[0]
        self.assertEqual((summary["platform"], summary["modality"]), ("mobile", "live"))
        self.assertIsNone(summary["first_audible_ms"])
        self.assertIsNone(summary["cost_usd"])


if __name__ == "__main__":
    unittest.main()
