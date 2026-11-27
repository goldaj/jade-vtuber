"""Discord-only selection of Live/classic from global monthly API consumption.

50 EUR requires complete, sufficiently fresh monetary coverage. A bounded
estimate uses the user's 40 EUR threshold. Unknown/stale totals select classic.
Neither mode stops normal classic replies or changes mobile preferences.
"""
from __future__ import annotations

import asyncio
import copy
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import inspect
import json
import sqlite3

from .global_spend import SpendStore, amount, aware, paris_month, run_blocking_owned
from .live_usage import quote_voice

OWNER_ENABLED_KEY = "discord_live_owner_enabled"
MONTHLY_USAGE_KEY = "discord_live_monthly_usage"


class DiscordLiveSpendPolicy:
    def __init__(self, collector, *, db_path=None, refresh_seconds=300, now=None):
        if not 30 <= refresh_seconds <= 900:
            raise ValueError("invalid Discord spend refresh interval")
        self.collector = collector
        self.refresh_seconds = float(refresh_seconds)
        self.store = SpendStore(db_path if db_path is not None else collector.db_path)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._snapshot = None
        self._local_unavailable = False
        self._decision = {"allow_live": False, "mode": "classic", "reason": "spend_not_ready",
                          "coverage": "unknown", "threshold_eur": "40", "spent_eur": None}
        self._lock = asyncio.Lock()
        self._collection_lock = asyncio.Lock()
        self._task = None
        self._refresh_task = None
        self._closed = False
        self._load_usage()

    def _load_usage(self, db=None):
        saved = self._get_state("discord_live_usage", {}, db)
        self._usage = saved.get("sessions", {})
        self._usage_events = saved.get("events", [])
        self._usage_unknown = saved.get("unknown", False)
        self._usage_unknown_at = saved.get("unknown_at")
        self._carry_month = saved.get("carry_month")
        self._carry_usd = amount(saved.get("carry_usd", 0))
        self._last_report_usd = saved.get("last_report_usd")

    def _get_state(self, key, default, db=None):
        if db is None:
            return self.store.get(key, default)
        row = db.execute("SELECT value FROM global_spend_state WHERE name=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def _put_state(self, key, value, db=None):
        if db is None:
            self.store.put(key, value)
        else:
            db.execute("INSERT OR REPLACE INTO global_spend_state VALUES(?,?)",
                       (key, json.dumps(value, allow_nan=False, separators=(",", ":"))))

    def _month_usage(self, db, month):
        # Seed only once from the retained cumulative observations. Older
        # sessions lack dated seconds, so their historical split is partial.
        saved = self._get_state(MONTHLY_USAGE_KEY, None, db)
        if saved is None:
            seconds = sum((amount(value["seconds"]) for value in self._usage.values()
                           if value.get("month") == month), Decimal(0))
            saved = {"month": month, "seconds": str(seconds), "partial": bool(seconds)}
            self._put_state(MONTHLY_USAGE_KEY, saved, db)
        if saved["month"] != month:
            return {"month": month, "seconds": "0", "partial": False}
        return saved

    async def mobile_settings(self, enabled=None):
        """Expose only the owner's Discord preference and observed monthly usage."""
        async with self._lock:
            return await run_blocking_owned(self._mobile_settings_sync, aware(self._now()), enabled)

    def _mobile_settings_sync(self, now, enabled):
        with closing(self.store.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._load_usage(db)
            if enabled is not None:
                self._put_state(OWNER_ENABLED_KEY, enabled, db)
            month = paris_month(now)[0]
            usage = self._month_usage(db, month)
            partial = usage["partial"] or self._usage_unknown or any(
                record.get("phase") != "settled" for record in self._reservations(db).values())
            return {"enabled": self._get_state(OWNER_ENABLED_KEY, True, db),
                    "month": month, "minutes": float(amount(usage["seconds"]) / 60),
                    "partial": partial}

    async def start(self):
        if self._closed:
            return
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="discord-global-spend")

    async def refresh(self):
        if self._closed:
            return
        async with self._collection_lock:
            try:
                async with asyncio.timeout(25):
                    snapshot = self.collector.collect()
                    if inspect.isawaitable(snapshot):
                        snapshot = await snapshot
                if not isinstance(snapshot, dict):
                    raise ValueError("invalid spend snapshot")
                async with self._lock:
                    await run_blocking_owned(self._reconcile_snapshot_sync, snapshot)
                    self._local_unavailable = False
            except asyncio.CancelledError:
                raise
            except Exception:
                async with self._lock:
                    self._snapshot = {"month": paris_month(aware(self._now()))[0], "coverage": "unknown",
                                      "checked_at": aware(self._now()).isoformat(), "reason": "spend_collection_failed"}
                    try:
                        await run_blocking_owned(self._reconcile_snapshot_sync, self._snapshot)
                    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
                        self._local_unavailable = True

    def _reconcile_snapshot_sync(self, snapshot):
        with closing(self.store.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._load_usage(db)
            snapshot = copy.deepcopy(snapshot)
            snapshot.setdefault("checked_at", aware(self._now()).isoformat())
            previous = self._get_state("discord_live_policy_snapshot", None, db)
            if (previous and aware(datetime.fromisoformat(previous["checked_at"]))
                    > aware(datetime.fromisoformat(snapshot["checked_at"]))):
                self._snapshot = previous
                return
            self._snapshot = snapshot
            # Every reader must see the same base report as the reconciled
            # overlay. Otherwise an older in-memory base could consume a carry
            # already removed by another process's newer report.
            self._put_state("discord_live_policy_snapshot", snapshot, db)
            if snapshot.get("coverage") in ("bounded", "complete"):
                cutoff = aware(datetime.fromisoformat(snapshot["checked_at"]))
                month = snapshot["month"]
                if self._carry_month != month:
                    self._carry_month, self._carry_usd, self._last_report_usd = month, Decimal(0), None
                previous_events = sum((amount(event["usd"]) for event in self._usage_events
                                       if event["month"] == month
                                       and aware(datetime.fromisoformat(event["at"])) < cutoff), Decimal(0))
                reported = snapshot.get("sources", {}).get("openai", {}).get("amounts", {}).get("USD")
                growth = Decimal(0)
                if reported is not None:
                    reported = amount(reported)
                    if self._last_report_usd is not None:
                        growth = max(Decimal(0), reported - amount(self._last_report_usd))
                    self._last_report_usd = str(reported)
                # A successful fetch alone is NOT evidence that Costs
                # has caught up. Preserve the known monetary floor until
                # the reported OPENAI total grows; other providers or FX
                # movements cannot absorb local Live observations.
                self._carry_usd = max(Decimal(0), self._carry_usd + previous_events - growth)
                self._usage_events = [event for event in self._usage_events
                                      if event["month"] == month
                                      and aware(datetime.fromisoformat(event["at"])) >= cutoff]
                if self._usage_unknown_at:
                    unknown_at = aware(datetime.fromisoformat(self._usage_unknown_at))
                    through = snapshot.get("complete_through")
                    reconciled = (snapshot.get("coverage") == "complete" and through
                                  and aware(datetime.fromisoformat(through)) >= unknown_at)
                    if paris_month(unknown_at)[0] != month or reconciled:
                        self._usage_unknown, self._usage_unknown_at = False, None
                self._save_usage(db)

    async def _run(self):
        try:
            while not self._closed:
                await self.refresh()
                await self.decision()
                await asyncio.sleep(self.refresh_seconds)
        except asyncio.CancelledError:
            pass

    def _schedule_refresh(self):
        if not self._closed and not self._collection_lock.locked() and (self._refresh_task is None or self._refresh_task.done()):
            self._refresh_task = asyncio.create_task(self.refresh(), name="discord-spend-refresh")

    def _save_usage(self, db=None):
        self._put_state("discord_live_usage", {"sessions": self._usage,
                       "events": self._usage_events, "unknown": self._usage_unknown,
                       "unknown_at": self._usage_unknown_at,
                       "carry_month": self._carry_month, "carry_usd": str(self._carry_usd),
                       "last_report_usd": self._last_report_usd}, db)

    @staticmethod
    def _identifier(value):
        if not isinstance(value, str) or not value or len(value) > 256:
            raise ValueError("invalid Live technical identifier")
        return hashlib.sha256(value.encode()).hexdigest()

    def _reservations(self, db):
        return {row[0]: json.loads(row[1]) for row in db.execute(
            "SELECT reservation_key,value FROM discord_live_reservations")}

    @staticmethod
    def _put_reservation(db, key, record):
        db.execute("INSERT OR REPLACE INTO discord_live_reservations VALUES(?,?)",
                   (key, json.dumps(record, allow_nan=False, separators=(",", ":"))))

    def _observe_usage(self, db, session_id, usage, *, model, now):
        if model not in ("gpt-live-1", "gpt-live-1.1") or not isinstance(usage, dict):
            raise ValueError("unknown Live usage")
        key = self._identifier(session_id)
        seconds = amount(usage.get("seconds"))
        month = paris_month(now)[0]
        previous = self._usage.get(key, {"seconds": "0", "month": month})
        old = amount(previous["seconds"])
        monthly = self._month_usage(db, month)
        if seconds > old:
            delta = seconds - old
            self._usage_events.append({"at": now.isoformat(), "month": month,
                                       "usd": str(quote_voice(delta))})
            monthly["seconds"] = str(amount(monthly["seconds"]) + delta)
            self._put_state(MONTHLY_USAGE_KEY, monthly, db)
        previous.update(seconds=str(max(old, seconds)), month=month)
        self._usage[key] = previous
        reservations = self._reservations(db)
        for reservation_key, record in reservations.items():
            if record.get("session_key") == key and record.get("phase") != "settled":
                record["observed_seconds"] = str(max(amount(record.get("observed_seconds", 0)), seconds))
                self._put_reservation(db, reservation_key, record)
        pending_sessions = {record.get("session_key") for record in reservations.values()
                            if record.get("phase") != "settled"}
        self._usage = {key: value for key, value in self._usage.items()
                       if value.get("month") == month or key in pending_sessions}
        if len(self._usage) > 4096 or len(self._usage_events) > 10000:
            raise ValueError("Live observation coverage exceeded")

    def _unknown_usage(self, now):
        self._usage_unknown = True
        self._usage_unknown_at = now.isoformat()

    async def record_live_usage(self, session_id, usage, *, model):
        """Observe cumulative Discord Live seconds; never admit/charge/replay audio.

        The delta is a conservative all-active quote. Its timestamp is an
        observation time, not an invented invoice timestamp; policy therefore
        remains in the 40 EUR estimated tier whenever this overlay is present.
        """
        if self._closed:
            return
        async with self._lock:
            try:
                await run_blocking_owned(self._record_usage_sync, session_id, usage, model, aware(self._now()))
            except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
                self._unknown_usage(aware(self._now()))
                try:
                    await run_blocking_owned(self._save_usage)
                except (OSError, sqlite3.Error, ValueError):
                    pass

    def _record_usage_sync(self, session_id, usage, model, now):
        with closing(self.store.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._load_usage(db)
            try:
                self._observe_usage(db, session_id, usage, model=model, now=now)
            except (ValueError, TypeError, KeyError):
                self._unknown_usage(now)
            self._save_usage(db)

    def _base_decision(self, now, db, *, estimated_exposure=False):
        month = paris_month(now)[0]
        result = {"allow_live": False, "mode": "classic", "month": month,
                  "threshold_eur": "40", "spent_eur": None, "coverage": "unknown",
                  "checked_at": None, "reason": "spend_not_ready", "latched": False}
        if self._closed:
            result["reason"] = "spend_policy_stopped"
            return result
        if self._local_unavailable:
            result["reason"] = "spend_state_unavailable"
            return result
        latch = db.execute("SELECT threshold_eur,observed_eur FROM discord_live_month_latch WHERE month=?",
                           (month,)).fetchone()
        if latch:
            result.update(reason="monthly_threshold_reached", latched=True,
                          threshold_eur=latch[0], spent_eur=latch[1])
            return result
        source = self._snapshot
        if source is None:
            return result
        result["checked_at"] = source.get("checked_at")
        result["spent_eur"] = source.get("spent_eur", source.get("last_known_eur"))
        if source.get("month") != month:
            result["reason"] = "spend_month_changed"
            return result
        if source.get("coverage") not in ("bounded", "complete"):
            result["reason"] = source.get("reason", "spend_unbounded")
            return result
        checked = aware(datetime.fromisoformat(source["checked_at"]))
        if not 0 <= (now - checked).total_seconds() <= self.refresh_seconds + 30:
            result["reason"] = "spend_stale"
            return result
        total, coverage = amount(source["spent_eur"]), source["coverage"]
        if estimated_exposure:
            coverage = "bounded"
        if self._usage_unknown:
            raise ValueError("unpriced live exposure")
        overlay = sum((amount(event["usd"]) for event in self._usage_events
                       if event["month"] == month), Decimal(0))
        if self._carry_month == month:
            overlay += self._carry_usd
        if overlay:
            total += overlay / self._usd_rate()
            coverage = "bounded"
            result["live_since_report_estimate_usd"] = str(overlay)
        if coverage == "complete":
            through = source.get("complete_through")
            if not through or not 0 <= (now - aware(datetime.fromisoformat(through))).total_seconds() <= self.refresh_seconds:
                coverage = "bounded"
        threshold = amount(50 if coverage == "complete" else 40)
        result.update(coverage=coverage, threshold_eur=str(threshold), spent_eur=str(total))
        if total >= threshold:
            db.execute("INSERT OR IGNORE INTO discord_live_month_latch VALUES(?,?,?,?)",
                       (month, str(threshold), str(total), now.isoformat()))
            result.update(reason="monthly_threshold_reached", latched=True)
        else:
            result.update(allow_live=True, mode="live", reason="within_monthly_threshold")
        return result

    def _usd_rate(self):
        rate = amount((self._snapshot or {}).get("fx", {}).get("rates", {}).get("USD"))
        if not rate:
            raise ValueError("Live conversion unavailable")
        return rate

    def _reservation_exposure(self, records, now):
        reserved, unobserved, count = Decimal(0), Decimal(0), 0
        unknown = False
        for record in records.values():
            if record.get("phase") == "settled":
                continue
            count += 1
            if record.get("phase") not in ("opening", "active"):
                unknown = True
            elapsed = amount((now - aware(datetime.fromisoformat(record["created_at"]))).total_seconds())
            observed = amount(record.get("observed_seconds", 0))
            unobserved += quote_voice(max(Decimal(0), elapsed - observed))
            future = amount(record.get("close_seconds", 0)) + amount(record.get("control_seconds", 0))
            if record.get("phase") == "opening":
                future += max(Decimal(0), amount(record["opening_seconds"]) - elapsed)
            reserved += quote_voice(future)
        return reserved, unobserved, count, unknown

    def _decide_sync(self, now, specification=None):
        # BEGIN IMMEDIATE makes read-headroom + insert indivisible across policy
        # instances/processes, not just concurrent coroutines in this runtime.
        with closing(self.store.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._load_usage(db)
            if not self._local_unavailable:
                self._snapshot = self._get_state("discord_live_policy_snapshot", self._snapshot, db)
            records = self._reservations(db)
            if specification:
                self._put_state("discord_live_admission_guard", specification["guard"], db)
            reserved, unobserved, count, unknown = self._reservation_exposure(records, now)
            result = self._base_decision(now, db, estimated_exposure=bool(unobserved))
            result["outstanding_live_reservations"] = count
            if reserved or unobserved:
                rate = self._usd_rate()
                result.update(reserved_eur=str(reserved / rate),
                              unreported_live_exposure_eur=str(unobserved / rate))
            else:
                result.update(reserved_eur="0", unreported_live_exposure_eur="0")
            if unknown:
                result.update(allow_live=False, mode="classic", reason="live_reservation_unknown")
            if not self._get_state(OWNER_ENABLED_KEY, True, db):
                result.update(allow_live=False, mode="classic", reason="manual_classic")
            if not result["allow_live"]:
                return result
            total, threshold = amount(result["spent_eur"]), amount(result["threshold_eur"])
            additional = Decimal(0)
            existing = None
            if specification:
                existing = records.get(specification["key"])
                if existing and existing.get("phase") == "settled":
                    result.update(allow_live=False, mode="classic", reason="live_reservation_already_settled")
                    return result
                if existing is None:
                    additional = amount(specification["guard"]["usd"])
            elif count == 0:
                # After a refused opening, subsequent speech stays on classic
                # until there is enough headroom; this does not latch the month.
                guard = self._get_state("discord_live_admission_guard", {}, db)
                additional = amount(guard.get("usd", 0))
            exposure = total
            if reserved or unobserved or additional:
                rate = self._usd_rate()
                exposure += (reserved + unobserved + additional) / rate
                result["admission_reserve_eur"] = str(additional / rate)
            result["exposure_eur"] = str(exposure)
            if exposure >= threshold:
                result.update(allow_live=False, mode="classic", reason="live_reservation_insufficient")
                return result
            if specification:
                if existing is None:
                    self._put_reservation(db, specification["key"], specification["record"])
                    result["outstanding_live_reservations"] = count + 1
                    result["reserved_eur"] = str((reserved + additional) / self._usd_rate())
                result["reservation_id"] = specification["id"]
            return result

    async def _decide(self, specification=None):
        now = aware(self._now())
        async with self._lock:
            try:
                result = await run_blocking_owned(self._decide_sync, now, specification)
            except (OSError, sqlite3.Error, ValueError, KeyError, TypeError):
                result = {"allow_live": False, "mode": "classic", "month": paris_month(now)[0],
                          "reason": "spend_state_unavailable", "coverage": "unknown",
                          "threshold_eur": "40", "spent_eur": None, "latched": False}
        self._decision = result
        if result["reason"] in ("spend_not_ready", "spend_month_changed", "spend_stale"):
            self._schedule_refresh()
        return copy.deepcopy(result)

    async def decision(self):
        return await self._decide()

    async def reserve_live(self, attempt_id, *, model, opening_seconds, close_seconds, control_seconds):
        """Reserve actual bounded opening/closing/control time before any start.

        No WebRTC startup fee applies to primary PCM WebSocket sessions. Future
        time is kept distinct from consumption. Refusing headroom never latches
        a month whose observed consumption is still below its threshold.
        """
        try:
            key = self._identifier(attempt_id)
            if model not in ("gpt-live-1", "gpt-live-1.1"):
                raise ValueError("unknown Live price")
            opening, closing_time, control = map(amount, (opening_seconds, close_seconds, control_seconds))
            if not (0 < opening <= 30 and 0 < closing_time <= 30 and 0 < control <= 30):
                raise ValueError("unbounded Live time guard")
            now = aware(self._now())
            guard = {"usd": str(quote_voice(opening + closing_time + control)), "model": model}
            record = {"phase": "opening", "created_at": now.isoformat(), "month": paris_month(now)[0],
                      "opening_seconds": str(opening), "close_seconds": str(closing_time),
                      "control_seconds": str(control), "observed_seconds": "0", "model": model}
        except (ValueError, TypeError):
            return {"allow_live": False, "mode": "classic", "reason": "live_reservation_unpriced", "latched": False}
        return await self._decide({"key": key, "id": attempt_id, "guard": guard, "record": record})

    async def bind_live(self, attempt_id, session_id):
        """A successful provider opening leaves only close/control commitments."""
        key, session_key = self._identifier(attempt_id), self._identifier(session_id)
        async with self._lock:
            def bind():
                with closing(self.store.connect()) as db, db:
                    db.execute("BEGIN IMMEDIATE")
                    records = self._reservations(db)
                    record = records.get(key)
                    if not record or record.get("phase") not in ("opening", "active"):
                        raise ValueError("Live reservation unavailable")
                    if record.get("session_key") not in (None, session_key):
                        raise ValueError("Live reservation identity mismatch")
                    self._load_usage(db)
                    record.update(phase="active", session_key=session_key,
                                  observed_seconds=self._usage.get(session_key, {}).get("seconds", "0"))
                    self._put_reservation(db, key, record)
                return True
            return await run_blocking_owned(bind)

    async def settle_live(self, attempt_id, *, confirmed=False, never_started=False,
                          session_id=None, usage=None, model):
        """Atomically record terminal usage and release only proven closure.

        Unknown starts/closes remain durable across restarts and calendar months.
        Confirmed closure with absent usage releases future time, but preserves
        unknown consumption. Replayed terminals cannot charge twice or reopen a
        settled reservation. No private audio, transcript, or identity is stored.
        """
        key = self._identifier(attempt_id)
        async with self._lock:
            return await run_blocking_owned(self._settle_sync, key, confirmed is True,
                                           never_started is True, session_id, usage, model, aware(self._now()))

    def _settle_sync(self, key, confirmed, never_started, session_id, usage, model, now):
        with closing(self.store.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            records = self._reservations(db)
            record = records.get(key)
            if record and record.get("phase") == "settled":
                return True
            if record is None:
                # Recovery of a transport journal from an older runtime still
                # records its terminal; missing reservation never implies free.
                record = {"created_at": now.isoformat(), "phase": "unknown", "model": model,
                          "opening_seconds": "0", "close_seconds": "0", "control_seconds": "0"}
            self._load_usage(db)
            if never_started and (record.get("session_key") or amount(record.get("observed_seconds", 0))):
                never_started = False  # A contradictory claim cannot erase an established session.
                confirmed = False
            if record.get("session_key"):
                try:
                    if record["session_key"] != self._identifier(session_id):
                        confirmed, never_started = False, False
                except ValueError:
                    confirmed, never_started = False, False
            if not never_started:
                try:
                    self._observe_usage(db, session_id, usage, model=model, now=now)
                except (ValueError, TypeError, KeyError):
                    # Before a confirmed terminal, the durable unknown
                    # reservation already blocks admission. A later valid
                    # terminal can reconcile it without inventing zero usage.
                    if confirmed:
                        self._unknown_usage(now)
            # Wall time was an exposure guard, not invoiced consumption. A
            # valid terminal's cumulative seconds replaces it, including zero.
            # It must never become a fabricated connection/cleanup charge.
            record.update(phase="settled" if confirmed or never_started else "unknown",
                          settled_at=now.isoformat() if confirmed or never_started else None)
            self._put_reservation(db, key, record)
            self._save_usage(db)
        return True

    def status(self):
        status = copy.deepcopy(self._decision)
        if self._snapshot is not None:
            status["sources"] = copy.deepcopy(self._snapshot.get("sources", {}))
            status["fx"] = copy.deepcopy(self._snapshot.get("fx", {}))
            status["final_invoice_guaranteed"] = False
        return status

    async def close(self):
        self._closed = True
        tasks = [task for task in (self._task, self._refresh_task) if task is not None and not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
