import unittest

from src.jade_runtime.live_voice import JADE_VOICE_PROMPT, prepare_voice_review


class LiveVoicePreparationTests(unittest.TestCase):
    def test_prompt_at_documented_limit_prepares_without_creating_a_voice(self):
        result = prepare_voice_review(prompt="a" * 2000)
        self.assertEqual(len(result["request"]["json"]["prompt"]), 2000)
        self.assertEqual(result["status"], "prepared_only")
        self.assertFalse(result["voice_created"])
        self.assertFalse(result["audio_listened"])

    def test_prompt_exceeding_documented_api_limit_is_rejected(self):
        for prompt in ("a" * 2001, "a" * 4000, "   "):
            with self.subTest(length=len(prompt)), self.assertRaises(ValueError):
                prepare_voice_review(prompt=prompt)

    def test_original_jade_prompt_remains_valid_after_trimming(self):
        result = prepare_voice_review(prompt="  " + JADE_VOICE_PROMPT + "  ")
        self.assertEqual(result["request"]["json"]["prompt"], JADE_VOICE_PROMPT)
        self.assertEqual(result["request"]["json"]["type"], "prompt")
        self.assertLessEqual(len(JADE_VOICE_PROMPT), 2000)


if __name__ == "__main__":
    unittest.main()
