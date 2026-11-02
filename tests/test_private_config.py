import contextlib
import importlib
import io
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.utility import private_config


class PrivateConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env_file = Path(self.temp.name) / 'private.env'
        self.env_file.write_text('TWITCH_TOKEN=old-access\nTWITCH_REFRESH_TOKEN=old-refresh\n', encoding='utf-8')
        self.environment = patch.dict(os.environ, {'JADE_SECRETS_FILE': str(self.env_file)}, clear=True)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def test_environment_overrides_private_file_and_missing_keys_have_defaults(self):
        self.assertEqual(private_config.environ('TWITCH_TOKEN'), 'old-access')
        os.environ['TWITCH_TOKEN'] = 'process-access'
        self.assertEqual(private_config.environ('TWITCH_TOKEN'), 'process-access')
        self.assertEqual(private_config.environ('UNCONFIGURED', 'fallback'), 'fallback')

    def test_refreshed_tokens_are_persisted_only_in_selected_private_file(self):
        source_path = Path(private_config.__file__)
        source_before = source_path.read_bytes()
        private_config.save_twitch_tokens('new-access', 'new-refresh')
        self.assertEqual(private_config.environ('TWITCH_TOKEN'), 'new-access')
        self.assertEqual(private_config.environ('TWITCH_REFRESH_TOKEN'), 'new-refresh')
        with patch.dict(os.environ, {'JADE_SECRETS_FILE': str(self.env_file)}, clear=True):
            self.assertEqual(private_config.environ('TWITCH_TOKEN'), 'new-access')
            self.assertEqual(private_config.environ('TWITCH_REFRESH_TOKEN'), 'new-refresh')
        self.assertEqual(source_path.read_bytes(), source_before)

    def test_missing_file_uses_default_without_creating_a_file(self):
        self.env_file.unlink()
        self.assertEqual(private_config.environ('UNCONFIGURED', 'fallback'), 'fallback')
        self.assertFalse(self.env_file.exists())


class TwitchRefreshTests(unittest.TestCase):
    def test_success_persists_both_tokens_without_rewriting_credentials_source(self):
        fake_credentials = types.ModuleType('src.utility.credentials')
        fake_credentials.TWITCH_CLIENT_ID = 'test-client'
        fake_credentials.TWITCH_CLIENT_SECRET = 'test-secret'
        fake_credentials.TWITCH_REFRESH_TOKEN = 'old-refresh'
        with patch.dict('sys.modules', {'src.utility.credentials': fake_credentials}):
            module = importlib.import_module('src.twitch.twitch_auth')
        response = Mock(status_code=200)
        response.json.return_value = {'access_token': 'new-access', 'refresh_token': 'new-refresh'}
        with patch.object(module, 'credentials', fake_credentials), patch.object(module.requests, 'post', return_value=response) as request, patch.object(module, 'save_twitch_tokens') as save, patch.object(module.importlib, 'reload'):
            self.assertEqual(module.refresh_twitch_token(), 'new-access')
            save.assert_called_once_with('new-access', 'new-refresh')
            self.assertEqual(request.call_args.kwargs['timeout'], 30)

    def test_error_body_is_not_printed(self):
        fake_credentials = types.ModuleType('src.utility.credentials')
        fake_credentials.TWITCH_CLIENT_ID = 'test-client'
        fake_credentials.TWITCH_CLIENT_SECRET = 'test-secret'
        fake_credentials.TWITCH_REFRESH_TOKEN = 'old-refresh'
        with patch.dict('sys.modules', {'src.utility.credentials': fake_credentials}):
            module = importlib.import_module('src.twitch.twitch_auth')
        response = Mock(status_code=401, text='sensitive-response-body')
        output = io.StringIO()
        with patch.object(module, 'credentials', fake_credentials), patch.object(module.requests, 'post', return_value=response), contextlib.redirect_stdout(output):
            self.assertIsNone(module.refresh_twitch_token())
        self.assertIn('401', output.getvalue())
        self.assertNotIn(response.text, output.getvalue())


if __name__ == '__main__':
    unittest.main()
