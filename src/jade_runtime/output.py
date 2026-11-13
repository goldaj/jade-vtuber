"""Ordered audio output and OBS subtitles; no third-party speech engine."""
import asyncio
import logging
import os
from pathlib import Path
import tempfile

from .avatar import child_environment
from .messages import Reply
from .openai_services import OpenAIServices

LOG = logging.getLogger("jade.output")


class AudioOutput:
    def __init__(self, mode="none"):
        if mode not in ("none", "ffplay"):
            raise ValueError("unsupported WAV output mode")
        self.mode = mode
        self.playback_observer = None

    def _observe(self, observer, event, data):
        if observer is not None:
            try:
                observer(event, data)
            except Exception:
                LOG.warning("Audio playback observer failed")

    async def play(self, data: bytes):
        if self.mode == "none":
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
            fp.write(data)
            path = Path(fp.name)
        process = None
        spawn = None
        observer = self.playback_observer
        started = False
        try:
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                "ffplay", "-nodisp", "-autoexit", "-loglevel", "error",
                str(path), stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL, env=child_environment(os.environ)))
            process = await asyncio.shield(spawn)
            started = True
            self._observe(observer, "start", data)
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
            if started:
                self._observe(observer, "end", data)
            # Windows may still have the WAV open if the process refused to stop.
            if process is None or process.returncode is not None:
                path.unlink(missing_ok=True)


class SpeechOutput:
    """Only one spoken response at a time; clear subtitles even on failure."""
    def __init__(self, services: OpenAIServices, player: AudioOutput,
                 subtitle_path: Path, secondary_player=None, audio_gate=None,
                 secondary_broadcast=False):
        self.services = services
        self.player = player
        self.subtitle_path = Path(subtitle_path)
        self.lock = asyncio.Lock()
        self.secondary_player = secondary_player
        self.audio_gate = audio_gate
        # Kept only for callers of the former opt-in API. The owner has chosen
        # to broadcast spoken responses whenever a voice bridge is connected.
        self.secondary_broadcast = True

    def _delivery_context(self):
        """Take a playback snapshot; an absent bridge leaves local output intact."""
        get_context = getattr(self.secondary_player, "delivery_context", None)
        if not callable(get_context):
            return None
        try:
            return get_context()
        except Exception:
            LOG.warning("Discord voice delivery unavailable")
            return None

    async def _play_other_source(self, wav, context):
        """Cancel stale Discord playback without interrupting the local player."""
        if context is None:
            return
        valid = getattr(self.secondary_player, "delivery_context_valid", None)
        play = getattr(self.secondary_player, "play_for_context", None)
        if not callable(valid) or not callable(play):
            return
        task = None
        try:
            if not valid(context):
                return
            task = asyncio.create_task(play(wav, context))
            while not task.done():
                if not valid(context):
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    return
                await asyncio.wait({task}, timeout=0.05)
            if task.cancelled():
                return
            await task
        except asyncio.CancelledError:
            raise
        except Exception:
            # A Discord disconnect must not prevent a local or text reply.
            LOG.warning("Discord voice delivery failed")
        finally:
            if task is not None and not task.done():
                task.cancel()
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)

    def start_early(self, source):
        """Create an opt-in early voice turn if the runtime can actually stream."""
        if (source.platform != "discord_voice"
                or getattr(self.player, "mode", None) != "none"
                or self.secondary_player is None
                or not callable(getattr(self.secondary_player, "play_pcm_stream_for_reply", None))
                or not callable(getattr(self.services, "stream_speech_pcm", None))):
            return None
        model = getattr(getattr(self.services, "settings", None), "tts_model", "")
        if not model.startswith(("gpt-realtime", "gpt-4o-realtime")):
            return None
        from .early_speech import EarlySpeechTurn
        return EarlySpeechTurn(self, source)

    async def _speak_progressive(self, reply, context, require_session, *, discord_voice):
        """Use streaming only for Discord with no simultaneous local WAV player.

        The offline demo and local/dual output keep the original WAV adapter.
        One PCM iterator feeds exactly one Discord player and is cancelled
        whenever that player stops or its voice session is revoked.
        """
        if getattr(self.player, "mode", None) != "none":
            return False
        stream_factory = getattr(self.services, "stream_speech_pcm", None)
        method_name = ("play_pcm_stream_for_reply" if discord_voice
                       else "play_pcm_stream_for_context")
        bridge_method = getattr(self.secondary_player, method_name, None)
        if not callable(stream_factory) or not callable(bridge_method):
            return False
        if not discord_voice and context is None:
            return False
        stream = stream_factory(reply.text)
        if stream is None:
            return False

        gated = False
        written = False
        played = False
        path = self.subtitle_path
        try:
            if discord_voice:
                require_session()
            if self.audio_gate is not None:
                await self.audio_gate.begin_speech()
                gated = True
            if discord_voice:
                require_session()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(reply.text, encoding="utf-8")
            tmp.replace(path)
            written = True
            if discord_voice:
                require_session()
                played = await bridge_method(stream, reply.source)
            else:
                valid = getattr(self.secondary_player, "delivery_context_valid", None)
                if not callable(valid) or not valid(context):
                    return True  # Destination revoked; do not synthesize.
                played = await bridge_method(stream, context)
            if discord_voice and played is True:
                require_session()
                acknowledge = getattr(self.secondary_player, "mark_voice_reply_played", None)
                if callable(acknowledge):
                    acknowledge(reply.source)
            return True
        finally:
            # The bridge normally closes its iterator. Also close it if the
            # gate/subtitle preparation failed before playback started.
            close = getattr(stream, "aclose", None)
            if callable(close):
                try:
                    await close()
                except Exception:
                    pass
            try:
                if gated:
                    await self.audio_gate.end_speech()
            finally:
                if written:
                    path.write_text("", encoding="utf-8")

    async def speak(self, reply: Reply):
        async with self.lock:
            discord_voice = reply.source.platform == "discord_voice"
            context = None if discord_voice else self._delivery_context()
            muted = getattr(self.secondary_player, "voice_muted", None)
            if (not discord_voice and context is None and getattr(self.player, "mode", None) == "none"
                    and callable(muted) and muted()):
                return  # Discord is muted and there is no local audible output.

            def require_session():
                # Discord voice is a private, revocable session.  Fail closed
                # even for local audio and OBS, before exposing its response.
                authorize = getattr(self.secondary_player, "reply_authorized", None)
                if not callable(authorize) or not authorize(reply.source):
                    raise PermissionError("Discord voice reply session is not authorized")

            if discord_voice:
                require_session()
            if await self._speak_progressive(
                    reply, context, require_session, discord_voice=discord_voice):
                return
            # New adapters can report the words actually spoken; legacy service
            # doubles still provide synthesize_wav only.
            rich_synthesis = getattr(type(self.services), "synthesize_speech", None)
            if callable(rich_synthesis):
                spoken = await rich_synthesis(self.services, reply.text)
                wav, spoken_text = spoken.audio, spoken.transcript
            else:
                wav = await self.services.synthesize_wav(reply.text)
                spoken_text = reply.text
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
                tmp.write_text(spoken_text, encoding="utf-8")
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
                    if context is None:
                        await self.player.play(wav)
                    else:
                        async with asyncio.TaskGroup() as players:
                            players.create_task(self.player.play(wav))
                            players.create_task(self._play_other_source(wav, context))
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
