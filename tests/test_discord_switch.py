"""One operator switch governs Discord without changing mobile preferences."""
import unittest
from unittest.mock import AsyncMock, patch

import main
from src.jade_runtime import discord_config
from src.jade_runtime.config import Settings
from src.jade_runtime.diagnostics import inspect_environment
from src.jade_runtime.discord_config import selected_discord_channels
from src.jade_runtime.live_config import LiveConfig


class DiscordMasterSwitchTests(unittest.TestCase):
    def test_code_switch_overrides_all_historical_private_discord_flags(self):
        legacy = {"JADE_DISCORD_ENABLED": "1", "JADE_DISCORD_LIVE_ENABLED": "1",
                  "JADE_DISCORD_SEND": "1", "JADE_DISCORD_VOICE_ENABLED": "1"}
        for enabled in (False, True):
            with self.subTest(enabled=enabled), patch.object(discord_config, "DISCORD_ENABLED", enabled), \
                    patch("src.jade_runtime.config.environ", side_effect=lambda k, d: legacy.get(k, d)):
                settings = Settings.load()
                self.assertEqual(settings.discord_enabled, enabled)
                self.assertEqual(settings.live.discord_enabled, enabled)
                self.assertTrue(settings.live.enabled)
                self.assertTrue(settings.live.mobile_enabled)

    def test_false_disables_both_transports_and_true_preserves_cli_selection(self):
        for text in (False, True):
            for voice in (False, True):
                self.assertEqual(selected_discord_channels(False, text, voice), (False, False))
                self.assertEqual(selected_discord_channels(True, text, voice), (text, voice))

    def test_mobile_off_does_not_disable_discord_policy_capability(self):
        with patch.object(discord_config, "DISCORD_ENABLED", True):
            config = LiveConfig.from_env({"JADE_LIVE_ENABLED": "0",
                                          "JADE_MOBILE_LIVE_ENABLED": "0"}.get)
        status = config.preflight(api_key_present=True)
        self.assertFalse(status["available"])
        self.assertTrue(status["discord"]["available"])
        self.assertTrue(status["discord"]["monthly_policy_required"])

    def test_disabled_discord_preflight_needs_no_token_or_discord_packages(self):
        with patch.object(discord_config, "DISCORD_ENABLED", False):
            settings = Settings()
        with patch("src.jade_runtime.diagnostics._discord_stack_ok", side_effect=AssertionError("not selected")):
            checks = inspect_environment(settings, discord=True, discord_voice=True)
        self.assertTrue(all(check.ok for check in checks))
        self.assertTrue(any(check.name == "Discord désactivé" for check in checks))

    def test_all_channels_and_explicit_cli_flags_cannot_bypass_off(self):
        for flags in (["--all-channels"], ["--live", "--discord", "--discord-voice"]):
            with self.subTest(flags=flags), patch.object(discord_config, "DISCORD_ENABLED", False):
                settings = Settings()
                console = AsyncMock()
                with patch("sys.argv", ["main.py", *flags]), \
                        patch("main.start_session_logging"), \
                        patch("main.Settings.load", return_value=settings), \
                        patch("main.console", console):
                    main.main()
                self.assertFalse(console.await_args.kwargs["discord"])
                self.assertFalse(console.await_args.kwargs["discord_voice"])
                if "--all-channels" in flags:
                    self.assertTrue(console.await_args.kwargs["mobile"])


if __name__ == "__main__":
    unittest.main()
