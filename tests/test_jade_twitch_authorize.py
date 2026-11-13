"""Device authorization is tested offline with synthetic responses."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.jade_runtime.twitch_token import TwitchIdentity
from tools.jade_twitch_authorize import AuthorizationError, DEVICE_URL, TOKEN_URL, authorize


class TwitchAuthorizationTests(unittest.TestCase):
    def test_pending_then_success_creates_private_new_file_without_printing_tokens(self):
        responses = [
            (200, {"user_code": "ABCD1234", "device_code": "synthetic-device-code",
                   "interval": 1, "expires_in": 30}),
            (400, {"message": "authorization_pending"}),
            (200, {"access_token": "synthetic_access_token", "refresh_token": "synthetic_refresh_token"}),
        ]
        calls, shown, tick = [], [], [0]
        def post(url, params):
            calls.append((url, params.copy()))
            return responses.pop(0)
        def sleep(seconds): tick[0] += seconds
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new.env"
            with patch("tools.jade_twitch_authorize.validate_twitch_token", return_value=TwitchIdentity(login="testbot", can_send=True)) as validate:
                result = authorize("client123", output, allow_send=True, post=post,
                                   now=lambda: tick[0], sleep=sleep, prompt=shown.append)
            self.assertEqual(result, output.resolve())
            self.assertEqual(calls[0][0], DEVICE_URL)
            self.assertEqual(calls[1][0], TOKEN_URL)
            self.assertEqual(calls[0][1]["scopes"], "chat:read chat:edit")
            validate.assert_called_once_with("synthetic_access_token", send_enabled=True)
            self.assertIn("TWITCH_BOT_LOGIN=testbot", output.read_text(encoding="utf-8"))
            self.assertNotIn("synthetic_access_token", str(shown))
            self.assertNotIn("synthetic_refresh_token", str(shown))
            self.assertNotIn("synthetic-device-code", str(shown))

    def test_existing_file_never_overwritten_or_network_called(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.env"
            output.write_text("original", encoding="utf-8")
            with self.assertRaises(AuthorizationError):
                authorize("client123", output, post=lambda *args: self.fail("network called"))
            self.assertEqual(output.read_text(encoding="utf-8"), "original")

    def test_refusal_deletes_placeholder_and_hides_server_message(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new.env"
            with self.assertRaises(AuthorizationError) as caught:
                authorize("client123", output, post=lambda *args: (400, {"message": "sensitive-server-body"}))
            self.assertNotIn("sensitive-server-body", str(caught.exception))
            self.assertFalse(output.exists())

    def test_rejects_output_inside_git_checkout(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(AuthorizationError):
            authorize("client123", root / "forbidden.env", post=lambda *args: self.fail("network called"))


if __name__ == "__main__":
    unittest.main()
