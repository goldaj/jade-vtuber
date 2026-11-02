import asyncio
import unittest
from unittest.mock import patch
from unittest.mock import AsyncMock

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.local_http import LocalHTTP


def msg(channel='a', ident='x'):
    return Incoming('local_http', 'tester', 'hello', channel, ident, True)


class RuntimeSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_shutdown_waits_for_active_cleanup(self):
        started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        cleaned = []
        backend = AsyncMock()
        backend.complete.return_value = 'ok'
        async def output(reply):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
                cleaned.append(True)
        runtime = Runtime(Dialogue(backend, 'Jade'), output)
        await runtime.start()
        await runtime.submit(msg())
        await started.wait()
        runtime.begin_shutdown()
        await cleaning.wait()
        stop = asyncio.create_task(runtime.stop(graceful=False, timeout=2))
        await asyncio.sleep(0)
        release.set()
        await stop
        self.assertEqual(cleaned, [True])

    async def test_expired_queued_work_does_not_call_backend(self):
        gate = asyncio.Event()
        started = asyncio.Event()
        async def complete(messages):
            started.set()
            await gate.wait()
            return 'ok'
        backend = AsyncMock()
        backend.complete.side_effect = complete
        runtime = Runtime(Dialogue(backend, 'Jade'), AsyncMock())
        await runtime.start()
        await runtime.submit(msg('first'))
        await started.wait()
        future = asyncio.get_running_loop().create_future()
        await runtime.submit(msg('second'), deadline=asyncio.get_running_loop().time() + .01, result=future)
        await asyncio.sleep(.03)
        gate.set()
        with self.assertRaises(TimeoutError):
            await future
        await runtime.idle()
        self.assertEqual(backend.complete.await_count, 1)
        await runtime.stop()

    async def test_timeout_during_call_does_not_save_or_emit(self):
        started = asyncio.Event()
        async def stalled(messages):
            started.set()
            await asyncio.Event().wait()
        backend = AsyncMock()
        backend.complete.side_effect = stalled
        output = AsyncMock()
        dialogue = Dialogue(backend, 'Jade')
        runtime = Runtime(dialogue, output)
        await runtime.start()
        future = asyncio.get_running_loop().create_future()
        await runtime.submit(msg(), deadline=asyncio.get_running_loop().time() + .05, result=future)
        await started.wait()
        with self.assertRaises(TimeoutError):
            await future
        await runtime.idle()
        self.assertEqual(len(dialogue.history[('local_http', 'a')]), 0)
        output.assert_not_awaited()
        await runtime.stop()

    async def test_late_result_ignoring_cancel_does_not_save_or_emit(self):
        async def slow(messages):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return 'late answer'
        backend = AsyncMock()
        backend.complete.side_effect = slow
        dialogue = Dialogue(backend, 'Jade')
        output = AsyncMock()
        runtime = Runtime(dialogue, output)
        await runtime.start()
        future = asyncio.get_running_loop().create_future()
        await runtime.submit(msg(), deadline=asyncio.get_running_loop().time() + .05, result=future)
        with self.assertRaises(TimeoutError):
            await future
        await runtime.idle()
        self.assertEqual(len(dialogue.history[('local_http', 'a')]), 0)
        output.assert_not_awaited()
        await runtime.stop()

    async def test_shutdown_cancels_active_and_rejects_admission(self):
        started = asyncio.Event()
        async def stalled(messages):
            started.set()
            await asyncio.Event().wait()
        backend = AsyncMock()
        backend.complete.side_effect = stalled
        runtime = Runtime(Dialogue(backend, 'Jade'), AsyncMock(), max_queue=1)
        await runtime.start()
        await runtime.submit(msg('active'))
        await started.wait()
        future = asyncio.get_running_loop().create_future()
        await runtime.submit(msg('pending'), result=future)
        runtime.begin_shutdown()
        self.assertTrue(future.cancelled())
        with self.assertRaises(RuntimeError):
            await runtime.submit(msg())
        await asyncio.wait_for(runtime.stop(graceful=False), 1)
        await runtime.stop(graceful=False)
        await asyncio.wait_for(runtime.queue.join(), 1)
        self.assertEqual(backend.complete.await_count, 1)

    async def test_lru_never_evicts_active_or_waiting_session(self):
        gate = asyncio.Event()
        entered = asyncio.Event()
        async def stalled(messages):
            entered.set()
            await gate.wait()
            return 'ok'
        backend = AsyncMock()
        backend.complete.side_effect = stalled
        dialogue = Dialogue(backend, 'Jade', max_sessions=1)
        first = asyncio.create_task(dialogue.respond(msg('a')))
        await entered.wait()
        second = asyncio.create_task(dialogue.respond(msg('a', 'y')))
        await asyncio.sleep(0)
        with self.assertRaises(RuntimeError):
            await dialogue.respond(msg('b'))
        gate.set()
        await asyncio.gather(first, second)
        await dialogue.respond(msg('b'))
        self.assertNotIn(('local_http', 'a'), dialogue.locks)
        self.assertEqual(len(dialogue.locks), 1)

    async def test_failure_can_retry_same_id(self):
        backend = AsyncMock()
        backend.complete.side_effect = [ValueError('provider failure'), 'ok']
        dialogue = Dialogue(backend, 'Jade')
        with self.assertRaises(ValueError):
            await dialogue.respond(msg())
        self.assertEqual((await dialogue.respond(msg())).text, 'ok')
        self.assertEqual(backend.complete.await_count, 2)

    async def test_expired_idle_session_is_removed(self):
        backend = AsyncMock()
        backend.complete.return_value = 'ok'
        dialogue = Dialogue(backend, 'Jade', max_sessions=2, session_ttl=2)
        with patch('src.jade_runtime.dialogue.time.monotonic', return_value=10):
            await dialogue.respond(msg('a'))
        with patch('src.jade_runtime.dialogue.time.monotonic', return_value=13):
            await dialogue.respond(msg('a', 'again'))
        self.assertEqual(len(dialogue.history[('local_http', 'a')]), 2)

    async def test_http_provider_failure_returns_503_without_waiting(self):
        backend = AsyncMock()
        backend.complete.side_effect = ValueError('synthetic provider error')
        runtime = Runtime(Dialogue(backend, 'Jade'), AsyncMock())
        await runtime.start()
        gateway = LocalHTTP(runtime, token='safe-token-' * 4)
        reader = asyncio.StreamReader()
        body = b'{"text":"hello"}'
        reader.feed_data(b'POST /message HTTP/1.1\r\nAuthorization: Bearer ' +
                         gateway.token.encode() + b'\r\nContent-Length: ' +
                         str(len(body)).encode() + b'\r\n\r\n' + body)
        reader.feed_eof()
        writer = AsyncMock()
        writer.write = unittest.mock.Mock()
        writer.close = unittest.mock.Mock()
        await asyncio.wait_for(gateway.handle(reader, writer), timeout=1)
        self.assertIn(b'503 Service Unavailable', writer.write.call_args[0][0])
        self.assertNotIn(b'synthetic provider error', writer.write.call_args[0][0])
        await runtime.stop()

    async def test_http_rejects_over_limit_before_reading(self):
        gateway = LocalHTTP(AsyncMock(), token='safe-token-' * 4)
        gateway.active_connections = gateway.max_connections
        reader = AsyncMock()
        writer = AsyncMock()
        writer.close = unittest.mock.Mock()
        await gateway.handle(reader, writer)
        reader.readline.assert_not_awaited()
        writer.close.assert_called_once()
