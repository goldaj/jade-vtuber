"""Experimental opt-in Discord PCM transport. STT/TTS remain **OpenAI only**.

Uses discord-ext-voice-recv as an audio *transport*, NOT a recognition engine.
Captures two-second chunks (unoptimized for turn boundaries) and ignores
silent PCM. Explicit informed consent of people in the channel is required
before enabling recording. Never stores received audio to disk.
"""
import asyncio
from io import BytesIO
from pathlib import Path
import tempfile
import threading
import time
import wave

from .microphone import is_speech_loud_enough
from .messages import Incoming

PCM_CHUNK_BYTES = 48000 * 2 * 2 * 2  # 2 sec × stereo × signed 16-bit
MAX_PENDING_USERS = 12
BUFFER_IDLE_SECONDS = 15


def pcm_48k_stereo_wav(data: bytes) -> bytes:
    if not data or len(data) % 4:
        raise ValueError("invalid 48 kHz stereo PCM")
    out = BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(data)
    return out.getvalue()


class DiscordVoiceBridge:
    def __init__(self, services, runtime, channel_id: int, *, threshold=550):
        if type(channel_id) is not int or channel_id <= 0:
            raise ValueError("Discord voice channel must be positive")
        self.services, self.runtime = services, runtime
        self.channel_id = channel_id
        self.threshold = threshold
        self.buffers = {}
        self.buffer_updated = {}
        self.buffers_lock = threading.Lock()
        self.lifecycle_lock = asyncio.Lock()
        self.pending = asyncio.Queue(maxsize=8)
        self.worker = None
        self.loop = None
        self.connection = None
        self.seq = 0
        self.generation = 0

    def _accept(self, author, pcm, generation=None):
        if (generation is not None and generation != self.generation) or self.worker is None or self.worker.done():
            return
        if self.pending.full():
            return  # Bound memory; drop overload rather than block receiver.
        self.pending.put_nowait((author, pcm))

    def receive_pcm(self, user_id: int, author: str, pcm: bytes):
        """Called by the voice receive thread, never blocks on OpenAI/network."""
        if (type(user_id) is not int or user_id <= 0 or not author
                or not isinstance(pcm, bytes) or len(pcm) % 4):
            return
        with self.buffers_lock:
            now = time.monotonic()
            expired = [uid for uid, seen in self.buffer_updated.items()
                       if now - seen >= BUFFER_IDLE_SECONDS]
            for uid in expired:
                self.buffers.pop(uid, None)
                self.buffer_updated.pop(uid, None)
            if user_id not in self.buffers and len(self.buffers) >= MAX_PENDING_USERS:
                return
            data = self.buffers.setdefault(user_id, bytearray())
            self.buffer_updated[user_id] = now
            # Never store indefinitely in memory if a stream is continuous.
            data.extend(pcm[:PCM_CHUNK_BYTES])
            if len(data) < PCM_CHUNK_BYTES:
                return
            samples = bytes(data[:PCM_CHUNK_BYTES])
            del data[:PCM_CHUNK_BYTES]
            if not data:
                self.buffers.pop(user_id, None)
                self.buffer_updated.pop(user_id, None)
            loop, generation = self.loop, self.generation
        if not is_speech_loud_enough(samples, threshold=self.threshold):
            return
        if loop is not None:
            loop.call_soon_threadsafe(self._accept, author, samples, generation)

    async def _consume(self):
        while True:
            item = await self.pending.get()
            try:
                if item is None:
                    return
                author, pcm = item
                value = await self.services.transcribe_wav(pcm_48k_stereo_wav(pcm))
                if value:
                    self.seq += 1
                    await self.runtime.submit(Incoming(
                        "discord_voice", author, value,
                        channel=str(self.channel_id),
                        message_id=f"discord-voice-{self.seq}"))
            except asyncio.CancelledError:
                raise
            except Exception:
                import logging
                logging.getLogger("jade.discord.voice").warning(
                    "Discord voice chunk dropped after STT or delivery failure")
            finally:
                self.pending.task_done()

    async def connect(self, client):
        async with self.lifecycle_lock:
            await self._connect_locked(client)

    async def _connect_locked(self, client):
        if self.connection is not None:
            return
        try:
            from discord.ext import voice_recv
        except ImportError as exc:
            raise RuntimeError("install optional discord-voice extra") from exc
        channel = client.get_channel(self.channel_id)
        if channel is None or not hasattr(channel, "connect"):
            raise ValueError("configured Discord voice channel not available")
        connection = await channel.connect(cls=voice_recv.VoiceRecvClient)
        self.loop = asyncio.get_running_loop()
        bridge = self

        class Sink(voice_recv.AudioSink):
            def wants_opus(self):
                return False
            def write(self, user, data):
                if user is None or getattr(user, "bot", False):
                    return
                pcm = getattr(data, "pcm", None)
                if pcm:
                    bridge.receive_pcm(
                        user.id, getattr(user, "display_name", str(user)), bytes(pcm))
            def cleanup(self):
                pass

        try:
            self.worker = asyncio.create_task(self._consume(), name="jade-discord-voice")
            self.connection = connection
            connection.listen(Sink())
        except BaseException:
            await self._close_locked()
            raise

    async def play(self, wav: bytes):
        """Optional playback of OpenAI-generated WAV, never a TTS engine."""
        connection = self.connection
        if connection is None:
            return
        import discord
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
            fp.write(wav)
            path = Path(fp.name)
        try:
            if connection.is_playing():
                # Caller serializes Jade voice; refuse overlapping attempts.
                return
            source = discord.FFmpegPCMAudio(str(path))
            done = asyncio.Event()
            failure = []
            loop = asyncio.get_running_loop()
            def after(err):
                if err is not None:
                    failure.append(err)
                loop.call_soon_threadsafe(done.set)
            connection.play(
                source, after=after)
            await asyncio.wait_for(done.wait(), timeout=120)
            if failure:
                raise RuntimeError("Discord audio playback failed")
        finally:
            try:
                if 'source' in locals():
                    try:
                        connection.stop()
                    finally:
                        source.cleanup()
            finally:
                path.unlink(missing_ok=True)

    async def close(self):
        async with self.lifecycle_lock:
            await self._close_locked()

    async def _close_locked(self):
        connection, self.connection = self.connection, None
        worker, self.worker = self.worker, None
        with self.buffers_lock:
            self.generation += 1
            self.loop = None
        if worker is not None:
            worker.cancel()
            try:
                await asyncio.wait_for(asyncio.gather(worker, return_exceptions=True), timeout=2)
            except TimeoutError:
                pass
        while True:
            try:
                self.pending.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self.pending.task_done()
        with self.buffers_lock:
            self.buffers.clear()
            self.buffer_updated.clear()
        if connection is not None:
            try:
                connection.stop_listening()
            except Exception:
                # A partially initialized listener may never have started.
                import logging
                logging.getLogger("jade.discord.voice").warning("Discord listener cleanup failed")
            finally:
                await asyncio.wait_for(connection.disconnect(), timeout=2)
