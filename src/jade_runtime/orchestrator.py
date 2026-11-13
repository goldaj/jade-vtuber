"""Bounded message queue with explicit cancellation and shutdown."""
import asyncio
import logging
from dataclasses import dataclass, field, replace
from collections.abc import Awaitable, Callable
import time
from .dialogue import Dialogue
from .messages import Incoming, Reply


@dataclass
class Work:
    message: Incoming
    deadline: float | None = None
    result: asyncio.Future | None = None
    cancelled: bool = False
    task: asyncio.Task | None = None
    turn: int = 0
    queued_at: float = field(default_factory=time.monotonic)

    def valid(self):
        return not self.cancelled and (self.deadline is None or
            asyncio.get_running_loop().time() < self.deadline)


class Runtime:
    def __init__(self, dialogue: Dialogue, on_reply: Callable[[Reply], Awaitable[None]],
                 max_queue: int = 64, on_stream_start=None):
        if not 1 <= max_queue <= 1024:
            raise ValueError("invalid queue limit")
        self.dialogue, self.on_reply = dialogue, on_reply
        self.on_stream_start = on_stream_start
        self.queue = asyncio.Queue(maxsize=max_queue)
        self.worker = None
        self.active = None
        self.state = "STOPPED"
        self._abort = False
        self.log = logging.getLogger("jade.runtime")
        self.latency_log = logging.getLogger("jade.latency")
        self._turn_sequence = 0
        self.errors = 0
        self._stop_lock = asyncio.Lock()

    async def start(self):
        if self.state != "STOPPED" or (self.worker and not self.worker.done()):
            raise RuntimeError("runtime already running")
        self.state = "RUNNING"
        self._abort = False
        self.worker = asyncio.create_task(self._process(), name="jade-consumer")

    async def submit(self, message: Incoming, *, deadline=None, result=None):
        if self.state != "RUNNING" or self.worker is None or self.worker.done():
            raise RuntimeError("runtime is not running")
        self._turn_sequence += 1
        item = Work(message, deadline, result, turn=self._turn_sequence)
        self.queue.put_nowait(item)
        return item

    def cancel_work(self, item):
        if item.cancelled:
            return
        item.cancelled = True
        if item.task is not None and not item.task.done():
            item.task.cancel()
        if item.result is not None and not item.result.done():
            item.result.cancel()

    def _expire_work(self, item):
        if item.cancelled:
            return
        item.cancelled = True
        if item.result is not None and not item.result.done():
            item.result.set_exception(TimeoutError("message expired"))
        if item.task is not None and not item.task.done():
            item.task.cancel()

    def begin_shutdown(self):
        if self.state == "STOPPED":
            return
        if self._abort:
            return
        self.state = "STOPPING"
        self._abort = True
        if self.active is not None:
            self.cancel_work(self.active)
        self._discard_pending()

    def _discard_pending(self):
        while True:
            try:
                item = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                if item is not None:
                    self.cancel_work(item)
            finally:
                self.queue.task_done()

    async def idle(self):
        await self.queue.join()

    def current_valid(self):
        return not self._abort and self.active is not None and self.active.valid()

    def mark_timing(self, stage):
        """Optional local timing: no message content or participant identity."""
        item = self.active
        if (item is not None and item.message.platform == "discord_voice"
                and self.latency_log.isEnabledFor(logging.INFO)):
            self.latency_log.info("turn=%d stage=%s since_queue_ms=%.1f",
                                  item.turn, stage, (time.monotonic() - item.queued_at) * 1000)

    async def stop(self, *, graceful=True, timeout=5.0):
        async with self._stop_lock:
            if self.worker is None:
                self.state = "STOPPED"
                return
            self.state = "STOPPING"
            end = asyncio.get_running_loop().time() + timeout
            if graceful:
                try:
                    await asyncio.wait_for(self.queue.join(), timeout=max(0, end - asyncio.get_running_loop().time()))
                except TimeoutError:
                    self.begin_shutdown()
            else:
                self.begin_shutdown()
            self._discard_pending()
            worker = self.worker
            # Allow cancellation cleanup (notably audio process termination) to
            # finish before cancelling the worker that is awaiting this task.
            active = self.active
            if active is not None and active.task is not None and not active.task.done():
                done, _ = await asyncio.wait({active.task}, timeout=max(0, end - asyncio.get_running_loop().time()))
                if not done:
                    raise TimeoutError("active work did not stop")
            if not worker.done():
                worker.cancel()
            done, _ = await asyncio.wait({worker}, timeout=max(0, end - asyncio.get_running_loop().time()))
            if not done:
                raise TimeoutError("runtime worker did not stop")
            if not worker.cancelled():
                worker.result()
            self.worker = None
            self.state = "STOPPED"

    async def _execute(self, item):
        if not item.valid():
            raise TimeoutError("message expired")
        self.mark_timing("queue_start")
        turn = None
        committed = False
        try:
            if (self.on_stream_start is not None and item.message.platform == "discord_voice"
                    and callable(getattr(self.dialogue.backend, "complete_stream", None))):
                turn = self.on_stream_start(item.message)
            if turn is None:
                if isinstance(self.dialogue, Dialogue):
                    reply = await self.dialogue.respond(item.message, valid=item.valid,
                                                        on_timing=self.mark_timing)
                else:
                    reply = await self.dialogue.respond(item.message, valid=item.valid)
            else:
                reply = await self.dialogue.respond(
                    item.message, valid=item.valid, on_sentence=turn.emit,
                    on_timing=self.mark_timing, defer_history=True)
            if not item.valid():
                raise TimeoutError("message expired")
            if reply is None and turn is not None:
                await turn.abort()
                turn = None
            if turn is not None:
                await turn.finish_input()
            if item.result is not None and not item.result.done():
                if reply is None:
                    item.result.set_exception(RuntimeError("message not accepted"))
                else:
                    item.result.set_result(reply.text)
            if reply is not None and item.valid():
                await self.on_reply(replace(reply, spoken=True) if turn is not None else reply)
            if turn is not None:
                played = await turn.wait()
                await self.dialogue.commit_stream_response(item.message,
                                                           reply.text if played else None)
                committed = True
        except BaseException:
            if turn is not None:
                await turn.abort()
                if not committed and turn.has_submitted:
                    await self.dialogue.commit_stream_response(item.message, None)
            raise

    async def _process(self):
        while True:
            item = await self.queue.get()
            self.active = item
            timer = None
            try:
                if not item.valid():
                    raise TimeoutError("message expired")
                item.task = asyncio.create_task(self._execute(item))
                if item.deadline is None:
                    await item.task
                else:
                    timer = asyncio.get_running_loop().call_at(item.deadline, self._expire_work, item)
                    await item.task
            except asyncio.CancelledError:
                if item.task is not None and not item.task.done():
                    item.task.cancel()
                if item.result is not None and not item.result.done():
                    item.result.cancel()
                if asyncio.current_task().cancelling():
                    raise
            except Exception as exc:
                self.errors += 1
                if item.result is not None and not item.result.done():
                    item.result.set_exception(TimeoutError() if isinstance(exc, TimeoutError)
                                              else RuntimeError("message processing failed"))
                self.log.warning("Message processing failed (%s)", self.errors)
            finally:
                if timer is not None:
                    timer.cancel()
                self.active = None
                self.queue.task_done()
