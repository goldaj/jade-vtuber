"""Regression: cancellation must win over a simultaneous IRC read."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from src.jade_runtime.twitch_irc import TwitchIRC
from src.jade_runtime.twitch_managed import run_managed_twitch


class TwitchCancelRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_when_irc_join_reply_arrives_closes_transport(self):
        holder = {}

        class Reader:
            reads = 0

            async def readline(self):
                self.reads += 1
                if self.reads == 1:
                    # The join reply and cancellation arrive in the same turn.
                    holder["task"].cancel()
                    return b":server 366 bot #channel :End of names\r\n"
                await asyncio.Event().wait()

        class Writer:
            closed = False
            waited = False

            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                self.closed = True

            async def wait_closed(self):
                self.waited = True

        writer = Writer()
        client = TwitchIRC(login="bot", token="synthetic", channel="channel",
                           on_message=AsyncMock(),
                           connector=AsyncMock(return_value=(Reader(), writer)))
        task = asyncio.create_task(client.connect_once())
        holder["task"] = task
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.25)
        self.assertTrue(writer.closed)
        self.assertTrue(writer.waited)

    async def test_idle_timeout_still_closes_transport(self):
        class Reader:
            async def readline(self):
                await asyncio.Event().wait()

        writer = type("Writer", (), {
            "write": lambda self, data: None,
            "drain": AsyncMock(),
            "close": lambda self: setattr(self, "closed", True),
            "wait_closed": AsyncMock(),
            "closed": False,
        })()
        client = TwitchIRC(login="bot", token="synthetic", channel="channel",
                           on_message=AsyncMock(),
                           connector=AsyncMock(return_value=(Reader(), writer)))
        timeout = asyncio.timeout
        with patch("src.jade_runtime.twitch_irc.asyncio.timeout",
                   side_effect=lambda _: timeout(0.01)):
            with self.assertRaises(TimeoutError):
                await client.connect_once()
        self.assertTrue(writer.closed)
        writer.wait_closed.assert_awaited_once()

    async def _cancel_managed_during_join(self, wait_closed):
        joined = asyncio.Event()
        connects = []

        class Reader:
            async def readline(self):
                joined.set()
                await asyncio.Event().wait()

        class Writer:
            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                await wait_closed()

        async def connector(*args, **kwargs):
            connects.append(True)
            return Reader(), Writer()

        client = TwitchIRC(login="bot", token="synthetic", channel="channel",
                           on_message=AsyncMock(), connector=connector)
        task = asyncio.create_task(run_managed_twitch(client, SimpleNamespace()))
        try:
            await asyncio.wait_for(joined.wait(), 1)
            task.cancel()
            done, _ = await asyncio.wait([task], timeout=0.5)
            self.assertTrue(done, "managed connector did not stop")
            self.assertTrue(task.cancelled())
            self.assertEqual(len(connects), 1)
        finally:
            if not task.done():
                # Ensure a failing regression test does not leave a task behind.
                for child in asyncio.all_tasks():
                    if child.get_name() == "jade-twitch-connection":
                        child.cancel()
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_tls_close_error_does_not_mask_cancellation_or_reconnect(self):
        async def failed_close():
            raise ConnectionResetError("sensitive synthetic provider error")

        with self.assertNoLogs("jade.twitch", level="WARNING"):
            await self._cancel_managed_during_join(failed_close)

    async def test_tls_close_is_bounded_during_cancellation(self):
        async def hanging_close():
            await asyncio.Event().wait()

        with patch("src.jade_runtime.twitch_irc.CLOSE_TIMEOUT", 0.03):
            with self.assertNoLogs("jade.twitch", level="WARNING"):
                await self._cancel_managed_during_join(hanging_close)


if __name__ == "__main__":
    unittest.main()
