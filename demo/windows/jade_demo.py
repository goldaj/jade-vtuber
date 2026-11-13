"""A self-contained, offline visual demonstration of Jade's dialogue pipeline."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import tkinter as tk
from tkinter import scrolledtext, ttk

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming

PORTRAIT_NAME = "Jade_r21_master_v3_canvas_3840x4160.png"


def portrait_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets" / PORTRAIT_NAME
    return (Path(__file__).resolve().parents[2] / "jade-modeling" / "assets" /
            "live2d" / "r21_professional_art" / "master_v4_assets_v1" / PORTRAIT_NAME)


class DemoChat:
    """Same intentionally simulated response as the main runtime's demo backend."""

    async def complete(self, messages):
        return "Mode démo : " + messages[-1]["content"].split(": ", 1)[-1][:120]


class DemoWindow:
    def __init__(self, root):
        self.root = root
        self.dialogue = Dialogue(DemoChat(), "Démonstration locale de Jade")
        root.title("Jade — démonstration hors ligne")
        root.geometry("1000x700")
        root.minsize(740, 580)
        container = ttk.Frame(root, padding=14)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(1, weight=1)

        ttk.Label(container, text="JADE  ·  DÉMONSTRATION", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.full_image = tk.PhotoImage(file=str(portrait_path()))
        self.image = self.full_image.subsample(8, 8)
        ttk.Label(container, image=self.image).grid(row=1, column=0, sticky="n", padx=(0, 16))
        right = ttk.Frame(container)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="Portrait statique · aucun service externe", wraplength=420).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        self.transcript = scrolledtext.ScrolledText(right, wrap="word", height=15, state="disabled")
        self.transcript.grid(row=1, column=0, sticky="nsew")
        self.append("Jade", "Bonjour ! Cette réponse est simulée. Écris un message pour essayer.")
        self.entry = ttk.Entry(right)
        self.entry.grid(row=2, column=0, sticky="ew", pady=(12, 6))
        self.entry.bind("<Return>", self.send)
        ttk.Button(right, text="Envoyer", command=self.send).grid(row=3, column=0, sticky="e")
        ttk.Label(right, text="Le mode démo répète votre texte : aucune IA, voix ou animation n’est active.",
                  wraplength=420).grid(row=4, column=0, sticky="w", pady=(16, 0))
        self.entry.focus_set()

    def append(self, speaker, message):
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{speaker} : {message}\n\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def send(self, _event=None):
        text = self.entry.get().strip()
        if not text:
            return
        if len(text) > 1200:
            self.append("Démo", "Le message doit contenir au maximum 1 200 caractères.")
            return
        message = Incoming("demo", "Visiteur", text, force_reply=True)
        reply = asyncio.run(self.dialogue.respond(message))
        self.append("Vous", text)
        self.append("Jade", reply.text)
        self.entry.delete(0, "end")


def main():
    parser = argparse.ArgumentParser(description="Jade : démo locale hors ligne")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = tk.Tk()
    if args.smoke_test:
        root.withdraw()
    window = DemoWindow(root)
    if args.smoke_test:
        window.entry.insert(0, "Bonjour Jade")
        window.send()
        assert "Mode démo : Bonjour Jade" in window.transcript.get("1.0", "end")
        root.update_idletasks()
        root.destroy()
    else:
        root.mainloop()


if __name__ == "__main__":
    main()
