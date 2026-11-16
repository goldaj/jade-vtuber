"""Offline security regressions for queue arbitration and identity-link proofs."""
import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.jade_runtime.turn_arbitration import TurnArbiter


class ArbitrationPrivacyTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_use_memory_proof_never_reaches_arbitration_model(self):
        secret = "v1.twitch.6001.anActualOneTimeSecret1234567890"
        backend = SimpleNamespace(complete=AsyncMock(return_value="2"))
        now = time.monotonic()
        sources = (
            SimpleNamespace(turn=1, queued_at=now, deadline=None,
                            message=SimpleNamespace(platform="twitch",
                                text="!jade-memoire   CONFIRMER " + secret),
                            valid=lambda: True),
            SimpleNamespace(turn=2, queued_at=now, deadline=None,
                            message=SimpleNamespace(platform="discord",
                                text="Jade, bonjour"),
                            valid=lambda: True),
        )
        chosen = await asyncio.wait_for(TurnArbiter(backend).choose(sources), 3)
        self.assertEqual(chosen, 2)
        body = str(backend.complete.await_args.args[0])
        self.assertNotIn(secret, body)
        self.assertIn("[code masqué]", body)
        self.assertIn("Jade, bonjour", body)


if __name__ == "__main__":
    unittest.main()
