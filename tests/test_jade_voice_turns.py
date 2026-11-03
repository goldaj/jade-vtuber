import struct
import unittest

from src.jade_runtime.voice_turns import PcmTurnSegmenter


def pcm(seconds, amplitude):
    return struct.pack('<hh', amplitude, amplitude) * int(seconds * 48000)


class SegmentationTests(unittest.TestCase):
    def test_short_phrase_flushes_by_timer_without_more_packets(self):
        segmenter = PcmTurnSegmenter()
        phrase = pcm(1.2, 1500)
        self.assertEqual(segmenter.feed('a', phrase, now=1), [])
        self.assertEqual(segmenter.poll(now=1.69), [])
        out = segmenter.poll(now=1.71)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].pcm, phrase)
        self.assertFalse(out[0].partial)
        self.assertEqual(segmenter.poll(now=2), [])

    def test_long_phrase_splits_into_bounded_partial_and_final(self):
        s = PcmTurnSegmenter(max_turn_s=1, min_speech_s=.1)
        out = s.feed('a', pcm(2.4, 1500), now=1)
        self.assertEqual([x.partial for x in out], [True, True])
        out += s.poll(now=2)
        self.assertEqual([len(x.pcm) for x in out], [192000, 192000, 76800])
        self.assertEqual([x.partial for x in out], [True, True, False])

    def test_limit_boundary_and_short_tail_end_with_final_fragment(self):
        for duration in (1, 1.05):
            with self.subTest(duration=duration):
                s = PcmTurnSegmenter(max_turn_s=1, min_speech_s=.1)
                phrase = pcm(duration, 1500)
                out = s.feed('a', phrase, now=1)
                self.assertEqual([x.partial for x in out], [True])
                out += s.poll(now=2)
                self.assertEqual([x.partial for x in out], [True, False])
                self.assertEqual(b''.join(x.pcm for x in out), phrase)
                self.assertTrue(all(len(x.pcm) <= 192000 for x in out))
                self.assertEqual(s.poll(now=3), [])

    def test_continuation_closes_on_silence_and_revoke_discards_it(self):
        s = PcmTurnSegmenter(max_turn_s=1, end_silence_s=.2)
        out = s.feed('a', pcm(1, 1500) + pcm(.2, 0), now=1)
        self.assertEqual([x.partial for x in out], [True, False])
        self.assertEqual(len(out[-1].pcm), len(pcm(.2, 0)))
        self.assertEqual(s.poll(now=2), [])
        self.assertTrue(s.feed('a', pcm(1, 1500), now=3)[0].partial)
        s.revoke('a')
        self.assertEqual(s.poll(now=4), [])

    def test_silence_noise_and_brief_click(self):
        s = PcmTurnSegmenter()
        self.assertEqual(s.feed('a', pcm(1, 0) + pcm(1, 100), now=1), [])
        self.assertEqual(s.feed('a', pcm(.04, 2000), now=2), [])
        self.assertEqual(s.poll(now=3), [])

    def test_silent_pcm_closes_turn_without_waiting_for_timer(self):
        s = PcmTurnSegmenter(end_silence_s=.2)
        out = s.feed('a', pcm(.2, 1500) + pcm(.3, 0), now=1)
        self.assertEqual(len(out), 1)
        self.assertFalse(out[0].partial)

    def test_two_users_are_isolated(self):
        s = PcmTurnSegmenter()
        s.feed('a', pcm(.2, 1000), now=1)
        s.feed('b', pcm(.3, 2000), now=1.5)
        out = s.poll(now=1.8)
        self.assertEqual([x.user_id for x in out], ['a'])
        self.assertEqual([x.user_id for x in s.poll(now=2.3)], ['b'])

    def test_capacity_and_revocation(self):
        s = PcmTurnSegmenter(max_users=1)
        s.feed('a', pcm(.2, 1200), now=1)
        with self.assertRaises(ValueError):
            s.feed('b', pcm(.2, 1200), now=1)
        s.revoke('a')
        s.feed('b', pcm(.2, 1200), now=1)
        s.revoke()
        self.assertEqual(s.poll(now=2), [])

    def test_validation_and_timestamp(self):
        for kwargs in ({'max_users': 0}, {'max_turn_s': 31}, {'rms_threshold': 0},
                       {'min_speech_s': 2, 'max_turn_s': 1}):
            with self.assertRaises(ValueError):
                PcmTurnSegmenter(**kwargs)
        s = PcmTurnSegmenter()
        with self.assertRaises(ValueError):
            s.feed('a', b'123', now=1)
        s.feed('a', pcm(.2, 1000), now=2)
        with self.assertRaises(ValueError):
            s.poll(now=1)

    def test_no_audio_in_repr(self):
        s = PcmTurnSegmenter()
        s.feed('a', pcm(.2, 1000), now=1)
        result = s.poll(now=2)[0]
        self.assertNotIn('pcm=', repr(result))
        self.assertNotIn('user_id', repr(result))


if __name__ == '__main__':
    unittest.main()
