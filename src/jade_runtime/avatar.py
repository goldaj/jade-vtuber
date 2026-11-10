"""Isolated r20 renderer and approximate mouth motion from actual playback."""
import asyncio
import io
import json
import logging
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import wave

LOG = logging.getLogger("jade.avatar")
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "demo/reelle/avatar.py"
MODEL = ROOT / "jade-modeling/runtime-installed/Jade_professional_r20_idle_complete"


def child_environment(environ):
    # Allowlist rather than trying to enumerate every possible secret name.
    allowed = {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP",
               "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH",
               "LANG", "LC_ALL", "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"}
    return {k: v for k, v in environ.items() if k.upper() in allowed}


def levels(wav):
    """Return 40 ms amplitude windows. PCM remains in memory only."""
    if len(wav) > 20_000_000:
        return []
    try:
        with wave.open(io.BytesIO(wav), "rb") as f:
            channels, rate, width = f.getnchannels(), f.getframerate(), f.getsampwidth()
            if channels not in (1, 2) or not 8000 <= rate <= 48000 or width != 2:
                return []
            raw = f.readframes(min(f.getnframes(), rate * 180))
        step = max(1, rate // 25) * channels * 2
        result = []
        for offset in range(0, len(raw) - 1, step):
            chunk = raw[offset:offset + step]
            chunk = chunk[:len(chunk) // 2 * 2]
            samples = struct.unpack(f"<{len(chunk) // 2}h", chunk)
            rms = math.sqrt(sum(s * s for s in samples) / len(samples))
            result.append(min(1.0, rms / 10000))
        return result
    except (ValueError, EOFError, wave.Error, struct.error):
        return []


class Avatar:
    def __init__(self):
        self.process = None
        self._reader = None
        self._writer = None
        self._animation = None
        self._pending = asyncio.Queue(maxsize=1)
        self._active = {}

    async def start(self):
        if not SCRIPT.is_file() or not MODEL.is_dir():
            raise RuntimeError("Modèle r20 ou lanceur absent : utiliser un clone complet de Jade")
        options = dict(stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                       stderr=asyncio.subprocess.DEVNULL, env=child_environment(os.environ))
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, str(SCRIPT), "--model-dir", str(MODEL), **options)
        ready = asyncio.Event()
        signaled_ready = False
        async def read_output():
            nonlocal signaled_ready
            while line := await self.process.stdout.readline():
                if line.strip() == b"JADE_AVATAR_READY":
                    signaled_ready = True
                    ready.set()
            ready.set()
        self._reader = asyncio.create_task(read_output())
        try:
            await asyncio.wait_for(ready.wait(), 20)
            if not signaled_ready or self.process.returncode is not None:
                raise RuntimeError("Impossible de démarrer l’avatar : installer l’extra avatar et vérifier OpenGL")
            self._writer = asyncio.create_task(self._write_loop())
        except BaseException:
            await self.close()
            raise
        return self

    def _offer(self, value):
        if self._pending.full():
            self._pending.get_nowait()
        self._pending.put_nowait(value)

    async def _write_loop(self):
        try:
            while True:
                value = await self._pending.get()
                self.process.stdin.write((json.dumps({"type": "mouth", "value": value}) + "\n").encode())
                await asyncio.wait_for(self.process.stdin.drain(), 1)
        except (BrokenPipeError, ConnectionError, OSError, TimeoutError):
            LOG.warning("Avatar indisponible ; la voix continue sans animation")

    def observer(self, source):
        def notify(event, wav):
            if event == "start":
                self._active[source] = (asyncio.get_running_loop().time(), wav)
                if self._animation is None or self._animation.done():
                    self._animation = asyncio.create_task(self._animate())
            elif event == "end":
                self._active.pop(source, None)
                if not self._active:
                    self._offer(0.0)
        return notify

    async def _animate(self):
        cache = {}
        try:
            while self._active:
                source = "discord" if "discord" in self._active else next(iter(self._active))
                started, wav = self._active[source]
                key = (source, started)
                if key not in cache:
                    cache[key] = await asyncio.to_thread(levels, wav)
                if self._active.get(source, (None,))[0] != started:
                    continue
                windows = cache[key]
                index = int((asyncio.get_running_loop().time() - started) * 25)
                self._offer(windows[index] if index < len(windows) else 0.0)
                await asyncio.sleep(0.04)
        finally:
            self._offer(0.0)

    async def close(self):
        self._active.clear()
        for task in (self._animation, self._writer):
            if task:
                task.cancel()
        await asyncio.gather(*(t for t in (self._animation, self._writer) if t), return_exceptions=True)
        if self.process is not None and self.process.returncode is None:
            try:
                self.process.stdin.write(b'{"type":"stop"}\n')
                await asyncio.wait_for(self.process.stdin.drain(), 0.5)
                await asyncio.wait_for(self.process.wait(), 2)
            except (BrokenPipeError, ConnectionError, OSError, TimeoutError):
                if self.process.returncode is None:
                    self.process.kill()
                    await self.process.wait()
        if self._reader:
            await asyncio.gather(self._reader, return_exceptions=True)
