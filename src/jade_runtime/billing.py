"""Private organization cost reporting through OpenAI's documented admin API."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BillingCosts:
    """One cached snapshot per organization admin key; never exposes that key."""

    def __init__(self, admin_key: str = ""):
        self._key = admin_key
        self._lock = asyncio.Lock()
        self._snapshot = None
        self._last_attempt = 0.0
        self._error = None

    def _fetch(self, now: datetime) -> dict:
        month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        totals = {}
        days = {}
        page = None
        seen = set()
        opener = build_opener(_NoRedirect())
        for _ in range(20):
            query = {"start_time": int(month.timestamp()), "bucket_width": "1d", "limit": 31}
            if page:
                query["page"] = page
            request = Request("https://api.openai.com/v1/organization/costs?" + urlencode(query),
                              headers={"Authorization": "Bearer " + self._key, "Accept": "application/json"})
            with opener.open(request, timeout=8) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("cost response too large")
            payload = json.loads(raw, parse_float=Decimal)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError("invalid costs response")
            for bucket in payload["data"]:
                if not isinstance(bucket, dict) or not isinstance(bucket.get("results"), list):
                    raise ValueError("invalid cost bucket")
                start = bucket.get("start_time")
                if type(start) is not int or start < int(month.timestamp()) or start > int(now.timestamp()):
                    raise ValueError("unexpected cost bucket date")
                for result in bucket["results"]:
                    amount = result.get("amount") if isinstance(result, dict) else None
                    if not isinstance(amount, dict) or not isinstance(amount.get("currency"), str):
                        raise ValueError("missing monetary amount")
                    currency = amount["currency"].lower()
                    if not re.fullmatch(r"[a-z]{3}", currency):
                        raise ValueError("invalid currency")
                    try:
                        value = Decimal(str(amount["value"]))
                    except (KeyError, InvalidOperation):
                        raise ValueError("invalid cost") from None
                    if not value.is_finite():
                        raise ValueError("invalid cost")
                    totals[currency] = totals.get(currency, Decimal(0)) + value
                    if start >= int(today.timestamp()):
                        days[currency] = days.get(currency, Decimal(0)) + value
            if payload.get("has_more") is False:
                return {
                    "status": "ok",
                    "balance": None,
                    "balance_status": "unavailable",
                    "period_timezone": "UTC",
                    "today": {key: str(days.get(key, Decimal(0))) for key in totals},
                    "month": {key: str(value) for key, value in totals.items()},
                    "checked_at": now.isoformat(),
                }
            page = payload.get("next_page")
            if not isinstance(page, str) or not page or len(page) > 1024 or page in seen:
                raise ValueError("invalid costs pagination")
            seen.add(page)
        raise ValueError("cost pagination limit exceeded")

    def _dated_snapshot(self, now: datetime) -> tuple[dict, bool]:
        """Never present an old UTC period as the current day or month."""
        snapshot = dict(self._snapshot)
        checked = datetime.fromisoformat(snapshot["checked_at"]).astimezone(timezone.utc)
        changed = checked.date() != now.date()
        if changed:
            snapshot["today"] = None
        if (checked.year, checked.month) != (now.year, now.month):
            snapshot["month"] = None
        return snapshot, changed

    async def get(self, *, refresh: bool = False) -> dict:
        if not self._key:
            return {"status": "not_configured", "balance": None, "balance_status": "unavailable"}
        async with self._lock:
            current = time.monotonic()
            now = datetime.now(timezone.utc)
            snapshot, day_changed = (self._dated_snapshot(now) if self._snapshot is not None
                                     else (None, False))
            age_limit = 30 if refresh else 300
            if snapshot is not None and not day_changed and current - self._last_attempt < age_limit:
                return ({**snapshot, "status": "stale", "error": self._error}
                        if self._error else snapshot)
            if self._last_attempt and current - self._last_attempt < 30:
                return ({**snapshot, "status": "stale", "error": self._error}
                        if snapshot is not None else
                        {"status": self._error or "unavailable", "balance": None, "balance_status": "unavailable"})
            self._last_attempt = current
            try:
                self._snapshot = await asyncio.to_thread(self._fetch, now)
                self._error = None
            except HTTPError as exc:
                status = "access_denied" if exc.code in (401, 403) else "unavailable"
                self._error = status
                return {**snapshot, "status": "stale", "error": status} if snapshot is not None else {
                    "status": status, "balance": None, "balance_status": "unavailable"}
            except Exception:
                self._error = "unavailable"
                return {**snapshot, "status": "stale", "error": "unavailable"} if snapshot is not None else {
                    "status": "unavailable", "balance": None, "balance_status": "unavailable"}
            return self._snapshot
