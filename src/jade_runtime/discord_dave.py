"""DAVE receive support for discord-ext-voice-recv 0.5.2a179.

discord.py owns the DAVE handshake and session. The upstream receiver only
removes transport encryption, so remove DAVE before its jitter buffer/decoder.
This deliberately avoids a process-wide patch of the third-party package.
See https://github.com/imayhaveborkedit/discord-ext-voice-recv/pull/62.
"""

from __future__ import annotations

import logging

import davey
import discord
from discord.ext.voice_recv import AudioSink, VoiceRecvClient, rtp
from discord.ext.voice_recv.opus import PacketDecoder
from discord.ext.voice_recv.reader import AudioReader
from discord.ext.voice_recv.router import PacketRouter
from discord.opus import Decoder, OpusError


log = logging.getLogger(__name__)


class SafePacketDecoder(PacketDecoder):
    def _decode_packet(self, packet):
        try:
            return super()._decode_packet(packet)
        except OpusError:
            # A corrupt frame must not stop the single router thread for every
            # speaker. Use Opus packet-loss concealment, then one silent frame.
            try:
                return packet, self._decoder.decode(None, fec=False)
            except OpusError:
                return packet, b"\x00" * Decoder.FRAME_SIZE


class SafePacketRouter(PacketRouter):
    def get_decoder(self, ssrc):
        with self._lock:
            decoder = self.decoders.get(ssrc)
            if decoder is None:
                decoder = self.decoders[ssrc] = SafePacketDecoder(self, ssrc)
            return decoder

    def run(self):
        try:
            self._do_run()
        except Exception as exc:
            log.error("Discord voice packet router stopped")
            self.reader.error = exc
        finally:
            # Stopping a reader is asynchronous. Its old router must never stop
            # a new listening session established while it was winding down.
            client = self.reader.voice_client
            if client._reader is self.reader:
                client.stop_listening()
            self.waiter.clear()


class DaveAudioReader(AudioReader):
    def __init__(self, sink, voice_client, *, after=None):
        super().__init__(sink, voice_client, after=after)
        # The base router has not started yet; replace it for this reader only.
        self.packet_router = SafePacketRouter(sink, self)

    def _decrypt_dave(self, packet) -> bool:
        state = self.voice_client._connection
        version = getattr(state, "dave_protocol_version", None)
        if version is None:
            return False
        if version == 0 or packet.is_silence():
            return True
        session = getattr(state, "dave_session", None)
        user_id = self.voice_client._get_id_from_ssrc(packet.ssrc)
        if session is None or not session.ready or user_id is None:
            return False
        try:
            clear = session.decrypt(user_id, davey.MediaType.audio, bytes(packet.decrypted_data))
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            # PyO3 panic exceptions can inherit BaseException. Never log payloads,
            # exception text or session state, which can contain private data.
            return False
        if not isinstance(clear, bytes) or not clear:
            return False
        packet.decrypted_data = clear
        return True

    def callback(self, packet_data: bytes) -> None:
        # Decode transport then DAVE exactly once, before FEC can peek at a frame.
        # Do not log raw packet data or transport keys, including on errors.
        if self.error:
            self.stop()
            return
        try:
            if rtp.is_rtcp(packet_data):
                packet = rtp.decode_rtcp(self.decryptor.decrypt_rtcp(packet_data))
                is_rtcp = True
            else:
                packet = rtp.decode_rtp(packet_data)
                packet.decrypted_data = self.decryptor.decrypt_rtp(packet)
                if not self._decrypt_dave(packet):
                    return
                is_rtcp = False
        except Exception:
            log.debug("Dropped an invalid Discord voice packet")
            return
        if not packet:
            return
        try:
            if is_rtcp:
                self.packet_router.feed_rtcp(packet)
            elif packet.ssrc in self.voice_client._ssrc_to_id or not packet.is_silence():
                self.speaking_timer.notify(packet.ssrc)
                self.packet_router.feed_rtp(packet)
        except Exception as exc:
            log.error("Discord voice packet routing failed")
            self.error = exc
            self.stop()


class DaveVoiceRecvClient(VoiceRecvClient):
    """Receiver using a fresh DAVE-aware reader for each listening session."""

    def listen(self, sink: AudioSink, *, after=None) -> None:
        if not self.is_connected():
            raise discord.ClientException("Not connected to voice.")
        if not isinstance(sink, AudioSink):
            raise TypeError("sink must be an AudioSink")
        if self.is_listening():
            raise discord.ClientException("Already receiving audio.")
        self._reader = DaveAudioReader(sink, self, after=after)
        self._reader.start()
