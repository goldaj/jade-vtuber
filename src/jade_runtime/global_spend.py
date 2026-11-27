"""Private, read-only collection of the API spend used by Discord's policy.

The OpenAI organization query intentionally has no project, API-key, model or
channel filter: it includes Responses, speech, transcription, Realtime, Live,
tools and other charged OpenAI products. Tavily uses ACCOUNT usage, not key
usage. Neither collector ever blocks a mobile/classic request.

Sources verified 2026-11-27:
https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs
https://docs.tavily.com/documentation/api-reference/endpoint/usage
https://docs.tavily.com/documentation/api-credits
https://help.tavily.com/articles/3116968635-when-do-my-monthly-api-credits-reset
https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml

Provider reporting is not an instantaneous billing watermark. This standard
collector consequently returns bounded/estimated coverage (40 EUR policy),
never "complete" merely because an HTTP GET succeeded. The 40 EUR threshold is
the owner's prudential margin, not a guarantee of the final provider invoice.
"""
from __future__ import annotations

import asyncio
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_UP
import json
import os
from pathlib import Path
import sqlite3
import time as monotonic_time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

from .paris_clock import paris_date


OPENAI_COSTS_URL = "https://api.openai.com/v1/organization/costs"
TAVILY_USAGE_URL = "https://api.tavily.com/usage"
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
TAVILY_PRICE_SOURCE = "https://docs.tavily.com/documentation/api-credits"
TAVILY_CREDIT_USD_UPPER = Decimal("0.008")
TAVILY_PRICE_DATE = "2026-11-27"
TAVILY_STANDARD_PLANS = frozenset(("researcher", "free", "project", "bootstrap", "startup", "growth", "pay as you go", "pay-as-you-go", "paygo"))
ZERO = Decimal(0)


async def run_blocking_owned(function, *args):
    """Keep ownership of bounded blocking work until its real thread finishes.

    Cancelling an await on to_thread does not stop SQLite/HTTP in that thread.
    Releasing a policy lock or reporting close complete at that point can leave
    a writer touching state after shutdown; Windows also refuses file cleanup.
    Preserve cancellation, including repeated requests, but first join the work
    while its caller still owns the relevant lock and private resources.
    """
    worker = asyncio.create_task(asyncio.to_thread(function, *args))
    cancelled = None
    while True:
        try:
            result = await asyncio.shield(worker)
        except asyncio.CancelledError as error:
            if worker.cancelled():
                raise
            cancelled = error
        except BaseException:
            if cancelled is not None:
                raise cancelled from None
            raise
        else:
            if cancelled is not None:
                raise cancelled
            return result


def aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("spend timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def amount(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("invalid spend amount")
    try:
        value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("invalid spend amount") from None
    if not value.is_finite() or value < 0 or value > Decimal("1000000000000"):
        raise ValueError("invalid spend amount")
    return value


def paris_month(now: datetime) -> tuple[str, datetime, datetime]:
    """Exact Paris month bounds, including Windows without installed tzdata."""
    local = paris_date(aware(now))
    first = local.replace(day=1)
    following = (first.replace(day=28) + timedelta(days=4)).replace(day=1)

    def midnight(day):
        utc_midnight = datetime.combine(day, time.min, tzinfo=timezone.utc)
        for offset in (1, 2):
            candidate = utc_midnight - timedelta(hours=offset)
            if paris_date(candidate) == day and paris_date(candidate - timedelta(microseconds=1)) < day:
                return candidate
        raise ValueError("Paris month boundary unavailable")

    return first.isoformat()[:7], midnight(first), midnight(following)


class SpendStore:
    """Only totals, dates and technical reasons; no keys or user content."""

    def __init__(self, path):
        self.path = Path(path).expanduser()
        repo = Path(__file__).resolve().parents[2]
        if (not self.path.is_absolute() or self.path.suffix != ".sqlite3"
                or self.path.resolve().is_relative_to(repo) or self.path.is_symlink()):
            raise ValueError("global spend requires an absolute private SQLite path outside Git")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(descriptor)
        if os.name != "nt":
            self.path.chmod(0o600)
        with closing(self.connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS global_spend_state (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS discord_live_month_latch (
                month TEXT PRIMARY KEY, threshold_eur TEXT NOT NULL,
                observed_eur TEXT NOT NULL, triggered_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS discord_live_reservations (
                reservation_key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
            db.commit()

    def connect(self):
        return sqlite3.connect(self.path, timeout=.25)

    def get(self, name, default=None):
        with closing(self.connect()) as db:
            row = db.execute("SELECT value FROM global_spend_state WHERE name=?", (name,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, name, value):
        with closing(self.connect()) as db:
            db.execute("INSERT OR REPLACE INTO global_spend_state VALUES(?,?)",
                       (name, json.dumps(value, allow_nan=False, separators=(",", ":"))))
            db.commit()

    def latch(self, month):
        with closing(self.connect()) as db:
            row = db.execute("SELECT threshold_eur,observed_eur,triggered_at FROM discord_live_month_latch WHERE month=?",
                             (month,)).fetchone()
        return {"threshold_eur": row[0], "observed_eur": row[1], "triggered_at": row[2]} if row else None

    def trigger(self, month, threshold, total, now):
        with closing(self.connect()) as db:
            db.execute("INSERT OR IGNORE INTO discord_live_month_latch VALUES(?,?,?,?)",
                       (month, str(threshold), str(total), aware(now).isoformat()))
            db.commit()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get(url, key="") -> bytes:
    """Read-only fixed-provider GET; authorization must never follow redirects."""
    headers = {"Accept": "application/json, application/xml"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = Request(url, headers=headers, method="GET")
    with build_opener(_NoRedirect()).open(request, timeout=8) as response:
        data = response.read(1_000_001)
    if len(data) > 1_000_000:
        raise ValueError("spend response too large")
    return data


def _json(raw):
    value = json.loads(raw, parse_float=Decimal)
    if not isinstance(value, dict):
        raise ValueError("invalid spend response")
    return value


class GlobalSpendCollector:
    def __init__(self, *, admin_key="", tavily_key="", web_enabled=False,
                 db_path, refresh_seconds=300, now=None, get=None):
        if not 30 <= refresh_seconds <= 900:
            raise ValueError("invalid spend collection interval")
        self._admin_key, self._tavily_key = admin_key, tavily_key
        self.web_enabled = bool(web_enabled)
        self.refresh_seconds = float(refresh_seconds)
        self.db_path = Path(db_path)
        self.store = SpendStore(db_path)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._get = get or _get
        self._lock = asyncio.Lock()
        self._fx_cache = None

    def _openai(self, now):
        if not self._admin_key:
            return {"status": "unknown", "reason": "openai_admin_key_missing"}
        month, start, end = paris_month(now)
        totals, pages, page = {}, set(), None
        overlap = False
        seen_buckets = set()
        deadline = monotonic_time.monotonic() + 12
        for _ in range(20):
            if monotonic_time.monotonic() > deadline:
                raise ValueError("OpenAI costs collection deadline")
            query = {"start_time": int(start.timestamp()), "end_time": int(now.timestamp()),
                     "bucket_width": "1d", "limit": 35}
            if page:
                query["page"] = page
            payload = _json(self._get(OPENAI_COSTS_URL + "?" + urlencode(query), self._admin_key))
            if not isinstance(payload.get("data"), list):
                raise ValueError("invalid OpenAI costs buckets")
            for bucket in payload["data"]:
                if not isinstance(bucket, dict) or not isinstance(bucket.get("results"), list):
                    raise ValueError("invalid OpenAI costs bucket")
                lo, hi = bucket.get("start_time"), bucket.get("end_time")
                if (type(lo) is not int or type(hi) is not int or hi <= lo
                        or lo >= int(now.timestamp()) + 1 or hi <= int(start.timestamp())
                        or lo < int(start.timestamp()) - 86400 or hi > int(now.timestamp()) + 86400):
                    raise ValueError("OpenAI costs bucket outside requested month")
                if (lo, hi) in seen_buckets:
                    raise ValueError("duplicate OpenAI costs bucket")
                seen_buckets.add((lo, hi))
                overlap |= lo < int(start.timestamp()) or hi > int(now.timestamp())
                for row in bucket["results"]:
                    price = row.get("amount") if isinstance(row, dict) else None
                    if not isinstance(price, dict) or not isinstance(price.get("currency"), str):
                        raise ValueError("OpenAI amount missing")
                    currency = price["currency"].upper()
                    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
                        raise ValueError("invalid OpenAI currency")
                    # Adjustments can be negative. They must not cancel the
                    # observed gross API consumption used by the user's policy.
                    value = Decimal(str(price.get("value")))
                    if not value.is_finite() or abs(value) > Decimal("1000000000000"):
                        raise ValueError("invalid OpenAI amount")
                    totals[currency] = totals.get(currency, ZERO) + max(ZERO, value)
            if payload.get("has_more") is False:
                return {"status": "ok", "scope": "organization_all_api_products_all_channels",
                        "month": month, "amounts": {key: str(value) for key, value in totals.items()},
                        "query_start": start.isoformat(), "query_end": now.isoformat(),
                        "collected_at": now.isoformat(), "complete_through": None,
                        "quality": "provider_report_with_unverified_reporting_lag",
                        "bucket_overlap_upper_bound": overlap, "source": OPENAI_COSTS_URL}
            page = payload.get("next_page")
            if not isinstance(page, str) or not page or len(page) > 1024 or page in pages:
                raise ValueError("invalid OpenAI costs pagination")
            pages.add(page)
        raise ValueError("OpenAI costs pagination limit")

    def _tavily(self, now):
        month, start, _ = paris_month(now)
        # A provider configured earlier this month remains part of the total
        # after its feature/key is disabled; disabling it cannot erase spend.
        was_active = self.store.get("tavily_active_month") == month
        if not self.web_enabled and not self._tavily_key and not was_active:
            return {"status": "not_applicable", "amounts": {}, "scope": "no_tavily_account_configured"}
        self.store.put("tavily_active_month", month)
        if not self._tavily_key:
            return {"status": "unknown", "reason": "tavily_key_missing"}
        data = _json(self._get(TAVILY_USAGE_URL, self._tavily_key))
        account = data.get("account")
        if not isinstance(account, dict):
            raise ValueError("Tavily ACCOUNT usage missing")
        plan = account.get("current_plan")
        if not isinstance(plan, str) or plan.strip().lower() not in TAVILY_STANDARD_PLANS:
            return {"status": "unknown", "reason": "tavily_custom_or_unknown_pricing"}
        used = amount(account.get("plan_usage")) + amount(account.get("paygo_usage"))
        previous = self.store.get("tavily_last")
        boundary = self.store.get("tavily_boundary:" + month)
        if boundary is None:
            # The reset is calendar-month based, but the endpoint does not give
            # a time zone or cycle ID. Do not count an old cycle as the new Paris
            # month. An observed reset establishes the new cycle; otherwise wait
            # through the bounded transition window. A quota is NOT a charge.
            reset_observed = (previous is not None and used < amount(previous.get("used", 0)))
            if (now - start).total_seconds() < 48 * 3600 and not reset_observed:
                self.store.put("tavily_last", {"month": month, "used": str(used), "at": now.isoformat()})
                return {"status": "unknown", "reason": "tavily_cycle_boundary_unknown"}
            boundary = {"basis": "observed_reset" if reset_observed else "calendar_cycle_after_transition",
                        "established_at": now.isoformat()}
            self.store.put("tavily_boundary:" + month, boundary)
        if previous and previous.get("month") == month and used < amount(previous.get("used", 0)):
            # A reset/correction away from the month boundary has no reliable
            # attribution. Keep the prior total and require a later good report.
            previous_at = aware(datetime.fromisoformat(previous["at"]))
            if (now - start).total_seconds() > 48 * 3600:
                return {"status": "unknown", "reason": "tavily_cycle_decreased_unexpectedly"}
            if now < previous_at:
                raise ValueError("Tavily time moved backwards")
        self.store.put("tavily_last", {"month": month, "used": str(used), "at": now.isoformat()})
        estimated = used * TAVILY_CREDIT_USD_UPPER
        return {"status": "ok", "scope": "account_all_endpoints_all_keys",
                "month": month, "amounts": {"USD": str(estimated)},
                "reported_credits": str(used), "reported_usage_estimate_usd": str(estimated),
                "cycle_evidence": boundary, "complete_through": None,
                "quality": "calendar_credit_usage_estimated_at_prudent_rate",
                "price_usd_per_credit": str(TAVILY_CREDIT_USD_UPPER),
                "price_date": TAVILY_PRICE_DATE, "price_source": TAVILY_PRICE_SOURCE,
                "collected_at": now.isoformat(), "source": TAVILY_USAGE_URL}

    def _fx(self, now):
        cached = self._fx_cache
        if cached and 0 <= (now - aware(datetime.fromisoformat(cached["checked_at"]))).total_seconds() < 6 * 3600:
            return cached
        raw = self._get(ECB_URL)
        root = ET.fromstring(raw)
        rates, fixing = {"EUR": "1"}, None
        for element in root.iter():
            if "time" in element.attrib:
                fixing = date.fromisoformat(element.attrib["time"])
            if "currency" in element.attrib:
                currency, value = element.attrib["currency"], amount(element.attrib.get("rate"))
                if not value or len(currency) != 3:
                    raise ValueError("invalid ECB fixing")
                rates[currency] = str(value)
        if fixing is None or not 0 <= (now.date() - fixing).days <= 7 or "USD" not in rates:
            raise ValueError("ECB fixing missing or stale")
        self._fx_cache = {"status": "ok", "base": "EUR", "rates": rates,
                          "date": fixing.isoformat(), "checked_at": now.isoformat(), "source": ECB_URL}
        return self._fx_cache

    async def _source(self, name, function, now):
        try:
            async with asyncio.timeout(20):
                return await run_blocking_owned(function, now)
        except HTTPError as exc:
            return {"status": "unknown", "reason": name + ("_access_denied" if exc.code in (401, 403) else "_unavailable")}
        except Exception:
            return {"status": "unknown", "reason": name + "_unavailable"}

    async def collect(self):
        async with self._lock:
            now = aware(self._now())
            month, start, end = paris_month(now)
            # Join every source on cancellation. Ordinary gather may propagate
            # the first cancelled child while another still owns SQLite state.
            results = await asyncio.gather(
                self._source("openai", self._openai, now),
                self._source("tavily", self._tavily, now),
                self._source("fx", self._fx, now), return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException):
                    raise result
            openai, tavily, fx = results
            sources = {"openai": openai, "tavily": tavily}
            failures = [value.get("reason", key + "_unavailable") for key, value in sources.items()
                        if value.get("status") not in ("ok", "not_applicable")]
            if fx.get("status") != "ok":
                failures.append(fx.get("reason", "fx_unavailable"))
            snapshot = {"month": month, "timezone": "Europe/Paris", "period_start": start.isoformat(),
                        "period_end": end.isoformat(), "checked_at": now.isoformat(),
                        "coverage": "unknown" if failures else "bounded", "spent_eur": None,
                        "reason": failures[0] if failures else "prudential_estimate",
                        "issues": failures or ["provider_reporting_lag_unverified"],
                        "sources": sources, "fx": fx, "final_invoice_guaranteed": False}
            if not failures:
                total = ZERO
                for source in sources.values():
                    for currency, value in source.get("amounts", {}).items():
                        rate = fx["rates"].get(currency)
                        if rate is None:
                            snapshot.update(coverage="unknown", reason="fx_currency_unavailable")
                            snapshot["issues"].append("fx_currency_unavailable")
                            break
                        total += amount(value) / amount(rate)
                if snapshot["coverage"] == "bounded":
                    snapshot["spent_eur"] = str(total.quantize(Decimal("0.000001"), rounding=ROUND_UP))
            try:
                previous = await run_blocking_owned(self.store.get, "last_good_snapshot")
                if snapshot["coverage"] != "unknown":
                    await run_blocking_owned(self.store.put, "last_good_snapshot", snapshot)
                elif previous and previous.get("month") == month:
                    snapshot["last_known_eur"] = previous.get("spent_eur")
                    snapshot["last_known_at"] = previous.get("checked_at")
                await run_blocking_owned(self.store.put, "last_attempt", snapshot)
            except (OSError, sqlite3.Error, ValueError):
                snapshot.update(coverage="unknown", reason="spend_storage_unavailable", spent_eur=None)
            return snapshot
