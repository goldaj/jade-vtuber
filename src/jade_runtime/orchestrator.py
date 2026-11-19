"""Bounded message queue with explicit cancellation and shutdown."""
import asyncio
import logging
from dataclasses import dataclass, field, replace
from collections.abc import Awaitable, Callable
import time
from .dialogue import Dialogue
from .messages import Incoming, Reply
from .turn_logging import record_input, record_reply, record_outcome
from .turn_arbitration import ArbitratingQueue, TurnArbiter


@dataclass
class Work:
    message: Incoming
    deadline: float | None = None
    result: asyncio.Future | None = None
    cancelled: bool = False
    task: asyncio.Task | None = None
    turn: int = 0
    queued_at: float = field(default_factory=time.monotonic)
    finished: asyncio.Future | None = field(default=None, repr=False)

    def valid(self):
        return not self.cancelled and (self.deadline is None or
            asyncio.get_running_loop().time() < self.deadline)


class Runtime:
    def __init__(self, dialogue: Dialogue, on_reply: Callable[[Reply], Awaitable[None]],
                 max_queue: int = 64, on_stream_start=None, delivery_plan=None,
                 memory_service=None):
        if not 1 <= max_queue <= 1024:
            raise ValueError("invalid queue limit")
        self.dialogue, self.on_reply = dialogue, on_reply
        self.on_stream_start = on_stream_start
        self.delivery_plan = delivery_plan
        self.memory_service = memory_service
        self.queue = ArbitratingQueue(maxsize=max_queue)
        self.arbiter = TurnArbiter(dialogue.backend) if isinstance(dialogue, Dialogue) else None
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
        item = Work(message, deadline, result, turn=self._turn_sequence,
                    finished=asyncio.get_running_loop().create_future())
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
        if item.task is None and item.finished is not None and not item.finished.done():
            item.finished.set_result(None)

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
        if item is not None and self.latency_log.isEnabledFor(logging.INFO):
            # Only technical routing metadata and monotonic elapsed time;
            # never record participants, raw speech or message content.
            self.latency_log.info(
                "turn=%d platform=%s modality=%s stage=%s since_queue_ms=%.1f",
                item.turn, item.message.platform,
                ("voice" if item.message.platform in ("discord_voice", "microphone")
                 else item.message.input_modality),
                stage, (time.monotonic() - item.queued_at) * 1000)

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
        record_input(item.turn, item.message)
        turn = None
        committed = False
        command_reply = None
        memory_context = ""
        history_messages = []
        try:
            if self.memory_service is not None:
                self.mark_timing("memory_start")
                command_reply = await self.memory_service.command(item.message)
                if command_reply is None:
                    memory_context = await self.memory_service.context_for(item.message)
                    if (isinstance(self.dialogue, Dialogue)
                            and item.message.history_key not in self.dialogue.history):
                        history_messages = await self.memory_service.history_for(
                            item.message, limit=self.dialogue.max_messages // 2)
                self.mark_timing("memory_end")
            if (command_reply is None and self.on_stream_start is not None
                    and item.message.platform == "discord_voice"
                    and callable(getattr(self.dialogue.backend, "complete_stream", None))):
                turn = self.on_stream_start(item.message)
            if command_reply is not None:
                reply = command_reply
            elif turn is None:
                if isinstance(self.dialogue, Dialogue):
                    reply = await self.dialogue.respond(item.message, valid=item.valid,
                                                        on_timing=self.mark_timing,
                                                        memory_context=memory_context,
                                                        history_messages=history_messages)
                else:
                    reply = await self.dialogue.respond(item.message, valid=item.valid)
            else:
                reply = await self.dialogue.respond(
                    item.message, valid=item.valid, on_sentence=turn.emit,
                    on_timing=self.mark_timing, defer_history=True,
                    on_intent=getattr(turn, "set_intent", None),
                    memory_context=memory_context,
                    history_messages=history_messages)
            if not item.valid():
                raise TimeoutError("message expired")
            if reply is None and turn is not None:
                await turn.abort()
                turn = None
            if turn is not None:
                await turn.finish_input()
            if reply is None:
                self.mark_timing("no_reply")
                record_outcome(item.turn, "no_reply")
            else:
                destinations = (self.delivery_plan(reply) if self.delivery_plan is not None
                                else ("console_text",))
                record_reply(item.turn, reply, destinations)
            if item.result is not None and not item.result.done():
                if reply is None:
                    item.result.set_exception(RuntimeError("message not accepted"))
                else:
                    item.result.set_result(reply.text)
            if reply is not None and item.valid():
                self.mark_timing("delivery_start")
                try:
                    await self.on_reply(replace(reply, spoken=True) if turn is not None else reply)
                finally:
                    self.mark_timing("delivery_end")
            played = True
            if turn is not None:
                played = await turn.wait()
                await self.dialogue.commit_stream_response(item.message,
                                                           reply.text if played else None)
                committed = True
            if (reply is not None and played and command_reply is None and item.valid()
                    and self.memory_service is not None):
                await self.memory_service.remember_turn(item.message, reply)
                self.memory_service.schedule(item.message, reply)
            self.mark_timing("turn_complete")
        except BaseException as exc:
            self.mark_timing("turn_cancelled" if isinstance(
                exc, asyncio.CancelledError) else "turn_failed")
            record_outcome(item.turn, "cancelled" if isinstance(
                exc, asyncio.CancelledError) else "failed")
            if turn is not None:
                await turn.abort()
                if not committed and turn.has_submitted:
                    await self.dialogue.commit_stream_response(item.message, None)
            raise

    async def _process(self):
        while True:
            # Interleaved sources compete on content and recency, never on transport.
            # Heads preserve the order of each independent conversation.
            if self.arbiter is not None and self.queue.qsize() >= 2:
                choice = await self.arbiter.choose(self.queue.heads())
                if choice is not None:
                    self.queue.choose(choice)
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
                if item.finished is not None and not item.finished.done():
                    item.finished.set_result(None)
