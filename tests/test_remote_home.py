"""Phone saves survive a lost compute cache, with no overwrite on failed commits."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from capture_store import CaptureStore
from ec import Invalid
from home import home_scope
from lectic_mcp import Server
from remote_home import RemoteHome


class FreeHostingTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which('node'): self.skipTest('Node runtime is required for Worker integration tests')
        root = Path(__file__).resolve().parents[1]
        self.process = subprocess.Popen(['node', '--no-warnings', str(root / 'tests/free_worker_runtime.mjs')],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        def stop():
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process.stdout.close()
        self.addCleanup(stop)
        line = self.process.stdout.readline()
        if not line: self.fail('Worker test runtime did not start')
        self.origin = f"http://127.0.0.1:{json.loads(line)['port']}"
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'project'; self.project.mkdir()

    def request(self, path, payload=None, token='test-user-token', headers=None):
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(self.origin + path, data=data,
                     headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token, **(headers or {})})
        with urllib.request.urlopen(request, timeout=10) as response: return json.load(response)

    def cache(self, name):
        return RemoteHome(self.base / name, self.origin + '/store', 'test-store-token')

    def test_phone_save_survives_a_new_python_server_and_is_imported_once(self):
        saved = self.request('/capture', {'value': 'https://www.instagram.com/reel/WayKitFreeFixture/'})
        self.assertTrue(saved['saved'])
        first = self.cache('first-cache'); server = Server(self.project)
        with first.operation(server):
            self.assertEqual(CaptureStore(self.project).find(saved['capture_id'])[0]['url'],
                             'https://www.instagram.com/reel/WayKitFreeFixture/')
        second = self.cache('entirely-new-cache')
        with second.operation(server):
            self.assertEqual(len(CaptureStore(self.project).all()), 1)
        self.assertEqual(self.request('/store/queue', token='test-store-token')['items'], [])

    def test_failed_commit_never_acknowledges_or_loses_a_phone_save(self):
        saved = self.request('/capture', {'value': 'Keep this exact note.'})
        cache = self.cache('cache'); original = cache.request
        def fail_commit(path, value=None):
            if path == 'commit': raise Invalid('Injected commit failure')
            return original(path, value)
        with patch.object(cache, 'request', side_effect=fail_commit), self.assertRaises(Invalid):
            with cache.operation(Server(self.project)): pass
        self.assertEqual(self.request('/store/queue', token='test-store-token')['items'][0]['id'], saved['capture_id'])
        fresh = self.cache('after-restart')
        with fresh.operation(Server(self.project)):
            self.assertEqual(len(CaptureStore(self.project).all()), 1)

    def test_concurrent_writer_is_refused_and_machine_credentials_do_not_travel(self):
        cache = self.cache('cache')
        with cache.operation(Server(self.project)):
            with self.assertRaises(Invalid):
                with self.cache('other-cache').operation(Server(self.project)): pass
            (cache.root / 'server.json').write_text('{"token":"machine-only"}', encoding='utf-8')
        state = cache.request('manifest')
        self.assertNotIn('server.json', state['files'])

    def test_existing_local_home_cannot_be_used_as_a_replaceable_cache(self):
        home = self.base / 'user-home'; home.mkdir(); (home / 'library.json').write_text('{}')
        with self.assertRaises(Invalid): RemoteHome(home, self.origin + '/store', 'test-store-token')

    def test_phone_save_refreshes_capture_inventory_without_rechecking_all_methods(self):
        cache=self.cache('cache'); server=Server(self.project)
        first=self.request('/capture', {'value':'First saved note'})
        with cache.operation(server): pass
        second=self.request('/capture', {'value':'Second saved note'})
        with patch.object(server,'tool_library',side_effect=AssertionError('Unchanged methods were rechecked')):
            with cache.operation(server): pass
        state=cache.request('manifest')
        captures=state['library']['collections'][0]['captures']
        self.assertEqual({row['capture_id'] for row in captures}, {first['capture_id'],second['capture_id']})
        self.assertEqual(cache.request('queue')['items'],[])

    def test_server_identity_survives_restart_but_is_excluded_from_backup(self):
        from home_archive import archive_home, open_archive
        from identity import save_identity, load_identity
        cache = self.cache('first-cache')
        with cache.operation(Server(self.project)):
            Server(self.project).tool_capture_save(text='A saved note for the identity backup test.')
            identity = save_identity(self.project, 'Test Author', 'test@example.invalid')
        fresh = self.cache('new-cache')
        with fresh.operation(Server(self.project)):
            self.assertEqual(load_identity(self.project)['public_key'], identity['public_key'])
            self.assertNotIn('identity.json', open_archive(archive_home(fresh.root))[1])

    def test_phone_retry_is_idempotent_even_after_import_and_wrong_keys_are_refused(self):
        headers = {'Idempotency-Key': 'abcdef0123456789abcdef0123456789'}
        first = self.request('/capture', {'value': 'A retained note'}, headers=headers)
        with self.cache('cache').operation(Server(self.project)): pass
        again = self.request('/capture', {'value': 'A retained note'}, headers=headers)
        self.assertFalse(again['new']); self.assertEqual(first['capture_id'], again['capture_id'])
        with self.assertRaises(urllib.error.HTTPError): self.request('/store/manifest', token='wrong-token')
        with self.assertRaises(urllib.error.HTTPError): self.request('/capture', {'value': 'x'}, token='wrong-token')


if __name__ == '__main__': unittest.main()
