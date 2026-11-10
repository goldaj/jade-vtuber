"""Windows demo: real OpenAI conversation alongside an animated Live2D window.

The entered API key remains in process memory and is never passed to the
renderer or written to disk. Nothing connects until the user sends a message.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, ttk

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from demo.reelle.session import DemoSession

EXPRESSIONS = {"Neutre": "Neutral", "Sourire": "Smile", "Tristesse": "Sad", "Colère": "Angry",
               "Surprise": "Surprised", "Cligner": "Blink", "Clin gauche": "WinkL",
               "Clin droit": "WinkR"}

def demo_prompt() -> str:
    """Use Jade's tracked persona, adding only the demo's visitor context."""
    path = (Path(sys._MEIPASS) / "assets" / "prompt_chat.txt"
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2] / "prompt_chat.txt")
    text = path.read_text(encoding="utf-8").strip()
    if not text or len(text) > 20_000:
        raise ValueError("Personnalité Jade absente ou invalide")
    return text + "\nLa personne de cette démo est un visiteur, pas nécessairement ton créateur."


def asset_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / "model"
    return (Path(__file__).resolve().parents[2] / "jade-modeling" /
            "runtime-installed" / "Jade_professional_r20_idle_complete")


def renderer_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).parent / "renderer" / "Jade-renderer.exe"), "--renderer"]
    return [sys.executable, str(Path(__file__).resolve()), "--renderer"]


def launch_renderer():
    sensitive = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY", re.I)
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(("OPENAI_", "JADE_", "DISCORD_", "TWITCH_"))
           and not sensitive.search(key)
           and key.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                                   "PYTHONPATH", "PYTHONHOME"}}
    # No console window, no credentials, and no unbounded stdout/stderr pipes.
    return subprocess.Popen(renderer_command(), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class AsyncSession:
    """Own one event loop on a worker thread; never block the Tk event loop."""

    def __init__(self, key, notify):
        self.loop = asyncio.new_event_loop()
        self.session = None
        self._closing = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.ready = asyncio.run_coroutine_threadsafe(self._initialize(key, notify), self.loop)

    async def _initialize(self, key, notify):
        if self._closing.is_set():
            return False
        session = DemoSession(key, demo_prompt(), notify)
        self.session = session
        if self._closing.is_set():
            try:
                await session.close()
            finally:
                self.session = None
            return False
        return True

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
        self.loop.close()

    def submit(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def cancel(self):
        def request():
            if self.session is not None:
                self.session.cancel()
        try:
            if not self.loop.is_closed():
                self.loop.call_soon_threadsafe(request)
        except RuntimeError:
            pass

    def close(self):
        """Request cleanup without blocking Tk, including during initialization."""
        if self._closing.is_set():
            return
        self._closing.set()

        async def shutdown():
            try:
                try:
                    await asyncio.wrap_future(self.ready)
                except (Exception, asyncio.CancelledError):
                    pass
                if self.session is not None:
                    await self.session.close()
            except Exception:
                pass
            finally:
                self.session = None
                self.loop.call_soon(self.loop.stop)

        coroutine = shutdown()
        try:
            asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        except RuntimeError:
            coroutine.close()


class DemoApp:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue(maxsize=64)
        self.level_lock = threading.Lock()
        self.latest_level = None
        self.worker = None
        self.renderer = None
        self.renderer_started_at = None
        self.renderer_slow_reported = False
        self.renderer_messages = queue.Queue(maxsize=1)
        self.renderer_ready = threading.Event()
        self.session_ready = False
        self.busy = False
        self.closed = False
        self.error_visible = False
        root.title("Jade — démo animée")
        root.geometry("660x720")
        root.minsize(540, 560)
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)
        ttk.Label(frame, text="JADE", font=("Segoe UI", 22, "bold")).grid(row=0, sticky="w")
        ttk.Label(frame, text="Personnage Live2D r20 · dialogue et voix OpenAI",
                  wraplength=600).grid(row=1, sticky="w", pady=(2, 12))
        ttk.Label(frame, text=("Votre clé OpenAI est gardée en mémoire pour cette session ; "
                               "les appels sont facturés sur votre compte. "
                               "Ne communiquez jamais votre clé à une autre personne."),
                  wraplength=600).grid(row=2, sticky="w")
        credentials = ttk.Frame(frame)
        credentials.grid(row=3, sticky="ew", pady=10)
        credentials.columnconfigure(1, weight=1)
        ttk.Label(credentials, text="Clé API OpenAI").grid(row=0, column=0, padx=(0, 8))
        self.key = ttk.Entry(credentials, show="•")
        self.key.grid(row=0, column=1, sticky="ew")
        self.connect = ttk.Button(credentials, text="Commencer", command=self.start_session)
        self.connect.grid(row=0, column=2, padx=(8, 0))
        self.transcript = scrolledtext.ScrolledText(frame, state="disabled", wrap="word")
        self.transcript.grid(row=4, sticky="nsew")
        self.append("Jade", "Bonjour ! Saisissez votre clé puis écrivez-moi un message.")
        self.message = ttk.Entry(frame)
        self.message.grid(row=5, sticky="ew", pady=(10, 8))
        self.message.bind("<Return>", self.send)
        controls = ttk.Frame(frame)
        controls.grid(row=6, sticky="ew")
        self.send_button = ttk.Button(controls, text="Envoyer", command=self.send, state="disabled")
        self.send_button.pack(side="left")
        self.mic_button = ttk.Button(controls, text="Parler (3 s)", command=self.record, state="disabled")
        self.mic_button.pack(side="left", padx=8)
        self.stop_button = ttk.Button(controls, text="Arrêter", command=self.cancel, state="disabled")
        self.stop_button.pack(side="left")
        self.expression = ttk.Combobox(controls, values=list(EXPRESSIONS), width=14, state="readonly")
        self.expression.set("Sourire")
        self.expression.pack(side="left", padx=(8, 3))
        ttk.Button(controls, text="Expression", command=self.set_expression).pack(side="left")
        self.status = tk.StringVar(value="En attente de votre clé")
        ttk.Label(frame, textvariable=self.status, wraplength=600).grid(row=7, sticky="w", pady=(12, 0))
        ttk.Label(frame, text="Le micro n’est activé qu’après un clic. La voix est générée par IA.",
                  wraplength=600).grid(row=8, sticky="w", pady=(6, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.start_renderer()
        root.after(40, self.poll)

    def append(self, speaker, text):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{speaker} : {text}\n\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def start_renderer(self):
        try:
            self.renderer = launch_renderer()
            self.renderer_started_at = time.monotonic()
            threading.Thread(target=self._write_renderer, args=(self.renderer,),
                             daemon=True, name="jade-avatar-output").start()
            threading.Thread(target=self._read_renderer, args=(self.renderer,),
                             daemon=True, name="jade-avatar-input").start()
        except OSError:
            self.status.set("Impossible de lancer le modèle animé ; vérifiez OpenGL et relancez Jade.")

    def _read_renderer(self, process):
        if process.stdout is None:
            return
        try:
            while line := process.stdout.readline(4096):
                if line.rstrip(b"\r\n") == b"JADE_AVATAR_READY":
                    self.renderer_ready.set()
        except (OSError, ValueError):
            pass

    def _write_renderer(self, process):
        while process.poll() is None:
            message = self.renderer_messages.get()
            try:
                if process.stdin is None:
                    return
                process.stdin.write((json.dumps(message) + "\n").encode())
                process.stdin.flush()
            except (OSError, ValueError):
                return
            if message.get("type") == "stop":
                return

    def _send_renderer(self, message):
        # Mouth updates may replace each other but cannot discard a pending
        # expression or stop command. The UI never waits for the pipe.
        try:
            existing = self.renderer_messages.get_nowait()
        except queue.Empty:
            existing = None
        if (message.get("type") == "mouth" and existing is not None
                and existing.get("type") != "mouth"):
            message = existing
        try:
            self.renderer_messages.put_nowait(message)
        except queue.Full:
            pass

    def start_session(self):
        key = self.key.get().strip()
        if not key:
            self.status.set("Saisissez votre clé API OpenAI pour commencer.")
            return
        try:
            self.session_ready = False
            self.worker = AsyncSession(key, self.enqueue)
        except Exception:
            self.status.set("Impossible de préparer la session. Vérifiez votre installation.")
            return
        finally:
            self.key.delete(0, "end")
        self.key.configure(state="disabled")
        self.connect.configure(state="disabled")
        self.status.set("Préparation de la session…")
        worker = self.worker
        def initialized(result):
            from demo.reelle.session import DemoEvent
            try:
                ready = result.result()
            except Exception:
                ready = False
            if not self.closed:
                self.enqueue(DemoEvent("session_ready" if ready else "session_failed", ""))
        worker.ready.add_done_callback(initialized)

    def enqueue(self, event):
        if event.kind == "audio_level":
            with self.level_lock:
                self.latest_level = event.value
            return
        try:
            self.events.put_nowait(event)
        except queue.Full:
            try:
                self.events.get_nowait()
                self.events.put_nowait(event)
            except (queue.Empty, queue.Full):
                pass

    def send(self, _event=None):
        if not self.session_ready or self.worker is None or self.worker.session is None or self.busy:
            return
        text = self.message.get().strip()
        if not text or len(text) > 1200:
            self.status.set("Le message doit contenir de 1 à 1 200 caractères.")
            return
        self.message.delete(0, "end")
        self.run_turn(self.worker.session.send_text(text))

    def record(self):
        if self.session_ready and self.worker is not None and self.worker.session is not None and not self.busy:
            self.run_turn(self.worker.session.record_and_reply())

    def run_turn(self, coroutine):
        self.busy = True
        self.send_button.configure(state="disabled")
        self.mic_button.configure(state="disabled")
        future = self.worker.submit(coroutine)
        def done(result):
            try:
                result.result()
            except Exception:
                self.enqueue_text("Une demande est déjà en cours ou a été interrompue.")
                from demo.reelle.session import DemoEvent
                self.enqueue(DemoEvent("state", "idle"))
        future.add_done_callback(done)

    def enqueue_text(self, text):
        from demo.reelle.session import DemoEvent
        self.enqueue(DemoEvent("error", text))

    def cancel(self):
        if self.worker is not None:
            self.worker.cancel()

    def mouth(self, level):
        if self.renderer is None or self.renderer.poll() is not None or self.renderer.stdin is None:
            return
        self._send_renderer({"type": "mouth", "value": level})

    def set_expression(self):
        expression = EXPRESSIONS.get(self.expression.get())
        if expression and self.renderer is not None and self.renderer.poll() is None:
            self._send_renderer({"type": "expression", "value": expression})
        else:
            self.status.set("Le modèle animé est indisponible.")

    def poll(self):
        if self.closed:
            return
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event.kind == "user_text":
                self.append("Vous", str(event.value))
            elif event.kind == "reply_text":
                self.append("Jade", str(event.value))
            elif event.kind == "spoken_text":
                self.append("Jade (voix)", str(event.value))
            elif event.kind == "session_ready":
                self.session_ready = True
                self.send_button.configure(state="normal")
                self.mic_button.configure(state="normal")
                self.stop_button.configure(state="normal")
                self.status.set("Prête — aucun appel n’a encore été effectué")
                self.message.focus_set()
            elif event.kind == "session_failed":
                self.session_ready = False
                if self.worker is not None:
                    self.worker.close()
                    self.worker = None
                self.key.configure(state="normal")
                self.connect.configure(state="normal")
                self.status.set("Impossible de préparer la session. Vérifiez votre installation.")
            elif event.kind == "error":
                self.status.set(str(event.value))
                self.error_visible = True
            elif event.kind == "state":
                names = {"idle": "Prête", "recording": "Micro actif pendant 3 secondes…",
                         "transcribing": "Transcription…", "thinking": "Jade réfléchit…",
                         "synthesizing": "Génération de la voix…", "speaking": "Jade parle…"}
                if event.value != "idle":
                    self.error_visible = False
                if not self.error_visible:
                    self.status.set(names.get(str(event.value), "En cours…"))
                if event.value == "idle":
                    self.busy = False
                    self.send_button.configure(state="normal")
                    self.mic_button.configure(state="normal")
                    self.mouth(0.0)
        with self.level_lock:
            level, self.latest_level = self.latest_level, None
        if level is not None and self.busy:
            self.mouth(level)
        if self.renderer is not None and self.renderer.poll() is not None:
            self.status.set("Le modèle animé s’est fermé ; relancez Jade pour le rouvrir.")
            self.renderer = None
        elif self.renderer is not None and self.renderer_started_at is not None:
            if (not self.renderer_ready.is_set() and not self.renderer_slow_reported
                    and time.monotonic() - self.renderer_started_at >= 15):
                self.status.set("Le modèle animé ne répond pas ; vérifiez OpenGL et relancez Jade.")
                self.renderer_slow_reported = True
            elif self.renderer_ready.is_set() and self.renderer_slow_reported:
                self.status.set("Modèle animé prêt.")
                self.renderer_slow_reported = False
        self.root.after(40, self.poll)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.session_ready = False
        if self.worker is not None:
            self.worker.close()
        if self.renderer is not None:
            try:
                self._send_renderer({"type": "stop"})
                self.renderer.wait(timeout=2)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                self.renderer.terminate()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--renderer", action="store_true")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--dependencies-smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.dependencies_smoke_test:
        import openai
        import sounddevice
        import websockets
        demo_prompt()
        if not openai or not sounddevice or not websockets:
            raise RuntimeError("Dépendance manquante")
        return
    if args.renderer:
        from demo.reelle.avatar import run_renderer
        run_renderer(asset_root(), input_stream=None if args.smoke_test else sys.stdin,
                     hidden=args.smoke_test, max_frames=45 if args.smoke_test else None)
        return
    root = tk.Tk()
    app = DemoApp(root)
    if args.smoke_test:
        root.withdraw()
        try:
            deadline = time.monotonic() + 15
            while not app.renderer_ready.is_set():
                root.update()
                if app.renderer is None or app.renderer.poll() is not None:
                    raise RuntimeError("animated model failed to start")
                if time.monotonic() >= deadline:
                    raise RuntimeError("animated model did not draw a frame")
                time.sleep(0.02)
        finally:
            app.close()
    else:
        root.mainloop()


if __name__ == "__main__":
    main()
