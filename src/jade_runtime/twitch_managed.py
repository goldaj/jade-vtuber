"""Coordinate an IRC connection with bounded, serialized token checks."""
from __future__ import annotations

import asyncio
import logging
import threading
from .twitch_rotation import MAX_VALIDATION_INTERVAL, _periodic_checks

LOG = logging.getLogger("jade.twitch.managed")


async def run_managed_twitch(client, manager, *, interval: float = MAX_VALIDATION_INTERVAL):
    """Run IRC and revalidation together until cancellation or failure.

    The caller supplies a client initialized from a validated manager state.
    A new token is swapped before closing the old socket, forcing a reconnect.
    Credential values and provider exception details are never logged here.
    """
    if not 0 < interval <= MAX_VALIDATION_INTERVAL:
        raise ValueError("Twitch validation interval must be at most 50 minutes")

    thread_lock = threading.Lock()
    queue_lock = asyncio.Lock()

    def check_locked():
        with thread_lock:
            return manager.check()

    async def check():
        # Do not start a queued worker thread after the coordinator is cancelled.
        async with queue_lock:
            worker = asyncio.create_task(asyncio.to_thread(check_locked))
            try:
                return await asyncio.shield(worker)
            except asyncio.CancelledError:
                # A thread cannot be cancelled safely after a one-use token may
                # have been consumed. Let it finish its durable state updates
                # before reporting shutdown; never include provider errors.
                try:
                    await asyncio.shield(worker)
                except Exception:
                    LOG.warning("Twitch credential check failed during shutdown; verify private backup")
                raise

    def apply(state):
        token = state.access_token
        if not isinstance(token, str):
            raise ValueError("Invalid Twitch credential state")
        token = token[6:] if token.lower().startswith("oauth:") else token
        if not token or any(c.isspace() for c in token):
            raise ValueError("Invalid Twitch credential state")
        if state.backup_pending:
            LOG.warning("Twitch private backup is not synchronized; local credentials are retained")
        if token == client.token:
            return False
        client.token = token
        # Connect/read loop owns wait_closed and the reconnection; never log the
        # token or issue a chat message as part of renewal.
        if client.writer is not None:
            client.writer.close()
        return True

    async def connect():
        while True:
            previous = client.token
            try:
                await client.connect_forever()
            except PermissionError:
                state = await check()
                changed = apply(state)
                # An hourly check may already have replaced the old token while
                # this particular socket was still reporting an auth failure.
                if changed or client.token != previous:
                    continue
                raise
            raise ConnectionError("Twitch connector stopped unexpectedly")

    async def watch():
        async def check_and_apply():
            apply(await check())
        await _periodic_checks(check_and_apply, interval)

    tasks = (asyncio.create_task(connect(), name="jade-twitch-connection"),
             asyncio.create_task(watch(), name="jade-twitch-validation"))
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        # Propagate the original error, not an ExceptionGroup or provider data.
        for task in done:
            task.result()
        raise RuntimeError("Twitch management stopped unexpectedly")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
