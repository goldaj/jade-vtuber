"""NEW-20: user-visible incidents are scoped, deterministic and non-billable."""
import asyncio
import unittest

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.incidents import explain_incident
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime


class BrokenProvider:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return "Une réponse normale."


class StatusError(Exception):
    def __init__(self, status):
        self.status_code = status
        super().__init__("secret=private-token-" + str(status))


class IncidentDescriptions(unittest.TestCase):
    def test_codes_and_safe_french_messages(self):
        cases = (
            (TimeoutError("secret timeout"), "timeout", True),
            (asyncio.QueueFull(), "busy", True),
            (ConnectionError("token secret"), "connection", True),
            (PermissionError("api key secret"), "permission", False),
            (StatusError(429), "provider_limit", True),
            (StatusError(401), "permission", False),
            (StatusError(503), "unavailable", True),
            (RuntimeError("private conversation content"), "unavailable", True),
        )
        for error, code, retryable in cases:
            with self.subTest(code=code, kind=type(error).__name__):
                result = explain_incident(error)
                self.assertEqual(result.code, code)
                self.assertIs(result.retryable, retryable)
                self.assertEqual(result.payload()["incident_code"], code)
                self.assertTrue(result.message)
                self.assertNotIn("secret", result.message)
                self.assertNotIn("private", result.message)
                self.assertNotIn("token", result.message)
                if str(error):
                    self.assertNotIn(str(error), result.message)


class RuntimeIncidentTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_failed_discord_turn_has_one_notice_no_second_llm(self):
        backend = BrokenProvider(ConnectionError("secret customer email"))
        notices = []
        delivered = []
        async def report(incoming, incident):
            notices.append((incoming, incident))
        async def deliver(reply):
            delivered.append(reply)

        runtime = Runtime(Dialogue(backend, "Tu es Jade"), deliver, on_incident=report)
        await runtime.start()
        try:
            source = Incoming("discord", "Alice", "Jade, peux-tu aider ?",
                              channel="private", message_id="id", force_reply=True,
                              private_channel=True, direct_request=True)
            await runtime.submit(source)
            await asyncio.wait_for(runtime.idle(), 2)
        finally:
            await runtime.stop()
        self.assertEqual(backend.calls, 1)
        self.assertEqual(delivered, [])
        self.assertEqual(len(notices), 1)
        self.assertIs(notices[0][0], source)
        self.assertEqual(notices[0][1].code, "connection")
        self.assertEqual(runtime.errors, 1)

    async def test_spontaneous_and_non_direct_turns_never_publish_incident(self):
        backend = BrokenProvider(RuntimeError("private content"))
        notices = []
        async def report(*args):
            notices.append(args)
        runtime = Runtime(Dialogue(backend, "Tu es Jade"),
                          lambda reply: asyncio.sleep(0), on_incident=report)
        await runtime.start()
        try:
            for direct, force in ((False, True), (True, False)):
                await runtime.submit(Incoming(
                    "discord", "Alice", "bonjour",
                    force_reply=force, direct_request=direct))
            await asyncio.wait_for(runtime.idle(), 2)
        finally:
            await runtime.stop()
        self.assertEqual(notices, [])

    async def test_no_duplicate_incident_after_transport_handoff_failure(self):
        backend = BrokenProvider(None)
        notices = []
        async def fail_send(reply):
            raise ConnectionError("discord unavailable")
        async def report(*args):
            notices.append(args)
        runtime = Runtime(Dialogue(backend, "Tu es Jade"), fail_send,
                          on_incident=report)
        await runtime.start()
        try:
            await runtime.submit(Incoming(
                "discord", "Alice", "Jade ?", force_reply=True,
                direct_request=True))
            await asyncio.wait_for(runtime.idle(), 2)
        finally:
            await runtime.stop()
        self.assertEqual(notices, [])
        self.assertEqual(backend.calls, 1)

    async def test_incident_callback_failure_does_not_block_next_reply(self):
        backend = BrokenProvider(RuntimeError("provider unavailable"))
        sent = []
        attempts = 0
        async def report(*args):
            nonlocal attempts
            attempts += 1
            raise OSError("disk full")
        async def on_reply(reply):
            sent.append(reply.text)
        runtime = Runtime(Dialogue(backend, "Tu es Jade"), on_reply,
                          on_incident=report)
        await runtime.start()
        try:
            source = Incoming("discord", "Alice", "Jade ?", force_reply=True,
                              direct_request=True)
            await runtime.submit(source)
            await asyncio.wait_for(runtime.idle(), 2)
            backend.error = None
            await runtime.submit(source)
            await asyncio.wait_for(runtime.idle(), 2)
        finally:
            await runtime.stop()
        self.assertEqual(attempts, 1)
        self.assertEqual(len(sent), 1)
        self.assertEqual(runtime.errors, 1)

    def test_direct_request_flag_cannot_be_untrusted_nonboolean(self):
        with self.assertRaisesRegex(ValueError, "direct request"):
            Incoming("discord", "A", "Bonjour", direct_request="true")


if __name__ == "__main__":
    unittest.main()
