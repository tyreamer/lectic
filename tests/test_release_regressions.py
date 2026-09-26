"""Release blockers reproduced through public operations in isolated user homes."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home, at_home
import ec
from collection_store import Library
from capture_store import CaptureStore
from demo import build
from goal_workflow import work
from identity import load_identity, save_identity, sign_manifest, check_manifest_signature, _key_id
from inbox import ensure_inbox_folder, route_all_inbox, route_inbox_item, scan_inbox
from lectic_mcp import Server
from packs import build_pack, install_pack, update_pack
from client_check import check_connection


class ReleaseRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'project'
        self.project.mkdir()
        self.home = isolate_home(self, self.base)
        self.env = patch.dict(os.environ, {'LECTIC_INBOX_DIR': str(self.base / 'drops')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_stale_library_writers_merge_index_and_reject_stale_collection(self):
        first, second = Library(self.project), Library(self.project)
        folder, _ = first.archive(name='First')
        second.archive(name='Second')
        self.assertEqual({c['name'] for c in Library(self.project).index['collections']}, {'First', 'Second'})
        _, old = first.resolve('First')
        _, newer = second.resolve('First')
        newer['name'] = 'Renamed'
        second.save(folder, newer)
        old['name'] = 'Stale'
        with self.assertRaisesRegex(ec.Invalid, 'changed in another operation'):
            first.save(folder, old)
        self.assertEqual(Library(self.project).resolve('Renamed')[1]['name'], 'Renamed')

    def test_public_verification_binds_publisher_and_rejects_forgery(self):
        identity = save_identity(self.project, 'Author', 'a@example.test')
        manifest = {'pack_id': 'example', 'files': {'a': 'hash'}, 'created_at': 'today'}
        manifest['publisher'] = sign_manifest(manifest, identity)
        self.assertEqual(check_manifest_signature(manifest)[0], 'signed')
        self.assertIn('not independently trusted', check_manifest_signature(manifest)[1])
        for field in ('name', 'contact', 'signature', 'key_id', 'public_key'):
            altered = copy.deepcopy(manifest)
            altered['publisher'][field] = '0' * 128 if field == 'signature' else 'altered'
            self.assertEqual(check_manifest_signature(altered)[0], 'invalid', field)
        legacy = {'publisher': {'name': 'Claim', 'key_id': 'fake', 'signature': 'fake'}}
        self.assertEqual(check_manifest_signature(legacy)[0], 'unverified')
        renamed = save_identity(self.project, 'New display name', 'a@example.test')
        self.assertEqual(identity['public_key'], renamed['public_key'])

    def test_legacy_identity_migrates_and_update_preserves_signer(self):
        key = 'ab' * 32
        legacy = {'name': 'Legacy author', 'contact': 'legacy@example.test', 'key_hex': key, 'key_id': _key_id(key)}
        ec.write(self.home / 'identity.json', legacy)
        Library(self.project).archive(adopt=build(self.base / 'demo'), name='Signed')
        work(project=self.project, collection='Signed', action='prepare', reconciled=True)
        pack = self.base / 'signed.lectic'
        build_pack(self.project, 'Signed', pack, include_sources=True, version='1')
        self.assertEqual(load_identity(self.project)['algorithm'], 'ed25519')
        self.assertEqual(ec.read(self.home / 'identity-legacy.json'), legacy)
        with at_home(self.base / 'recipient'):
            installed = install_pack(self.project, str(pack), name='Received')
            self.assertEqual(installed['publisher_status'], 'signed')
        replacement = {**load_identity(self.project), 'key_hex': 'cd' * 32}
        ec.write(self.home / 'identity.json', replacement)
        build_pack(self.project, 'Signed', pack, include_sources=True, version='2')
        with at_home(self.base / 'recipient'):
            with self.assertRaisesRegex(ec.Invalid, 'signing key'):
                update_pack(self.project, 'Received')
            folder, _ = Library(self.project).resolve('Received')
            self.assertEqual(ec.read(folder / 'pack-origin.json')['version'], '1')

    def test_mcp_cannot_read_or_capture_lectic_credentials(self):
        save_identity(self.project, 'Private', 'private@example.test')
        server = Server(str(self.project))
        for filename in ('identity.json', 'server.json', 'identity-legacy.json', 'cookies.txt'):
            path = self.home / filename
            if not path.exists(): path.write_text('private', encoding='utf-8')
            with self.assertRaisesRegex(ec.Invalid, 'credentials'):
                server.tool_read(str(path))
            with self.assertRaisesRegex(ec.Invalid, 'credentials'):
                server.tool_capture_save(files=[str(path)])

    def test_inbox_selection_failure_retry_and_matching(self):
        Library(self.project).archive(name='Debugging')
        folder = ensure_inbox_folder(self.project)
        first, second = folder / 'debugging.txt', folder / 'later.txt'
        first.write_text('Debugging: reproduce the failure.', encoding='utf-8')
        second.write_text('Save for later.', encoding='utf-8')
        self.assertEqual(scan_inbox(self.project)['count'], 2)
        with patch.object(CaptureStore, 'import_folder', return_value={'items': [], 'needs_attention': ['injected']}):
            result = route_all_inbox(self.project, {'debugging.txt': 'Debugging'})
        self.assertEqual(result['processed_count'], 0)
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())
        with patch('inbox.shutil.move', side_effect=OSError('injected archive failure')):
            pending = route_inbox_item(self.project, first, 'Debugging')
        self.assertEqual(pending['phase'], 'captured_pending_archive')
        result = route_all_inbox(self.project, {'debugging.txt': 'Debugging'})
        self.assertEqual(result['processed_count'], 1)
        self.assertTrue(second.exists())
        self.assertEqual(len(CaptureStore(self.project).all()), 1)
        outside = self.base / 'outside.txt'
        outside.write_text('Keep me', encoding='utf-8')
        with self.assertRaises(ec.Invalid): route_inbox_item(self.project, outside)

    def test_updated_interpretation_same_sources_persists_and_preserves_history(self):
        run = build(self.base / 'demo')
        Library(self.project).archive(adopt=run, name='Debugging')
        work(project=self.project, collection='Debugging', action='prepare', reconciled=True)
        pack = self.base / 'debugging.lectic'
        build_pack(self.project, 'Debugging', pack, team=True, version='1')
        recipient = self.base / 'recipient'
        recipient.mkdir()
        with at_home(self.base / 'recipient-home'):
            installed = install_pack(recipient, str(pack))
            lib = Library(recipient)
            old_folder, old_data = lib.resolve(installed['collection_id'])
            old_run = lib.run(old_folder, old_data)
            old_ir = ec.validate_ir(old_run)
        lib = Library(self.project)
        folder, data = lib.resolve('Debugging')
        author_run = lib.run(folder, data)
        part_path = next(p for p in (author_run / 'units').glob('*.json') if ec.read(p)['units'])
        part = ec.read(part_path)
        part['units'][0]['statement'] += ' Apply within the cited conditions.'
        changed_id = part['units'][0]['unit_id']
        ec.write(part_path, part)
        work(project=self.project, collection='Debugging', action='prepare', reconciled=True)
        build_pack(self.project, 'Debugging', pack, team=True, version='2')
        with at_home(self.base / 'recipient-home'):
            updated = update_pack(recipient, installed['collection_id'])
            self.assertTrue(updated['knowledge_matches_pack'])
            lib = Library(recipient)
            folder, data = lib.resolve(installed['collection_id'])
            active = ec.validate_ir(lib.run(folder, data))
            self.assertNotEqual(lib.run(folder, data), old_run)
            self.assertEqual(ec.validate_ir(old_run), old_ir)
            actual = next(u for u in active['units'] if u['unit_id'] == changed_id)
            self.assertTrue(actual['statement'].endswith('Apply within the cited conditions.'))

    def test_mcp_source_defaults_and_explicit_exclusion(self):
        run = build(self.base / 'demo')
        Library(self.project).archive(adopt=run, name='Example')
        work(project=self.project, collection='Example', action='prepare', reconciled=True)
        server = Server(str(self.project))
        default = server.tool_pack(collection='Example', out=str(self.base / 'default.lectic'))
        excluded = server.tool_pack(collection='Example', out=str(self.base / 'excluded.lectic'), team=True, include_sources=False)
        self.assertFalse(default['sources_included'])
        self.assertFalse(excluded['sources_included'])

    def test_configured_invalid_command_is_unreachable(self):
        self.assertEqual(check_connection({'command': str(self.base / 'missing-python'), 'args': []}), (False, None))
        script = self.base / 'false-server.py'
        script.write_text('print("{}")', encoding='utf-8')
        self.assertEqual(check_connection({'command': sys.executable, 'args': [str(script)]}), (False, None))

    def test_direct_youtube_url_reaches_link_adapter(self):
        from ingestors.transcript_files import TranscriptFiles
        from ingestors.youtube import YouTubeIngestor
        records = TranscriptFiles(ec.ROOT / 'fixtures/debugging').collect()
        with patch.object(YouTubeIngestor, 'collect', return_value=records) as collect:
            result = work(project=self.project, input='https://www.youtube.com/watch?v=abcdefghijk', name='Linked', action='save')
        self.assertEqual(result['phase'], 'archived')
        collect.assert_called_once()

    def test_codex_config_preserves_apostrophes_and_other_sections(self):
        import cli
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        config = self.base / 'config.toml'
        config.write_text('[mcp_servers.other]\ncommand = "keep"\n', encoding='utf-8')
        command = [str(self.base / "O'Brien" / 'python.exe'), '-m', 'lectic.cli', 'serve']
        with patch('cli.codex_config_path', return_value=config), patch('cli.server_command', return_value=command):
            self.assertEqual(cli.connect_codex(), 'connected')
        actual = tomllib.loads(config.read_text(encoding='utf-8'))
        self.assertEqual(actual['mcp_servers']['lectic']['command'], command[0])
        self.assertEqual(actual['mcp_servers']['other']['command'], 'keep')

    def test_starter_fresh_process_and_http_release_gate(self):
        from release_check import check_release
        report = check_release()
        self.assertEqual(report['status'], 'passed')


if __name__ == '__main__': unittest.main()
