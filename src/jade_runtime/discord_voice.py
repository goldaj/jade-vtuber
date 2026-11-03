"""Experimental opt-in Discord PCM transport. STT/TTS remain **OpenAI only**.

Uses discord-ext-voice-recv as an audio *transport*, NOT a recognition engine.
Captures two-second chunks (unoptimized for turn boundaries) and ignores
silent PCM. Explicit informed consent of people in the channel is required
before enabling recording. Never stores received audio to disk.
"""
import asyncio
from dataclasses import dataclass
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
import tempfile
import threading
import time
import secrets
import wave

from .microphone import is_speech_loud_enough
from .messages import Incoming
from .orchestrator import Work

PCM_CHUNK_BYTES = 48000 * 2 * 2 * 2  # 2 sec × stereo × signed 16-bit
MAX_PENDING_USERS = 12
BUFFER_IDLE_SECONDS = 15


@dataclass(frozen=True, repr=False)
class _VoiceChunk:
    user_id: int
    author: str
    pcm: bytes
    generation: int
    session_id: str
    audio_epoch: int = 0


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
    def __init__(self, services, runtime, channel_id: int, *, threshold=550,
                 authorized_user_ids=(), consent_confirmed=False):
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
        self.authorized_user_ids = frozenset()
        self.consent_confirmed = False
        self.session_id = None
        self.own_bot_id = None
        self._transcribing = None
        self._transcribing_generation = None
        self._submitted = []
        self._playback_active = False
        self._audio_epoch = 0
        if authorized_user_ids or consent_confirmed:
            self.set_session(authorized_user_ids, consent_confirmed=consent_confirmed)

    def set_session(self, authorized_user_ids, *, consent_confirmed):
        """Replace the authorized participants; revoke the prior session immediately.

        The caller must obtain informed consent outside this method. Identity
        display names do not grant permission. A fresh random session also
        prevents conversation history from being reused across sessions.
        """
        if type(consent_confirmed) is not bool or isinstance(authorized_user_ids, (str, bytes)):
            raise ValueError("explicit Discord voice consent and user IDs required")
        try:
            ids = tuple(authorized_user_ids)
        except TypeError:
            raise ValueError("explicit Discord voice consent and user IDs required") from None
        if len(ids) > 100 or any(type(uid) is not int or uid <= 0 for uid in ids):
            raise ValueError("invalid Discord voice user IDs")
        allowed = frozenset(ids) if consent_confirmed else frozenset()
        if allowed and self.connection is not None and not self._snapshot_allowed(
                getattr(self.connection, "channel", None), allowed, self.own_bot_id):
            self.set_session([], consent_confirmed=False)
            raise ValueError("Discord voice participants are not authorized")
        with self.buffers_lock:
            self.generation += 1
            generation = self.generation
            self.buffers.clear()
            self.buffer_updated.clear()
            self.authorized_user_ids = allowed
            self.consent_confirmed = consent_confirmed and bool(allowed)
            self.session_id = secrets.token_hex(16) if self.consent_confirmed else None
            loop = self.loop
            connection = self.connection
        # The prior session is invalidated synchronously. Stop its current audio
        # immediately rather than waiting for STT/worker cleanup or disconnect.
        if connection is not None:
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if loop is not None and running is not loop:
                try:
                    loop.call_soon_threadsafe(self._stop_playback, connection)
                except RuntimeError:
                    pass
            else:
                self._stop_playback(connection)
        if loop is not None:
            try:
                loop.call_soon_threadsafe(self._purge_stale, generation)
                if not allowed:
                    loop.call_soon_threadsafe(self._close_revoked, generation)
            except RuntimeError:
                pass  # A closed loop cannot process more audio.

    @staticmethod
    def _stop_playback(connection):
        stop = getattr(connection, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                import logging
                logging.getLogger("jade.discord.voice").warning("Discord voice playback stop failed")

    def _close_revoked(self, generation):
        with self.buffers_lock:
            should_close = generation == self.generation and not self.consent_confirmed
        if should_close and self.connection is not None:
            task = asyncio.create_task(self.close())
            def finish(result):
                if not result.cancelled() and result.exception() is not None:
                    import logging
                    logging.getLogger("jade.discord.voice").warning("Discord voice revocation cleanup failed")
            task.add_done_callback(finish)

    def _allowed(self, user_id, generation, session_id):
        with self.buffers_lock:
            return (self.consent_confirmed and self.session_id == session_id
                    and self.generation == generation and user_id in self.authorized_user_ids)

    @staticmethod
    def _snapshot_allowed(channel, authorized_user_ids, own_bot_id):
        try:
            return DiscordVoiceBridge._snapshot_allowed_checked(channel, authorized_user_ids, own_bot_id)
        except Exception:
            # Voice cache may change concurrently with the audio receiver thread.
            # Missing/inconsistent state or a read error must never permit capture.
            return False

    @staticmethod
    def _snapshot_allowed_checked(channel, authorized_user_ids, own_bot_id):
        members = getattr(channel, "members", None)
        states = getattr(channel, "voice_states", None)
        channel_id = getattr(channel, "id", None)
        if (type(own_bot_id) is not int or own_bot_id <= 0
                or not isinstance(members, (list, tuple)) or not isinstance(states, Mapping)
                or type(channel_id) is not int or channel_id <= 0):
            return False
        state_ids = set()
        for uid, state in states.items():
            if (type(uid) is not int or uid <= 0 or state is None
                    or getattr(getattr(state, "channel", None), "id", None) != channel_id):
                return False
            state_ids.add(uid)
        humans = []
        member_ids = set()
        for member in members:
            bot = getattr(member, "bot", None)
            uid = getattr(member, "id", None)
            if type(bot) is not bool or type(uid) is not int or uid <= 0 or uid in member_ids:
                return False
            member_ids.add(uid)
            if uid == own_bot_id and not bot:
                return False
            if bot and uid != own_bot_id:
                return False
            if not bot:
                humans.append(uid)
        return (state_ids == member_ids and bool(humans)
                and all(uid in authorized_user_ids for uid in humans))

    def _members_authorized(self, channel):
        """Require a complete, non-empty authorized human membership snapshot."""
        with self.buffers_lock:
            allowed = self.authorized_user_ids if self.consent_confirmed else frozenset()
            own_bot_id = self.own_bot_id
        return bool(allowed) and self._snapshot_allowed(channel, allowed, own_bot_id)

    def _capture_authorized(self, user_id, generation=None, session_id=None, audio_epoch=None):
        """Recheck the entire channel before buffering, queuing and STT.

        Called on the Discord audio thread as well as the event loop. A cache
        read exception or an unresolved/new participant revokes the session;
        no provider or cache exception is exposed.
        """
        with self.buffers_lock:
            if (not self.consent_confirmed or self._playback_active
                    or (generation is not None and generation != self.generation)
                    or (session_id is not None and session_id != self.session_id)
                    or (audio_epoch is not None and audio_epoch != self._audio_epoch)):
                return False
            observed_generation = self.generation
            observed_session = self.session_id
            connection = self.connection
            allowed = self.authorized_user_ids
            own_bot_id = self.own_bot_id
        try:
            valid = (connection is not None and self._snapshot_allowed(
                getattr(connection, "channel", None), allowed, own_bot_id))
        except Exception:
            valid = False
        if not valid:
            with self.buffers_lock:
                still_current = (self.generation == observed_generation
                                 and self.session_id == observed_session
                                 and self.connection is connection)
            if still_current:
                self.set_session([], consent_confirmed=False)
            return False
        with self.buffers_lock:
            return (self.consent_confirmed and not self._playback_active
                    and (audio_epoch is None or audio_epoch == self._audio_epoch)
                    and self.generation == observed_generation
                    and self.session_id == observed_session and self.connection is connection
                    and user_id in self.authorized_user_ids)

    def _playback_authorized(self, connection, generation, session_id):
        with self.buffers_lock:
            if (not self.consent_confirmed or self.generation != generation
                    or self.session_id != session_id or self.connection is not connection):
                return False
            allowed = self.authorized_user_ids
            own_bot_id = self.own_bot_id
        if not allowed or not self._snapshot_allowed(getattr(connection, "channel", None), allowed, own_bot_id):
            return False
        with self.buffers_lock:
            return (self.consent_confirmed and self.generation == generation
                    and self.session_id == session_id and self.connection is connection)

    async def _require_playback_authorization(self, connection, generation, session_id):
        if not self._playback_authorized(connection, generation, session_id):
            with self.buffers_lock:
                same_session = (self.generation == generation and self.session_id == session_id
                                and self.connection is connection)
            # A stale response must not revoke a newer valid session.
            if same_session:
                self.set_session([], consent_confirmed=False)
                await self.close()
            raise PermissionError("Discord voice playback authorization is no longer valid")

    async def voice_state_changed(self, member, before, after, *, own_bot_id=None):
        """Revoke on human membership changes or this bot leaving the channel."""
        bot = getattr(member, "bot", None)
        before_id = getattr(getattr(before, "channel", None), "id", None)
        after_id = getattr(getattr(after, "channel", None), "id", None)
        if before_id == after_id or self.channel_id not in (before_id, after_id):
            return
        if (bot is True and type(own_bot_id) is int
                and getattr(member, "id", None) == own_bot_id and after_id == self.channel_id):
            return  # This bot joining is the expected completion of connect().
        with self.buffers_lock:
            active = self.consent_confirmed
        if active:
            self.set_session([], consent_confirmed=False)
            await self.close()

    def _purge_stale(self, generation):
        """Drop revoked queued audio and cancel any no-longer-authorized STT."""
        with self.buffers_lock:
            if generation != self.generation:
                return
            if self._transcribing is not None and self._transcribing_generation != generation:
                self._transcribing.cancel()
            retained_work = []
            for work_generation, work in self._submitted:
                if work_generation != generation:
                    self.runtime.cancel_work(work)
                else:
                    retained_work.append((work_generation, work))
            self._submitted = retained_work
            retained = []
            while True:
                try:
                    item = self.pending.get_nowait()
                except asyncio.QueueEmpty:
                    break
                self.pending.task_done()
                if isinstance(item, _VoiceChunk) and item.generation == generation:
                    retained.append(item)
            for item in retained:
                self.pending.put_nowait(item)

    def _accept(self, item):
        if (not self._capture_authorized(item.user_id, item.generation, item.session_id, item.audio_epoch)
                or self.worker is None or self.worker.done()):
            return
        with self.buffers_lock:
            if (not self.consent_confirmed or self._playback_active
                    or item.generation != self.generation or item.session_id != self.session_id
                    or item.audio_epoch != self._audio_epoch
                    or item.user_id not in self.authorized_user_ids):
                return
            if self.pending.full():
                return  # Bound memory; drop overload rather than block receiver.
            self.pending.put_nowait(item)

    def receive_pcm(self, user_id: int, author: str, pcm: bytes):
        """Called by the voice receive thread, never blocks on OpenAI/network."""
        if (type(user_id) is not int or user_id <= 0 or not author
                or not isinstance(pcm, bytes) or len(pcm) % 4):
            return
        with self.buffers_lock:
            observed_generation = self.generation
            observed_session = self.session_id
            observed_audio_epoch = self._audio_epoch
        if not self._capture_authorized(user_id, observed_generation,
                                        observed_session, observed_audio_epoch):
            return
        with self.buffers_lock:
            if (not self.consent_confirmed or self._playback_active
                    or self.generation != observed_generation
                    or self.session_id != observed_session
                    or self._audio_epoch != observed_audio_epoch
                    or user_id not in self.authorized_user_ids):
                return
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
            loop, generation, session_id, audio_epoch = self.loop, self.generation, self.session_id, self._audio_epoch
        if not is_speech_loud_enough(samples, threshold=self.threshold):
            return
        if loop is not None:
            loop.call_soon_threadsafe(self._accept, _VoiceChunk(
                user_id, author, samples, generation, session_id, audio_epoch))

    async def _transcribe_authorized(self, item):
        # Recheck when the task actually begins: session revocation can run
        # after task creation but before the coroutine gets CPU time.
        if not self._capture_authorized(item.user_id, item.generation,
                                        item.session_id, item.audio_epoch):
            return None
        return await self.services.transcribe_wav(pcm_48k_stereo_wav(item.pcm))

    async def _consume(self):
        while True:
            item = await self.pending.get()
            try:
                if item is None:
                    return
                if (not isinstance(item, _VoiceChunk)
                        or not self._capture_authorized(item.user_id, item.generation, item.session_id, item.audio_epoch)):
                    continue
                self._transcribing_generation = item.generation
                self._transcribing = asyncio.create_task(self._transcribe_authorized(item))
                try:
                    value = await self._transcribing
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        raise
                    continue  # Revocation cancels this STT, not the session worker.
                finally:
                    self._transcribing = None
                    self._transcribing_generation = None
                if value and self._capture_authorized(item.user_id, item.generation, item.session_id, item.audio_epoch):
                    self.seq += 1
                    work = await self.runtime.submit(Incoming(
                        "discord_voice", item.author, value,
                        channel=str(self.channel_id),
                        message_id=f"discord-voice-{self.seq}",
                        speaker_id=item.user_id, voice_session_id=item.session_id))
                    if isinstance(work, Work):
                        self._submitted = [(generation, previous) for generation, previous in self._submitted
                                           if not previous.cancelled and (previous.task is None or not previous.task.done())]
                        self._submitted.append((item.generation, work))
                        if not self._allowed(item.user_id, item.generation, item.session_id):
                            self.runtime.cancel_work(work)
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
        with self.buffers_lock:
            if not self.consent_confirmed or not self.authorized_user_ids or not self.session_id:
                raise ValueError("Discord voice requires explicit consent and authorized users")
            own_bot_id = getattr(getattr(client, "user", None), "id", None)
            if type(own_bot_id) is not int or own_bot_id <= 0:
                raise ValueError("Discord bot identity is not available")
            generation = self.generation
            self.own_bot_id = own_bot_id
        try:
            from discord.ext import voice_recv
        except ImportError as exc:
            raise RuntimeError("install optional discord-voice extra") from exc
        channel = client.get_channel(self.channel_id)
        if channel is None or not hasattr(channel, "connect"):
            raise ValueError("configured Discord voice channel not available")
        if not self._members_authorized(channel):
            raise ValueError("Discord voice participants are not authorized")
        connection = await channel.connect(cls=voice_recv.VoiceRecvClient)
        with self.buffers_lock:
            valid = (self.generation == generation and self.consent_confirmed
                     and bool(self.authorized_user_ids) and self.session_id is not None)
        if not valid or not self._members_authorized(channel):
            await asyncio.wait_for(connection.disconnect(), timeout=2)
            raise ValueError("Discord voice authorization changed during connection")
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

    def reply_authorized(self, source):
        """Check the source and current session before any reply side effect."""
        speaker_id = getattr(source, "speaker_id", None)
        session_id = getattr(source, "voice_session_id", "")
        if (getattr(source, "platform", None) != "discord_voice"
                or getattr(source, "channel", None) != str(self.channel_id)
                or type(speaker_id) is not int or speaker_id <= 0 or not session_id):
            return False
        with self.buffers_lock:
            connection, generation = self.connection, self.generation
            if (connection is None or self.session_id != session_id
                    or speaker_id not in self.authorized_user_ids):
                return False
        return self._playback_authorized(connection, generation, session_id)

    async def play_for_reply(self, wav: bytes, source):
        """Play only a reply from an authorized speaker in the active session."""
        speaker_id = getattr(source, "speaker_id", None)
        session_id = getattr(source, "voice_session_id", "")
        if not self.reply_authorized(source):
            raise PermissionError("Discord voice reply source is not authorized")
        return await self.play(wav, expected_session=session_id, expected_speaker=speaker_id)

    def _begin_playback(self, connection, generation, session_id):
        """Invalidate buffered input before starting a half-duplex response."""
        with self.buffers_lock:
            if (not self.consent_confirmed or self.generation != generation
                    or self.session_id != session_id or self.connection is not connection):
                raise PermissionError("Discord voice playback authorization is no longer valid")
            if self._playback_active:
                raise RuntimeError("Discord voice playback already active")
            self._playback_active = True
            self._audio_epoch += 1
            self.buffers.clear()
            self.buffer_updated.clear()
        if self._transcribing is not None:
            self._transcribing.cancel()
        while True:
            try:
                self.pending.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                self.pending.task_done()

    def _end_playback(self):
        with self.buffers_lock:
            self._audio_epoch += 1
            self._playback_active = False

    async def play(self, wav: bytes, *, expected_session=None, expected_speaker=None):
        """Optional playback of OpenAI-generated WAV, never a TTS engine."""
        connection = self.connection
        if connection is None:
            return
        with self.buffers_lock:
            generation, session_id = self.generation, self.session_id
            if (expected_session is not None and
                    (session_id != expected_session or expected_speaker not in self.authorized_user_ids)):
                raise PermissionError("Discord voice reply is from another session")
        await self._require_playback_authorization(connection, generation, session_id)
        self._begin_playback(connection, generation, session_id)
        path = None
        source = None
        try:
            import discord
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
                fp.write(wav)
                path = Path(fp.name)
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
            await self._require_playback_authorization(connection, generation, session_id)
            connection.play(
                source, after=after)
            await asyncio.wait_for(done.wait(), timeout=120)
            if failure:
                raise RuntimeError("Discord audio playback failed")
        finally:
            try:
                if source is not None:
                    try:
                        connection.stop()
                    finally:
                        source.cleanup()
            finally:
                try:
                    if path is not None:
                        path.unlink(missing_ok=True)
                finally:
                    self._end_playback()

    async def close(self):
        async with self.lifecycle_lock:
            await self._close_locked()

    async def _close_locked(self):
        connection, self.connection = self.connection, None
        if connection is not None:
            self._stop_playback(connection)
        worker, self.worker = self.worker, None
        with self.buffers_lock:
            self.generation += 1
            self.loop = None
            self.authorized_user_ids = frozenset()
            self.consent_confirmed = False
            self.session_id = None
            self.own_bot_id = None
        for _, work in self._submitted:
            self.runtime.cancel_work(work)
        self._submitted.clear()
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
