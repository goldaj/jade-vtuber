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
                 subtitle_path: Path, secondary_player=None, audio_gate=None,
                 secondary_broadcast=False):
        if secondary_broadcast:
            raise ValueError("Cross-source Discord voice broadcast is not yet available")
        self.services = services
        self.player = player
        self.subtitle_path = Path(subtitle_path)
        self.lock = asyncio.Lock()
        self.secondary_player = secondary_player
        self.audio_gate = audio_gate
        self.secondary_broadcast = secondary_broadcast

    async def speak(self, reply: Reply):
        async with self.lock:
            discord_voice = reply.source.platform == "discord_voice"

            def require_session():
                # Discord voice is a private, revocable session.  Fail closed
                # even for local audio and OBS, before exposing its response.
                authorize = getattr(self.secondary_player, "reply_authorized", None)
                if not callable(authorize) or not authorize(reply.source):
                    raise PermissionError("Discord voice reply session is not authorized")

            if discord_voice:
                require_session()
            wav = await self.services.synthesize_wav(reply.text)
            if discord_voice:
                require_session()
            # OBS text source shows the whole phrase while the WAV plays.
            # Not character-accurate alignment: OpenAI speech WAV returns no
            # guaranteed per-character timing. Never fake precision.
            path = self.subtitle_path
            gated = False
            subtitle_written = False
            discord_played = False
            try:
                if self.audio_gate is not None:
                    await self.audio_gate.begin_speech()
                    gated = True
                if discord_voice:
                    require_session()
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(path.name + ".tmp")
                tmp.write_text(reply.text, encoding="utf-8")
                tmp.replace(path)
                subtitle_written = True
                if discord_voice:
                    require_session()
                    finished = asyncio.Event()

                    async def play_local():
                        require_session()
                        await self.player.play(wav)

                    async def play_both():
                        nonlocal discord_played
                        try:
                            async with asyncio.TaskGroup() as players:
                                players.create_task(play_local())
                                discord_task = players.create_task(
                                    self.secondary_player.play_for_reply(wav, reply.source))
                            # Only the bridge can attest that Discord actually
                            # completed playback; a missing/false result is not success.
                            discord_played = discord_task.result() is True
                        finally:
                            finished.set()

                    async def watch_session():
                        while not finished.is_set():
                            require_session()
                            try:
                                await asyncio.wait_for(finished.wait(), timeout=0.05)
                            except TimeoutError:
                                continue

                    async with asyncio.TaskGroup() as tasks:
                        tasks.create_task(play_both())
                        tasks.create_task(watch_session())
                else:
                    await self.player.play(wav)
            finally:
                try:
                    if gated:
                        await self.audio_gate.end_speech()
                finally:
                    if subtitle_written:
                        path.write_text("", encoding="utf-8")
            if discord_voice and discord_played:
                # The session may have been revoked during playback or while
                # releasing the local audio gate. The bridge checks it again.
                require_session()
                acknowledge = getattr(self.secondary_player, "mark_voice_reply_played", None)
                if callable(acknowledge):
                    acknowledge(reply.source)
