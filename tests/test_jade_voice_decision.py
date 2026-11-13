"""Synthetic voice decisions; no network, audio or real transcripts."""
import unittest

from src.jade_runtime.voice_decision import ConversationTurnDecider


class VoiceDecisionTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.policy = ConversationTurnDecider(clock=lambda: self.now, ttl=120,
                                               follow_up_seconds=30, max_sessions=2)
        self.session = "a" * 32

    def decide(self, text, *, session=None, speaker=1, participants=1, **kwargs):
        return self.policy.decide(session or self.session, speaker, text,
                                  authorized=kwargs.pop("authorized", True),
                                  consent_confirmed=kwargs.pop("consent_confirmed", True),
                                  participant_count=participants, **kwargs)

    def test_private_solo_accepts_normal_speech_without_any_name(self):
        for text in ("Salut", "Tu penses quoi de ça ?", "Et pourquoi ?", "Oui", "Attends"):
            with self.subTest(text=text):
                self.assertTrue(self.decide(text).should_reply)

    def test_noise_invalid_input_and_apartes_are_ignored(self):
        for text in ("", "...", "euh", "HUM", "!", "[musique]", "Je pense tout haut", "Ce n'est pas pour toi"):
            with self.subTest(text=text):
                self.assertFalse(self.decide(text).should_reply)
        self.assertEqual(self.decide("bonjour", authorized=False).reason, "not_authorized")
        self.assertEqual(self.decide("bonjour", consent_confirmed=False).reason, "not_authorized")
        self.assertEqual(self.decide("bonjour", is_bot=True).reason, "not_authorized")
        self.assertFalse(self.decide("a" * 4001).should_reply)

    def test_denied_turn_never_creates_a_session(self):
        self.decide("private test words", authorized=False)
        self.assertEqual(len(self.policy._sessions), 0)

    def test_silence_and_resume_are_session_specific(self):
        first = self.decide("bonjour")
        self.assertTrue(first.should_reply)
        self.assertEqual(self.decide("Arrête de parler !").reason, "muted")
        self.assertFalse(self.policy.mark_replied(self.session, first.turn_id))
        self.assertEqual(self.decide("Tu peux m'aider ?").reason, "muted")
        self.assertTrue(self.decide("Salut", session="b" * 32).should_reply)
        self.assertEqual(self.decide("Tu peux reprendre").reason, "resumed")
        self.assertTrue(self.decide("Et pourquoi ?").should_reply)

    def test_muted_sessions_survive_ttl_and_capacity_pressure(self):
        self.assertEqual(self.decide("silence").reason, "muted")
        self.assertEqual(self.decide("silence", session="b" * 32).reason, "muted")
        self.now += 1000
        self.assertEqual(self.decide("bonjour").reason, "muted")
        self.assertEqual(self.decide("bonjour", session="c" * 32).reason, "session_capacity")
        self.assertEqual(self.decide("reprends").reason, "resumed")
        self.assertTrue(self.decide("bonjour").should_reply)

    def test_group_requires_trusted_address_or_confirmed_same_speaker_followup(self):
        self.assertEqual(self.decide("silence", participants=2).reason, "ambiguous_group")
        self.assertEqual(self.decide("Quel temps fait-il ?", participants=2).reason,
                         "ambiguous_group")
        addressed = self.decide("Tu peux m'aider ?", participants=2, direct_address=True)
        self.assertTrue(addressed.should_reply)
        self.assertFalse(self.decide("Et pourquoi ?", participants=2).should_reply)
        self.assertTrue(self.policy.mark_replied(self.session, addressed.turn_id))
        self.assertTrue(self.decide("Et pourquoi ?", participants=2).should_reply)
        self.assertFalse(self.decide("Et pourquoi ?", participants=2, speaker=2).should_reply)
        self.now += 31
        self.assertFalse(self.decide("Et pourquoi ?", participants=2).should_reply)

    def test_session_revoke_expiry_and_capacity_forget_prior_context(self):
        first = self.decide("Tu peux m'aider ?", participants=2, direct_address=True)
        self.assertTrue(self.policy.mark_replied(self.session, first.turn_id))
        self.policy.revoke(self.session)
        self.assertFalse(self.decide("Et pourquoi ?", participants=2).should_reply)
        self.decide("bonjour", session="b" * 32)
        self.decide("bonjour", session="c" * 32)
        self.assertLessEqual(len(self.policy._sessions), 2)
        self.now += 121
        self.decide("bonjour", session="d" * 32)
        self.assertEqual(len(self.policy._sessions), 1)

    def test_late_or_unknown_response_cannot_start_followup(self):
        accepted = self.decide("bonjour", participants=2, direct_address=True)
        self.assertFalse(self.policy.mark_replied(self.session, "unknown"))
        self.now += 121
        self.assertFalse(self.policy.mark_replied(self.session, accepted.turn_id))
        self.assertFalse(self.decide("Et pourquoi ?", participants=2).should_reply)

    def test_transcript_is_not_retained_in_session_state(self):
        marker = "phrases synthétiques confidentielles"
        self.assertTrue(self.decide(marker).should_reply)
        self.assertNotIn(marker, repr(self.policy._sessions))
        state = self.policy._sessions[self.session]
        self.assertNotIn(marker, str(vars(state)))


if __name__ == "__main__":
    unittest.main()
