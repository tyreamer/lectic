"""Updater integrity, recovery and scheduling contract; no model or network calls."""
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import install_skill
import update_skill as updater

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'a' * 40
NEXT = 'b' * 40


class UpdatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.dest = self.base / 'Assistant With Spaces/skills/expertise-compiler'
        self.dest.mkdir(parents=True)
        (self.dest / 'SKILL.md').write_text('Old customized skill\n', encoding='utf-8')
        (self.dest / 'private.txt').write_text('Retain the entire original installation', encoding='utf-8')
        self.state = updater.locations(self.dest)[1]
        self.project = self.base / 'project/.expertise-compiler'
        self.project.mkdir(parents=True)
        (self.project / 'library.json').write_text('{"saved":"do not change"}', encoding='utf-8')
        self.original = updater.inventory(self.dest)

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, commit=COMMIT, extras=None):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            # A small valid payload, including the actual standalone runner for reload tests.
            for name in updater.PAYLOAD:
                if '.' in name:
                    text = ('---\nname: lectic\ndescription: Test updates\n---\n# Lectic\n'
                            if name == 'SKILL.md' else 'Example\n')
                    archive.writestr(f'lectic-{commit}/{name}', text)
                else:
                    archive.writestr(f'lectic-{commit}/{name}/example.txt', 'Example\n')
            archive.writestr(f'lectic-{commit}/scripts/update_skill.py', (ROOT / 'scripts/update_skill.py').read_bytes())
            archive.writestr(f'lectic-{commit}/agents/openai.yaml', (ROOT / 'agents/openai.yaml').read_bytes())
            archive.writestr(f'lectic-{commit}/workspace/private.txt', 'Never install')
            archive.writestr(f'lectic-{commit}/.expertise-compiler/library.json', '{}')
            for name, content in (extras or {}).items():
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)  # Deliberately malformed archive.
                    archive.writestr(name, content)
        return data.getvalue()

    def update(self, commit=COMMIT, **kwargs):
        with patch.object(updater, 'latest_commit', return_value=commit), \
                patch.object(updater, 'download', return_value=self.archive(commit)):
            return updater.operate('update', self.dest, **kwargs)

    def test_explicit_adoption_backup_and_project_isolation(self):
        with self.assertRaisesRegex(updater.UpdateError, 'Unmanaged'):
            self.update()
        result = self.update(adopt=True)
        self.assertEqual(result['installed_commit'], COMMIT)
        self.assertEqual(updater.inventory(Path(result['backups'][0]['path'])), self.original)
        receipt = updater.read(Path(result['backups'][0]['path']).with_suffix('.receipt.json'))
        self.assertEqual(receipt['files'], self.original)
        self.assertNotIn('private.txt', updater.inventory(self.dest))
        self.assertFalse((self.dest / 'workspace').exists())
        self.assertFalse((self.dest / '.expertise-compiler').exists())
        self.assertEqual(json.loads((self.project / 'library.json').read_text()), {'saved': 'do not change'})
        self.assertFalse(result['automatic_updates'])

    def test_noop_current_and_fresh_process_status(self):
        result = self.update(adopt=True)
        with patch.object(updater, 'latest_commit', return_value=COMMIT), patch.object(updater, 'download') as fetch:
            again = updater.operate('update', self.dest)
        fetch.assert_not_called()
        self.assertEqual(again['backups'], result['backups'])
        command = [sys.executable, '-B', str(self.state / 'runner.py'), 'status', '--dest', str(self.dest)]
        fresh = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertEqual(json.loads(fresh.stdout)['installed_commit'], COMMIT)

    def test_modified_added_and_deleted_files_pause_before_network(self):
        for kind in ['modify', 'add', 'delete']:
            with self.subTest(kind=kind):
                if not (self.state / 'state.json').exists():
                    self.update(adopt=True)
                skill = (self.dest / 'SKILL.md').read_bytes()
                if kind == 'modify': (self.dest / 'SKILL.md').write_text('My edits')
                if kind == 'add': (self.dest / 'notes.txt').write_text('My file')
                if kind == 'delete': (self.dest / 'SKILL.md').unlink()
                before = updater.inventory(self.dest)
                with patch.object(updater, 'latest_commit') as network:
                    with self.assertRaisesRegex(updater.UpdateError, 'Local edits'):
                        updater.operate('update', self.dest, adopt=True)
                network.assert_not_called()
                self.assertEqual(before, updater.inventory(self.dest))
                self.assertEqual(updater.operate('status', self.dest)['status'], 'local_changes')
                (self.dest / 'SKILL.md').write_bytes(skill)
                (self.dest / 'notes.txt').unlink(missing_ok=True)

    def test_due_gate_pause_and_network_failure_preserve_installation(self):
        self.update(adopt=True)
        updater.operate('enable', self.dest)
        with patch.object(updater, 'latest_commit') as network:
            self.assertEqual(updater.operate('run', self.dest)['status'], 'not_due')
            network.assert_not_called()
        state = updater.load_state(self.dest, self.state)
        state['last_check'] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        updater.write(self.state / 'state.json', state)
        before = updater.inventory(self.dest)
        with patch.object(updater, 'latest_commit', side_effect=OSError('offline')):
            with self.assertRaisesRegex(OSError, 'offline'):
                updater.operate('run', self.dest)
        self.assertEqual(updater.inventory(self.dest), before)
        self.assertEqual(updater.operate('status', self.dest)['last_result'], 'needs_attention')
        updater.operate('pause', self.dest)
        with patch.object(updater, 'latest_commit') as network:
            self.assertEqual(updater.operate('run', self.dest)['status'], 'paused')
            network.assert_not_called()

    def test_new_revision_retains_old_backup_and_updates_runner(self):
        self.update(adopt=True)
        first = updater.inventory(self.dest)
        result = self.update(NEXT)
        self.assertEqual(result['installed_commit'], NEXT)
        self.assertEqual(len(result['backups']), 2)
        self.assertEqual(updater.inventory(Path(result['backups'][1]['path'])), first)
        self.assertEqual((self.state / 'runner.py').read_bytes(), (self.dest / 'scripts/update_skill.py').read_bytes())

    def test_new_named_install_and_legacy_name_receive_same_release(self):
        for name in ['expertise-compiler', 'lectic']:
            with self.subTest(name=name):
                self.dest = self.dest.parent / name
                self.dest.mkdir(exist_ok=True)
                if name == 'lectic':
                    (self.dest / 'SKILL.md').write_text('Older Lectic copy', encoding='utf-8')
                self.state = updater.locations(self.dest)[1]
                self.update(adopt=True)
                updater.operate('enable', self.dest, task_name='Existing schedule')
                result = self.update(NEXT)
                self.assertEqual(result['installed_commit'], NEXT)
                self.assertEqual(result['task_name'], 'Existing schedule')
                self.assertTrue(result['automatic_updates'])
                self.assertEqual(self.state.name, name)
                self.assertIn(f'\nname: {name}\n', (self.dest / 'SKILL.md').read_text())
                self.assertIn(f'Use ${name} ', (self.dest / 'agents/openai.yaml').read_text())
                self.assertEqual(result['changed_files'], [])
                self.assertEqual(updater.operate('run', self.dest)['status'], 'not_due')

    def test_clean_install_both_names_runs_and_remains_idempotent(self):
        for name in ['lectic', 'expertise-compiler']:
            with self.subTest(name=name):
                target = self.base / 'Clean Personal Skills' / name
                install_skill.install(target)
                self.assertIn(f'\nname: {name}\n', (target / 'SKILL.md').read_text(encoding='utf-8'))
                self.assertIn(f'Use ${name} ', (target / 'agents/openai.yaml').read_text(encoding='utf-8'))
                self.assertEqual(install_skill.install(target), target)
                self.assertEqual((target / 'schemas/source.schema.json').read_bytes(),
                                 (ROOT / 'schemas/source.schema.json').read_bytes())
                project = self.base / f'Fresh Project {name}'
                project.mkdir()
                response = subprocess.run([sys.executable, '-B', str(target / 'scripts/ec.py'),
                                           'library', '--project', str(project)], capture_output=True, text=True)
                self.assertEqual(response.returncode, 0, response.stderr)
                self.assertEqual(json.loads(response.stdout)['phase'], 'lectic_library')
                self.assertFalse((project / '.expertise-compiler').exists())

    def test_identity_adaptation_does_not_rewrite_source_or_body(self):
        original = b'---\nname: lectic\ndescription: Example\n---\nname: lectic\n.expertise-compiler/\n'
        actual = updater.installed_bytes('SKILL.md', original, 'expertise-compiler')
        self.assertEqual(actual, original.replace(b'name: lectic', b'name: expertise-compiler', 1))
        self.assertEqual(updater.installed_bytes('fixtures/transcript.txt', original, 'expertise-compiler'), original)
        with self.assertRaisesRegex(updater.UpdateError, 'Unknown'):
            updater.installed_bytes('SKILL.md', original, 'something-else')

    def test_bad_archives_and_malformed_code_do_not_replace_install(self):
        self.update(adopt=True)
        before = updater.inventory(self.dest)
        for extra in [
            {f'lectic-{NEXT}/../escape': 'bad'},
            {f'lectic-{NEXT}/scripts/CON.py': 'bad'},
            {f'lectic-{NEXT}/scripts/example.txt': 'duplicate'},
            {f'lectic-{NEXT}/schemas/broken.json': '{'},
            {f'lectic-{NEXT}/scripts/broken.py': 'def :' },
        ]:
            with self.subTest(extra=extra), patch.object(updater, 'latest_commit', return_value=NEXT), \
                    patch.object(updater, 'download', return_value=self.archive(NEXT, extra)):
                with self.assertRaises((updater.UpdateError, SyntaxError, json.JSONDecodeError)):
                    updater.operate('update', self.dest)
            self.assertEqual(updater.inventory(self.dest), before)
            self.assertFalse(list(self.dest.parent.glob('.lectic-stage-*')))

    def test_symlink_archive_is_rejected(self):
        data = io.BytesIO(self.archive())
        with zipfile.ZipFile(data, 'a') as archive:
            entry = zipfile.ZipInfo(f'lectic-{COMMIT}/scripts/link')
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, '../../private')
        stage = self.base / 'staging'
        stage.mkdir()
        with self.assertRaisesRegex(updater.UpdateError, 'Unsafe'):
            updater.unpack(data.getvalue(), COMMIT, stage)

    def test_swap_failure_restores_previous_installation(self):
        self.update(adopt=True)
        before = updater.inventory(self.dest)
        replace = updater.os.replace
        def fail_second(source, target):
            if Path(source).name.startswith('.lectic-stage-'):
                raise OSError('locked destination')
            return replace(source, target)
        with patch.object(updater.os, 'replace', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'locked destination'):
                self.update(NEXT)
        self.assertEqual(updater.inventory(self.dest), before)
        self.assertFalse((self.state / 'transaction.json').exists())

    def test_interrupted_swap_recovers_on_next_run_even_when_paused(self):
        self.update(adopt=True)
        before = updater.inventory(self.dest)
        replace = updater.os.replace
        def interrupt_second(source, target):
            if Path(source).name.startswith('.lectic-stage-'):
                raise KeyboardInterrupt()
            return replace(source, target)
        with patch.object(updater.os, 'replace', side_effect=interrupt_second):
            with self.assertRaises(KeyboardInterrupt): self.update(NEXT)
        self.assertFalse(self.dest.exists())
        self.assertTrue((self.state / 'runner.py').exists())
        self.assertEqual(updater.operate('run', self.dest)['status'], 'paused')
        self.assertEqual(updater.inventory(self.dest), before)

    def test_interrupted_after_swap_finalizes_receipt(self):
        self.update(adopt=True)
        recover = updater.recover
        def interrupt_after(dest, state):
            if (state / 'transaction.json').exists(): raise KeyboardInterrupt()
            return recover(dest, state)
        with patch.object(updater, 'recover', side_effect=interrupt_after):
            with self.assertRaises(KeyboardInterrupt): self.update(NEXT)
        self.assertTrue((self.state / 'transaction.json').exists())
        updater.operate('run', self.dest)
        self.assertEqual(updater.operate('status', self.dest)['installed_commit'], NEXT)
        self.assertFalse((self.state / 'transaction.json').exists())

    def test_lock_excludes_concurrent_update_and_releases_after_error(self):
        with updater.locked(self.state):
            with self.assertRaisesRegex(updater.UpdateError, 'Another'):
                with updater.locked(self.state): pass
        with updater.locked(self.state): pass

    def test_paths_and_receipt_cannot_target_another_install(self):
        with self.assertRaises(updater.UpdateError):
            updater.locations(self.project)
        with self.assertRaisesRegex(updater.UpdateError, 'outside'):
            updater.locations(self.dest, self.dest / 'state')
        self.update(adopt=True)
        value = updater.read(self.state / 'state.json')
        value['destination'] = str(self.project)
        updater.write(self.state / 'state.json', value)
        with self.assertRaisesRegex(updater.UpdateError, 'receipt'):
            updater.operate('update', self.dest)

    def test_checkout_or_project_data_never_adopted(self):
        for name in ['.git', '.expertise-compiler', 'workspace']:
            (self.dest / name).mkdir()
            with patch.object(updater, 'latest_commit') as network:
                with self.assertRaisesRegex(updater.UpdateError, 'checkout or project data'):
                    updater.operate('update', self.dest, adopt=True)
                network.assert_not_called()
            self.assertTrue((self.dest / 'private.txt').is_file())
            (self.dest / name).rmdir()

    def test_updater_and_clean_installer_ship_same_payload(self):
        self.assertEqual(updater.PAYLOAD, install_skill.PAYLOAD)
        candidate = self.base / 'clean-candidate'
        candidate.mkdir()
        for name, source in install_skill.payload_files(ROOT).items():
            target = candidate / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        updater.validate_candidate(candidate)


if __name__ == '__main__':
    unittest.main()
