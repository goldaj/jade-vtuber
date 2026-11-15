"""Offline tests for multi-source scheduling and the one-click all-channels CLI."""
import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

from src.jade_runtime.config import Settings
from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming, Reply
from src.jade_runtime.orchestrator import Runtime, Work
from src.jade_runtime.output import AudioOutput, SpeechOutput
from src.jade_runtime.turn_arbitration import ArbitratingQueue, TurnArbiter
from src.jade_runtime.turn_logging import planned_destinations


def work(platform, channel, turn, *, text="Bonjour Jade", waiting=0, deadline=None):
    return Work(
        Incoming(platform, "someone", text, channel=channel, force_reply=True),
        deadline=deadline, turn=turn, queued_at=time.monotonic() - waiting)


class UnifiedTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_keeps_join_accounting_when_model_reorders(self):
        queue = ArbitratingQueue(maxsize=3)
        queue.put_nowait(work("discord", "chat", 1))
        queue.put_nowait(work("mobile", "owner", 2))
        self.assertEqual([item.turn for item in queue.heads()], [1, 2])
        queue.choose(2)
        item = queue.get_nowait()
        self.assertEqual(item.turn, 2)
        queue.task_done()
        self.assertEqual(queue.get_nowait().turn, 1)
        queue.task_done()
        await asyncio.wait_for(queue.join(), timeout=.2)

    async def test_one_candidate_per_conversation(self):
        queue = ArbitratingQueue(maxsize=4)
        queue.put_nowait(work("discord", "thread", 1))
        queue.put_nowait(work("discord", "thread", 2))
        queue.put_nowait(work("microphone", "mic", 3))
        self.assertEqual([item.turn for item in queue.heads()], [1, 3])

    async def test_jade_model_chooses_without_platform_preference(self):
        backend = type("Backend", (), {})()
        backend.complete = AsyncMock(return_value="2")
        arbiter = TurnArbiter(backend)
        self.assertEqual(await arbiter.choose([
            work("discord", "chat", 1, text="Bonjour"),
            work("mobile", "owner", 2, text="Question urgente ?"),
        ]), 2)
        self.assertIn("Aucun support n'a de priorité permanente",
                      backend.complete.await_args.args[0][0]["content"])

    async def test_fallback_no_extra_communication_and_oldest_fairness(self):
        backend = type("Backend", (), {})()
        backend.complete = AsyncMock(return_value="je veux faire autre chose")
        arbiter = TurnArbiter(backend)
        items = [work("mobile", "owner", 1), work("twitch", "chat", 2)]
        self.assertEqual(await arbiter.choose(items), 1)
        self.assertEqual(await arbiter.choose([
            work("discord", "chat", 1, waiting=16),
            work("mobile", "owner", 2),
        ]), 1)
        self.assertEqual(backend.complete.await_count, 1)

    async def test_deadline_prevents_loss_regardless_of_channel(self):
        backend = type("Backend", (), {})()
        backend.complete = AsyncMock(return_value="1")
        arbiter = TurnArbiter(backend)
        deadline = asyncio.get_running_loop().time() + 1
        self.assertEqual(await arbiter.choose([
            work("twitch", "chat", 1),
            work("mobile", "owner", 2, deadline=deadline),
        ]), 2)
        backend.complete.assert_not_awaited()

    async def test_runtime_honors_model_choice_when_two_channels_wait(self):
        started, release = asyncio.Event(), asyncio.Event()
        class FakeChat:
            async def complete(self, messages):
                if messages[0]["content"].startswith("Tu es le module d'arbitrage"):
                    return "3"
                if not started.is_set():
                    started.set()
                    await release.wait()
                return "OK"
        replies = []
        async def output(reply):
            replies.append(reply.source.platform)
        runtime = Runtime(Dialogue(FakeChat(), "Jade"), output)
        await runtime.start()
        try:
            await runtime.submit(Incoming("discord", "A", "Bonjour Jade", channel="a"))
            await asyncio.wait_for(started.wait(), 1)
            await runtime.submit(Incoming("twitch", "B", "Bonjour Jade", channel="b"))
            await runtime.submit(Incoming("mobile", "C", "Bonjour Jade", channel="c"))
            release.set()
            await asyncio.wait_for(runtime.idle(), 2)
            self.assertEqual(replies, ["discord", "mobile", "twitch"])
        finally:
            await runtime.stop(graceful=False)

    async def test_private_local_micro_never_uses_discord_broadcast(self):
        speaker = SpeechOutput(AsyncMock(), AudioOutput("ffplay"), "ignored.txt")
        bridge = type("Bridge", (), {})()
        bridge.delivery_context = lambda: "voice-session"
        speaker.secondary_player = bridge
        self.assertIsNone(speaker._delivery_context(
            Incoming("microphone", "Goldaj", "Bonjour Jade")))
        self.assertIsNone(speaker._delivery_context(
            Incoming("local_http", "owner", "Bonjour Jade")))
        destinations = planned_destinations(
            Reply(Incoming("microphone", "Goldaj", "Bonjour Jade"), "Bonjour"),
            has_speech=True, audio_output="ffplay", discord_voice=True)
        self.assertEqual(destinations, ("local_audio",))


class AllChannelsCLITests(unittest.TestCase):
    def test_all_channels_selects_all_inputs_without_a_mode(self):
        import main
        from unittest.mock import AsyncMock
        with patch("sys.argv", ["main.py", "--all-channels"]), \
                patch("main.Settings.load", return_value=Settings()), \
                patch("main.console", new_callable=AsyncMock) as launch:
            main.main()
        flags = launch.await_args.kwargs
        for key in ("live", "voice", "mic", "twitch", "discord",
                    "discord_voice", "http", "avatar", "mobile"):
            self.assertTrue(flags[key], key)
        self.assertFalse(flags["vts"])

    def test_twitch_must_send_when_all_channels_are_enabled(self):
        from src.jade_runtime.diagnostics import inspect_environment
        checks = inspect_environment(Settings(), live=True, twitch=True,
                                     all_channels=True)
        item = next(check for check in checks if check.name == "Twitch réponses activées")
        self.assertFalse(item.ok)
        self.assertTrue(item.required)

    def test_vtube_studio_is_also_enabled_when_configured(self):
        import main
        from unittest.mock import AsyncMock
        with patch("sys.argv", ["main.py", "--all-channels"]), \
                patch("main.Settings.load", return_value=Settings(vts_enabled=True, vts_token="fake")), \
                patch("main.console", new_callable=AsyncMock) as launch:
            main.main()
        self.assertTrue(launch.await_args.kwargs["vts"])


if __name__ == "__main__":
    unittest.main()
