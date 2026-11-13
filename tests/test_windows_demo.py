"""Checks the offline demo's real dialogue path and packaged assets."""
import asyncio
import importlib.util
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from src.jade_runtime.dialogue import Dialogue
from src.jade_runtime.messages import Incoming

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "demo/windows/jade_demo.py"
demo = None
if DEMO_PATH.is_file():
    try:
        SPEC = importlib.util.spec_from_file_location("jade_windows_demo", DEMO_PATH)
        demo = importlib.util.module_from_spec(SPEC)
        SPEC.loader.exec_module(demo)
    except ModuleNotFoundError as exc:
        if exc.name not in {"tkinter", "_tkinter"}:
            raise
        demo = None


@unittest.skipIf(demo is None, "graphical demo or Tk unavailable in this checkout")
class WindowsDemoTests(unittest.TestCase):
    def test_portrait_is_materialized_png(self):
        if not demo.portrait_path().is_file():
            self.skipTest("portrait omitted from this checkout")
        with demo.portrait_path().open("rb") as stream:
            signature = stream.read(8)
        if signature == b"version ":
            self.skipTest("Git LFS portrait not downloaded")
        self.assertEqual(signature, b"\x89PNG\r\n\x1a\n")

    def test_dialogue_uses_offline_simulation_and_keeps_unicode(self):
        async def run():
            dialogue = Dialogue(demo.DemoChat(), "Demo")
            message = Incoming("demo", "Visiteur", "Bonjour Jade, ça va ?", force_reply=True)
            first = await dialogue.respond(message)
            second = await dialogue.respond(message)
            self.assertEqual(first.text, "Mode démo : Bonjour Jade, ça va ?")
            self.assertEqual(second.text, first.text)

        loop = asyncio.new_event_loop()
        try:
            with patch.object(socket.socket, "connect", side_effect=AssertionError("Network is forbidden")):
                loop.run_until_complete(run())
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
