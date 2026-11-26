"""Private, durable, atomic Live reservations and cumulative usage accounting.

Zero budgets disable admission. Voice and backend share the envelope but retain
their own totals. Provider seconds, estimated dollar costs and invoice amounts
are distinguishable; this is not a claim of a hard provider-side spending cap.
Open reservations survive restarts and count in the current Paris day/month,
including reservations made before a rollover. Observed cost increments crossing
midnight are prorated over their observation interval, explicitly an estimate.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, ROUND_UP
import os
from pathlib import Path
import sqlite3
from typing import Callable

from .paris_clock import paris_date


ZERO = Decimal("0")
USD_QUANTUM = Decimal("0.000000000001")
ACTIVE_USD_PER_MINUTE = Decimal("0.05")
STANDBY_USD_PER_MINUTE = Decimal("0.02")
RATE_DATE = "2026-11-26"


def _amount(value: object, *, upper: Decimal = Decimal("1000000")) -> Decimal:
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise ValueError("invalid Live numeric amount") from exc
    if not result.is_finite() or not ZERO <= result <= upper:
        raise ValueError("Live numeric amounts must be finite, nonnegative and bounded")
    return result


def _usd(value: Decimal) -> str:
    return format(value, "f")


def quote_voice(seconds: object, *, active_rate: object = ACTIVE_USD_PER_MINUTE) -> Decimal:
    """Conservative all-active quote, rounded upward; no second startup surcharge."""
    duration = _amount(seconds, upper=Decimal("31536000"))
    rate = _amount(active_rate)
    return (duration * rate / Decimal(60)).quantize(USD_QUANTUM, rounding=ROUND_UP)


def quote_session(config) -> Decimal:
    # The documented default startup charge is credited against elapsed duration.
    # Speech-wake billing remains a pilot measurement; reserve at least 15 seconds
    # conservatively, but never add 15 seconds to an already longer session.
    seconds = (Decimal(str(config.max_session_seconds))
               + Decimal(str(config.opening_timeout_seconds))
               + Decimal(str(config.close_timeout_seconds)))
    return quote_voice(max(Decimal(15), seconds))


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Live accounting requires a timezone-aware timestamp")
    return value.astimezone(timezone.utc)


def _period_slices(start: datetime, end: datetime) -> list[tuple[str, Decimal]]:
    """Split a wall-clock interval at Paris midnight, including DST and Windows.

    paris_clock provides the project's IANA/EU fallback. Both supported Paris
    offsets are tested against that function instead of assuming 24-hour days.
    """
    if end <= start:
        return [(paris_date(end).isoformat(), Decimal(1))]
    result = []
    point = start
    while point < end:
        day = paris_date(point)
        tomorrow = day + timedelta(days=1)
        midnight_utc = datetime.combine(tomorrow, time.min, tzinfo=timezone.utc)
        boundary = None
        for offset in (1, 2):
            candidate = midnight_utc - timedelta(hours=offset)
            if (paris_date(candidate) == tomorrow
                    and paris_date(candidate - timedelta(microseconds=1)) == day):
                boundary = candidate
                break
        if boundary is None:
            raise ValueError("Paris accounting boundary cannot be established")
        stop = min(end, boundary)
        weight = Decimal(str((stop - point).total_seconds()))
        result.append((day.isoformat(), weight))
        point = stop
    return result


class LiveBudgetLedger:
    def __init__(self, path: str | Path, daily_usd: object, monthly_usd: object,
                 *, now: Callable[[], datetime] | None = None,
                 active_rate: object = ACTIVE_USD_PER_MINUTE,
                 standby_rate: object = STANDBY_USD_PER_MINUTE):
        self.path = Path(path).expanduser()
        repo_root = Path(__file__).resolve().parents[2]
        if (not self.path.is_absolute() or self.path.suffix != ".sqlite3"
                or self.path.resolve().is_relative_to(repo_root) or self.path.is_symlink()):
            raise ValueError("Live ledger requires an absolute private SQLite path outside Git")
        self.daily_usd = _amount(daily_usd, upper=Decimal(10000))
        self.monthly_usd = _amount(monthly_usd, upper=Decimal(10000))
        if self.daily_usd > self.monthly_usd:
            raise ValueError("Live daily budget cannot exceed monthly budget")
        self.active_rate = _amount(active_rate)
        self.standby_rate = _amount(standby_rate)
        if not self.active_rate or self.standby_rate > self.active_rate:
            raise ValueError("invalid Live duration rates")
        self._clock = now or (lambda: datetime.now(timezone.utc))
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.path, flags, 0o600)
        os.close(descriptor)
        if os.name != "nt":
            self.path.chmod(0o600)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jade_live_budget_reservations(
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                    quote_usd TEXT NOT NULL, spent_usd TEXT NOT NULL DEFAULT '0',
                    state TEXT NOT NULL DEFAULT 'reserved',
                    quality TEXT NOT NULL DEFAULT 'estimated',
                    seconds TEXT NOT NULL DEFAULT '0',
                    estimate_seconds TEXT NOT NULL DEFAULT '0',
                    active_seconds TEXT NOT NULL DEFAULT '0',
                    paused_seconds TEXT NOT NULL DEFAULT '0',
                    created_at TEXT NOT NULL, observed_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jade_live_budget_charges(
                    reservation_id TEXT NOT NULL REFERENCES jade_live_budget_reservations(id),
                    day TEXT NOT NULL, month TEXT NOT NULL, usd TEXT NOT NULL,
                    PRIMARY KEY(reservation_id,day));
                CREATE INDEX IF NOT EXISTS jade_live_budget_period
                    ON jade_live_budget_charges(day,month);
            """)
            # Additive migration for private ledgers created by the first prototype.
            db.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in db.execute("PRAGMA table_info(jade_live_budget_reservations)")}
            if "estimate_seconds" not in columns:
                db.execute("""ALTER TABLE jade_live_budget_reservations
                    ADD COLUMN estimate_seconds TEXT NOT NULL DEFAULT '0'""")
            db.commit()

    @contextmanager
    def _connect(self, *, transaction: bool = False):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            if transaction:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if transaction:
                db.commit()
        except BaseException:
            if transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def _now(self, now: datetime | None) -> datetime:
        return _aware(now if now is not None else self._clock())

    @staticmethod
    def _id(value: object) -> str:
        if (not isinstance(value, str) or not 1 <= len(value) <= 256
                or any(ord(char) < 32 for char in value)):
            raise ValueError("invalid Live reservation ID")
        return value

    @staticmethod
    def _row(db, reservation_id: str):
        row = db.execute("SELECT * FROM jade_live_budget_reservations WHERE id=?",
                         (reservation_id,)).fetchone()
        if row is None:
            raise KeyError("unknown Live reservation")
        return row

    def _snapshot(self, db, now: datetime) -> dict:
        day = paris_date(now).isoformat()
        month = day[:7]
        buckets = {period: {"spent": ZERO, "voice": ZERO, "backend": ZERO,
                            "estimated": ZERO, "confirmed": ZERO, "invoiced": ZERO}
                   for period in ("daily", "monthly")}
        rows = db.execute("""SELECT c.day,c.month,c.usd,r.kind,r.quality
            FROM jade_live_budget_charges c JOIN jade_live_budget_reservations r
            ON c.reservation_id=r.id WHERE c.day=? OR c.month=?""", (day, month))
        for row in rows:
            amount = Decimal(row["usd"])
            for period, matches in (("daily", row["day"] == day),
                                    ("monthly", row["month"] == month)):
                if not matches:
                    continue
                bucket = buckets[period]
                bucket["spent"] += amount
                bucket[row["kind"]] += amount
                if row["quality"] == "estimated":
                    bucket["estimated"] += amount
                else:
                    bucket["confirmed"] += amount
                if row["quality"] == "invoice":
                    bucket["invoiced"] += amount
        pending = db.execute("""SELECT quote_usd,spent_usd,state
            FROM jade_live_budget_reservations WHERE state IN ('reserved','active','unknown')""").fetchall()
        reserved = sum((max(ZERO, Decimal(row["quote_usd"]) - Decimal(row["spent_usd"]))
                        for row in pending), ZERO)
        snapshot = {
            "timezone": "Europe/Paris", "date": day, "month": month,
            "rate_date": RATE_DATE,
            "period_allocation": "observation_interval_estimate",
            "open_reservations": len(pending),
            "unknown_reservations": sum(row["state"] == "unknown" for row in pending),
            "reserved_usd": _usd(reserved),
        }
        available = []
        for period, limit in (("daily", self.daily_usd), ("monthly", self.monthly_usd)):
            bucket = buckets[period]
            exposure = bucket["spent"] + reserved
            remaining = max(ZERO, limit - exposure)
            available.append(remaining)
            snapshot[period] = {
                "limit_usd": _usd(limit), "spent_usd": _usd(bucket["spent"]),
                "reserved_usd": _usd(reserved), "exposure_usd": _usd(exposure),
                "available_usd": _usd(remaining), "over_limit": exposure > limit,
                "voice_usd": _usd(bucket["voice"]), "backend_usd": _usd(bucket["backend"]),
                "estimated_usd": _usd(bucket["estimated"]),
                "confirmed_usd": _usd(bucket["confirmed"]),
                "invoiced_usd": _usd(bucket["invoiced"]),
            }
        snapshot["available_usd"] = _usd(min(available))
        snapshot["admission"] = bool(self.daily_usd and self.monthly_usd and min(available) > 0)
        snapshot["remaining_usd"] = snapshot["available_usd"]
        snapshot["available"] = snapshot["admission"]
        snapshot["over_budget"] = any(snapshot[period]["over_limit"] for period in ("daily", "monthly"))
        return snapshot

    def snapshot(self, *, now: datetime | None = None) -> dict:
        point = self._now(now)
        with self._connect() as db:
            # One consistent read snapshot across reservation and charge tables.
            db.execute("BEGIN")
            return self._snapshot(db, point)

    def admission(self, quote: object, *, now: datetime | None = None) -> bool:
        """Read-only indication; only reserve() can grant atomic admission."""
        amount = _amount(quote)
        result = self.snapshot(now=now)
        return bool(amount and result["admission"] and amount <= Decimal(result["available_usd"]))

    def reserve(self, reservation_id: str, quote: object, kind: str = "voice",
                *, now: datetime | None = None) -> bool:
        identifier = self._id(reservation_id)
        amount = _amount(quote)
        point = self._now(now)
        if kind not in ("voice", "backend"):
            raise ValueError("invalid Live cost category")
        if not amount or not self.daily_usd or not self.monthly_usd:
            return False
        with self._connect(transaction=True) as db:
            previous = db.execute("SELECT * FROM jade_live_budget_reservations WHERE id=?",
                                  (identifier,)).fetchone()
            if previous is not None:
                if previous["kind"] != kind or Decimal(previous["quote_usd"]) != amount:
                    raise ValueError("Live reservation ID reused with different terms")
                return previous["state"] in ("reserved", "active")
            current = self._snapshot(db, point)
            if amount > Decimal(current["available_usd"]):
                return False
            stamp = point.isoformat()
            db.execute("""INSERT INTO jade_live_budget_reservations
                (id,kind,quote_usd,created_at,observed_at) VALUES(?,?,?,?,?)""",
                       (identifier, kind, _usd(amount), stamp, stamp))
        return True

    def _allocate(self, db, row, new_total: Decimal, now: datetime) -> None:
        """Replace a cumulative total, keeping exact Decimal sums across buckets."""
        old_total = Decimal(row["spent_usd"])
        delta = new_total - old_total
        if delta == 0:
            return
        if delta < 0:
            # More precise split/rate or an invoice can replace a high estimate.
            charges = db.execute("""SELECT day,usd FROM jade_live_budget_charges
                WHERE reservation_id=? ORDER BY day""", (row["id"],)).fetchall()
            remaining = new_total
            for index, charge in enumerate(charges):
                value = (remaining if index == len(charges) - 1 else
                         (Decimal(charge["usd"]) * new_total / old_total).quantize(
                             USD_QUANTUM, rounding=ROUND_HALF_EVEN))
                value = min(remaining, max(ZERO, value))
                remaining -= value
                db.execute("""UPDATE jade_live_budget_charges SET usd=?
                    WHERE reservation_id=? AND day=?""", (_usd(value), row["id"], charge["day"]))
            return
        start = _aware(datetime.fromisoformat(row["observed_at"]))
        slices = _period_slices(start, now)
        weight_sum = sum((weight for _, weight in slices), ZERO)
        remaining = delta
        for index, (day, weight) in enumerate(slices):
            value = (remaining if index == len(slices) - 1 else
                     (delta * weight / weight_sum).quantize(USD_QUANTUM, rounding=ROUND_HALF_EVEN))
            value = min(remaining, max(ZERO, value))
            remaining -= value
            previous = db.execute("""SELECT usd FROM jade_live_budget_charges
                WHERE reservation_id=? AND day=?""", (row["id"], day)).fetchone()
            total = value + (Decimal(previous["usd"]) if previous else ZERO)
            db.execute("""INSERT INTO jade_live_budget_charges(reservation_id,day,month,usd)
                VALUES(?,?,?,?) ON CONFLICT(reservation_id,day) DO UPDATE SET usd=excluded.usd""",
                       (row["id"], day, day[:7], _usd(total)))

    @staticmethod
    def _reservation(row) -> dict:
        return {
            "reservation_id": row["id"], "kind": row["kind"], "state": row["state"],
            "quote_usd": row["quote_usd"], "spent_usd": row["spent_usd"],
            "remaining_reserved_usd": _usd(max(ZERO, Decimal(row["quote_usd"])
                                                   - Decimal(row["spent_usd"])))
            if row["state"] in ("reserved", "active", "unknown") else "0",
            "quality": row["quality"], "seconds": row["seconds"],
            "estimated_seconds": row["estimate_seconds"],
            "active_seconds": row["active_seconds"], "paused_seconds": row["paused_seconds"],
        }

    def reservation(self, reservation_id: str) -> dict:
        with self._connect() as db:
            return self._reservation(self._row(db, self._id(reservation_id)))

    def estimate_usage(self, reservation_id: str, seconds: object,
                       *, now: datetime | None = None) -> dict:
        """Wall-clock upper estimate, separate from the cumulative provider counter.

        A later provider snapshot may replace this value downwards. It must never
        be interpreted as another duration increment or as confirmed final usage.
        """
        identifier = self._id(reservation_id)
        duration = _amount(seconds, upper=Decimal("31536000"))
        point = self._now(now)
        with self._connect(transaction=True) as db:
            row = self._row(db, identifier)
            if row["kind"] != "voice":
                raise ValueError("duration estimates belong only to voice reservations")
            if (row["state"] in ("closed", "released")
                    or duration <= Decimal(row["estimate_seconds"])):
                return self._reservation(row)
            cost = max(Decimal(row["spent_usd"]), quote_voice(duration, active_rate=self.active_rate))
            self._allocate(db, row, cost, point)
            db.execute("""UPDATE jade_live_budget_reservations SET spent_usd=?,estimate_seconds=?,
                quality='estimated',observed_at=? WHERE id=?""",
                       (_usd(cost), _usd(duration),
                        max(point, datetime.fromisoformat(row["observed_at"])).isoformat(), identifier))
            return self._reservation(self._row(db, identifier))

    def update_usage(self, reservation_id: str, seconds: object, *,
                     active_seconds: object | None = None, paused_seconds: object | None = None,
                     final: bool = False, now: datetime | None = None) -> dict:
        identifier = self._id(reservation_id)
        total = _amount(seconds, upper=Decimal("31536000"))
        point = self._now(now)
        if type(final) is not bool:
            raise ValueError("invalid usage finalization flag")
        if (active_seconds is None) != (paused_seconds is None):
            raise ValueError("active and paused usage must be supplied together")
        active = _amount(active_seconds) if active_seconds is not None else None
        paused = _amount(paused_seconds) if paused_seconds is not None else None
        if active is not None and active + paused > total:
            raise ValueError("usage components exceed total seconds")
        with self._connect(transaction=True) as db:
            row = self._row(db, identifier)
            if row["kind"] != "voice":
                raise ValueError("duration usage belongs only to voice reservations")
            previous_total = Decimal(row["seconds"])
            if row["state"] in ("closed", "released") or total < previous_total:
                return self._reservation(row)
            previous_active, previous_paused = Decimal(row["active_seconds"]), Decimal(row["paused_seconds"])
            if active is not None:
                if active < previous_active or paused < previous_paused:
                    return self._reservation(row)
            else:
                active, paused = previous_active, previous_paused
            unknown = total - active - paused
            cost = (((active + unknown) * self.active_rate + paused * self.standby_rate)
                    / Decimal(60)).quantize(USD_QUANTUM, rounding=ROUND_UP)
            quality = "estimated" if unknown else "provider_usage"
            self._allocate(db, row, cost, point)
            state = "closed" if final else ("unknown" if row["state"] == "unknown" else "active")
            observed = (max(point, datetime.fromisoformat(row["observed_at"])).isoformat()
                        if total > previous_total else row["observed_at"])
            db.execute("""UPDATE jade_live_budget_reservations SET spent_usd=?,seconds=?,
                active_seconds=?,paused_seconds=?,quality=?,state=?,observed_at=? WHERE id=?""",
                       (_usd(cost), _usd(total), _usd(active), _usd(paused), quality,
                        state, observed, identifier))
            return self._reservation(self._row(db, identifier))

    def reconcile(self, reservation_id: str, actual_usd: object, *, confirmed: bool = True,
                  invoiced: bool = False, now: datetime | None = None) -> dict:
        """Finalize a known charge. Uncertain work must use mark_unknown instead."""
        identifier = self._id(reservation_id)
        amount = _amount(actual_usd)
        point = self._now(now)
        if type(confirmed) is not bool or type(invoiced) is not bool or (invoiced and not confirmed):
            raise ValueError("invalid cost evidence flags")
        quality = "invoice" if invoiced else ("confirmed_cost" if confirmed else "estimated")
        with self._connect(transaction=True) as db:
            row = self._row(db, identifier)
            evidence_order = {"estimated": 0, "provider_usage": 1, "confirmed_cost": 2, "invoice": 3}
            if evidence_order[row["quality"]] > evidence_order[quality]:
                return self._reservation(row)
            self._allocate(db, row, amount, point)
            db.execute("""UPDATE jade_live_budget_reservations SET spent_usd=?,quality=?,
                state='closed',observed_at=? WHERE id=?""",
                       (_usd(amount), quality, point.isoformat(), identifier))
            return self._reservation(self._row(db, identifier))

    def release(self, reservation_id: str, *, now: datetime | None = None) -> bool:
        """Release unused exposure after a known refusal/cancellation, retaining usage."""
        identifier = self._id(reservation_id)
        self._now(now)
        with self._connect(transaction=True) as db:
            row = self._row(db, identifier)
            if row["state"] in ("closed", "released"):
                return False
            if row["state"] == "unknown":
                raise ValueError("unknown Live cost must be reconciled before releasing its reserve")
            db.execute("UPDATE jade_live_budget_reservations SET state='released' WHERE id=?", (identifier,))
        return True

    def mark_unknown(self, reservation_id: str, *, now: datetime | None = None) -> dict:
        """Persist ambiguous creation/closure/backend work, without freeing its reserve."""
        identifier = self._id(reservation_id)
        self._now(now)
        with self._connect(transaction=True) as db:
            row = self._row(db, identifier)
            if row["state"] not in ("closed", "released"):
                db.execute("UPDATE jade_live_budget_reservations SET state='unknown' WHERE id=?", (identifier,))
            return self._reservation(self._row(db, identifier))
