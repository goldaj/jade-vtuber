from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from src.jade_runtime.live_config import LiveConfig
from src.jade_runtime.live_voice import LiveVoice, JADE_VOICE_PROMPT, VOICE_REVIEW_CORPUS, prepare_voice_review


class LiveConfigTests(unittest.TestCase):
    def test_defaults_never_enable_paid_live_or_discord(self):
        keys = []

        def get(key, default):
            keys.append(key)
            return default

        config = LiveConfig.from_env(get)
        self.assertFalse(config.enabled)
        self.assertTrue(config.mobile_enabled)
        self.assertFalse(config.discord_enabled)
        self.assertEqual(config.daily_usd, Decimal(0))
        self.assertFalse(config.preflight(api_key_present=True)["available"])
        self.assertNotIn("OPENAI_API_KEY", keys)

    def test_explicit_budget_and_key_are_needed_for_admission(self):
        values = {"JADE_LIVE_ENABLED": "true", "JADE_LIVE_DAILY_USD": "1.25",
                  "JADE_LIVE_MONTHLY_USD": "10.5"}
        config = LiveConfig.from_env(values.get)
        self.assertEqual(config.daily_usd, Decimal("1.25"))
        self.assertTrue(config.preflight(api_key_present=True)["available"])
        self.assertFalse(config.preflight(api_key_present=False)["available"])

    def test_empty_example_budget_path_uses_private_default(self):
        defaults = LiveConfig.from_env({}.get)
        for empty in ("", "   "):
            with self.subTest(value=empty):
                config = LiveConfig.from_env({"JADE_LIVE_BUDGET_DB_PATH": empty}.get)
                self.assertEqual(config.budget_db_path, defaults.budget_db_path)
                self.assertTrue(Path(config.budget_db_path).is_absolute())

    def test_discord_flag_does_not_claim_missing_adapter_exists(self):
        config = replace(LiveConfig(), enabled=True, daily_usd=Decimal(1),
                         monthly_usd=Decimal(1), discord_enabled=True)
        result = config.preflight(api_key_present=True)
        self.assertIn("discord_adapter_unavailable", result["reasons"])
        self.assertFalse(result["available"])

    def test_invalid_config_is_fail_closed(self):
        bad = (
            {"enabled": 1}, {"heartbeat_seconds": float("nan")},
            {"lease_seconds": 4}, {"idle_standby_seconds": 8.5},
            {"idle_standby_seconds": 4}, {"idle_close_seconds": 8},
            {"max_starts_per_minute": 0}, {"max_delegations_per_session": True},
            {"opening_timeout_seconds": float("inf")},
            {"daily_usd": Decimal("NaN")}, {"monthly_usd": Decimal(-1)},
            {"daily_usd": Decimal(2), "monthly_usd": Decimal(1)},
            {"model": "gpt-realtime-2.1-mini"}, {"voice": "aube"},
            {"budget_db_path": "state.sqlite3"},
        )
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(LiveConfig(), **changes).validate()

    def test_config_cannot_put_private_ledger_in_git(self):
        path = Path(__file__).resolve().parents[1] / "unsafe.sqlite3"
        with self.assertRaises(ValueError):
            replace(LiveConfig(), budget_db_path=str(path)).validate()
        self.assertFalse(path.exists())

    def test_config_accepts_external_private_paths_without_creating_them(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new" / "budget.sqlite3"
            config = replace(LiveConfig(), budget_db_path=str(path))
            config.validate()
            self.assertFalse(path.parent.exists())

    def test_session_contract_is_live_client_delegation_and_no_client_commands(self):
        history = [{"type": "message", "role": "user",
                    "content": [{"type": "input_text", "text": "Bonjour"}]}]
        payload = LiveConfig().session_config(instructions="Jade", input=history)
        self.assertEqual(payload["model"], "gpt-live-1.1")
        self.assertEqual(payload["delegation"]["type"], "client")
        self.assertFalse(payload["store"])
        self.assertEqual(payload["wake_policy"], {"type": "speech"})
        self.assertEqual(payload["idle_timeout_s"], 8)
        self.assertNotIn("format", payload["audio"])
        self.assertEqual(payload["client"]["data_channel"]["allowed_client_events"], [])
        self.assertEqual(payload["input"], history)

    def test_voice_selection_never_invents_aube_identifier_or_alias(self):
        selection = LiveVoice()
        self.assertEqual(selection.api_value(), "brise")
        status = selection.public_status()
        self.assertEqual(status["requested_prototype"], "Aube")
        self.assertTrue(status["fallback"])
        self.assertFalse(status["aube_api_verified"])
        with self.assertRaises(ValueError):
            LiveVoice("aube").api_value()
        custom = LiveVoice(custom_id="voice_saved_123")
        self.assertEqual(custom.api_value(), {"id": "voice_saved_123"})
        self.assertNotIn("voice_saved_123", str(custom.public_status()))
        self.assertTrue(JADE_VOICE_PROMPT)
        self.assertEqual(len(VOICE_REVIEW_CORPUS), 7)

    def test_voice_packet_is_an_offline_plan_not_a_created_or_previewed_voice(self):
        packet = prepare_voice_review()
        self.assertEqual(packet["request"]["json"]["type"], "prompt")
        self.assertFalse(packet["voice_created"])
        self.assertFalse(packet["audio_listened"])
        self.assertNotIn("id", packet["request"]["json"])
        self.assertEqual(len(packet["corpus"]), 7)
        with self.assertRaises(ValueError):
            prepare_voice_review(prompt=" ")


if __name__ == "__main__":
    unittest.main()
