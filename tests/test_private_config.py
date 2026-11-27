import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_missing_file_uses_default_without_creating_a_file(self):
        self.env_file.unlink()
        self.assertEqual(private_config.environ('UNCONFIGURED', 'fallback'), 'fallback')
        self.assertFalse(self.env_file.exists())


if __name__ == '__main__':
    unittest.main()
