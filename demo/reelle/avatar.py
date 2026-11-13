"""Standalone r20 Live2D window for the Windows demo.

Run on the main thread of a child process. The parent sends one JSON object per
line on stdin: {"type":"mouth","value":0.0..1.0},
{"type":"expression","value":"Smile"} or {"type":"stop"}. No API key,
transcript or audio is needed here. The original model is read-only.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import threading
import time

EXPRESSIONS = ("Smile", "Sad", "Angry", "Surprised", "Blink", "WinkL", "WinkR")
NEUTRAL_EXPRESSION = "Neutral"


class AvatarControls:
    """Latest-value mailbox; audio callbacks cannot accumulate an unbounded queue."""

    def __init__(self):
        self._lock = threading.Lock()
        self._level = 0.0
        self._updated = 0.0
        self._expression = None
        self.stopped = threading.Event()

    def accept(self, line: str) -> bool:
        if not isinstance(line, str) or len(line) > 1024:
            return False
        try:
            message = json.loads(line)
        except (ValueError, TypeError):
            return False
        if not isinstance(message, dict):
            return False
        if message.get("type") == "stop":
            self.stopped.set()
            return True
        value = message.get("value")
        if message.get("type") == "expression":
            if not isinstance(value, str) or value not in (*EXPRESSIONS, NEUTRAL_EXPRESSION):
                return False
            with self._lock:
                self._expression = value
            return True
        if (message.get("type") != "mouth" or type(value) not in (int, float)
                or not 0 <= value <= 1 or not math.isfinite(value)):
            return False
        with self._lock:
            self._level = float(value)
            self._updated = time.monotonic()
        return True

    def level(self, *, now=None) -> float:
        at = time.monotonic() if now is None else now
        with self._lock:
            # Return to rest if a parent or its audio thread disappears.
            return self._level if at - self._updated <= 0.5 else 0.0

    def take_expression(self) -> str | None:
        """Read and clear the latest requested expression without queue growth."""
        with self._lock:
            value, self._expression = self._expression, None
            return value


def _apply_expression(model, expression: str) -> None:
    """Replace the active expression; neutral resets all expression overlays."""
    if expression not in (*EXPRESSIONS, NEUTRAL_EXPRESSION):
        raise ValueError("Expression inconnue")
    model.ResetExpressions()
    if expression != NEUTRAL_EXPRESSION:
        model.SetExpression(expression)


def _read_commands(stream, controls: AvatarControls) -> None:
    if stream is None:
        controls.stopped.set()
        return
    try:
        while not controls.stopped.is_set():
            line = stream.readline(1025)
            if not line:
                break
            if len(line) > 1024 or not line.endswith("\n"):
                # Discard oversized/partial records; never parse their suffix.
                while line and not line.endswith("\n"):
                    line = stream.readline(1025)
                continue
            controls.accept(line)
    except (OSError, ValueError, UnicodeError):
        pass
    finally:
        controls.stopped.set()


def run_renderer(model_dir: Path | str, *, input_stream=None, hidden=False,
                 max_frames=None) -> None:
    """Display the actual r20 model, looping its idle and applying mouth levels.

    `hidden`/`max_frames` are for automated rendering checks, not a visual QA.
    `input_stream` must provide newline-delimited JSON in normal operation.
    Raises on missing files, graphics initialization or model-loading failure.
    """
    import pygame
    import live2d

    model_dir = Path(model_dir).resolve()
    model_path = model_dir / "Jade.model3.json"
    motion_path = model_dir / "Jade_idle.motion3.json"
    if not model_path.is_file() or not motion_path.is_file():
        raise FileNotFoundError("Ressources du modèle Jade absentes")
    if max_frames is not None and (type(max_frames) is not int or not 1 <= max_frames <= 10000):
        raise ValueError("invalid frame limit")
    controls = AvatarControls()
    if input_stream is not None:
        threading.Thread(target=_read_commands, args=(input_stream, controls),
                         name="jade-avatar-control", daemon=True).start()
    elif max_frames is None:
        raise ValueError("avatar control stream required")

    model = None
    initialized = False
    try:
        pygame.display.init()
        live2d.init()
        initialized = True
        flags = pygame.DOUBLEBUF | pygame.OPENGL
        if hidden:
            flags |= pygame.HIDDEN
        pygame.display.set_caption("Jade — modèle animé r20")
        pygame.display.set_mode((640, 700), flags)
        live2d.glInit()
        model = live2d.Model()
        model.LoadModelJson(str(model_path))
        model.Resize(640, 700)
        if "ParamMouthOpenY" not in model.GetParamIds():
            raise ValueError("Paramètre de bouche absent du modèle")
        if not set(EXPRESSIONS).issubset(model.GetExpressions()):
            raise ValueError("Expressions attendues absentes du modèle")
        model.SetAutoBlink(True)
        model.SetAutoBreath(True)
        index = model.LoadExtraMotion("JadeIdle", str(motion_path))
        if type(index) is not int or index < 0:
            raise ValueError("Mouvement d'attente non chargé")
        model.StartMotion("JadeIdle", index, 3)
        clock = pygame.time.Clock()
        mouth = 0.0
        frames = 0
        while not controls.stopped.is_set():
            elapsed = min(clock.tick(60) / 1000.0, 0.1)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    controls.stopped.set()
            if controls.stopped.is_set():
                break
            if model.IsMotionFinished():
                model.StartMotion("JadeIdle", index, 3)
            expression = controls.take_expression()
            if expression is not None:
                _apply_expression(model, expression)
            model.Update(elapsed)
            target = controls.level()
            mouth += (target - mouth) * 0.5
            model.SetParamById("ParamMouthOpenY", mouth)
            live2d.clearBuffer(0.13, 0.16, 0.18, 1.0)
            model.Draw()
            pygame.display.flip()
            frames += 1
            if frames == 1 and sys.stdout is not None:
                print("JADE_AVATAR_READY", flush=True)
            if max_frames is not None and frames >= max_frames:
                break
    finally:
        # Release model before disposing Cubism/OpenGL and destroying its window.
        model = None
        if initialized:
            live2d.dispose()
        pygame.quit()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Jade : modèle Live2D r20")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        run_renderer(args.model_dir, input_stream=None if args.smoke_test else sys.stdin,
                     hidden=args.smoke_test, max_frames=45 if args.smoke_test else None)
    except Exception:
        # Avoid sending file paths or any environment value to the parent UI.
        if sys.stderr is not None:
            print("Impossible de démarrer le modèle animé Jade.", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
