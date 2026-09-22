"""`lectic setup` connects whatever assistants are present, verifies the server, and is safe to repeat."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import cli


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.user = self.base / 'user'; self.user.mkdir()
        self.home = isolate_home(self, self.base)
        patch('cli.Path.home', return_value=self.user).start(); self.addCleanup(patch.stopall)
        patch('cli.shutil.which', side_effect=lambda name: None).start()
        patch('cli.sys.stdin', io.StringIO()).start()  # never interactive in tests

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out): code = cli.main(list(args))
        return code, out.getvalue()

    def test_setup_connects_present_assistants_by_editing_their_configs(self):
        (self.user / '.claude.json').write_text(json.dumps({'projects': {}, 'mcpServers': {'other': {'command': 'x'}}}), encoding='utf-8')
        (self.user / '.codex').mkdir(); (self.user / '.codex/config.toml').write_text('model = "gpt-5"\n', encoding='utf-8')
        code, out = self.run_cli('setup', '--yes')
        self.assertEqual(code, 0, out)
        self.assertIn('Claude Code  connected', out); self.assertIn('Codex        connected', out)
        self.assertIn(str(self.home.resolve()), out); self.assertIn('Save this for later', out)
        claude = json.loads((self.user / '.claude.json').read_text(encoding='utf-8'))
        self.assertEqual(claude['mcpServers']['other'], {'command': 'x'})  # nothing else touched
        server = claude['mcpServers']['lectic']
        self.assertEqual([server['command']] + server['args'], cli.server_command())
        codex = (self.user / '.codex/config.toml').read_text(encoding='utf-8')
        self.assertTrue(codex.startswith('model = "gpt-5"\n'))
        self.assertIn('[mcp_servers.lectic]', codex); self.assertIn("'serve'", codex)
        # The recorded command really starts the server.
        probe = subprocess.run(cli.server_command(), input='{"jsonrpc":"2.0","id":1,"method":"ping"}\n',
                               capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(json.loads(probe.stdout.strip())['result'], {})
        # Running setup again changes nothing.
        before = (self.user / '.claude.json').read_text(encoding='utf-8'), codex
        self.assertEqual(self.run_cli('setup', '--yes')[0], 0)
        self.assertEqual(before, ((self.user / '.claude.json').read_text(encoding='utf-8'), (self.user / '.codex/config.toml').read_text(encoding='utf-8')))

    def test_setup_prefers_the_claude_cli_and_replaces_a_stale_entry(self):
        calls = []
        def fake_run(command, **kwargs):
            calls.append(command)
            if command[1:3] == ['mcp', 'add'] and len(calls) == 1:
                return subprocess.CompletedProcess(command, 1, '', 'MCP server lectic already exists in user config')
            return subprocess.CompletedProcess(command, 0, '', '')
        with patch('cli.shutil.which', side_effect=lambda name: 'claude' if name == 'claude' else None), \
             patch('cli.subprocess.run', side_effect=fake_run):
            self.assertEqual(cli.connect_claude(), 'connected')
        self.assertEqual([c[1:3] for c in calls], [['mcp', 'add'], ['mcp', 'remove'], ['mcp', 'add']])
        self.assertEqual(calls[-1][calls[-1].index('--') + 1:], cli.server_command())

    def test_setup_explains_when_no_assistant_is_present(self):
        code, out = self.run_cli('setup', '--yes')
        self.assertEqual(code, 0)
        self.assertIn('Claude Code  not installed', out); self.assertIn('Codex        not installed', out)
        self.assertIn('No supported assistant was found', out); self.assertIn(' '.join(cli.server_command()), out)

    def test_status_reports_home_connections_and_server_health(self):
        code, out = self.run_cli('status')
        self.assertEqual(code, 0)
        for line in ('Python', 'Knowledge', 'Collections 0', 'Claude Code not connected', 'Codex       not connected', 'Server      ok', 'lectic setup'):
            self.assertIn(line, out)
        self.assertEqual(self.run_cli()[1], out)  # bare `lectic` is status
        self.assertEqual(self.run_cli('nonsense')[0], 2)


if __name__ == '__main__':
    unittest.main()
