"""Offline checks of the DAVE layer before the upstream jitter buffer."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    import davey  # noqa: F401
    from discord.ext import voice_recv  # noqa: F401
except ImportError:
    DaveAudioReader = DaveVoiceRecvClient = None
else:
    from src.jade_runtime.discord_dave import (
        DaveAudioReader, DaveVoiceRecvClient, SafePacketDecoder, SafePacketRouter,
    )


@unittest.skipUnless(DaveAudioReader, "Discord voice extra not installed")
class DaveReceiveTests(unittest.TestCase):
    def setUp(self):
        self.session = SimpleNamespace(ready=True, decrypt=Mock(return_value=b"opus"))
        self.state = SimpleNamespace(dave_protocol_version=1, dave_session=self.session)
        self.client = SimpleNamespace(
            _connection=self.state, _get_id_from_ssrc=Mock(return_value=42),
            _ssrc_to_id={100: 42},
        )
        self.reader = DaveAudioReader.__new__(DaveAudioReader)
        self.reader.voice_client = self.client
        self.reader.error = None
        self.reader.decryptor = SimpleNamespace(decrypt_rtp=Mock(return_value=b"encrypted"),
                                                decrypt_rtcp=Mock(return_value=b"rtcp"))
        self.reader.packet_router = SimpleNamespace(feed_rtp=Mock(), feed_rtcp=Mock())
        self.reader.speaking_timer = SimpleNamespace(notify=Mock())
        self.packet = SimpleNamespace(ssrc=100, sequence=2, decrypted_data=None,
                                      is_silence=lambda: self.packet.decrypted_data == b"\xf8\xff\xfe")

    def receive(self):
        with patch("src.jade_runtime.discord_dave.rtp.is_rtcp", return_value=False), \
             patch("src.jade_runtime.discord_dave.rtp.decode_rtp", return_value=self.packet):
            self.reader.callback(b"rtp")

    def test_decrypts_once_before_forwarding_to_buffer(self):
        self.receive()
        self.session.decrypt.assert_called_once()
        self.assertEqual(self.session.decrypt.call_args.args[0], 42)
        self.assertEqual(self.session.decrypt.call_args.args[2], b"encrypted")
        self.assertEqual(self.packet.decrypted_data, b"opus")
        self.reader.packet_router.feed_rtp.assert_called_once_with(self.packet)

    def test_failed_missing_or_unready_session_and_sender_are_dropped(self):
        for session, sender in [(None, 42), (SimpleNamespace(ready=False), 42),
                                (self.session, None)]:
            with self.subTest(session=session, sender=sender):
                self.state.dave_session = session
                self.client._get_id_from_ssrc.return_value = sender
                self.receive()
                self.reader.packet_router.feed_rtp.assert_not_called()
        self.state.dave_session = self.session
        self.client._get_id_from_ssrc.return_value = 42
        self.session.decrypt.side_effect = ValueError("private details")
        with self.assertNoLogs("src.jade_runtime.discord_dave", level="DEBUG"):
            self.receive()
        self.reader.packet_router.feed_rtp.assert_not_called()

    def test_session_is_read_fresh_on_epoch_change(self):
        self.receive()
        next_session = SimpleNamespace(ready=True, decrypt=Mock(return_value=b"next opus"))
        self.state.dave_session = next_session
        self.receive()
        next_session.decrypt.assert_called_once()
        self.assertEqual(self.packet.decrypted_data, b"next opus")

    def test_fec_uses_already_decrypted_frame_without_decrypting_twice(self):
        from discord.ext.voice_recv.opus import PacketDecoder
        from discord.ext.voice_recv.rtp import FakePacket
        self.receive()
        decoder = PacketDecoder.__new__(PacketDecoder)
        decoder._buffer = SimpleNamespace(peek_next=lambda: self.packet)
        decoder._decoder = SimpleNamespace(decode=Mock(return_value=b"pcm"))
        decoder._decode_packet(FakePacket(100, 1, 960))
        decoder._decode_packet(self.packet)
        self.assertEqual(decoder._decoder.decode.call_count, 2)
        self.assertEqual(decoder._decoder.decode.call_args_list[0].args[0], b"opus")
        self.session.decrypt.assert_called_once()

    def test_decrypted_frame_decodes_with_real_opus_when_available(self):
        from discord.opus import Decoder, Encoder, OpusNotLoaded
        try:
            encoder, opus = Encoder(), Decoder()
        except (OpusNotLoaded, OSError):
            self.skipTest("native libopus unavailable")
        clear = encoder.encode(b"\x01\x00" * (Encoder.FRAME_SIZE // 2),
                               Encoder.SAMPLES_PER_FRAME)
        self.session.decrypt.return_value = clear
        self.receive()
        decoder = SafePacketDecoder.__new__(SafePacketDecoder)
        decoder._decoder = opus
        _, pcm = decoder._decode_packet(self.packet)
        self.assertEqual(len(pcm), Decoder.FRAME_SIZE)
        self.session.decrypt.assert_called_once()

    def test_plain_protocol_zero_and_silence(self):
        self.state.dave_protocol_version = 0
        self.receive()
        self.assertEqual(self.packet.decrypted_data, b"encrypted")
        self.session.decrypt.assert_not_called()
        self.state.dave_protocol_version = 1
        self.reader.decryptor.decrypt_rtp.return_value = b"\xf8\xff\xfe"
        self.receive()
        self.session.decrypt.assert_not_called()
        self.assertEqual(self.reader.packet_router.feed_rtp.call_count, 2)

    def test_unknown_protocol_or_bad_cleartext_is_dropped(self):
        self.state.dave_protocol_version = None
        self.receive()
        self.state.dave_protocol_version = 1
        self.session.decrypt.return_value = None
        self.receive()
        self.reader.packet_router.feed_rtp.assert_not_called()

    def test_rtcp_is_routed_without_dave(self):
        packet = object()
        with patch("src.jade_runtime.discord_dave.rtp.is_rtcp", return_value=True), \
             patch("src.jade_runtime.discord_dave.rtp.decode_rtcp", return_value=packet):
            self.reader.callback(b"rtcp")
        self.reader.packet_router.feed_rtcp.assert_called_once_with(packet)
        self.session.decrypt.assert_not_called()

    def test_transport_failure_does_not_log_exception_or_route(self):
        self.reader.decryptor.decrypt_rtp.side_effect = ValueError("private details")
        with self.assertLogs("src.jade_runtime.discord_dave", level="DEBUG") as logs:
            self.receive()
        self.assertNotIn("private details", str(logs.output))
        self.reader.packet_router.feed_rtp.assert_not_called()

    def test_client_builds_fresh_reader_for_each_listen(self):
        from discord.ext.voice_recv import AudioSink
        client = DaveVoiceRecvClient.__new__(DaveVoiceRecvClient)
        client.is_connected = Mock(return_value=True)
        client.is_listening = Mock(return_value=False)
        sink = Mock(spec=AudioSink)
        first, second = Mock(), Mock()
        with patch("src.jade_runtime.discord_dave.DaveAudioReader", side_effect=[first, second]) as reader:
            client.listen(sink)
            self.assertIs(client._reader, first)
            client.listen(sink)
            self.assertEqual(reader.call_count, 2)
            self.assertIs(client._reader, second)
            first.start.assert_called_once()
            second.start.assert_called_once()
            client.stop_listening()
            second.stop.assert_called_once()

    def test_corrupt_opus_uses_concealment_or_silence(self):
        from discord.opus import Decoder, OpusError
        error = OpusError.__new__(OpusError)
        decoder = SafePacketDecoder.__new__(SafePacketDecoder)
        decoder._decoder = SimpleNamespace(decode=Mock(side_effect=[error, b"recovered"]))
        packet, pcm = decoder._decode_packet(self.packet)
        self.assertIs(packet, self.packet)
        self.assertEqual(pcm, b"recovered")
        decoder._decoder.decode.side_effect = [error, error]
        _, pcm = decoder._decode_packet(self.packet)
        self.assertEqual(pcm, b"\x00" * Decoder.FRAME_SIZE)

    def test_old_router_cannot_stop_a_new_listener(self):
        client = SimpleNamespace(_reader=object(), stop_listening=Mock())
        reader = SimpleNamespace(voice_client=client, error=None)
        router = SafePacketRouter.__new__(SafePacketRouter)
        router.reader = reader
        router.waiter = SimpleNamespace(clear=Mock())
        router._do_run = Mock()
        router.run()
        client.stop_listening.assert_not_called()
        client._reader = reader
        router.run()
        client.stop_listening.assert_called_once()


if __name__ == "__main__":
    unittest.main()
