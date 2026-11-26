"""Optional mobile Live wiring without making the classic PWA depend on it."""
from __future__ import annotations

import logging
from pathlib import Path
import sqlite3

from .live_bridge import LiveConversationBridge
from .live_budget import LiveBudgetLedger
from .live_provider import OpenAILiveProvider
from .live_sessions import LiveSessionManager

LOG = logging.getLogger("jade.live.runtime")


class _UnavailableBudget:
    """Allow known-session cleanup while an unreadable ledger blocks admission."""

    def snapshot(self):
        return {"available": False, "over_budget": True, "remaining_usd": "0",
                "reason": "live_budget_unavailable"}

    def reserve(self, *args, **kwargs):
        return False

    def mark_unknown(self, *args, **kwargs):
        raise OSError("live_budget_unavailable")

    update_usage = reconcile = mark_unknown


async def create_mobile_live(runtime, settings, *, provider=None):
    """No creation/capture on startup; recover old known IDs by closing them.

    If optional private storage is unavailable the classic gateway can still
    start. The readable session registry is retained for best-effort shutdown.
    """
    config = settings.live
    unavailable = False
    try:
        budget = LiveBudgetLedger(config.budget_db_path, daily_usd=config.daily_usd,
                                  monthly_usd=config.monthly_usd)
    except (OSError, sqlite3.Error):
        budget, unavailable = _UnavailableBudget(), True
        LOG.error("Live budget storage unavailable; classic mobile remains available")
    try:
        manager = LiveSessionManager(
            config, provider if provider is not None else OpenAILiveProvider(
                settings.api_key, timeout_seconds=config.opening_timeout_seconds), budget,
            api_key_present=bool(settings.api_key and settings.api_key != "example"),
            metrics=runtime.metrics)
    except (OSError, sqlite3.Error):
        LOG.error("Live session registry unavailable; classic mobile remains available")
        return None
    manager._storage_failed = unavailable
    try:
        manager.bridge = LiveConversationBridge(
            runtime, journal_path=Path(config.budget_db_path).with_name("jade-live-journal.sqlite3"),
            publish=manager.publish, reserve_delegation=manager.reserve_delegation,
            settle_delegation=manager.settle_delegation)
    except (OSError, sqlite3.Error):
        manager._storage_failed = True
        LOG.error("Live journal unavailable; classic mobile remains available")
    try:
        await manager.start()
    except (OSError, sqlite3.Error):
        manager._storage_failed = True
        LOG.error("Live recovery unavailable; new Live admission disabled")
    return manager
