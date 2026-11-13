"""Read-only Twitch token validation uses synthetic credentials only."""
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.jade_runtime.twitch_token import (
    TwitchTokenError, TwitchValidationUnavailable, _fetch_metadata,
    validate_twitch_token,
)
from src.jade_runtime.twitch_irc import TwitchIRC


class TwitchTokenTests(unittest.TestCase):
    def test_irc_uses_same_case_insensitive_oauth_prefix(self):
        client = TwitchIRC(login="bot", token="OAuth:synthetic", channel="channel",
                           on_message=lambda message: None)
        self.assertEqual(client.token, "synthetic")

    def test_derives_login_and_requires_edit_only_for_send(self):
        with patch("src.jade_runtime.twitch_token._fetch_metadata", return_value={
            "login": "ExampleBot", "scopes": ["chat:read"]
        }) as fetch:
            identity = validate_twitch_token("oauth:synthetic-token")
            self.assertEqual(identity.login, "examplebot")
            self.assertNotIn("ExampleBot", repr(identity))
            self.assertFalse(identity.can_send)
            fetch.assert_called_with("synthetic-token")
            with self.assertRaisesRegex(TwitchTokenError, "chat:edit"):
                validate_twitch_token("synthetic-token", send_enabled=True)

    def test_login_mismatch_and_missing_read_fail_closed(self):
        with patch("src.jade_runtime.twitch_token._fetch_metadata", return_value={
            "login": "Bot", "scopes": ["chat:read", "chat:edit"]
        }):
            self.assertTrue(validate_twitch_token("fake", login="BOT", send_enabled=True).can_send)
            with self.assertRaisesRegex(TwitchTokenError, "does not match"):
                validate_twitch_token("fake", login="another")
        with patch("src.jade_runtime.twitch_token._fetch_metadata", return_value={
            "login": "bot", "scopes": []
        }):
            with self.assertRaisesRegex(TwitchTokenError, "chat:read"):
                validate_twitch_token("fake")

    def test_invalid_or_app_token_and_bad_response_fail_closed(self):
        with self.assertRaises(TwitchTokenError):
            validate_twitch_token("  ")
        with patch("src.jade_runtime.twitch_token._fetch_metadata", return_value={
            "scopes": ["chat:read"]
        }):
            with self.assertRaises(TwitchTokenError):
                validate_twitch_token("fake")
        with patch("src.jade_runtime.twitch_token._fetch_metadata", return_value={
            "login": "bot", "scopes": None
        }):
            with self.assertRaises(TwitchValidationUnavailable):
                validate_twitch_token("fake")

    def test_http_failure_never_includes_sensitive_error_body(self):
        synthetic = "sensitive-error-content"
        error = HTTPError("https://example.invalid", 401, synthetic, {}, io.BytesIO(synthetic.encode()))
        with patch("src.jade_runtime.twitch_token.build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(TwitchTokenError) as caught:
                _fetch_metadata("synthetic-token")
            self.assertNotIn(synthetic, str(caught.exception))
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://id.twitch.tv/oauth2/validate")
            self.assertNotIn("synthetic-token", request.full_url)
        with patch("src.jade_runtime.twitch_token.build_opener") as opener:
            opener.return_value.open.side_effect = URLError(synthetic)
            with self.assertRaises(TwitchValidationUnavailable) as caught:
                _fetch_metadata("synthetic-token")
            self.assertNotIn(synthetic, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
