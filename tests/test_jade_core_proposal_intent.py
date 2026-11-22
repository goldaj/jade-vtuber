"""Regression: Core requests are proposals, while owner L2 remains mandatory.

Uses unittest so the repository's offline unittest discovery has no pytest dependency.
"""
import unittest

from src.jade_runtime.explicit_memory_intent import parse_explicit_memory_intent


class CoreProposalIntentTests(unittest.TestCase):
    def test_explicit_core_request_is_only_a_proposal(self):
        phrases = (
            "Jade, enregistre dans tes Core Memories que tu es née en 2025.",
            "Jade, mets dans ta mémoire de niveau 3 que tu es née en 2025.",
            "Jade, mets dans ton core memory que tu es née en 2025.",
            "Jade, ajoute en souvenirs de niveau 3 que tu es née en 2025.",
            "Jade, conserve dans tes souvenirs fondateurs que tu es née en 2025.",
            "Jade, garde comme core memories que tu es née en 2025.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                intent = parse_explicit_memory_intent(phrase)
                self.assertIsNotNone(intent)
                self.assertTrue(intent.requested_core)
                self.assertIn("2025", intent.summary)

    def test_explicit_ordinary_level_2_is_mandatory_only_for_owner(self):
        phrases = (
            "Retiens que je commence le piano.",
            "Jade, enregistre dans ta mémoire ordinaire que je commence le piano.",
            "Jade, note dans tes souvenirs que je commence le piano.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                intent = parse_explicit_memory_intent(phrase)
                self.assertIsNotNone(intent)
                self.assertFalse(intent.requested_core)
                self.assertIn("piano", intent.summary)


if __name__ == "__main__":
    unittest.main()
