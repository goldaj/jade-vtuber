"""Offline acceptance tests: memory, social, continuity, metrics; no paid API."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from src.jade_runtime.cross_channel import CrossChannelContinuity, natural_command
from src.jade_runtime.deploy_supervisor import Supervisor, branch_valid
from src.jade_runtime.group_context import addressed_to_other
from src.jade_runtime.memory_relevance import rank_memories
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming
from src.jade_runtime.personality_evolution import personality_snapshot
from src.jade_runtime.presence_memory import PresenceMemoryCache
from src.jade_runtime.turn_metrics import TurnMetrics, bind_metrics, reset_metrics, record_model_usage


class ScopedMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = MemoryStore(Path(self.tmp.name) / "jade-test.sqlite3")
        self.owner = ("microphone", "goldaj")
        self.other = ("discord", "12345")
        self.store.enable(self.owner)
        self.store.enable(self.other)

    async def test_scoped_relevance_and_no_public_mixing(self):
        self.store.put(self.owner, kind="ordinary", scope="person",
                       summary="Jade apprend le dessin manga", significance="important")
        self.store.put(self.other, kind="ordinary", scope="discord:88",
                       summary="Le chien mange des pommes", significance="sans rapport")
        candidates = self.store.recall_candidates(self.owner, "person")
        selected = rank_memories(candidates, "Tu apprends le dessin manga ?", limit=8)
        self.assertEqual(len(selected), 1)
        self.assertIn("dessin manga", selected[0]["summary"])
        self.assertEqual(self.store.recall_candidates(self.other, "person"), [])
        self.assertEqual(self.store.recall_candidates(self.owner, "discord:88"), [])
        self.assertEqual(self.store.recall_candidates(self.other, "discord:88", linked=True), [])

    async def test_presence_cache_invalidates_on_delete_and_unlink(self):
        self.store.put(self.owner, kind="ordinary", scope="person",
                       summary="Jade aime les cerisiers", significance="important")
        cache = PresenceMemoryCache(self.store)
        first = await cache.candidates(self.owner, "person")
        self.assertEqual(len(first), 1)
        entries = self.store.list_for_account(self.owner)
        self.store.delete_memory(self.owner, entries[0]["id"])
        self.assertEqual(await cache.candidates(self.owner, "person"), [])
        self.store.put(self.owner, kind="ordinary", scope="person",
                       summary="Jade joue aux échecs", significance="important")
        self.assertEqual(len(await cache.candidates(self.owner, "person")), 1)

    async def test_cache_never_outlives_ordinary_memory_expiry(self):
        self.store.put(self.owner, kind="ordinary", scope="person",
                       summary="Jade prépare un rendez-vous", significance="utile")
        imminent = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
        with self.store._db() as db:
            db.execute("UPDATE memories SET expires_at=?", (imminent,))
        cache = PresenceMemoryCache(self.store, ttl_seconds=600)
        self.assertEqual(len(await cache.candidates(self.owner, "person")), 1)
        deadline = next(iter(cache._entries.values()))[0]
        self.assertLess(deadline - cache.clock(), 3)

    async def test_identity_never_uses_nickname(self):
        no_verified = ("discord", "999")
        cache = PresenceMemoryCache(self.store)
        self.assertEqual(await cache.candidates(no_verified, "person"), [])


class PersonalityTests(unittest.TestCase):
    def test_stable_version_and_correction(self):
        row = {"summary": "Jade aime dessiner", "kind": "ordinary",
               "significance": "trait durable", "created_at": "2026-11-19"}
        profile = personality_snapshot([row, dict(row)])
        self.assertEqual(len(profile["observations"]), 1)
        self.assertEqual(profile["version"], personality_snapshot([row, row])["version"])
        self.assertEqual(len(personality_snapshot([row])["observations"]), 1)
        self.assertEqual(personality_snapshot([
            {"summary": "Louis aime dessiner", "kind": "core_relationship",
             "significance": "n/a"}
        ])["observations"], [])


class GroupTests(unittest.TestCase):
    def test_reply_to_other_human_without_jade(self):
        person = SimpleNamespace(id=15)
        msg = SimpleNamespace(content="Tu crois vraiment ?", guild=object(),
                              mentions=[person], reference=None)
        self.assertTrue(addressed_to_other(msg, own_user_id=99))
        msg.content = "Jade, tu crois vraiment ?"
        self.assertFalse(addressed_to_other(msg, own_user_id=99))
        msg.content = "ok"
        msg.mentions = []
        msg.reference = SimpleNamespace(resolved=SimpleNamespace(
            author=SimpleNamespace(id=15)))
        self.assertTrue(addressed_to_other(msg, own_user_id=99))


class ContinuityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = MemoryStore(Path(self.tmp.name) / "jade-continuity.sqlite3")
        self.store.enable(("microphone", "goldaj"))
        self.sent = []

        async def sender(dest, text):
            self.sent.append((dest, text))
            return True
        self.coordinator = CrossChannelContinuity(
            self.store, send_discord=sender, allowed_discord_channels=[555])
        self.owner = Incoming(platform="mobile", author="Goldaj",
                              channel="session-owner", text="!jade-tache liste", force_reply=True)

    async def test_owner_tasks_persist_and_resume_in_a_new_channel(self):
        owner = self.owner
        add = await self.coordinator.command(
            Incoming(platform="mobile", author="Goldaj",
                     channel=owner.channel, text="!jade-tache ajouter Préparer la démo"))
        self.assertIn("Tâche suivie", add.text)
        tasks = self.coordinator._tasks(("microphone", "goldaj"), operation="list")
        self.assertEqual(len(tasks), 1)
        other = Incoming(platform="mobile", author="Goldaj",
                         channel="session-autre", text="!jade-tache reprendre "
                         + tasks[0]["id"][:8])
        self.assertIn("Objectif repris", (await self.coordinator.command(other)).text)
        later = Incoming(platform="mobile", author="Goldaj",
                         channel="session-autre", text="Poursuis notre tâche")
        self.assertIn("Préparer la démo", await self.coordinator.context_for(later))
        self.assertIn("Tâche terminée", (await self.coordinator.command(
            Incoming(platform="mobile", author="Goldaj",
                     channel="session-autre", text="!jade-tache terminer "
                     + tasks[0]["id"][:8]))).text)
        self.assertFalse(await self.coordinator.context_for(later))

    async def test_natural_phrases_only_execute_explicit_commands(self):
        natural = Incoming(platform="mobile", author="Goldaj", channel="private",
                           text="Jade, ajoute une tâche : Terminer le plan de recette")
        answer = await self.coordinator.command(natural)
        self.assertIn("Tâche suivie", answer.text)
        tasks = self.coordinator._tasks(("microphone", "goldaj"), operation="list")
        self.assertEqual(len(tasks), 1)
        self.assertIn("Terminer le plan de recette", await self.coordinator.context_for(
            Incoming(platform="mobile", author="Goldaj", channel="autre-session",
                     text="On en était où ?")))
        self.assertIn("Tâches en cours", (await self.coordinator.command(
            Incoming(platform="mobile", author="Goldaj", channel="private",
                     text="Jade, liste mes tâches en cours"))).text)
        transfer = Incoming(platform="mobile", author="Goldaj", channel="private",
                            text="Jade, envoie ce message sur Discord dans le salon 555 : "
                                 "La recette commence demain.")
        self.assertIn("remis", (await self.coordinator.command(transfer)).text)
        self.assertEqual(self.sent, [("555", "La recette commence demain.")])
        # An ambiguous conversational mention must not trigger an action.
        self.assertIsNone(natural_command("Peut-être qu'on pourrait prévenir le Discord."))
        self.assertIsNone(await self.coordinator.command(
            Incoming(platform="mobile", author="Goldaj", channel="private",
                     text="Je pensais envoyer une annonce sur Discord")))

    async def test_explicit_allowlisted_cross_channel_send(self):
        cmd = Incoming(platform="mobile", author="Goldaj", channel="private",
                       text="!jade-transfert discord:555 Bonjour à tous")
        self.assertIn("remis", (await self.coordinator.command(cmd)).text)
        self.assertEqual(self.sent, [("555", "Bonjour à tous")])
        bad = Incoming(platform="mobile", author="Goldaj", channel="private",
                       text="!jade-transfert discord:666 message interdit")
        self.assertIn("non autorisée", (await self.coordinator.command(bad)).text)
        self.assertEqual(len(self.sent), 1)
        public = Incoming(platform="discord", author="Goldaj", channel="444",
                          account_id="123", text=cmd.text)
        self.assertIn("privée", (await self.coordinator.command(public)).text)
        self.assertEqual(len(self.sent), 1)


class DeploymentSupervisorTests(unittest.TestCase):
    def test_untrusted_branch_names_rejected(self):
        self.assertTrue(branch_valid("develop"))
        self.assertTrue(branch_valid("feature/jade"))
        for value in ("../secrets", "feature//oops", "bad..ref", "-bad", "", "@{x}"):
            self.assertFalse(branch_valid(value))

    def test_failed_restart_restores_previous_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / ".git").mkdir()
            manager = Supervisor(Path(temporary), ["jade-local"])
            class FakeChild:
                stopped = False
                def terminate(self):
                    self.stopped = True
                def wait(self, timeout):
                    return 0
                def poll(self):
                    return 0 if self.stopped else None

            manager.child = FakeChild()
            manager.state["branch"] = "develop"
            manager.state["phase"] = "working"
            manager.git = lambda *args, **kwargs: (
                "abc123" if args[0] == "rev-parse" else "develop")
            attempts = []
            def launch():
                attempts.append("launch")
                if len(attempts) == 1:
                    raise RuntimeError("jade_exited_on_start")
                manager.child = FakeChild()
            manager._launch = launch
            manager._perform(None, restart_only=True)
            self.assertEqual(len(attempts), 2)
            self.assertTrue(manager.snapshot()["running"])
            self.assertEqual(manager.snapshot()["sha"], "abc123")
            self.assertEqual(manager.snapshot()["phase"], "idle")
            self.assertEqual(manager.snapshot()["error"], "jade_exited_on_start")


class MetricsTests(unittest.TestCase):
    def test_provider_tokens_are_attributed_only_to_current_turn(self):
        clock = [10.0]
        metrics = TurnMetrics(clock=lambda: clock[0])
        metrics.begin(1, "mobile", "text", clock[0])
        token = bind_metrics(metrics, 1)
        try:
            record_model_usage(60, 12)
            record_model_usage(20, 8)
            record_model_usage(None, None)
        finally:
            reset_metrics(token)
        record_model_usage(1000, 1000)
        clock[0] = 11.0
        metrics.end(1)
        summary = metrics.summary()[0]
        self.assertEqual(summary["usage"], {
            "n": 1, "input_tokens": 80, "output_tokens": 20})
        self.assertIsNone(summary["cost_usd"])

    def test_quantiles_without_private_user_data(self):
        clock = [1.0]
        metrics = TurnMetrics(clock=lambda: clock[0])
        metrics.begin(7, "mobile", "text", clock[0])
        clock[0] = 1.10
        metrics.mark(7, "llm_first_token")
        clock[0] = 1.50
        metrics.end(7)
        rows = metrics.summary()
        self.assertEqual(rows[0]["latency"]["total_ms"]["p95_ms"], 500.0)
        self.assertIsNone(rows[0]["first_audible_ms"])
        self.assertIsNone(rows[0]["cost_usd"])
        self.assertNotIn("Goldaj", str(rows))


if __name__ == "__main__":
    unittest.main()
