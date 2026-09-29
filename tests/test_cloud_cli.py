"""Tests for Lectic Cloud CLI subcommands."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from cli import main


class CloudCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = str(Path(self.temp.name) / 'cloud')

    def test_cloud_cli_user_lifecycle_and_export(self):
        # 1. Create user
        buf = io.StringIO()
        with patch('sys.stdout', buf):
            code = main(['cloud', 'create-user', 'carol@example.com', '--password', 'secPass123', '--name', 'Carol', '--root', self.root, '--json'])
        self.assertEqual(code, 0)
        res = json.loads(buf.getvalue())
        self.assertEqual(res['account']['email'], 'carol@example.com')
        self.assertEqual(res['account']['display_name'], 'Carol')
        self.assertIn('initial_token', res)

        # 2. List users
        buf = io.StringIO()
        with patch('sys.stdout', buf):
            code = main(['cloud', 'list-users', '--root', self.root, '--json'])
        self.assertEqual(code, 0)
        users = json.loads(buf.getvalue())
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]['email'], 'carol@example.com')

        # 3. Create token
        buf = io.StringIO()
        with patch('sys.stdout', buf):
            code = main(['cloud', 'token', 'carol@example.com', '--client', 'Claude Mobile', '--root', self.root, '--json'])
        self.assertEqual(code, 0)
        tok_data = json.loads(buf.getvalue())
        self.assertIn('token', tok_data)

        # 4. Export library
        out_file = str(Path(self.temp.name) / 'carol_library.lectic-home')
        buf = io.StringIO()
        with patch('sys.stdout', buf):
            code = main(['cloud', 'export', 'carol@example.com', '--out', out_file, '--root', self.root])
        self.assertEqual(code, 0)
        self.assertTrue(Path(out_file).is_file())
        self.assertGreater(Path(out_file).stat().st_size, 0)


if __name__ == '__main__':
    unittest.main()
