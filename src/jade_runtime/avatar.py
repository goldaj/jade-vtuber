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
    def __init__(self, *, intent_enabled=True):
        self.process = None
        self._reader = None
        self._writer = None
        self._animation = None
        self.intent_enabled = bool(intent_enabled)
        # Two coalesced channels: high-frequency mouth levels cannot evict a
        # low-frequency facial expression, and the child has only ONE writer.
        self._wakeup = asyncio.Event()
        self._pending_mouth = None
        self._pending_expression = None
        self._loop = None
        self._intent_counts = {}
        self._intent_generation = 0
        self._reset_task = None
        self._active = {}

    async def start(self):
        self._loop = asyncio.get_running_loop()
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

    def _queue_mouth(self, value):
        self._pending_mouth = max(0.0, min(1.0, float(value)))
        self._wakeup.set()

    def _offer(self, value):
        # Discord PCM observers may run on the sound thread. Never touch an
        # asyncio Event directly outside the renderer's owning event loop.
        try:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._queue_mouth, value)
            else:
                self._queue_mouth(value)
        except RuntimeError:
            pass  # Loop stopped during shutdown; audio still finishes safely.

    def _queue_expression(self, value):
        self._pending_expression = value
        self._wakeup.set()

    def set_intent(self, label):
        """Show one of two known expressions, including for text-only replies."""
        if not self.intent_enabled:
            return
        from .intent_engine import normalize_intent
        from .intent_visuals import reaction_for_intent
        label = normalize_intent(label)
        index = self._intent_counts.get(label, 0)
        try:
            reaction = reaction_for_intent(label, index)
        except (ValueError, OSError, TypeError, KeyError):
            LOG.warning("Live2D expression palette unavailable")
            return  # Never break text/audio delivery for an optional visual.
        self._intent_counts[label] = index + 1
        self._intent_generation += 1
        self._queue_expression(reaction["expression"])
        if self._reset_task is not None:
            self._reset_task.cancel()
        self._reset_task = asyncio.create_task(
            self._reset_after_timeout(self._intent_generation))

    async def _reset_after_timeout(self, generation):
        try:
            await asyncio.sleep(12)
            # While an audio player is active, end/pcm_end resets the face.
            if generation == self._intent_generation and not self._active:
                self._queue_expression("Neutral")
        except asyncio.CancelledError:
            pass

    async def _write_loop(self):
        try:
            while True:
                await self._wakeup.wait()
                expression, mouth = self._pending_expression, self._pending_mouth
                self._pending_expression = None
                self._pending_mouth = None
                self._wakeup.clear()
                frames = []
                if expression is not None:
                    frames.append({"type": "expression", "value": expression})
                if mouth is not None:
                    frames.append({"type": "mouth", "value": mouth})
                if frames:
                    packet = "".join(json.dumps(frame) + "\n" for frame in frames)
                    self.process.stdin.write(packet.encode("utf-8"))
                    await asyncio.wait_for(self.process.stdin.drain(), 1)
        except (BrokenPipeError, ConnectionError, OSError, TimeoutError):
            LOG.warning("Avatar unavailable; voice continues without animation")

    def observer(self, source):
        def notify(event, wav):
            if event == "start":
                self._active[source] = (asyncio.get_running_loop().time(), wav)
                if self._animation is None or self._animation.done():
                    self._animation = asyncio.create_task(self._animate())
            elif event == "pcm_start":
                # Streaming mouth motion is driven by actual PCM frames consumed
                # by Discord's audio thread, not by a guessed time offset.
                self._active[source] = ("pcm", None)
                self._offer(0.0)
            elif event == "pcm_level":
                if source in self._active and self._active[source][0] == "pcm":
                    self._offer(max(0.0, min(1.0, float(wav))))
            elif event in ("end", "pcm_end"):
                self._active.pop(source, None)
                if not self._active:
                    self._offer(0.0)
                    if self.intent_enabled:
                        # Audio finished: return to neutral rather than holding
                        # the previous emotional overlay indefinitely.
                        self._queue_expression("Neutral")
        return notify

    async def _animate(self):
        cache = {}
        try:
            while self._active:
                source = "discord" if "discord" in self._active else next(iter(self._active))
                started, wav = self._active[source]
                if started == "pcm":
                    await asyncio.sleep(0.04)
                    continue
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
        for task in (self._animation, self._writer, self._reset_task):
            if task:
                task.cancel()
        await asyncio.gather(*(t for t in (self._animation, self._writer, self._reset_task) if t), return_exceptions=True)
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
