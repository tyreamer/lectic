"""Real compiler/pack round trips, isolated homes, simulated GitHub Git database."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home, at_home
from ec import ROOT, Invalid, read, write
from collection_store import Library
from packs import install_pack
import github_sync as gs


class GitHubFixture(gs.GitHub):
    def __init__(self):
        self.private, self.writable, self.offline, self.race = True, True, False, False
        self.calls, self.blobs, self.trees, self.commits = [], {}, {}, {}
        self.head = 'a' * 40
        self.trees['b' * 40] = {}
        self.commits[self.head] = {'tree': {'sha': 'b' * 40}}

    def api(self, path, data=None, method=None):
        self.calls.append((path, deepcopy(data), method))
        if self.offline:
            raise Invalid('GitHub could not be reached; your local work is safe. Sync will retry.')
        if path == '/user': return {'login': 'alice'}
        if path == '/user/repos':
            assert data['private'] is True and data['auto_init'] is True
            return {}
        if path == '/repos/alice/lectic-packs':
            return {'private': self.private, 'permissions': {'push': self.writable}, 'default_branch': 'main'}
        if '/git/ref/heads/' in path:
            return {'object': {'sha': self.head}}
        if path.endswith('/git/blobs'):
            raw = base64.b64decode(data['content'])
            sha = hashlib.sha1(raw).hexdigest()
            self.blobs[sha] = raw
            return {'sha': sha}
        if '/git/blobs/' in path:
            raw = self.blobs[path.rsplit('/', 1)[1]]
            return {'encoding': 'base64', 'content': base64.b64encode(raw).decode()}
        if path.endswith('/git/trees'):
            tree = dict(self.trees[data['base_tree']])
            for entry in data['tree']:
                tree[entry['path']] = {**entry, 'size': len(self.blobs[entry['sha']])}
            sha = hashlib.sha1(json.dumps(tree, sort_keys=True).encode()).hexdigest()
            self.trees[sha] = tree
            return {'sha': sha}
        if '/git/trees/' in path:
            sha = path.rsplit('/', 1)[1].split('?')[0]
            return {'tree': list(self.trees[sha].values()), 'truncated': False}
        if path.endswith('/git/commits'):
            sha = hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()
            self.commits[sha] = {**data, 'tree': {'sha': data['tree']}}
            return {'sha': sha}
        if '/git/commits/' in path:
            return self.commits[path.rsplit('/', 1)[1]]
        if '/git/refs/heads/' in path:
            assert method == 'PATCH' and data['force'] is False
            if self.race or self.commits[data['sha']]['parents'] != [self.head]:
                raise Invalid('GitHub changed during sync; retry. Nothing was overwritten.')
            self.head = data['sha']
            return {}
        raise AssertionError(path)

    def files(self):
        tree = self.trees[self.commits[self.head]['tree']['sha']]
        return {path: self.blobs[entry['sha']] for path, entry in tree.items()}


class GitHubSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = isolate_home(self, self.base)
        self.remote = GitHubFixture()
        self.repo = 'alice/lectic-packs'

    def seed(self):
        return install_pack(self.base, ROOT / 'fixtures/packs/debugging-starter.lectic')['collection_id']

    def connect(self):
        return gs.connect(self.base, self.repo, client=self.remote)

    def sync(self, **kwargs):
        return gs.sync(self.base, client=self.remote, **kwargs)

    def rename(self, cid, name):
        library = Library(self.base)
        folder, data = library.resolve(cid)
        data['name'] = name
        library.save(folder, data)

    def test_try_needs_no_account_network_or_seeded_content(self):
        with patch.object(gs, 'GitHub', side_effect=AssertionError('No authentication during trial')):
            self.assertEqual(gs.sync(self.base)['phase'], 'local_only')
            self.assertEqual(Library(self.base).index['collections'], [])

    def test_round_trip_two_homes_readable_evidence_and_no_repeated_upload(self):
        self.seed()
        self.connect()
        self.assertEqual(self.sync()['phase'], 'synced')
        files = self.remote.files()
        self.assertEqual(len(files), 3)
        text = next(raw.decode() for path, raw in files.items() if path.endswith('.md'))
        self.assertIn('Evidence status:', text)
        self.assertIn('Source:', text)
        self.assertIn('> ', text)
        initial_head = self.remote.head
        self.assertEqual(self.sync()['phase'], 'synced')
        self.assertEqual(self.remote.head, initial_head)
        with at_home(self.base / 'second-home'):
            self.connect()
            result = self.sync()
            self.assertEqual(result['phase'], 'synced', result)
            self.assertEqual(len(Library(self.base).index['collections']), 1)
            self.assertEqual(self.sync()['phase'], 'synced')
            self.assertEqual(len(Library(self.base).index['collections']), 1)
            self.assertEqual(self.remote.head, initial_head)

    def test_offline_work_retries_and_keeps_last_verified_sync_time(self):
        cid = self.seed(); self.connect(); self.sync()
        last = gs.status(self.base)['last_synced']
        self.rename(cid, 'My improved pack')
        self.remote.offline = True
        result = self.sync()
        self.assertEqual(result['phase'], 'retry_pending')
        self.assertEqual(result['last_synced'], last)
        self.assertEqual(Library(self.base).resolve(cid)[1]['name'], 'My improved pack')
        self.remote.offline = False
        self.assertEqual(self.sync()['phase'], 'synced')
        self.assertIn(b'My improved pack', self.remote.files()[gs.INDEX])

    def test_remote_and_local_edits_never_overwrite_one_another(self):
        cid = self.seed(); self.connect(); self.sync()
        with at_home(self.base / 'second'):
            self.connect(); self.sync()
            second_id = Library(self.base).index['collections'][0]['collection_id']
            self.rename(second_id, 'Changed on second computer')
            self.assertEqual(self.sync()['phase'], 'synced')
        self.rename(cid, 'Changed on first computer')
        head = self.remote.head
        result = self.sync()
        self.assertEqual(result['phase'], 'needs_attention', result)
        self.assertEqual(len(result['conflicts']), 1)
        self.assertEqual(self.remote.head, head)
        self.assertEqual(Library(self.base).resolve(cid)[1]['name'], 'Changed on first computer')

    def test_reverting_to_an_earlier_revision_preserves_immutable_pack_bytes(self):
        cid = self.seed(); self.connect(); self.sync()
        original_name = Library(self.base).resolve(cid)[1]['name']
        original_files = self.remote.files()
        self.rename(cid, 'A different revision'); self.sync()
        self.rename(cid, original_name)
        self.assertEqual(self.sync()['phase'], 'synced')
        for path, raw in original_files.items():
            self.assertEqual(self.remote.files()[path], raw)

    def test_interrupted_import_is_adopted_without_a_duplicate(self):
        self.seed(); self.connect(); self.sync()
        with at_home(self.base / 'second'):
            self.connect(); self.sync()
            state = read(gs.state_path(self.base))
            state['bindings'] = {}
            write(gs.state_path(self.base), state)
            self.assertEqual(self.sync()['phase'], 'synced')
            self.assertEqual(len(Library(self.base).index['collections']), 1)

    def test_remote_only_update_reuses_existing_collection(self):
        self.seed(); self.connect(); self.sync()
        with at_home(self.base / 'second'):
            self.connect(); self.sync()
            cid = Library(self.base).index['collections'][0]['collection_id']
            self.rename(cid, 'Changed remotely'); self.sync()
        result = self.sync()
        self.assertEqual(result['phase'], 'synced', result)
        self.assertEqual(len(Library(self.base).index['collections']), 1)
        head = self.remote.head
        self.assertEqual(self.sync()['phase'], 'synced')
        self.assertEqual(self.remote.head, head)

    def test_private_required_at_connect_and_every_sync(self):
        self.seed()
        self.remote.private = False
        with self.assertRaisesRegex(Invalid, 'private'):
            self.connect()
        self.assertFalse(gs.state_path(self.base).exists())
        self.remote.private = True; self.connect(); self.sync()
        head = self.remote.head
        self.remote.private = False
        self.assertEqual(self.sync()['phase'], 'retry_pending')
        self.assertEqual(self.remote.head, head)

    def test_private_creation_only_for_signed_in_owner_and_no_token_persistence(self):
        gs.connect(self.base, self.repo, create=True, client=self.remote)
        self.assertIn(('/user/repos', {'name': 'lectic-packs', 'private': True, 'auto_init': True,
            'description': 'My private Lectic context packs'}, None), self.remote.calls)
        self.assertNotIn('token', gs.state_path(self.base).read_text())
        gs.disconnect(self.base)
        with self.assertRaisesRegex(Invalid, 'own GitHub account'):
            gs.connect(self.base, 'someone-else/lectic-packs', create=True, client=self.remote)

    def test_competing_remote_commit_never_advances_local_sync_receipt(self):
        self.seed(); self.connect()
        self.remote.race = True
        result = self.sync()
        self.assertEqual(result['phase'], 'retry_pending')
        self.assertIsNone(result['last_synced'])
        self.assertEqual(read(gs.state_path(self.base))['bindings'], {})
        self.assertEqual(self.remote.files(), {})
        self.remote.race = False
        self.assertEqual(self.sync()['phase'], 'synced')

    def test_pending_drafts_and_secrets_are_not_uploaded(self):
        self.seed()
        drafts = self.base / 'drafts'; drafts.mkdir()
        (drafts / 'note.txt').write_text('Not compiled yet.')
        Library(self.base).archive(drafts, name='Unfinished')
        write(self.home / 'server.json', {'token': 'never-upload-this-secret'})
        self.connect()
        result = self.sync()
        self.assertEqual(result['phase'], 'needs_attention')
        self.assertEqual(result['pending'][0]['name'], 'Unfinished')
        self.assertFalse(any(b'never-upload-this-secret' in raw for raw in self.remote.files().values()))
        self.assertEqual(len(json.loads(self.remote.files()[gs.INDEX])['packs']), 1)

    def test_due_throttles_across_assistants_and_disconnect_preserves_packs(self):
        self.seed(); self.connect(); self.sync()
        calls = len(self.remote.calls)
        self.sync(due=True)
        self.assertEqual(len(self.remote.calls), calls)
        files = self.remote.files()
        self.assertEqual(gs.disconnect(self.base)['phase'], 'local_only')
        self.assertEqual(len(Library(self.base).index['collections']), 1)
        self.assertEqual(self.remote.files(), files)

    def test_corrupt_remote_pack_never_changes_local_library(self):
        self.seed(); self.connect(); self.sync()
        tree = self.remote.trees[self.remote.commits[self.remote.head]['tree']['sha']]
        pack = next(entry for path, entry in tree.items() if path.endswith('.lectic'))
        self.remote.blobs[pack['sha']] = b'x' * pack['size']
        with at_home(self.base / 'second'):
            self.connect()
            self.assertEqual(self.sync()['phase'], 'retry_pending')
            self.assertEqual(Library(self.base).index['collections'], [])

    def test_index_cannot_supply_paths_or_external_downloads(self):
        with self.assertRaises(Invalid):
            gs.validate_index({'version': 1, 'packs': {'../../private': {}}})
        with self.assertRaises(Invalid):
            gs.connect(self.base, 'https://evil.example/alice/repo', client=self.remote)

    def test_remote_removal_does_not_delete_or_silently_republish_local_work(self):
        cid = self.seed(); self.connect(); self.sync()
        head, tree, _, _ = self.remote.snapshot(self.repo, 'main')
        self.remote.commit(self.repo, 'main', head, tree,
                           {gs.INDEX: json.dumps({'version': 1, 'packs': {}}).encode()})
        self.rename(cid, 'Still needed here')
        head = self.remote.head
        self.assertEqual(self.sync()['phase'], 'needs_attention')
        self.assertEqual(self.remote.head, head)
        self.assertEqual(Library(self.base).resolve(cid)[1]['name'], 'Still needed here')

    def test_incomplete_import_cannot_replace_an_existing_collection(self):
        cid = self.seed()
        library = Library(self.base)
        folder, data = library.resolve(cid)
        (library.run(folder, data) / 'reconciliation.json').unlink()
        exported = gs.build_pack(self.base, cid, self.base / 'partial.lectic', include_sources=True)
        with at_home(self.base / 'second'):
            target = self.seed()
            before = (gs.storage_root(self.base) / 'library.json').read_bytes()
            with self.assertRaisesRegex(Invalid, 'cannot be restored completely'):
                install_pack(self.base, exported['pack'], collection_id=target, require_complete=True)
            self.assertEqual((gs.storage_root(self.base) / 'library.json').read_bytes(), before)

    def test_lost_receipt_does_not_discard_edits_when_remote_also_changed(self):
        first = self.seed(); self.connect(); self.sync()
        with at_home(self.base / 'second'):
            self.connect(); self.sync()
            second = Library(self.base).index['collections'][0]['collection_id']
            self.rename(second, 'Unsynced second edit')
            state = read(gs.state_path(self.base)); state['bindings'] = {}
            write(gs.state_path(self.base), state)
        self.rename(first, 'Changed first'); self.sync()
        with at_home(self.base / 'second'):
            self.assertEqual(self.sync()['phase'], 'needs_attention')
            self.assertEqual(Library(self.base).resolve(second)[1]['name'], 'Unsynced second edit')


if __name__ == '__main__':
    unittest.main()
