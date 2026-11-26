from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from src.jade_runtime.live_config import LiveConfig
from src.jade_runtime.live_voice import LiveVoice, JADE_VOICE_PROMPT, VOICE_REVIEW_CORPUS, prepare_voice_review


class LiveConfigTests(unittest.TestCase):
    def test_defaults_enable_mobile_live_without_enabling_discord_or_reading_keys(self):
        keys = []

        def get(key, default):
            keys.append(key)
            return default

        config = LiveConfig.from_env(get)
        self.assertTrue(config.enabled)
        self.assertTrue(config.mobile_enabled)
        self.assertFalse(config.discord_enabled)
        self.assertTrue(config.preflight(api_key_present=True)["available"])
        self.assertFalse(hasattr(config, "daily_usd"))
        self.assertFalse(hasattr(config, "monthly_usd"))
        self.assertFalse(hasattr(config, "backend_reservation_usd"))
        self.assertNotIn("OPENAI_API_KEY", keys)

    def test_old_financial_settings_are_ignored_even_when_zero_or_invalid(self):
        obsolete = {"JADE_LIVE_DAILY_USD", "JADE_LIVE_MONTHLY_USD",
                    "JADE_LIVE_BACKEND_RESERVATION_USD"}
        for value in ("0", "-1", "NaN", "invalid", "999999999"):
            with self.subTest(value=value):
                requested = []

                def get(key, default):
                    requested.append(key)
                    return value if key in obsolete else default

                config = LiveConfig.from_env(get)
                self.assertTrue(config.preflight(api_key_present=True)["available"])
                self.assertTrue(obsolete.isdisjoint(requested))

    def test_key_and_explicit_off_are_still_respected(self):
        config = LiveConfig.from_env({}.get)
        self.assertTrue(config.preflight(api_key_present=True)["available"])
        self.assertFalse(config.preflight(api_key_present=False)["available"])
        config = LiveConfig.from_env({"JADE_LIVE_ENABLED": "0"}.get)
        self.assertEqual(config.preflight(api_key_present=True)["reasons"], ["live_disabled"])

    def test_empty_usage_path_uses_private_default_and_old_path_is_migration_alias(self):
        defaults = LiveConfig.from_env({}.get)
        for empty in ("", "   "):
            with self.subTest(value=empty):
                config = LiveConfig.from_env({"JADE_LIVE_USAGE_DB_PATH": empty,
                                              "JADE_LIVE_BUDGET_DB_PATH": empty}.get)
                self.assertEqual(config.usage_db_path, defaults.usage_db_path)
                self.assertTrue(Path(config.usage_db_path).is_absolute())
        with tempfile.TemporaryDirectory() as directory:
            old = str(Path(directory) / "old.sqlite3")
            new = str(Path(directory) / "usage.sqlite3")
            self.assertEqual(LiveConfig.from_env({"JADE_LIVE_BUDGET_DB_PATH": old}.get).usage_db_path, old)
            config = LiveConfig.from_env({"JADE_LIVE_USAGE_DB_PATH": new,
                                          "JADE_LIVE_BUDGET_DB_PATH": old}.get)
            self.assertEqual(config.usage_db_path, new)

    def test_discord_flag_does_not_claim_missing_adapter_exists(self):
        config = replace(LiveConfig(), discord_enabled=True)
        result = config.preflight(api_key_present=True)
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["available"])
        self.assertFalse(result["discord"]["available"])
        self.assertEqual(result["discord"]["reason"], "discord_adapter_unavailable")

    def test_invalid_config_is_fail_closed(self):
        bad = (
            {"enabled": 1}, {"heartbeat_seconds": float("nan")},
            {"lease_seconds": 4}, {"idle_standby_seconds": 8.5},
            {"idle_standby_seconds": 4}, {"idle_close_seconds": 8},
            {"max_starts_per_minute": 0}, {"max_delegations_per_session": True},
            {"opening_timeout_seconds": float("inf")},
            {"model": "gpt-realtime-2.1-mini"}, {"voice": "aube"},
            {"usage_db_path": "state.sqlite3"},
        )
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(LiveConfig(), **changes).validate()

    def test_config_cannot_put_private_ledger_in_git(self):
        path = Path(__file__).resolve().parents[1] / "unsafe.sqlite3"
        with self.assertRaises(ValueError):
            replace(LiveConfig(), usage_db_path=str(path)).validate()
        self.assertFalse(path.exists())

    def test_config_accepts_external_private_paths_without_creating_them(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new" / "usage.sqlite3"
            config = replace(LiveConfig(), usage_db_path=str(path))
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
