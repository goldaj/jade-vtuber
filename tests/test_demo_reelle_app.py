"""Headless tests for demo UI event handling; no audio, account, or network."""
from concurrent.futures import Future
from io import BytesIO
from pathlib import Path
import queue
import os
import sys
import threading
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

APP_SOURCE = Path(__file__).resolve().parents[1] / "demo/reelle/app.py"
app = None
if APP_SOURCE.is_file():
    try:
        from demo.reelle import app
    except ModuleNotFoundError as exc:
        if exc.name not in {"tkinter", "_tkinter"}:
            raise


@unittest.skipIf(app is None, "real demo or Tk omitted from this export")
class DemoAppTests(unittest.TestCase):
    def test_persona_is_the_project_prompt_with_visitor_context(self):
        source = Path(__file__).resolve().parents[1] / "prompt_chat.txt"
        if not source.is_file():
            self.skipTest("project persona not included in this export")
        actual = source.read_text(encoding="utf-8").strip()
        self.assertTrue(bool(actual))
        prompt = app.demo_prompt()
        self.assertTrue(prompt.startswith(actual + "\n"))
        self.assertIn("visiteur", prompt[len(actual):].casefold())

    def test_absent_or_empty_persona_is_never_replaced_by_a_fallback(self):
        with patch.object(app.Path, "read_text", side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                app.demo_prompt()
        with patch.object(app.Path, "read_text", return_value=" \n"):
            with self.assertRaises(ValueError):
                app.demo_prompt()

    def test_renderer_never_inherits_sensitive_or_proxy_environment(self):
        inherited = {
            "SystemRoot": r"C:\Windows",
            "JADE_SECRETS_FILE": "synthetic",
            "OPENAI_BASE_URL": "synthetic",
            "TWITCH_TOKEN": "synthetic",
            "DISCORD_TOKEN": "synthetic",
            "JADEREVIEW_PASSWORD": "synthetic",
            "SOME_SECRET": "synthetic",
            "CUSTOM_APIKEY": "synthetic",
            "HTTPS_PROXY": "synthetic",
            "http_proxy": "synthetic",
            "PYTHONPATH": "synthetic",
            "PYTHONHOME": "synthetic",
        }
        with patch.dict(os.environ, inherited, clear=True), patch.object(app.subprocess, "Popen") as popen:
            app.launch_renderer()
        passed = {name.upper(): value for name, value in popen.call_args.kwargs["env"].items()}
        self.assertEqual(passed, {"SYSTEMROOT": r"C:\Windows"})

    def make_app(self):
        instance = app.DemoApp.__new__(app.DemoApp)
        instance.events = queue.Queue(maxsize=64)
        instance.level_lock = threading.Lock()
        instance.latest_level = None
        instance.renderer_ready = threading.Event()
        instance.renderer_started_at = None
        instance.renderer_slow_reported = False
        instance.renderer_messages = queue.Queue(maxsize=1)
        instance.session_ready = True
        instance.busy = False
        instance.closed = False
        instance.error_visible = False
        instance.root = MagicMock()
        instance.renderer = None
        instance.send_button = MagicMock()
        instance.mic_button = MagicMock()
        instance.stop_button = MagicMock()
        instance.key = MagicMock()
        instance.connect = MagicMock()
        instance.message = MagicMock()
        instance.expression = MagicMock()
        instance.status = MagicMock()
        instance.worker = MagicMock()
        instance.append = MagicMock()
        instance.mouth = MagicMock()
        return instance

    def test_expression_selection_sends_expected_model_commands(self):
        instance = self.make_app()
        instance.renderer = MagicMock()
        instance.renderer.poll.return_value = None
        expected = {"Neutre": "Neutral", "Sourire": "Smile", "Tristesse": "Sad",
                    "Colère": "Angry", "Surprise": "Surprised", "Cligner": "Blink",
                    "Clin gauche": "WinkL", "Clin droit": "WinkR"}
        for label, value in expected.items():
            instance.expression.get.return_value = label
            instance.set_expression()
            self.assertEqual(instance.renderer_messages.get_nowait(),
                             {"type": "expression", "value": value})
        instance.expression.get.return_value = "non autorisé"
        instance.set_expression()
        self.assertTrue(instance.renderer_messages.empty())

    def test_pending_expression_and_stop_cannot_be_overwritten_by_mouth(self):
        instance = self.make_app()
        expression = {"type": "expression", "value": "Smile"}
        instance._send_renderer(expression)
        for value in range(100):
            instance._send_renderer({"type": "mouth", "value": value / 100})
        self.assertEqual(instance.renderer_messages.get_nowait(), expression)
        stop = {"type": "stop"}
        instance._send_renderer(stop)
        instance._send_renderer({"type": "mouth", "value": 0.7})
        self.assertEqual(instance.renderer_messages.get_nowait(), stop)

    def test_session_creation_never_blocks_and_close_during_init_cleans_up(self):
        entered, release = threading.Event(), threading.Event()
        created = MagicMock()
        created.close = AsyncMock()
        def create(*args):
            entered.set()
            if not release.wait(2):
                raise TimeoutError("test initialization timed out")
            return created
        with patch.object(app, "DemoSession", side_effect=create):
            start = time.monotonic()
            worker = app.AsyncSession("synthetic", lambda event: None)
            self.assertLess(time.monotonic() - start, 1)
            try:
                self.assertTrue(entered.wait(1))
                self.assertFalse(worker.ready.done())
                start = time.monotonic()
                worker.close()
                self.assertLess(time.monotonic() - start, 1)
            finally:
                release.set()
                worker.thread.join(3)
            self.assertFalse(worker.thread.is_alive())
            created.close.assert_awaited_once()
            self.assertIsNone(worker.session)

    def test_session_buttons_enable_only_after_success(self):
        instance = self.make_app()
        instance.key.get.return_value = "synthetic-key"
        worker = MagicMock()
        worker.ready = Future()
        with patch.object(app, "AsyncSession", return_value=worker):
            instance.start_session()
        instance.key.delete.assert_called_once()
        instance.send_button.configure.assert_not_called()
        instance.status.set.assert_called_with("Préparation de la session…")
        worker.ready.set_result(True)
        instance.poll()
        instance.send_button.configure.assert_called_with(state="normal")
        instance.mic_button.configure.assert_called_with(state="normal")
        instance.status.set.assert_called_with("Prête — aucun appel n’a encore été effectué")

    def test_session_initialization_failure_restores_key_entry_without_details(self):
        instance = self.make_app()
        instance.key.get.return_value = "synthetic-key"
        worker = MagicMock()
        worker.ready = Future()
        with patch.object(app, "AsyncSession", return_value=worker):
            instance.start_session()
        worker.ready.set_exception(RuntimeError("private diagnostic"))
        instance.poll()
        worker.close.assert_called_once()
        self.assertIsNone(instance.worker)
        instance.key.configure.assert_called_with(state="normal")
        instance.connect.configure.assert_called_with(state="normal")
        self.assertNotIn("private diagnostic", repr(instance.status.set.call_args_list))

    def test_closed_window_ignores_late_initialization_result(self):
        instance = self.make_app()
        instance.key.get.return_value = "synthetic-key"
        worker = MagicMock()
        worker.ready = Future()
        with patch.object(app, "AsyncSession", return_value=worker):
            instance.start_session()
        instance.closed = True
        worker.ready.set_result(True)
        self.assertTrue(instance.events.empty())
        instance.send_button.configure.assert_not_called()

    def test_renderer_ready_requires_complete_exact_line(self):
        instance = self.make_app()
        process = MagicMock()
        process.stdout = BytesIO(b"noise\nNOT_JADE_AVATAR_READY\n")
        instance._read_renderer(process)
        self.assertFalse(instance.renderer_ready.is_set())
        process.stdout = BytesIO(b"noise\r\nJADE_AVATAR_READY\r\n")
        instance._read_renderer(process)
        self.assertTrue(instance.renderer_ready.is_set())

    def test_renderer_stall_and_late_recovery_are_reported_once(self):
        instance = self.make_app()
        instance.renderer = MagicMock()
        instance.renderer.poll.return_value = None
        instance.renderer_started_at = 100.0
        with patch.object(app.time, "monotonic", return_value=114.9):
            instance.poll()
        instance.status.set.assert_not_called()
        with patch.object(app.time, "monotonic", return_value=115.0):
            instance.poll()
            instance.poll()
        instance.status.set.assert_called_once_with(
            "Le modèle animé ne répond pas ; vérifiez OpenGL et relancez Jade.")
        instance.renderer_ready.set()
        with patch.object(app.time, "monotonic", return_value=116.0):
            instance.poll()
        instance.status.set.assert_called_with("Modèle animé prêt.")
        self.assertFalse(instance.renderer_slow_reported)

    def test_audio_updates_are_coalesced_without_losing_error_or_idle(self):
        from demo.reelle.session import DemoEvent
        instance = self.make_app()
        instance.busy = True
        for value in range(1000):
            instance.enqueue(DemoEvent("audio_level", value / 1000))
        instance.enqueue(DemoEvent("error", "Problème de réseau"))
        instance.enqueue(DemoEvent("state", "idle"))
        self.assertEqual(instance.events.qsize(), 2)
        instance.poll()
        self.assertFalse(instance.busy)
        instance.status.set.assert_called_with("Problème de réseau")
        instance.send_button.configure.assert_called_with(state="normal")
        instance.mic_button.configure.assert_called_with(state="normal")
        instance.mouth.assert_called_with(0.0)

    def test_send_is_ignored_while_busy_without_erasing_input(self):
        instance = self.make_app()
        instance.busy = True
        instance.message.get.return_value = "Message à préserver"
        instance.send()
        instance.message.delete.assert_not_called()
        instance.worker.session.send_text.assert_not_called()

    def test_enter_during_initialization_preserves_input_without_starting_turn(self):
        instance = self.make_app()
        instance.worker.session = None
        instance.session_ready = False
        instance.message.get.return_value = "Message à préserver"
        instance.send()
        instance.record()
        instance.message.delete.assert_not_called()
        instance.worker.submit.assert_not_called()

    def test_enter_before_ready_event_cannot_start_a_request(self):
        instance = self.make_app()
        instance.session_ready = False
        # The worker has finished constructing a session, but Tk has not yet
        # processed its readiness event; Enter must still be ignored.
        instance.worker.session = MagicMock()
        instance.message.get.return_value = "Message à préserver"
        instance.send()
        instance.record()
        instance.message.delete.assert_not_called()
        instance.worker.submit.assert_not_called()

    def test_interrupted_turn_reenables_buttons_and_preserves_error(self):
        instance = self.make_app()
        future = Future()
        instance.worker.submit.return_value = future
        instance.run_turn(object())
        self.assertTrue(instance.busy)
        instance.send_button.configure.assert_called_with(state="disabled")
        future.set_exception(RuntimeError("private error details"))
        instance.poll()
        self.assertFalse(instance.busy)
        instance.status.set.assert_called_with("Une demande est déjà en cours ou a été interrompue.")
        self.assertNotIn("private error details", repr(instance.status.set.call_args_list))
        instance.send_button.configure.assert_called_with(state="normal")

    def test_smoke_rejects_renderer_alive_without_ready(self):
        window = MagicMock()
        instance = MagicMock()
        instance.renderer_ready.is_set.return_value = False
        instance.renderer.poll.return_value = None
        with patch.object(sys, "argv", ["Jade", "--smoke-test"]), \
             patch.object(app.tk, "Tk", return_value=window), \
             patch.object(app, "DemoApp", return_value=instance), \
             patch.object(app.time, "monotonic", side_effect=[0, 16]):
            with self.assertRaisesRegex(RuntimeError, "did not draw a frame"):
                app.main()
        instance.close.assert_called_once()

    def test_smoke_accepts_ready_frame_and_closes(self):
        window = MagicMock()
        instance = MagicMock()
        instance.renderer_ready.is_set.side_effect = [False, True]
        instance.renderer.poll.return_value = None
        with patch.object(sys, "argv", ["Jade", "--smoke-test"]), \
             patch.object(app.tk, "Tk", return_value=window), \
             patch.object(app, "DemoApp", return_value=instance), \
             patch.object(app.time, "monotonic", side_effect=[0, 1]), \
             patch.object(app.time, "sleep"):
            app.main()
        instance.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
