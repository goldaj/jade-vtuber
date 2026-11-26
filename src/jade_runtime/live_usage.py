"""Private, passive Live usage observations with no spending policy.

Provider seconds, estimates and invoice amounts remain distinguishable. Recording
an operation never depends on its cost or earlier consumption. Monthly summaries
use Paris civil time. Internal daily rows only preserve the historical SQLite
format and split observations across calendar boundaries; they implement no
public daily view or limit. Callers handle storage failures best-effort, without
using this tracking to decide whether mobile Live can operate.
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


def _amount(value: object, *, upper: Decimal | None = None) -> Decimal:
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise ValueError("invalid Live numeric amount") from exc
    if not result.is_finite() or result < ZERO or (upper is not None and result > upper):
        raise ValueError("Live numeric amounts must be finite and nonnegative")
    return result


def _usd(value: Decimal) -> str:
    return format(value, "f")


def quote_voice(seconds: object, *, active_rate: object = ACTIVE_USD_PER_MINUTE) -> Decimal:
    """Conservative all-active quote, rounded upward; no second startup surcharge."""
    duration = _amount(seconds, upper=Decimal("31536000"))
    rate = _amount(active_rate)
    return (duration * rate / Decimal(60)).quantize(USD_QUANTUM, rounding=ROUND_UP)



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


class LiveUsageLedger:
    def __init__(self, path: str | Path,
                 *, now: Callable[[], datetime] | None = None,
                 active_rate: object = ACTIVE_USD_PER_MINUTE,
                 standby_rate: object = STANDBY_USD_PER_MINUTE):
        self.path = Path(path).expanduser()
        repo_root = Path(__file__).resolve().parents[2]
        if (not self.path.is_absolute() or self.path.suffix != ".sqlite3"
                or self.path.resolve().is_relative_to(repo_root) or self.path.is_symlink()):
            raise ValueError("Live ledger requires an absolute private SQLite path outside Git")
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
            # Retain legacy table names and observations; migrations are additive.
            db.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in db.execute("PRAGMA table_info(jade_live_budget_reservations)")}
            if "estimate_seconds" not in columns:
                db.execute("""ALTER TABLE jade_live_budget_reservations
                    ADD COLUMN estimate_seconds TEXT NOT NULL DEFAULT '0'""")
            db.execute("""CREATE TABLE IF NOT EXISTS jade_live_usage_backend(
                reservation_id TEXT PRIMARY KEY REFERENCES jade_live_budget_reservations(id),
                input_tokens TEXT, output_tokens TEXT, cached_input_tokens TEXT,
                status TEXT NOT NULL, observed_at TEXT NOT NULL)""")
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
        if (not isinstance(value, str) or not 1 <= len(value) <= 256 or not value.strip()
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
        month = paris_date(now).isoformat()[:7]
        totals = {key: ZERO for key in (
            "recorded", "voice", "backend", "estimated", "provider_usage", "confirmed", "invoiced")}
        rows = db.execute("""SELECT c.usd,r.kind,r.quality
            FROM jade_live_budget_charges c JOIN jade_live_budget_reservations r
            ON c.reservation_id=r.id WHERE c.month=?""", (month,))
        evidence = {"estimated": "estimated", "provider_usage": "provider_usage",
                    "confirmed_cost": "confirmed", "invoice": "invoiced"}
        for row in rows:
            amount = Decimal(row["usd"])
            totals["recorded"] += amount
            totals[row["kind"]] += amount
            if row["quality"] in evidence:
                totals[evidence[row["quality"]]] += amount
        records = db.execute("""SELECT state,quality,created_at,observed_at
            FROM jade_live_budget_reservations""").fetchall()
        open_records = unknown_records = unpriced = 0
        for row in records:
            ongoing = row["state"] in ("reserved", "active", "unknown")
            open_records += ongoing
            unknown_records += row["state"] == "unknown"
            start_month = paris_date(datetime.fromisoformat(row["created_at"])).isoformat()[:7]
            end_month = paris_date(datetime.fromisoformat(row["observed_at"])).isoformat()[:7]
            if row["quality"] == "unpriced" and start_month <= month and (ongoing or month <= end_month):
                unpriced += 1
        return {
            "mode": "passive", "scope": "live_only", "currency": "USD",
            "timezone": "Europe/Paris", "month": month, "rate_date": RATE_DATE,
            "period_allocation": "observation_interval_estimate",
            "open_records": open_records, "unknown_records": unknown_records,
            "monthly": {**{key + "_usd": _usd(value) for key, value in totals.items()},
                        "unpriced_records": unpriced},
        }

    def snapshot(self, *, now: datetime | None = None) -> dict:
        point = self._now(now)
        with self._connect() as db:
            db.execute("BEGIN")
            return self._snapshot(db, point)

    def reserve(self, reservation_id: str, quote_usd: object = 0, kind: str = "voice",
                *, now: datetime | None = None) -> bool:
        """Idempotently register an observation; never grant or deny spending.

        The retained method and quote names support existing call sites. A quote
        is optional historical metadata, never reserved money or a usage limit.
        """
        identifier = self._id(reservation_id)
        amount = _amount(quote_usd)
        point = self._now(now)
        if kind not in ("voice", "backend"):
            raise ValueError("invalid Live cost category")
        with self._connect(transaction=True) as db:
            previous = db.execute("SELECT * FROM jade_live_budget_reservations WHERE id=?",
                                  (identifier,)).fetchone()
            if previous is not None:
                if previous["kind"] != kind or Decimal(previous["quote_usd"]) != amount:
                    raise ValueError("Live observation ID reused with different metadata")
                return True
            stamp = point.isoformat()
            db.execute("""INSERT INTO jade_live_budget_reservations
                (id,kind,quote_usd,quality,created_at,observed_at) VALUES(?,?,?,'unpriced',?,?)""",
                       (identifier, kind, _usd(amount), stamp, stamp))
        return True

    def _allocate(self, db, row, new_total: Decimal, now: datetime, *, restate: bool = False) -> None:
        """Replace a cumulative total, keeping exact Decimal sums across buckets."""
        old_total = Decimal(row["spent_usd"])
        delta = new_total - old_total
        if delta == 0:
            return
        if delta < 0 or restate:
            # Refining a finished observation restates its original periods;
            # receipt of a later invoice is not new usage in the receipt month.
            charges = db.execute("""SELECT day,usd FROM jade_live_budget_charges
                WHERE reservation_id=? ORDER BY day""", (row["id"],)).fetchall()
            weights = [Decimal(charge["usd"]) for charge in charges]
            if charges and not sum(weights, ZERO):
                # A previously zeroed invoice retains its original period rows.
                # Their relative amounts are unknown, so keep an explicit equal
                # allocation estimate rather than moving usage to receipt time.
                weights = [Decimal(1)] * len(charges)
            weight_total = sum(weights, ZERO)
            remaining = new_total
            for index, charge in enumerate(charges):
                value = (remaining if index == len(charges) - 1 else
                         (weights[index] * new_total / weight_total).quantize(
                             USD_QUANTUM, rounding=ROUND_HALF_EVEN))
                value = min(remaining, max(ZERO, value))
                remaining -= value
                db.execute("""UPDATE jade_live_budget_charges SET usd=?
                    WHERE reservation_id=? AND day=?""", (_usd(value), row["id"], charge["day"]))
            if charges:
                return
        # First pricing of a finished, previously unpriced backend operation
        # uses its recorded execution interval, not the later invoice date.
        start = _aware(datetime.fromisoformat(row["created_at"] if restate else row["observed_at"]))
        if restate:
            now = _aware(datetime.fromisoformat(row["observed_at"]))
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
            "cost_usd": None if row["quality"] == "unpriced" else row["spent_usd"],
            "quality": row["quality"], "seconds": row["seconds"],
            "estimated_seconds": row["estimate_seconds"],
            "active_seconds": row["active_seconds"], "paused_seconds": row["paused_seconds"],
        }

    def reservation(self, reservation_id: str) -> dict:
        with self._connect() as db:
            identifier = self._id(reservation_id)
            result = self._reservation(self._row(db, identifier))
            if result["kind"] == "backend":
                result["backend_usage"] = self._backend_usage(db, identifier)
            return result

    @staticmethod
    def _backend_usage(db, identifier: str) -> dict:
        row = db.execute("SELECT * FROM jade_live_usage_backend WHERE reservation_id=?",
                         (identifier,)).fetchone()
        counters = {
            key: int(row[key]) if row is not None and row[key] is not None else None
            for key in ("input_tokens", "output_tokens", "cached_input_tokens")
        }
        # These counters do not cover every model, tool, cache rate or invoice.
        return {**counters, "status": row["status"] if row is not None else "unobserved",
                "quality": "partial", "cost_usd": None}

    def record_backend_usage(self, reservation_id: str, usage: dict | None, status: str,
                             *, now: datetime | None = None) -> dict:
        """Store cumulative backend counters without inventing a dollar amount.

        A completed operation can still have unpriced tool/model usage. Unknown
        fields, including an unverified cost_usd, are deliberately not persisted.
        Replayed counters replace earlier snapshots instead of being added.
        """
        identifier = self._id(reservation_id)
        point = self._now(now)
        if status not in ("completed", "cancelled", "unknown"):
            raise ValueError("invalid backend observation status")
        if usage is not None and not isinstance(usage, dict):
            raise ValueError("backend usage must contain counters")
        incoming = {}
        for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
            value = (usage or {}).get(key)
            if value is not None:
                if type(value) is not int or value < 0:
                    raise ValueError("backend token counts must be nonnegative integers")
                incoming[key] = value
        with self._connect(transaction=True) as db:
            row = self._row(db, identifier)
            if row["kind"] != "backend":
                raise ValueError("backend counters belong only to backend observations")
            previous = self._backend_usage(db, identifier)
            counters = {key: (max(value, incoming[key]) if value is not None and key in incoming
                              else incoming.get(key, value))
                        for key, value in previous.items()
                        if key in ("input_tokens", "output_tokens", "cached_input_tokens")}
            if previous["status"] == "completed":
                status = "completed"
            stamp = max(point, datetime.fromisoformat(row["observed_at"])).isoformat()
            values = [str(counters[key]) if counters[key] is not None else None
                      for key in ("input_tokens", "output_tokens", "cached_input_tokens")]
            db.execute("""INSERT INTO jade_live_usage_backend
                (reservation_id,input_tokens,output_tokens,cached_input_tokens,status,observed_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(reservation_id) DO UPDATE SET
                input_tokens=excluded.input_tokens,output_tokens=excluded.output_tokens,
                cached_input_tokens=excluded.cached_input_tokens,status=excluded.status,
                observed_at=excluded.observed_at""", (identifier, *values, status, stamp))
            state = row["state"]
            if state not in ("closed", "released"):
                state = "closed" if status == "completed" else "unknown"
            db.execute("""UPDATE jade_live_budget_reservations
                SET state=?,observed_at=? WHERE id=?""", (state, stamp, identifier))
            result = self._reservation(self._row(db, identifier))
            result["backend_usage"] = self._backend_usage(db, identifier)
            return result

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
            evidence_order = {"unpriced": -1, "estimated": 0, "provider_usage": 1,
                              "confirmed_cost": 2, "invoice": 3}
            if evidence_order[row["quality"]] > evidence_order[quality]:
                return self._reservation(row)
            self._allocate(db, row, amount, point, restate=row["state"] in ("closed", "released"))
            db.execute("""UPDATE jade_live_budget_reservations SET spent_usd=?,quality=?,
                state='closed',observed_at=? WHERE id=?""",
                       (_usd(amount), quality, point.isoformat(), identifier))
            return self._reservation(self._row(db, identifier))

    def release(self, reservation_id: str, *, now: datetime | None = None) -> bool:
        """Finish a known unused operation, retaining all observed usage."""
        identifier = self._id(reservation_id)
        self._now(now)
        with self._connect(transaction=True) as db:
            row = self._row(db, identifier)
            if row["state"] in ("closed", "released"):
                return False
            if row["state"] == "unknown":
                raise ValueError("unknown Live usage cannot be declared unused")
            db.execute("""UPDATE jade_live_budget_reservations SET state='released',
                quality=CASE WHEN quality='unpriced' THEN 'confirmed_cost' ELSE quality END
                WHERE id=?""", (identifier,))
        return True

    def mark_unknown(self, reservation_id: str, *, now: datetime | None = None) -> dict:
        """Preserve uncertainty for observation only; it never blocks other records."""
        identifier = self._id(reservation_id)
        self._now(now)
        with self._connect(transaction=True) as db:
            row = self._row(db, identifier)
            if row["state"] not in ("closed", "released"):
                db.execute("UPDATE jade_live_budget_reservations SET state='unknown' WHERE id=?", (identifier,))
            return self._reservation(self._row(db, identifier))
