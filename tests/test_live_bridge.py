"""Live continuity and effects, using real local business stores and fake models.

No OpenAI connection, audio device, Discord account or paid call is used.
"""
import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.documents import DocumentService
from src.jade_runtime.live_bridge import LiveConversationBridge, LiveJournalConflict
from src.jade_runtime.memory_service import MemoryService
from src.jade_runtime.memory_store import MemoryStore
from src.jade_runtime.messages import Incoming
from src.jade_runtime.orchestrator import Runtime
from src.jade_runtime.reminders import ReminderService
from src.jade_runtime.responses_chat import ResponsesChat
from src.jade_runtime.turn_metrics import record_model_usage
from src.jade_runtime.web_search import SearchHit, SearchJournal, SearchResponse, WebSearchService


OWNER = ("microphone", "goldaj")


class Model:
    def __init__(self):
        self.requests = []
        self.answer = "[INTENT:curious] Je garde le fil de notre conversation."

    async def complete(self, messages):
        self.requests.append(messages)
        record_model_usage(73, 19)
        return self.answer


class ToolModel(Model):
    def __init__(self, script):
        super().__init__()
        self.script = script

    async def complete_with_tools(self, messages, action):
        self.requests.append(messages)
        record_model_usage(120, 30)
        return await self.script(action)


class LiveBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = MemoryStore(self.root / "memory.sqlite3")
        self.store.enable(OWNER)
        self.model = Model()
        self.memory = MemoryService(self.store, self.model)
        self.classic = []
        self.published = []
        self.sent = []
        self.reservations = []
        self.settlements = []
        self.allowed = True
        self.valid = True
        self.release_events = []
        self.deferred_writers = []

        async def on_reply(reply):
            self.classic.append(reply)

        async def publish(context, event):
            self.published.append(event)

        async def reserve(context, delegation):
            self.reservations.append(delegation)
            return "reserve-" + delegation if self.allowed else None

        async def settle(context, delegation, reservation, usage, status):
            self.settlements.append((delegation, reservation, usage, status))

        self.runtime = Runtime(Dialogue(self.model, "Tu es Jade, avec ta personnalité approuvée."),
                               on_reply, memory_service=self.memory)
        await self.runtime.start()
        self.bridge = LiveConversationBridge(self.runtime,
            journal_path=self.root / "live.sqlite3", publish=publish,
            reserve_delegation=reserve, settle_delegation=settle,
            fragment_wait_seconds=0, close_timeout=.1)
        self.ctx = {"owner": "Goldaj", "thread_id": "thread_live_01",
                    "session_id": "live_session_1", "generation": 1,
                    "valid": lambda: self.valid}
        await self.bridge.open_session(self.ctx)
        self.sequence = 0

    async def asyncTearDown(self):
        # Failed assertions must not leave a fake backend or writer holding
        # a SQLite file while TemporaryDirectory removes it on Windows.
        for event in self.release_events:
            event.set()
        await self.bridge.close()
        await self.runtime.stop(graceful=False, timeout=1)
        await self.finish_tasks()
        await self.finish_flushes()
        for writer in self.deferred_writers:
            await writer.close()
        await self.memory.close()
        self.temp.cleanup()

    async def send(self, event):
        self.sent.append(event)

    async def transcript(self, role, text, start=0, end=1000, *, eid=None, context=None):
        self.sequence += 1
        event = {"type": "session." + ("input" if role == "user" else "output")
                        + "_transcript.delta",
                 "event_id": eid or "event-" + str(self.sequence), "delta": text,
                 "start_ms": start, "end_ms": end}
        await self.bridge.handle_event(event, context or self.ctx, self.send)
        return event

    async def delegation(self, ident="delegation1", offset=1000, *, wait=True, context=None):
        self.sequence += 1
        event = {"type": "session.delegation.created", "event_id": "delegation-event-" + str(self.sequence),
                 "offset_ms": offset, "delegation": {"id": ident, "type": "delegation", "target": "client"}}
        await self.bridge.handle_event(event, context or self.ctx, self.send)
        if wait:
            await self.finish_tasks()
        return event

    async def finish_tasks(self):
        for _ in range(6):
            tasks = [task for state in self.bridge.sessions.values() for task in state.tasks.values()]
            if not tasks:
                return
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 3)
        self.fail("Live tasks did not finish")

    async def finish_flushes(self):
        # close_session deliberately bounds its wait, not the lifetime of
        # offline persistence. Join the actual work before inspecting storage.
        tasks = {state.flush_task for state in self.bridge.sessions.values()
                 if state.flush_task is not None}
        tasks.update(self.bridge._flush_tasks)
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks), 10)

    async def close_and_flush(self, reason):
        await self.bridge.close_session(self.ctx, reason)
        await self.finish_flushes()

    def journal_rows(self, table):
        with closing(sqlite3.connect(self.root / "live.sqlite3")) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT * FROM " + table)]

    def use_model(self, model):
        self.model = model
        self.runtime.dialogue.backend = model
        self.runtime.arbiter.backend = model

    async def test_native_transcript_replay_and_classic_live_context_round_trip(self):
        self.store.enable(("discord", "123"))
        self.store.put(("discord", "123"), kind="ordinary", scope="discord:100",
                       summary="Alice prépare un roman de fantasy.", significance="Projet d'Alice.")
        self.store.put_self_core(OWNER, summary="Jade a rencontré Alice pendant un atelier.",
                                 significance="Un épisode choisi par Jade.")
        seeded = await self.bridge.prepare_context("Goldaj", self.ctx["thread_id"])
        self.assertIn("personnalité approuvée", seeded["instructions"])
        self.assertNotIn("[INTENT:", seeded["instructions"])
        self.assertIn("Alice", str(seeded["input"]))
        user_event = await self.transcript("user", "Notre héroïne s'appelle Hana.")
        await self.bridge.handle_event(user_event, self.ctx, self.send)
        await self.transcript("assistant", "Elle découvre une forêt.", 1200, 1800)
        self.assertEqual(self.model.requests, [])
        await self.close_and_flush("off")
        await self.bridge.close_session(self.ctx, "off")
        history = self.store.recent_conversation_turns(OWNER, "person")
        self.assertEqual(len(history), 2)
        self.assertIn("Hana", history[0]["content"])
        self.assertIn("interrompue", history[1]["content"])
        message = Incoming("mobile", "Goldaj", "Que fait Hana ensuite ?",
                           channel=self.ctx["thread_id"], message_id="written-1", force_reply=True)
        result = asyncio.get_running_loop().create_future()
        await self.runtime.submit(message, result=result)
        await result
        await self.runtime.idle()
        self.assertIn("Hana", str(self.model.requests[0]))
        again = await self.bridge.prepare_context("Goldaj", self.ctx["thread_id"])
        self.assertIn("Que fait Hana ensuite", str(again["input"]))
        self.assertEqual(len(self.classic), 1)
        self.assertEqual(len(self.journal_rows("live_events")), 2)

    async def test_late_cache_invalidation_loads_inside_dialogue_lock(self):
        await self.bridge.prepare_context("Goldaj", self.ctx["thread_id"])
        incoming = Incoming("mobile", "Goldaj", "Continue.", channel=self.ctx["thread_id"], force_reply=True)
        prepared = await self.runtime.prepare_turn(incoming)
        await self.transcript("user", "Le nom du royaume est Tsuki.")
        await self.transcript("assistant", "Je garde ce nom en tête.", 1100, 1500)
        await self.close_and_flush("idle")
        await self.runtime.dialogue.respond(incoming, **prepared.dialogue_arguments())
        self.assertIn("Tsuki", str(self.model.requests[-1]))

    async def test_no_persistent_transcript_without_memory(self):
        await self.close_and_flush("off")
        self.runtime.memory_service = None
        self.ctx = dict(self.ctx, session_id="no_memory", generation=2)
        await self.bridge.open_session(self.ctx)
        await self.transcript("user", "Une phrase volatile confidentielle.")
        await self.transcript("assistant", "Un retour volatile.", 1100, 1500)
        await self.close_and_flush("off")
        self.assertFalse(any(row["delta"] for row in self.journal_rows("live_events")))
        self.assertEqual(self.store.recent_conversation_turns(OWNER, "person"), [])
        volatile = self.runtime.dialogue.history[("mobile", self.ctx["thread_id"])]
        self.assertIn("volatile confidentielle", str(volatile))

    async def test_duplicate_payload_conflict_and_two_client_admission(self):
        event = await self.transcript("user", "Une seule demande.", eid="same")
        with self.assertRaises(LiveJournalConflict):
            await self.bridge.handle_event(dict(event, delta="Autre contenu."), self.ctx, self.send)
        await self.close_and_flush("off")
        candidates = [dict(self.ctx, session_id="new_" + str(i), generation=i + 2) for i in range(2)]
        results = await asyncio.gather(*(self.bridge.open_session(ctx) for ctx in candidates), return_exceptions=True)
        self.assertEqual(sum(isinstance(result, LiveJournalConflict) for result in results), 1)
        with self.assertRaises(LiveJournalConflict):
            await self.bridge.open_session(self.ctx)

    async def test_delegation_uses_existing_tools_once_without_second_delivery(self):
        self.runtime.document_service = DocumentService(self.root / "documents", memory_store=self.store,
                                                        access_mode="owner")
        self.runtime.reminder_service = ReminderService(self.root / "reminders.sqlite3")
        searches = []

        class Search:
            name = "fake"
            async def search(self, query, **kwargs):
                searches.append(query)
                return SearchResponse((SearchHit("Source", "https://example.test/source", "Un fait vérifié."),))

        self.runtime.web_service = WebSearchService(Search(), SearchJournal(self.root / "search.jsonl"))
        due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

        async def script(action):
            query = json.dumps({"query": "un fait actuel public", "reason": "Vérifier la demande."})
            await action.web_search(query, call_id="web1")
            await action.web_search(query, call_id="web1")
            doc = json.dumps({"filename": "notes.txt", "content": "Le résultat utile."})
            await action.create_document(doc)
            await action.create_document(doc)
            reminder = json.dumps({"action": "create", "title": "Relire le résultat", "due_at": due, "id": None})
            await action.manage_reminder(reminder)
            await action.manage_reminder(reminder)
            action.used = True
            await action(json.dumps({"kind": "core_relationship", "summary": "Jade a choisi de retenir ce projet.",
                                     "significance": "Décision libre de Jade."}))
            return "[INTENT:excited] Ton document et ton rappel sont prêts."

        self.use_model(ToolModel(script))
        await self.transcript("user", "Recherche ce fait, prépare les notes et un rappel.")
        await self.delegation()
        self.assertEqual(len(self.model.requests), 1)
        self.assertEqual(len(searches), 1)
        self.assertEqual(len(self.runtime.reminder_service.store.list()), 1)
        self.assertEqual(len(list((self.root / "documents").glob("*.bin"))), 1)
        self.assertEqual([row["kind"] for row in self.store.list_for_account(OWNER)], ["core_relationship"])
        self.assertEqual(self.classic, [])
        completed = [event for event in self.published if event["type"] == "live_delegation"][-1]
        self.assertEqual(completed["intent"], "excited")
        self.assertTrue(completed["attachments"][0]["url"].startswith("/api/documents/"))
        self.assertFalse(any("[INTENT" in event.get("content", "") for event in self.sent))
        self.assertEqual(self.settlements[-1][2], {"input_tokens": 120, "output_tokens": 30})
        await self.delegation()  # New event ID, same delegation ID.
        await self.delegation("duplicate_id_for_same_input")
        self.assertEqual(len(self.model.requests), 1)
        # A genuinely repeated user request has new input IDs and remains actionable.
        await self.transcript("user", "Recherche ce fait, prépare les notes et un rappel.", 6000, 7000)
        await self.delegation("second_request", 7000)
        self.assertEqual(len(self.model.requests), 2)
        self.assertEqual(len(self.runtime.reminder_service.store.list()), 2)

    async def test_native_context_reaches_backend_delegation(self):
        await self.transcript("user", "Le personnage se nomme Riku.", 0, 500)
        await self.transcript("assistant", "Riku habite à Kyoto.", 550, 1200)
        await self.transcript("user", "Cherche une idée de voyage pour lui.", 5000, 6500)
        await self.delegation(offset=6500)
        prompt = str(self.model.requests[-1])
        self.assertIn("Riku", prompt)
        self.assertIn("Kyoto", prompt)
        self.assertIn("mobile", prompt)
        self.assertEqual(self.classic, [])
        self.assertEqual(self.store.recent_conversation_turns(OWNER, "person"), [])

    async def test_a_new_question_after_native_reply_does_not_reexecute_previous_request(self):
        await self.transcript("user", "Une première demande.", 0, 500)
        await self.transcript("assistant", "La première demande est terminée.", 600, 1200)
        await self.transcript("user", "Une deuxième demande seulement.", 1300, 1600)
        await self.delegation(offset=1600)
        self.assertIn("deuxième demande", self.model.requests[-1][-1]["content"])
        self.assertNotIn("première demande", self.model.requests[-1][-1]["content"])
        self.assertIn("première demande", str(self.model.requests[-1][:-1]))

    async def test_fragment_catchup_and_no_previous_request_substitution(self):
        entered, fragments_ready = asyncio.Event(), asyncio.Event()
        self.release_events.append(fragments_ready)
        original_request_at = self.bridge._request_at

        async def after_fragments(state, offset):
            entered.set()
            await fragments_ready.wait()
            return await original_request_at(state, offset)

        # The delegation arrives first; both real transcript transactions
        # complete before reconstruction, regardless of the filesystem speed.
        self.bridge._request_at = after_fragments
        try:
            await self.delegation(offset=1500, wait=False)
            await asyncio.wait_for(entered.wait(), 3)
            await self.transcript("user", "Prépare ", 1000, 1250)
            await self.transcript("user", "un document.", 1250, 1500)
            fragments_ready.set()
            await self.finish_tasks()
        finally:
            fragments_ready.set()
            self.bridge._request_at = original_request_at
        self.assertIn("Prépare un document.", str(self.model.requests[-1]))
        await self.delegation("missing", offset=20000)
        self.assertEqual(len(self.model.requests), 1)
        self.assertIn("préciser", self.sent[-1]["content"])

    async def test_long_request_is_not_silently_truncated(self):
        await self.transcript("user", "question " * 600, 0, 1200)
        await self.delegation(offset=1200)
        self.assertEqual(self.model.requests, [])
        self.assertEqual(self.reservations, [])
        await self.close_and_flush("off")
        history = self.store.recent_conversation_turns(OWNER, "person")
        retained = "".join(entry["content"].removeprefix("Goldaj (mobile): ")
                           for entry in history if entry["role"] == "user")
        self.assertEqual(retained, "question " * 600)

    async def test_budget_refuses_backend_without_classic_fallback(self):
        self.allowed = False
        await self.transcript("user", "Peux-tu chercher cette information ?")
        await self.delegation()
        self.assertEqual(self.model.requests, [])
        self.assertEqual(self.classic, [])
        self.assertIn("budget", self.sent[-1]["content"])

    async def test_explicit_owner_l2_stays_deferred_and_core_stays_voluntary(self):
        await self.transcript("user", "Jade, retiens que nous avons finalisé le prototype.")
        await self.delegation()
        writes = tuple(self.memory._explicit_writes)
        if writes:
            await asyncio.gather(*writes)
        self.assertEqual(self.model.requests, [])
        self.assertEqual([row["kind"] for row in self.store.list_for_account(OWNER)], ["ordinary"])
        await self.transcript("user", "Jade, garde cette discussion dans tes Core Memories.", 6000, 7000)
        await self.delegation("core_proposal", 7000)
        self.assertEqual(len(self.model.requests), 1)
        self.assertEqual([row["kind"] for row in self.store.list_for_account(OWNER)], ["ordinary"])

    async def test_close_does_not_wait_for_cancel_ignoring_backend_or_emit_late_reply(self):
        entered, release = asyncio.Event(), asyncio.Event()
        self.release_events.append(release)

        class Slow(Model):
            async def complete(self, messages):
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                return "[INTENT:neutral] Résultat trop tardif."

        self.use_model(Slow())
        await self.transcript("user", "Une action longue.")
        await self.delegation(wait=False)
        await asyncio.wait_for(entered.wait(), 1)
        await asyncio.wait_for(self.bridge.close_session(self.ctx, "kill"), .6)
        release.set()
        await self.runtime.idle()
        await self.finish_flushes()
        self.assertFalse(any("trop tardif" in event.get("content", "") for event in self.sent))
        self.assertEqual(self.classic, [])
        self.assertIn("Une action longue", str(self.store.recent_conversation_turns(OWNER, "person")))
        self.assertTrue(any(row["state"] == "unknown" for row in self.journal_rows("live_operations")))

    async def test_playback_without_timeline_never_claims_full_delivery(self):
        await self.transcript("assistant", "Un texte reçu.", 100, 900)
        await self.bridge.observe_playback(self.ctx, {"state": "playing", "offset_ms": 900})
        await self.bridge.observe_playback(self.ctx, {"state": "drained"})
        self.assertEqual(self.published[-1]["segments"][0]["playback"], "playing")
        await self.bridge.observe_playback(self.ctx, {"state": "drained", "offset_ms": 900})
        await self.bridge.observe_playback(self.ctx, {"state": "interrupted", "offset_ms": 1500})
        self.assertEqual(self.published[-1]["segments"][0]["playback"], "drained")

    async def test_metadata_fragments_are_never_visible(self):
        await self.transcript("assistant", "[INTENT:cu", 100, 200)
        self.assertEqual(self.published[-1]["segments"], [])
        await self.transcript("assistant", "rious] Bonjour.", 200, 500)
        self.assertEqual(self.published[-1]["segments"][0]["text"], "Bonjour.")

    async def test_crash_recovery_keeps_input_and_never_repeats_unknown_effect(self):
        await self.transcript("user", "À conserver après une interruption du serveur.")
        context = next(iter(self.bridge.sessions.values())).context
        self.bridge.journal.claim(context, "operation-crashed", "reminder", "same-arguments")
        recovered = LiveConversationBridge(self.runtime, journal_path=self.root / "live.sqlite3")
        try:
            await recovered.prepare_context("Goldaj", self.ctx["thread_id"])
            self.assertIn("interruption du serveur", str(self.store.recent_conversation_turns(OWNER, "person")))
            state, _ = recovered.journal.claim(context, "operation-crashed", "reminder", "same-arguments")
            self.assertEqual(state, "unknown")
            with self.assertRaises(LiveJournalConflict):
                recovered.journal.claim(context, "operation-crashed", "reminder", "different-arguments")
            await recovered.prepare_context("Goldaj", self.ctx["thread_id"])
            self.assertEqual(len(self.store.recent_conversation_turns(OWNER, "person")), 2)
        finally:
            await recovered.close()

    async def test_profile_replacement_cannot_receive_old_session(self):
        old_person = self.store.account(OWNER)
        await self.transcript("user", "Le contexte de mon ancien profil.")
        with self.store._db() as db:
            db.execute("DELETE FROM identities WHERE platform=? AND account_id=?", OWNER)
        self.store.enable(OWNER)
        self.assertNotEqual(self.store.account(OWNER), old_person)
        await self.close_and_flush("off")
        self.assertEqual(self.store.recent_conversation_turns(OWNER, "person"), [])
        self.assertFalse(any(row["delta"] for row in self.journal_rows("live_events")))
        self.assertFalse(self.store.append_conversation_turn(OWNER, "person", source_platform="mobile",
            message_id="old-session", user_content="ancien", assistant_content="ancien",
            expected_person_id=old_person))

    async def test_curation_is_durable_unique_budgeted_and_only_on_active_session(self):
        self.memory.curator_enabled = True
        curator = Model()
        curator.answer = '{"kind":"ordinary","summary":"Le projet de roman avance.","significance":"Projet choisi."}'
        self.memory.backend = curator
        await self.transcript("user", "Nous avons avancé sur le roman et son univers.")
        await self.transcript("assistant", "Nous avons choisi une nouvelle direction.", 1100, 1600)
        await self.close_and_flush("kill")
        self.assertEqual(curator.requests, [])
        self.assertEqual(self.journal_rows("live_curations")[0]["state"], "pending")
        self.ctx = dict(self.ctx, session_id="next_session", generation=2)
        await self.bridge.open_session(self.ctx)
        await self.finish_tasks()
        self.assertEqual(len(curator.requests), 1)
        self.assertEqual(self.journal_rows("live_curations")[0]["state"], "committed")
        self.assertTrue(self.reservations[-1].startswith("curation-"))
        self.assertEqual(self.settlements[-1][3], "completed")
        self.assertEqual(len(self.store.list_for_account(OWNER)), 1)
        await self.close_and_flush("off")
        self.ctx = dict(self.ctx, session_id="third_session", generation=3)
        await self.bridge.open_session(self.ctx)
        await self.finish_tasks()
        self.assertEqual(len(curator.requests), 1)

    async def test_deferred_memory_write_is_not_a_voice_confirmation_barrier(self):
        release, entered = asyncio.Event(), asyncio.Event()
        self.release_events.append(release)
        original = self.memory._execute_memory_action

        async def delayed(*args, **kwargs):
            entered.set()
            await release.wait()
            return await original(*args, **kwargs)

        self.memory._execute_memory_action = delayed
        writer = object.__new__(ResponsesChat)
        writer._closing = False
        writer._pending_writes = set()
        self.deferred_writers.append(writer)

        async def script(action):
            accepted = writer._queue_memory_write(action, json.dumps({
                "kind": "ordinary", "summary": "Jade choisit une écriture différée.",
                "significance": "Politique existante."}), call_id="deferred-memory")
            self.assertTrue(accepted)
            return "[INTENT:neutral] C'est enregistré dans ma mémoire."

        self.use_model(ToolModel(script))
        await self.transcript("user", "Nous avons une idée utile pour le projet.")
        await self.delegation()
        await asyncio.wait_for(entered.wait(), 1)
        self.assertEqual(self.store.list_for_account(OWNER), [])
        self.assertTrue(any("C'est enregistré" in event.get("content", "") for event in self.sent))
        await self.bridge.close_session(self.ctx, "off")
        release.set()
        if writer._pending_writes:
            await asyncio.gather(*writer._pending_writes)
        await self.finish_flushes()
        self.assertEqual(len(self.store.list_for_account(OWNER)), 1)
        self.assertEqual(self.journal_rows("live_curations"), [])

    async def test_classic_discord_and_live_delegations_share_worker_without_holding_session(self):
        entered, release = asyncio.Event(), asyncio.Event()
        self.release_events.append(release)
        active = 0
        maximum = 0

        class Serial(Model):
            async def complete(model, messages):
                nonlocal active, maximum
                model.requests.append(messages)
                active += 1
                maximum = max(maximum, active)
                try:
                    if "bloquant" in messages[-1]["content"]:
                        entered.set()
                        await release.wait()
                    return "[INTENT:neutral] Réponse unique."
                finally:
                    active -= 1

        self.use_model(Serial())
        incoming = Incoming("discord", "Alice", "message bloquant", channel="100",
                            account_id="123", message_id="discord-first", force_reply=True)
        await self.runtime.submit(incoming)
        await asyncio.wait_for(entered.wait(), 1)
        await self.transcript("user", "Une demande depuis le téléphone.")
        await self.transcript("assistant", "Je t'écoute.", 1050, 1400)
        self.assertTrue(self.published[-1]["segments"])
        await self.delegation(wait=False)
        await asyncio.sleep(.01)
        self.assertEqual(len(self.model.requests), 1)
        release.set()
        await self.finish_tasks()
        await self.runtime.idle()
        self.assertEqual(maximum, 1)
        self.assertEqual([reply.source.platform for reply in self.classic], ["discord"])
        self.assertEqual(len(self.model.requests), 2)
        self.assertTrue(all(event["session_id"] == self.ctx["session_id"] for event in self.published))

    async def test_context_limits_do_not_shorten_durable_history(self):
        for index in range(25):
            self.store.append_conversation_turn(OWNER, "person", source_platform="mobile",
                message_id="old-" + str(index), user_content="Question " + "é" * 1800,
                assistant_content="Réponse " + "à" * 1800)
        seeded = await self.bridge.prepare_context("Goldaj", self.ctx["thread_id"])
        self.assertLessEqual(len(seeded["input"]), 128)
        upper_bound = sum(len(item["content"][0]["text"].encode("utf-8")) + 24
                          for item in seeded["input"])
        self.assertLessEqual(upper_bound, 8192)
        self.assertLessEqual(len(seeded["instructions"].encode("utf-8")) + 128, 16384)
        self.assertEqual(len(self.store.recent_conversation_turns(OWNER, "person")), 50)
        self.assertTrue(all(item["role"] in ("user", "assistant", "developer") for item in seeded["input"]))
        self.assertEqual(self.model.requests, [])


if __name__ == "__main__":
    unittest.main()
