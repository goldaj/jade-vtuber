"""Ordered audio output and OBS subtitles; no third-party speech engine."""
import asyncio
import logging
from pathlib import Path
import tempfile

from .messages import Reply
from .openai_services import OpenAIServices

LOG = logging.getLogger("jade.output")


class AudioOutput:
    def __init__(self, mode="none"):
        if mode not in ("none", "ffplay"):
            raise ValueError("unsupported WAV output mode")
        self.mode = mode

    async def play(self, data: bytes):
        if self.mode == "none":
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
            fp.write(data)
            path = Path(fp.name)
        process = None
        spawn = None
        try:
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                "ffplay", "-nodisp", "-autoexit", "-loglevel", "error",
                str(path), stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL))
            process = await asyncio.shield(spawn)
            status = await process.wait()
            if status:
                raise RuntimeError("ffplay could not play the supplied WAV")
        except BaseException:
            if process is None and spawn is not None and not spawn.cancelled():
                try:
                    process = await asyncio.shield(spawn)
                except Exception:
                    pass
            if process is not None and process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), timeout=1)
                except asyncio.TimeoutError:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    try:
                        await asyncio.wait_for(process.wait(), timeout=1)
                    except asyncio.TimeoutError as exc:
                        raise RuntimeError("ffplay could not be stopped") from exc
            raise
        finally:
            # Windows may still have the WAV open if the process refused to stop.
            if process is None or process.returncode is not None:
                path.unlink(missing_ok=True)


class SpeechOutput:
    """Only one spoken response at a time; clear subtitles even on failure."""
    def __init__(self, services: OpenAIServices, player: AudioOutput,
                 subtitle_path: Path, secondary_player=None, audio_gate=None):
        self.services = services
        self.player = player
        self.subtitle_path = Path(subtitle_path)
        self.lock = asyncio.Lock()
        self.secondary_player = secondary_player
        self.audio_gate = audio_gate

    async def speak(self, reply: Reply):
        async with self.lock:
            wav = await self.services.synthesize_wav(reply.text)
            # OBS text source shows the whole phrase while the WAV plays.
            # Not character-accurate alignment: OpenAI speech WAV returns no
            # guaranteed per-character timing. Never fake precision.
            path = self.subtitle_path
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(reply.text, encoding="utf-8")
            tmp.replace(path)
            gated = False
            try:
                if self.audio_gate is not None:
                    await self.audio_gate.begin_speech()
                    gated = True
                if self.secondary_player is not None and reply.source.platform == "discord_voice":
                    async with asyncio.TaskGroup() as players:
                        players.create_task(self.player.play(wav))
                        players.create_task(self.secondary_player.play(wav))
                else:
                    await self.player.play(wav)
            finally:
                if gated:
                    await self.audio_gate.end_speech()
                path.write_text("", encoding="utf-8")
