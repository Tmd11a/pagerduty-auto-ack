import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pagerduty_auto_ack import cli


class CommandLineTests(unittest.TestCase):
    def test_once_uses_api_key_from_environment(self):
        with patch.dict(os.environ, {"PAGERDUTY_API_KEY": "u+example"}, clear=True):
            args = cli.parse_args(["--once"])

        self.assertTrue(args.once)
        self.assertEqual("u+example", args.pagerduty_api_key)

    def test_uses_api_key_from_env_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text("PAGERDUTY_API_KEY='u+from-file'\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                args = cli.parse_args(["--once", "--env-file", str(env_file)])

        self.assertEqual("u+from-file", args.pagerduty_api_key)

    def test_environment_takes_precedence_over_env_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text("PAGERDUTY_API_KEY=u+from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"PAGERDUTY_API_KEY": "u+from-environment"}):
                args = cli.parse_args(["--once", "--env-file", str(env_file)])

        self.assertEqual("u+from-environment", args.pagerduty_api_key)

    def test_duration_is_parsed_as_seconds(self):
        args = cli.parse_args(["--pagerduty-api-key", "u+example", "--duration", "1200"])

        self.assertEqual(1200, args.duration)

    def test_duration_must_be_positive(self):
        with self.assertRaises(SystemExit):
            cli.parse_args(["--pagerduty-api-key", "u+example", "--duration", "0"])
