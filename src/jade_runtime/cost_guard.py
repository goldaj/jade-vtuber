"""Private, durable USD reservations for optional API calls.

Reservations are conservative estimates, not the provider's final invoice.
Default limits of zero disable paid initiatives and classifier calls.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib
import sqlite3
from zoneinfo import ZoneInfo

_PARIS = ZoneInfo("Europe/Paris")


def money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid dollar amount") from exc
    if not amount.is_finite() or not 0 <= amount <= 10000:
        raise ValueError("invalid dollar budget")
    return amount


class CostGuard:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.suffix != ".sqlite3":
            raise ValueError("use an absolute private SQLite path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=5) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jade_cost_reservations(
                category TEXT NOT NULL, request_hash TEXT NOT NULL,
                date_local TEXT NOT NULL, month_local TEXT NOT NULL,
                estimated_usd TEXT NOT NULL, PRIMARY KEY(category,request_hash))""")
            db.execute("""CREATE INDEX IF NOT EXISTS idx_jade_cost_period
                ON jade_cost_reservations(category,date_local,month_local)""")

    def reserve(self, category, event_key, *, quote_usd, daily_usd,
                monthly_usd, now=None):
        if category not in ("social_review", "initiative"):
            raise ValueError("invalid optional category")
        if not isinstance(event_key, str) or not 1 <= len(event_key) <= 500:
            raise ValueError("invalid event")
        quote, daily, monthly = money(quote_usd), money(daily_usd), money(monthly_usd)
        if not quote or not daily or not monthly:
            return False
        day = (now or datetime.now(_PARIS)).astimezone(_PARIS).date().isoformat()
        month = day[:7]
        digest = hashlib.sha256(event_key.encode()).hexdigest()
        with sqlite3.connect(self.path, timeout=5, isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("""SELECT 1 FROM jade_cost_reservations
                WHERE category=? AND request_hash=?""",
                (category,digest)).fetchone():
                db.rollback()
                return False
            rows = db.execute("""SELECT date_local,month_local,estimated_usd
                FROM jade_cost_reservations
                WHERE category=? AND (date_local=? OR month_local=?)""",
                (category,day,month)).fetchall()
            today = sum((money(amount) for d,m,amount in rows if d==day),Decimal(0))
            current = sum((money(amount) for d,m,amount in rows if m==month),Decimal(0))
            if today+quote > daily or current+quote > monthly:
                db.rollback()
                return False
            db.execute("""INSERT INTO jade_cost_reservations
                (category,request_hash,date_local,month_local,estimated_usd)
                VALUES(?,?,?,?,?)""",(category,digest,day,month,str(quote)))
            db.commit()
            return True

    def reserved_usd(self, category, *, now=None):
        day=(now or datetime.now(_PARIS)).astimezone(_PARIS).date().isoformat()
        with sqlite3.connect(self.path, timeout=5) as db:
            amounts=db.execute("""SELECT estimated_usd FROM jade_cost_reservations
                WHERE category=? AND date_local=?""",(category,day)).fetchall()
        return sum((money(a[0]) for a in amounts),Decimal(0))
