"""Europe/Paris dates without a mandatory tzdata wheel on Windows.

Uses IANA zoneinfo when present. The fallback implements the current EU
daylight-saving rule, 01:00 UTC on the last Sunday of March/October. Revisit
if EU law changes.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _last_sunday(year: int, month: int) -> datetime:
    point = datetime(year, month, 31, 1, tzinfo=timezone.utc)
    return point - timedelta(days=(point.weekday() + 1) % 7)


def paris_date(now: datetime | None = None) -> date:
    point = now or datetime.now(timezone.utc)
    if point.tzinfo is None or point.utcoffset() is None:
        raise ValueError("a timezone-aware timestamp is required")
    try:
        return point.astimezone(ZoneInfo("Europe/Paris")).date()
    except ZoneInfoNotFoundError:
        utc = point.astimezone(timezone.utc)
        start, end = _last_sunday(utc.year, 3), _last_sunday(utc.year, 10)
        return (utc + timedelta(hours=2 if start <= utc < end else 1)).date()
