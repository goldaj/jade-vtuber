"""Offline acceptance of REC-006 progressive Discord PCM timing logs."""
import unittest
from unittest.mock import patch

from src.jade_runtime.pcm_timing import PCMProgressTiming, active_pcm_timing
from src.jade_runtime.realtime_tts import RealtimeTTS, RealtimeTTSError
from tests.test_jade_realtime_tts import FakeClient, configured, created, delta, transcript, done


class PCMProgressTimingTests(unittest.TestCase):
    def test_progressive_overlap_and_no_private_content(self):
        timing = PCMProgressTiming(started_at=100.0, tts_completed_at=101.5)
        data = timing.snapshot(100.2, playback_completed=True)
        self.assertEqual(data["first_pcm_ms"], 200)
        self.assertEqual(data["tts_completed_ms"], 1500)
        self.assertTrue(data["pcm_before_tts_complete"])
        self.assertEqual(data["verdict"], "progressive_confirmed")
        self.assertNotIn("text", str(data).lower())
        self.assertNotIn("audio", str(data).lower())

    def test_no_overlap_and_interrupted_are_not_misreported(self):
        timing = PCMProgressTiming(started_at=100.0, tts_completed_at=101.0)
        self.assertEqual(timing.snapshot(102.0, playback_completed=True)["verdict"],
                         "no_overlap_observed")
        self.assertEqual(timing.snapshot(100.2, playback_completed=False)["verdict"],
                         "progressive_observed_playback_incomplete")
        self.assertEqual(timing.snapshot(None, playback_completed=True)["verdict"],
                         "inconclusive")
        timing.tts_completed_at = None
        self.assertIsNone(timing.snapshot(100.3, playback_completed=True)["pcm_before_tts_complete"])

    def test_one_summary_and_audit_event_with_matching_fields(self):
        timing = PCMProgressTiming(started_at=100.0, tts_completed_at=101.0)
        with (patch("src.jade_runtime.pcm_timing.summary") as summary,
              patch("src.jade_runtime.pcm_timing.event") as event):
            timing.log(100.25, playback_completed=True)
        summary.assert_called_once()
        event.assert_called_once()
        self.assertEqual(summary.call_args.args, ("rec006_pcm_progress",))
        self.assertEqual(summary.call_args.kwargs, event.call_args.kwargs)


class RealtimeTTSCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_marks_completed_response_for_active_stream(self):
        client = FakeClient([configured(), created(), delta(b"\x04\x00" * 20),
                             transcript(), done()])
        timing = PCMProgressTiming()
        token = active_pcm_timing.set(timing)
        try:
            data = [piece async for piece in RealtimeTTS(
                client, verify_transcript=False).stream_pcm("Bonjour.")]
        finally:
            active_pcm_timing.reset(token)
        self.assertTrue(data)
        self.assertIsNotNone(timing.tts_completed_at)
        self.assertGreaterEqual(timing.tts_completed_at, timing.started_at)

    async def test_rejected_response_does_not_claim_tts_completion(self):
        client = FakeClient([configured(), created(), delta(b"\x04\x00" * 20),
                             {"type": "error", "error": {"message": "secret"}}])
        timing = PCMProgressTiming()
        token = active_pcm_timing.set(timing)
        try:
            with self.assertRaises(RealtimeTTSError):
                async for _ in RealtimeTTS(
                    client, verify_transcript=False).stream_pcm("Bonjour."):
                    pass
        finally:
            active_pcm_timing.reset(token)
        self.assertIsNone(timing.tts_completed_at)


class MobileProgressTests(unittest.TestCase):
    def test_mobile_socket_transmitted_before_tts_finished(self):
        from src.jade_runtime.pcm_timing import log_mobile_progress
        timing = PCMProgressTiming(started_at=100.0, tts_completed_at=102.0)
        with (patch("src.jade_runtime.pcm_timing.summary") as summary,
              patch("src.jade_runtime.pcm_timing.event") as event):
            log_mobile_progress(timing, 100.5, transfer_completed=True, transport="websocket")
        values = summary.call_args.kwargs
        self.assertEqual(summary.call_args.args, ("rec029_mobile_pcm_progress",))
        self.assertEqual(values["first_pcm_sent_ms"], 500)
        self.assertEqual(values["tts_completed_ms"], 2000)
        self.assertTrue(values["pcm_sent_before_tts_complete"])
        self.assertEqual(values["verdict"], "progressive_transport_confirmed")
        self.assertEqual(values, event.call_args.kwargs)

    def test_wav_transport_without_pcm_is_inconclusive(self):
        from src.jade_runtime.pcm_timing import log_mobile_progress
        timing = PCMProgressTiming(started_at=100.0)
        with patch("src.jade_runtime.pcm_timing.summary") as summary:
            log_mobile_progress(timing, None, transfer_completed=True, transport="http_ndjson")
        self.assertEqual(summary.call_args.kwargs["verdict"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
