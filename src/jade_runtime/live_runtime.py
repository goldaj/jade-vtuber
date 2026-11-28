"""Optional mobile Live wiring without making the classic PWA depend on it."""
from __future__ import annotations

import logging
from pathlib import Path
import sqlite3

from .live_bridge import LiveConversationBridge
from .live_usage import LiveUsageLedger
from .live_provider import OpenAILiveProvider
from .live_sessions import LiveSessionManager

LOG = logging.getLogger("jade.live.runtime")


async def create_mobile_live(runtime, settings, *, provider=None):
    """No creation/capture on startup; recover old known IDs by closing them.

    Usage is optional observability. The session registry and conversation
    journal remain required to admit and safely recover a Live session.
    """
    config = settings.live
    try:
        usage = LiveUsageLedger(config.usage_db_path)
    except (OSError, sqlite3.Error, ValueError):
        usage = None
        LOG.warning("Live usage tracking unavailable; mobile Live remains available")
    try:
        manager = LiveSessionManager(
            config, provider if provider is not None else OpenAILiveProvider(
                settings.api_key, timeout_seconds=config.opening_timeout_seconds), usage,
            api_key_present=bool(settings.api_key and settings.api_key != "example"),
            metrics=runtime.metrics)
    except (OSError, sqlite3.Error):
        LOG.error("Live session registry unavailable; classic mobile remains available")
        return None
    try:
        manager.bridge = LiveConversationBridge(
            runtime, journal_path=Path(config.usage_db_path).with_name("jade-live-journal.sqlite3"),
            publish=manager.publish, reserve_delegation=manager.reserve_delegation,
            settle_delegation=manager.settle_delegation, voice_style=config.voice_style)
    except (OSError, sqlite3.Error):
        manager._storage_failed = True
        LOG.error("Live journal unavailable; classic mobile remains available")
    try:
        await manager.start()
    except (OSError, sqlite3.Error):
        manager._storage_failed = True
        LOG.error("Live recovery unavailable; new Live admission disabled")
    return manager
