"""Owner-scoped Live admission, client leases and confirmed provider shutdown.

An armed microphone and a paid provider session have different lifetimes. All
network I/O is asynchronous; the small private registry is accessed off-loop.
Neither closing a browser socket nor closing a sideband proves finalization.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import hashlib
import inspect
import logging
import math
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time

from .live_config import LiveConfig
from .live_provider import LiveProviderError, validate_sdp
from .session_logging import event as audit_event
from .turn_metrics import TurnMetrics

LOG = logging.getLogger("jade.live.sessions")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{8,96}\Z")
INACTIVE_PHASES = ("closed", "retired_unconfirmed")
TECHNICAL_REASONS = frozenset((
    "opening", "waiting_for_speech", "idle", "mute", "muted_draining", "muted_drain_timeout",
    "mode_off", "user_stop", "text", "classic_voice", "background", "heartbeat_expired",
    "control_disconnected", "control_backpressure", "sideband_lost", "server_shutdown",
    "server_restart", "live_disabled", "live_state_unavailable", "live_supervisor_failed",
    "live_duration_limit", "live_start_rate_limit", "live_provider_error",
    "opening_timeout", "opening_abandoned", "live_open_failed", "creation_unconfirmed",
    "creation_rejected", "close_unconfirmed", "provider_closed", "owner_recovery",
))


class LiveSessionError(RuntimeError):
    def __init__(self, code: str, status: int = 409):
        super().__init__(code)
        self.code, self.status = code, status


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise LiveSessionError("invalid_live_identifier", 400)
    return value


async def _call(function, *args, **kwargs):
    value = function(*args, **kwargs)
    return await value if inspect.isawaitable(value) else value


class LiveRegistry:
    """Only identifiers, preferences and finalization metadata; never content."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, timeout=0.25, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS live_preferences (
                owner TEXT PRIMARY KEY, mode TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS live_sessions (
                handle TEXT PRIMARY KEY, owner TEXT NOT NULL, client_id TEXT NOT NULL,
                thread_id TEXT NOT NULL, lease_id TEXT NOT NULL, generation TEXT NOT NULL,
                provider_id TEXT NOT NULL, phase TEXT NOT NULL, reservation_id TEXT NOT NULL,
                reason TEXT NOT NULL, updated_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS live_pending ON live_sessions(owner, phase);
        """)
        self._db.commit()
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def preferences(self, owner):
        with self._lock:
            row = self._db.execute(
                "SELECT mode,revision FROM live_preferences WHERE owner=?", (owner,)).fetchone()
            return dict(row) if row else {"mode": "live", "revision": 0}

    def set_mode(self, owner, mode, revision):
        with self._lock, self._db:
            current = self.preferences(owner)
            # An old ON must not undo a newer OFF. An authenticated OFF is always
            # an effective stop, including when its displayed revision is old.
            if revision != current["revision"] and mode != "classic":
                raise LiveSessionError("preference_conflict")
            result = {"mode": mode, "revision": current["revision"] + 1}
            self._db.execute("INSERT INTO live_preferences VALUES(?,?,?) ON CONFLICT(owner) "
                             "DO UPDATE SET mode=excluded.mode,revision=excluded.revision",
                             (owner, result["mode"], result["revision"]))
            return result

    def save(self, session):
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO live_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                             (session.handle, session.owner, session.client_id, session.thread_id,
                              session.lease_id, session.generation, session.provider_id,
                              session.phase, session.reservation_id, session.reason, time.time()))
            self._db.execute("DELETE FROM live_sessions WHERE phase='closed' AND updated_at<?",
                             (time.time() - 7 * 86400,))

    def pending(self):
        with self._lock:
            return [dict(row) for row in self._db.execute(
                "SELECT * FROM live_sessions WHERE phase NOT IN (?,?)", INACTIVE_PHASES).fetchall()]

    def close(self):
        with self._lock:
            self._db.close()


@dataclass
class ClientLease:
    owner: str
    client_id: str
    thread_id: str
    lease_id: str
    heartbeat: float
    state: str = "armed"
    seq: int = -1
    session: str | None = None
    drain_deadline: float | None = None
    playback_active: bool = False
    speech_active: bool = False
    capture: str = "closed"
    reason: str = "armed"
    control_token: str | None = None


@dataclass
class ProviderSession:
    handle: str
    owner: str
    client_id: str
    thread_id: str
    lease_id: str
    generation: str
    reservation_id: str
    created: float
    last_activity: float
    provider_id: str = ""
    phase: str = "opening"
    reason: str = "opening"
    keep_arm: bool = False
    abandoned: bool = False
    ever_input: bool = False
    channel: object = None
    open_task: asyncio.Task | None = None
    sideband_task: asyncio.Task | None = None
    close_task: asyncio.Task | None = None
    attached: asyncio.Event = field(default_factory=asyncio.Event)
    started: asyncio.Event = field(default_factory=asyncio.Event)
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    seen_events: set = field(default_factory=set)
    event_order: deque = field(default_factory=deque)
    pending_delegations: set = field(default_factory=set)
    admitted_delegations: set = field(default_factory=set)
    total_delegations: int = 0
    usage_seconds: float = 0.0
    last_estimate: float = 0.0
    request_id: str = ""
    sdp_digest: str = ""
    answer: dict | None = None


class LiveSessionManager:
    def __init__(self, config: LiveConfig, provider, usage=None, *, registry_path=None,
                 bridge=None, api_key_present=True, clock=time.monotonic, metrics=None):
        config.validate()
        self.config, self.provider, self.usage = config, provider, usage
        self.bridge, self.api_key_present, self.clock = bridge, bool(api_key_present), clock
        self.metrics = metrics if metrics is not None else TurnMetrics(clock=clock)
        self.registry = LiveRegistry(registry_path or config.session_db_path or
                                     Path(config.usage_db_path).with_name("jade-live-sessions.sqlite3"))
        self._leases: dict[str, ClientLease] = {}
        self._sessions: dict[str, ProviderSession] = {}
        self._preferences = {}
        self._subscribers: dict[str, dict[str, asyncio.Queue]] = {}
        self._starts: dict[str, deque] = {}
        self._lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._watchdog = None
        self._tasks = set()
        self._running, self._stopped = False, False
        self._storage_failed = False
        self._usage_warning = False

    def _trace(self, session, stage, **numeric):
        """Technical observations only, never SDP, identities or transcripts."""
        self.metrics.mark("live:" + session.handle, stage)
        audit_event("live_lifecycle", stage=stage, phase=session.phase,
                    reason=session.reason if session.reason in TECHNICAL_REASONS else "other",
                    elapsed_ms=round(max(0, self.clock() - session.created) * 1000, 1),
                    **{k: v for k, v in numeric.items() if type(v) in (int, float, bool)})

    def _spawn(self, coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        self._tasks.add(task)

        def done(completed):
            self._tasks.discard(completed)
            if not completed.cancelled() and completed.exception() is not None:
                LOG.warning("Live background operation failed; private content omitted")
        task.add_done_callback(done)
        return task

    async def start(self):
        async with self._start_lock:
            await self._start()

    async def _start(self):
        if self._running:
            return
        if self._stopped:
            raise LiveSessionError("server_stopping", 503)
        for row in await asyncio.to_thread(self.registry.pending):
            session = ProviderSession(
                **{key: row[key] for key in ("handle", "owner", "client_id", "thread_id",
                                            "lease_id", "generation", "reservation_id")},
                created=self.clock(), last_activity=self.clock(),
                provider_id=row["provider_id"], phase="close_unconfirmed" if row["provider_id"]
                else "opening_unknown", reason="server_restart", abandoned=True)
            self._sessions[session.handle] = session
            if session.provider_id:
                session.started.set()  # Existing paid session; never resume its media.
                session.close_task = self._spawn(self._close_provider(session), "live-reconcile")
        self._running = True
        self._watchdog = self._spawn(self._watch(), "live-watchdog")

    async def preferences(self, owner):
        value = await asyncio.to_thread(self.registry.preferences, owner)
        self._preferences[owner] = value
        return dict(value)

    async def _persist(self, session):
        try:
            await asyncio.to_thread(self.registry.save, session)
            return True
        except Exception:
            self._storage_failed = True
            LOG.error("Live state persistence failed; new admission disabled")
            return False

    async def set_mode(self, owner, mode, revision):
        if mode not in ("classic", "live") or type(revision) is not int or revision < 0:
            raise LiveSessionError("invalid_voice_preference", 400)
        try:
            async with self._lock:
                if mode == "classic":
                    self._invalidate(owner, "mode_off")
                value = await asyncio.to_thread(self.registry.set_mode, owner, mode, revision)
                self._preferences[owner] = value
        except (sqlite3.Error, OSError):
            self._storage_failed = True
            if mode == "classic":
                await self.stop_owner(owner, "mode_off")
            raise LiveSessionError("live_state_unavailable", 503) from None
        self._broadcast(owner, {"type": "preference", **value})
        if mode == "classic":
            await self.stop_owner(owner, "mode_off")
        return dict(value)

    def _unresolved(self, owner):
        return any(s.owner == owner and s.phase in ("close_unconfirmed", "opening_unknown")
                   for s in self._sessions.values())

    def _blocking_sessions(self, owner):
        return [s for s in self._sessions.values()
                if s.owner == owner and s.phase not in INACTIVE_PHASES]

    def _can_retire(self, sessions):
        return bool(sessions) and all(
            s.phase == "close_unconfirmed" and s.provider_id and s.abandoned
            and s.close_task is not None and s.close_task.done()
            and (s.open_task is None or s.open_task.done())
            and (s.sideband_task is None or s.sideband_task.done())
            for s in sessions)

    async def _close_bridge(self, session, reason):
        if self.bridge:
            try:
                await asyncio.wait_for(_call(self.bridge.close_session, self._context(session), reason),
                                       self.config.close_timeout_seconds)
            except Exception:
                LOG.warning("Live history finalization incomplete; private journal retained")

    async def recover(self, owner):
        """Retire a lost transport explicitly, keeping unsettled usage unknown."""
        await self.start()
        async with self._lock:
            lease = self._leases.get(owner)
            if lease and lease.state != "closed":
                raise LiveSessionError("microphone_owned_by_other_client")
            if self._storage_failed:
                raise LiveSessionError("live_state_unavailable", 503)
            sessions = self._blocking_sessions(owner)
            if not sessions:
                return self.snapshot(owner)
            if not self._can_retire(sessions):
                code = "close_unconfirmed" if self._unresolved(owner) else "previous_session_not_closed"
                raise LiveSessionError(code)
            if self.bridge:
                for session in sessions:
                    await self._close_bridge(session, "owner_recovery")
                sessions = self._blocking_sessions(owner)
                if sessions and not self._can_retire(sessions):
                    raise LiveSessionError("previous_session_not_closed")
            for session in sessions:
                reason = session.reason
                session.phase, session.reason = "retired_unconfirmed", "owner_recovery"
                if not await self._persist(session):
                    session.phase, session.reason = "close_unconfirmed", reason
                    raise LiveSessionError("live_state_unavailable", 503)
                if lease and lease.session == session.handle:
                    lease.session, lease.reason = None, "owner_recovery"
                self._trace(session, "live_retired_unconfirmed")
            self._state(owner)
            return self.snapshot(owner)

    async def _observe_usage(self, method, *args, **kwargs):
        """Best-effort telemetry; it never grants or refuses Live work."""
        if self.usage is None:
            return None
        try:
            # Slow optional accounting must not hold the control/provider path.
            async with asyncio.timeout(1):
                return await asyncio.to_thread(getattr(self.usage, method), *args, **kwargs)
        except Exception:
            if not self._usage_warning:
                LOG.warning("Live usage tracking unavailable; mobile Live remains available")
                self._usage_warning = True
            return None

    async def usage_snapshot(self):
        result = await self._observe_usage("snapshot")
        if not isinstance(result, dict):
            return {"available": False, "reason": "usage_unavailable"}
        return {"available": True, **result}

    async def capabilities(self, owner):
        usage = await self.usage_snapshot()
        result = dict(self.config.preflight(api_key_present=self.api_key_present))
        reasons = list(result.get("reasons", []))
        if self._stopped:
            reasons.append("server_stopping")
        if self._storage_failed:
            reasons.append("live_state_unavailable")
        if self._unresolved(owner):
            reasons.append("close_unconfirmed")
        state = self.snapshot(owner)
        if state["session_state"] == "closing" and state["lease_state"] == "closed":
            reasons.append("previous_session_not_closed")
        result.update(enabled=self.config.enabled, available=not reasons,
                      reason=reasons[0] if reasons else "ready", reasons=reasons,
                      usage=usage,
                      heartbeat_seconds=self.config.heartbeat_seconds,
                      lease_seconds=self.config.lease_seconds,
                      opening_timeout_seconds=self.config.opening_timeout_seconds,
                      idle_close_seconds=self.config.idle_close_seconds,
                      state=state)
        return result

    async def arm(self, owner, client_id, thread_id):
        _identifier(client_id)
        _identifier(thread_id)
        await self.start()
        async with self._lock:
            prefs = await self.preferences(owner)
            if prefs["mode"] != "live":
                raise LiveSessionError("live_mode_off")
            caps = await self.capabilities(owner)
            if not caps["available"]:
                raise LiveSessionError(caps["reason"], 503)
            current = self._leases.get(owner)
            if current and current.state != "closed":
                if current.client_id == client_id and current.thread_id == thread_id:
                    return self.snapshot(owner)
                raise LiveSessionError("microphone_owned_by_other_client")
            if self._blocking_sessions(owner):
                raise LiveSessionError("previous_session_not_closed")
            lease = ClientLease(owner, client_id, thread_id, secrets.token_urlsafe(24), self.clock())
            self._leases[owner] = lease
            return self.snapshot(owner)

    def _lease(self, owner, client_id, lease_id, *, armed=False):
        lease = self._leases.get(owner)
        if (lease is None or lease.client_id != client_id or lease.lease_id != lease_id
                or lease.state == "closed" or (armed and lease.state != "armed")):
            raise LiveSessionError("invalid_or_expired_live_lease")
        if self.clock() - lease.heartbeat >= self.config.lease_seconds:
            self._invalidate(owner, "heartbeat_expired")
            self._spawn(self.stop_owner(owner, "heartbeat_expired"), "live-expired")
            raise LiveSessionError("invalid_or_expired_live_lease")
        return lease

    def snapshot(self, owner):
        lease = self._leases.get(owner)
        session = self._sessions.get(lease.session) if lease and lease.session else None
        sessions = self._blocking_sessions(owner)
        if session is not None and session.phase in INACTIVE_PHASES:
            session = None
        if session is None:
            session = next(iter(sessions), None)
        result = {"lease_id": lease.lease_id if lease else None,
                  "lease_state": lease.state if lease else "closed",
                  "session_state": session.phase if session else "absent",
                  "session_id": session.handle if session else None,
                  "reason": session.reason if session else (lease.reason if lease else "ready"),
                  "recovery_allowed": (not self._storage_failed and not self._stopped
                                       and (lease is None or lease.state == "closed")
                                       and self._can_retire(sessions)),
                  "heartbeat_seconds": self.config.heartbeat_seconds,
                  "lease_seconds": self.config.lease_seconds,
                  **self._preferences.get(owner, {"mode": "live", "revision": 0})}
        return result

    def _broadcast(self, owner, event):
        for token, queue in tuple(self._subscribers.get(owner, {}).items()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # A slow/disconnected UI must not let a paid session run alone.
                self._subscribers.get(owner, {}).pop(token, None)
                self._invalidate(owner, "control_backpressure")
                self._spawn(self.stop_owner(owner, "control_backpressure"), "live-backpressure")

    def _state(self, owner):
        self._broadcast(owner, {"type": "state", **self.snapshot(owner)})

    async def subscribe(self, owner, client_id, lease_id):
        lease = self._lease(owner, client_id, lease_id)
        if lease.control_token:
            raise LiveSessionError("live_control_already_connected")
        token = secrets.token_urlsafe(18)
        queue = asyncio.Queue(maxsize=128)
        lease.control_token = token
        self._subscribers.setdefault(owner, {})[token] = queue
        return token, queue

    async def unsubscribe(self, owner, token):
        self._subscribers.get(owner, {}).pop(token, None)
        lease = self._leases.get(owner)
        if lease and lease.control_token == token:
            lease.control_token = None
            await self.stop_owner(owner, "control_disconnected")

    async def heartbeat(self, owner, client_id, lease_id, event):
        lease = self._lease(owner, client_id, lease_id)
        seq = event.get("seq")
        if type(seq) is not int or not 0 <= seq <= 2**53 or seq <= lease.seq:
            raise LiveSessionError("stale_live_heartbeat", 400)
        if event.get("visible") is not True:
            await self.stop_owner(owner, "background")
            return {"type": "state", "seq": seq, **self.snapshot(owner)}
        if event.get("capture") not in ("armed", "closed"):
            raise LiveSessionError("invalid_live_capture_state", 400)
        lease.seq, lease.heartbeat = seq, self.clock()
        lease.capture = event["capture"]
        lease.playback_active = event.get("playback_active") is True
        lease.speech_active = event.get("speech_active") is True and lease.state == "armed"
        session = self._sessions.get(lease.session) if lease.session else None
        if session and (lease.playback_active or lease.speech_active):
            session.last_activity = self.clock()
            session.ever_input = session.ever_input or lease.speech_active
        # No renewal of a draining deadline; no creation or inference wake here.
        return {"type": "state", "seq": seq, **self.snapshot(owner)}

    async def create_session(self, owner, client_id, thread_id, lease_id, request_id, sdp):
        await self.start()
        _identifier(request_id)
        try:
            validate_sdp(sdp)
        except LiveProviderError:
            raise LiveSessionError("invalid_sdp", 400) from None
        digest = hashlib.sha256(sdp.encode()).hexdigest()
        async with self._lock:
            lease = self._lease(owner, client_id, lease_id, armed=True)
            if lease.thread_id != thread_id or not lease.control_token:
                raise LiveSessionError("live_control_required")
            if (await self.preferences(owner))["mode"] != "live":
                raise LiveSessionError("live_mode_off")
            prior = next((s for s in self._sessions.values()
                          if s.owner == owner and s.lease_id == lease_id and s.request_id == request_id), None)
            if prior:
                if prior.sdp_digest != digest or prior.phase in ("closed", "closing", "close_unconfirmed", "opening_unknown"):
                    raise LiveSessionError("live_request_already_used")
                task = prior.open_task
            else:
                if lease.session or self._unresolved(owner):
                    raise LiveSessionError("live_session_already_exists")
                caps = await self.capabilities(owner)
                if not caps["available"]:
                    raise LiveSessionError(caps["reason"], 503)
                starts = self._starts.setdefault(owner, deque())
                while starts and self.clock() - starts[0] >= 60:
                    starts.popleft()
                if len(starts) >= self.config.max_starts_per_minute:
                    self._invalidate(owner, "live_start_rate_limit")
                    raise LiveSessionError("live_start_rate_limit", 429)
                handle = secrets.token_urlsafe(24)
                reservation = "voice:" + handle
                await self._observe_usage("reserve", reservation, 0, "voice")
                starts.append(self.clock())
                session = ProviderSession(handle, owner, client_id, thread_id, lease_id,
                                          secrets.token_urlsafe(18), reservation, self.clock(), self.clock(),
                                          request_id=request_id, sdp_digest=digest)
                self._sessions[handle], lease.session = session, handle
                self.metrics.begin("live:" + handle, "mobile", "live", session.created)
                self._trace(session, "live_opening")
                if not await self._persist(session):
                    await self._closed_without_create(session)
                    raise LiveSessionError("live_state_unavailable", 503)
                task = session.open_task = self._spawn(self._open(session, sdp), "live-open")
        self._state(owner)
        try:
            return await asyncio.wait_for(asyncio.shield(task), self.config.opening_timeout_seconds)
        except asyncio.TimeoutError:
            await self.stop_owner(owner, "opening_timeout", wait=False)
            raise LiveSessionError("live_opening_timeout", 504) from None
        except asyncio.CancelledError:
            await self.stop_owner(owner, "opening_abandoned", wait=False)
            raise

    def _context(self, session):
        return {"owner": session.owner, "thread_id": session.thread_id,
                "session_id": session.provider_id, "handle": session.handle,
                "generation": session.generation,
                "valid": lambda: self._valid(session)}

    def _valid(self, session):
        lease = self._leases.get(session.owner)
        return (not self._stopped and not self._storage_failed and self.config.enabled
                and self.config.mobile_enabled and not session.abandoned and lease is not None
                and lease.lease_id == session.lease_id and lease.session == session.handle
                and lease.state in ("armed", "draining")
                and self.clock() - lease.heartbeat < self.config.lease_seconds
                and (lease.state != "draining" or self.clock() < (lease.drain_deadline or 0))
                and session.phase in ("opening", "active", "standby"))

    async def _open(self, session, sdp):
        sent = False
        try:
            context = await _call(self.bridge.prepare_context, session.owner, session.thread_id) if self.bridge else {}
            if not self._valid(session):
                raise LiveSessionError("live_opening_abandoned")
            config = self.config.session_config(**context)
            sent = True
            result = await self.provider.create_session(sdp, config)
            session.provider_id = result["session_id"]
            self._trace(session, "live_sdp_ready")
            if not await self._persist(session):
                await self._request_close(session, "live_state_unavailable", keep_arm=False, wait=False)
                raise LiveSessionError("live_state_unavailable", 503)
            if self.bridge:
                await _call(self.bridge.open_session, self._context(session))
            self._ensure_sideband(session)
            await asyncio.wait_for(session.attached.wait(), self.config.close_timeout_seconds)
            if not self._valid(session):
                await self._request_close(session, "opening_abandoned", keep_arm=False, wait=False)
                raise LiveSessionError("live_opening_abandoned")
            session.answer = {"sdp": result["sdp"], "session_id": session.handle,
                              "lease_id": session.lease_id, "generation": session.generation}
            return dict(session.answer)
        except LiveSessionError:
            if not sent:
                await self._closed_without_create(session)
            elif session.provider_id and not session.abandoned:
                await self._request_close(session, "live_open_failed", keep_arm=False, wait=False)
            raise
        except BaseException as exc:
            session.abandoned = True
            self._invalidate(session.owner, "live_open_failed")
            known_id = getattr(exc, "session_id", None)
            if known_id and not session.provider_id:
                session.provider_id = known_id
            if session.provider_id:
                await self._request_close(session, "live_open_failed", keep_arm=False, wait=False)
            elif sent and (not isinstance(exc, LiveProviderError) or exc.ambiguous):
                session.phase, session.reason = "opening_unknown", "creation_unconfirmed"
                await self._unknown_cost(session.reservation_id)
                await self._persist(session)
            else:
                await self._closed_without_create(session)
            self._state(session.owner)
            if isinstance(exc, asyncio.CancelledError):
                raise
            code = "creation_unconfirmed" if session.phase == "opening_unknown" else "live_open_failed"
            if isinstance(exc, LiveProviderError):
                public_codes = {"live_auth_failed", "live_access_denied", "live_model_unavailable",
                                "live_quota_exceeded", "live_rate_limited", "live_connection_failed"}
                if exc.code in public_codes:
                    code = exc.code
                elif exc.status_code in (401, 403, 404, 429):
                    code = {401: "live_auth_failed", 403: "live_access_denied",
                            404: "live_model_unavailable", 429: "live_rate_limited"}[exc.status_code]
                elif exc.code in ("session_creation_transport_failed", "sideband_connection_failed"):
                    code = "live_connection_failed"
            raise LiveSessionError(code, 503) from None

    async def _closed_without_create(self, session):
        session.phase, session.reason = "closed", "creation_rejected"
        session.closed.set()
        # A definitive rejection or abandonment before HTTP has no usage.
        await self._observe_usage("reconcile", session.reservation_id, 0, confirmed=True)
        await self._persist(session)
        lease = self._leases.get(session.owner)
        if lease and lease.session == session.handle:
            lease.session, lease.state = None, "closed"
        self._trace(session, "live_creation_rejected")
        self.metrics.end("live:" + session.handle, "rejected")

    def _ensure_sideband(self, session):
        if session.sideband_task is None or session.sideband_task.done():
            session.attached.clear()
            session.sideband_task = self._spawn(self._sideband(session), "live-sideband")

    async def _sideband(self, session):
        try:
            async with self.provider.attach(session.provider_id) as channel:
                session.channel = channel
                session.attached.set()
                async for event in channel:
                    await self._provider_event(session, event)
                    if session.closed.is_set():
                        break
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.warning("Live sideband unavailable; finalization requires reconciliation")
        finally:
            session.channel = None
            if not session.closed.is_set() and session.phase not in INACTIVE_PHASES:
                if session.close_task is None or session.close_task.done():
                    lease = self._leases.get(session.owner)
                    if lease and lease.lease_id == session.lease_id:
                        self._invalidate(session.owner, "sideband_lost")
                    session.abandoned = True
                    session.reason = "sideband_lost"
                    # Schedule after this receiver unwinds, so retry can attach.
                    self._spawn(self._close_after_receiver(session), "live-sideband-close")

    async def _close_after_receiver(self, session):
        await asyncio.sleep(0)
        await self._request_close(session, session.reason, keep_arm=False)

    async def _provider_event(self, session, event):
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            if event_id in session.seen_events:
                return
            session.seen_events.add(event_id)
            session.event_order.append(event_id)
            if len(session.event_order) > 4096:
                session.seen_events.discard(session.event_order.popleft())
        kind = event.get("type")
        if kind == "session.started":
            session.started.set()
            if not session.abandoned:
                session.phase, session.reason = "standby", "waiting_for_speech"
        elif kind in ("session.resumed", "session.paused") and not session.abandoned:
            # A late attachment may miss started's replay; resumed/paused prove
            # that the HTTP-created session has already started.
            session.started.set()
            session.phase = "active" if kind == "session.resumed" else "standby"
        elif kind in ("session.input_transcript.delta", "session.output_transcript.delta"):
            session.last_activity = self.clock()
            session.ever_input |= kind == "session.input_transcript.delta"
        if kind in ("session.usage.updated", "session.closed"):
            # Record the terminal independently of cost/history processing. A
            # failed database write must not erase an observed provider terminal.
            if kind == "session.closed":
                session.phase = "closed"
                session.closed.set()
            usage = event.get("usage")
            if (isinstance(usage, dict) and type(usage.get("seconds")) in (int, float)
                    and math.isfinite(usage["seconds"]) and usage["seconds"] >= 0):
                session.usage_seconds = max(session.usage_seconds, float(usage["seconds"]))
                active, paused = usage.get("active_seconds"), usage.get("paused_seconds")
                if active is None or paused is None:
                    active = paused = None
                await self._observe_usage("update_usage", session.reservation_id,
                                         session.usage_seconds, active_seconds=active,
                                         paused_seconds=paused, final=kind == "session.closed")
            elif kind == "session.closed":
                await self._unknown_cost(session.reservation_id)
        if kind == "session.closed":
            session.phase = "closed"
            session.reason = session.reason if session.abandoned else str(event.get("reason", "provider_closed"))[:80]
            try:
                await asyncio.to_thread(self.registry.save, session)
            except Exception:
                self._storage_failed = True
                LOG.error("Live terminal persistence failed; new admission disabled")
            lease = self._leases.get(session.owner)
            if lease and lease.session == session.handle:
                lease.session = None
                if not session.keep_arm:
                    lease.state = "closed"
                lease.reason = session.reason
            await self._close_bridge(session, session.reason)
            self._trace(session, "live_terminal", usage_seconds=session.usage_seconds)
            self.metrics.end("live:" + session.handle)
        elif kind == "error" and not session.abandoned and session.phase not in INACTIVE_PHASES:
            # Provider bodies may contain prompt fragments: expose a stable code only.
            self._broadcast(session.owner, {"type": "incident", "code": "live_provider_error",
                                           "session_id": session.handle})
            await self.stop_owner(session.owner, "live_provider_error", wait=False)
        elif self.bridge and self._valid(session):
            await _call(self.bridge.handle_event, event, self._context(session),
                        lambda payload: self.send(session.handle, payload))
        if kind in ("session.started", "session.resumed", "session.paused", "session.closed"):
            if kind != "session.closed":
                self._trace(session, "live_" + kind.split(".")[1])
            self._state(session.owner)

    async def send(self, handle, event):
        session = self._sessions.get(handle)
        if not session or not self._valid(session) or not session.channel:
            raise LiveSessionError("live_session_expired")
        await asyncio.wait_for(session.started.wait(), self.config.close_timeout_seconds)
        if not self._valid(session):
            raise LiveSessionError("live_session_expired")
        await asyncio.wait_for(session.channel.send(event), self.config.close_timeout_seconds)

    async def _unknown_cost(self, reservation_id):
        await self._observe_usage("mark_unknown", reservation_id)

    async def reserve_delegation(self, context, delegation_id):
        """Admit one bounded backend operation without a financial gate.

        The callback's historical reservation name is kept for the bridge.
        Identity, liveness and deduplication do not depend on optional usage I/O.
        """
        session = self._sessions.get(context.get("handle"))
        if (not session or session.generation != context.get("generation")
                or not isinstance(delegation_id, str) or not 1 <= len(delegation_id) <= 256
                or not delegation_id.strip()):
            return False
        async with self._lock:
            if (not self._valid(session)
                    or session.total_delegations >= self.config.max_delegations_per_session
                    or delegation_id in session.admitted_delegations):
                return False
            reservation = "backend:" + hashlib.sha256(
                (session.handle + ":" + delegation_id).encode()).hexdigest()
            await self._observe_usage("reserve", reservation, 0, "backend")
            # An OFF/lease expiry during SQLite I/O still prevents dispatch.
            if not self._valid(session):
                await self._observe_usage("release", reservation)
                return False
            session.pending_delegations.add(delegation_id)
            session.admitted_delegations.add(delegation_id)
            session.total_delegations += 1
            session.last_activity = self.clock()
            self._trace(session, "live_backend_admitted", delegations=session.total_delegations)
            return reservation

    async def settle_delegation(self, context, delegation_id, reservation, usage, status):
        session = self._sessions.get(context.get("handle"))
        if not session or session.generation != context.get("generation"):
            return
        expected = "backend:" + hashlib.sha256(
            (session.handle + ":" + delegation_id).encode()).hexdigest()
        if reservation != expected or delegation_id not in session.admitted_delegations:
            return
        try:
            # Tokens describe known work, not the full cost of its tools.
            await self._observe_usage("record_backend_usage", reservation, usage, status)
        finally:
            session.pending_delegations.discard(delegation_id)
            session.last_activity = self.clock()
            self._trace(session, "live_backend_settled", completed=status == "completed")

    async def publish(self, context, event):
        session = self._sessions.get(context.get("handle"))
        if not session or session.generation != context.get("generation"):
            return
        lease = self._leases.get(session.owner)
        if (not lease or lease.lease_id != session.lease_id or lease.thread_id != session.thread_id
                or lease.client_id != session.client_id or lease.session not in (None, session.handle)):
            return
        projection = dict(event)
        kind = projection.get("type")
        # A last transcript snapshot may reconcile this same lease after close;
        # actions/intents from an abandoned generation must never reach the UI.
        if kind != "live_transcript" and not self._valid(session):
            return
        projection["session_id"] = session.handle
        if kind == "live_transcript":
            projection["type"] = "transcript"
        elif kind == "live_incident":
            projection["type"] = "incident"
        elif kind == "live_delegation":
            if projection.get("attachments"):
                self._broadcast(session.owner, {"type": "attachments", "session_id": session.handle,
                                                "attachments": projection["attachments"]})
            projection["type"] = "intent"
        self._broadcast(session.owner, projection)

    async def observe_playback(self, owner, client_id, lease_id, observation):
        lease = self._lease(owner, client_id, lease_id)
        session = self._sessions.get(lease.session) if lease.session else None
        if not session or observation.get("session_id") != session.handle:
            raise LiveSessionError("stale_live_playback", 400)
        if observation.get("state") not in ("playing", "drained", "interrupted"):
            raise LiveSessionError("invalid_live_playback", 400)
        offset = observation.get("offset_ms")
        if offset is not None and (type(offset) is not int
                                   or not 0 <= offset <= self.config.max_session_seconds * 1000):
            raise LiveSessionError("invalid_live_playback", 400)
        lease.playback_active = observation["state"] == "playing"
        if lease.playback_active:
            session.last_activity = self.clock()
            self._trace(session, "live_playback_reported")
        if self.bridge and callable(getattr(self.bridge, "observe_playback", None)):
            await _call(self.bridge.observe_playback, self._context(session), observation)

    def _invalidate(self, owner, reason):
        lease = self._leases.get(owner)
        if lease:
            lease.state, lease.capture, lease.reason = "closed", "closed", reason
            lease.playback_active = lease.speech_active = False
            if lease.session:
                session = self._sessions.get(lease.session)
                if session:
                    session.abandoned, session.keep_arm, session.reason = True, False, reason

    async def close(self, owner, client_id, lease_id, *, reason="user_stop", drain=False):
        lease = self._leases.get(owner)
        # Idempotent closure remains available after expiry/feature/quota changes.
        if lease is None or lease.client_id != client_id or lease.lease_id != lease_id:
            raise LiveSessionError("invalid_or_expired_live_lease")
        session = self._sessions.get(lease.session) if lease.session else None
        if (drain and reason == "mute" and lease.state == "armed" and session
                and session.ever_input and self._valid(session)):
            lease.state, lease.capture = "draining", "closed"
            lease.speech_active = False
            lease.drain_deadline = self.clock() + self.config.muted_drain_seconds
            lease.reason = "muted_draining"
            self._state(owner)
        elif lease.state == "draining" and drain and reason == "mute":
            pass  # A repeated mute never extends the fixed deadline.
        else:
            await self.stop_owner(owner, reason)
        return self.snapshot(owner)

    async def stop_owner(self, owner, reason="user_stop", *, wait=True):
        self._invalidate(owner, reason)
        self._state(owner)
        pending = []
        for session in self._blocking_sessions(owner):
            if session.phase == "close_unconfirmed" and session.close_task and session.close_task.done():
                continue
            pending.append(self._request_close(session, reason, keep_arm=False, wait=wait))
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def _request_close(self, session, reason, *, keep_arm, wait=True):
        if session.closed.is_set() or session.phase in INACTIVE_PHASES:
            return
        session.abandoned, session.keep_arm, session.reason = True, keep_arm, reason
        self._trace(session, "live_close_requested")
        if not session.provider_id:
            session.phase = "opening_unknown"
            self._state(session.owner)
            await self._unknown_cost(session.reservation_id)
            await self._persist(session)
            return
        session.phase = "closing"
        # Start cleanup before persistence. A full/unavailable disk must never
        # prevent sending session.close to a known paid provider session.
        if session.close_task is None or session.close_task.done():
            session.close_task = self._spawn(self._close_provider(session), "live-close")
        self._state(session.owner)
        await self._persist(session)
        await self._close_bridge(session, reason)
        if wait:
            await asyncio.shield(session.close_task)

    async def _close_provider(self, session):
        # Closing is never gated by flags, admission or client authentication.
        deadline = asyncio.get_running_loop().time() + self.config.close_timeout_seconds

        async def bounded(awaitable):
            return await asyncio.wait_for(awaitable, max(0.001, deadline - asyncio.get_running_loop().time()))

        for attempt in range(2):
            if session.closed.is_set():
                return
            if asyncio.get_running_loop().time() >= deadline:
                break
            try:
                self._ensure_sideband(session)
                await bounded(session.attached.wait())
                if session.channel is None:
                    raise LiveSessionError("sideband_unavailable")
                # The HTTP creation already returned this ID. A late sideband
                # can miss session.started's 3-second replay; cleanup must still run.
                await bounded(session.channel.send({"type": "session.close"}))
                await bounded(session.closed.wait())
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                if session.sideband_task and not session.sideband_task.done():
                    session.sideband_task.cancel()
                    finished, _ = await asyncio.wait(
                        [session.sideband_task], timeout=max(0, deadline - asyncio.get_running_loop().time()))
                    if not finished:
                        break
                session.channel = None
                if attempt == 0:
                    await asyncio.sleep(0)
        if session.closed.is_set():
            return
        session.phase = "close_unconfirmed"
        self._trace(session, "live_close_unconfirmed")
        self.metrics.end("live:" + session.handle, "unconfirmed")
        self._invalidate(session.owner, "close_unconfirmed")
        self._state(session.owner)
        await self._unknown_cost(session.reservation_id)
        await self._persist(session)

    async def tick(self):
        now = self.clock()
        for owner, lease in tuple(self._leases.items()):
            if lease.state == "closed":
                continue
            reason = None
            if self._stopped or self._storage_failed or not self.config.enabled or not self.config.mobile_enabled:
                reason = "live_disabled"
            elif now - lease.heartbeat >= self.config.lease_seconds:
                reason = "heartbeat_expired"
            elif lease.state == "draining" and now >= (lease.drain_deadline or now):
                reason = "muted_drain_timeout"
            session = self._sessions.get(lease.session) if lease.session else None
            if session and now - session.created >= self.config.max_session_seconds:
                reason = "live_duration_limit"
            if reason:
                self._invalidate(owner, reason)
                self._spawn(self.stop_owner(owner, reason), "live-stop")
                continue
            if session and session.phase in ("active", "standby"):
                if now - session.last_estimate >= 1:
                    session.last_estimate = now
                    # Passive estimate only; no dollar amount can stop mobile.
                    await self._observe_usage("estimate_usage", session.reservation_id, now - session.created)
                if (lease.state == "armed" and not lease.playback_active and not lease.speech_active
                      and not session.pending_delegations
                      and now - session.last_activity >= self.config.idle_close_seconds):
                    self._spawn(self._request_close(session, "idle", keep_arm=True), "live-idle-close")

    async def _watch(self):
        try:
            while not self._stopped:
                await asyncio.sleep(min(0.5, self.config.heartbeat_seconds / 2))
                await self.tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Losing the supervisor is an admission and capture failure.
            for owner in tuple(self._leases):
                self._invalidate(owner, "live_supervisor_failed")
                self._spawn(self.stop_owner(owner, "live_supervisor_failed"), "live-supervisor-stop")
            self._stopped = True
            LOG.error("Live supervisor stopped; Live admission disabled")

    async def stop(self):
        if self._stopped and not self._running:
            return
        self._stopped = True
        owners = {s.owner for s in self._sessions.values()} | set(self._leases)
        await asyncio.gather(*(self.stop_owner(o, "server_shutdown", wait=False) for o in owners),
                             return_exceptions=True)
        if self._watchdog:
            self._watchdog.cancel()
        deadline = asyncio.get_running_loop().time() + self.config.opening_timeout_seconds + 2 * self.config.close_timeout_seconds + 1
        while True:
            pending = [t for t in self._tasks if not t.done() and t is not asyncio.current_task()]
            if not pending:
                break
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                break
            await asyncio.wait(pending, timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
        self._running = False
        await asyncio.to_thread(self.registry.close)
