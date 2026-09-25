from contextlib import redirect_stdout
import functools
import http.server
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home, at_home
import ec
from collection_store import Library
from demo import build
from goal_workflow import work
from library_guide import library_view
from packs import build_pack, inspect_pack, install_pack, open_pack, update_pack
from publish import publish_pack
import cli


class TeamDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.oracle = build(self.base / 'oracle')
        self.author = self.base / 'author'; self.author.mkdir()
        self.home = isolate_home(self, self.base, 'author-home')

    def seed(self, run):
        corpus, docs, _ = ec.validate_sources(run)
        _, originals, _ = ec.validate_sources(self.oracle)
        by_hash = {d['content_hash']: d for d in originals.values()}
        for sid, doc in docs.items():
            original = by_hash[doc['content_hash']]
            part = json.loads(json.dumps(ec.read(self.oracle / f"units/{original['source_id']}.json")).replace(original['source_id'], sid))
            part['corpus_id'] = corpus['corpus_id']
            ec.write(Path(run) / f'units/{sid}.json', part)

    def prepared_collection(self, name, inputs):
        folder = self.author / ('input-' + ec.digest(name.encode())[:6]); folder.mkdir()
        for filename, source in inputs.items(): shutil.copy(source, folder / filename)
        result = work(project=self.author, input=str(folder), name=name, action='save')
        self.seed(result['run'])
        result = work(project=self.author, collection=name, action='prepare', reconciled=True)
        self.assertEqual(result['phase'], 'knowledge_saved')
        return result

    def other_home(self, name):
        project = self.base / name; project.mkdir()
        return project, isolate_home(self, self.base, name + '-home')

    # ---- 2a. Team pack format
    def test_team_pack_format_includes_sources_distribution_and_install_md(self):
        self.prepared_collection('Engineering Standards', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack_out = self.base / 'eng.lectic'
        res = build_pack(self.author, 'Engineering Standards', pack_out, team=True, version='2.1.0')

        self.assertEqual(res['version'], '2.1.0')
        self.assertTrue(res['team'])
        self.assertTrue(res['sources_included'])
        self.assertEqual(res['distribution']['scope'], 'team')
        self.assertEqual(res['distribution']['install_name'], 'engineering-standards')
        self.assertEqual(res['distribution']['pinned_version'], '2.1.0')

        # Check archive contents
        with zipfile.ZipFile(pack_out) as archive:
            names = set(archive.namelist())
            self.assertIn('INSTALL.md', names)
            self.assertIn('README.md', names)
            self.assertIn('pack.json', names)
            install_content = archive.read('INSTALL.md').decode('utf-8')
            self.assertIn('Claude Code', install_content)
            self.assertIn('Codex', install_content)
            self.assertIn('ChatGPT', install_content)
            self.assertIn('lectic install', install_content)
            self.assertIn('--as engineering-standards', install_content)
            self.assertIn('--pin', install_content)

        # inspect_pack should surface distribution and install_md
        info = inspect_pack(str(pack_out))
        self.assertEqual(info['version'], '2.1.0')
        self.assertEqual(info['distribution']['scope'], 'team')
        self.assertIn('install_md', info)
        self.assertIn('Claude Code', info['install_md'])

    def test_install_team_pack_default_name_and_as_flag_with_pin(self):
        self.prepared_collection('Engineering Standards', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack_out = self.base / 'eng.lectic'
        build_pack(self.author, 'Engineering Standards', pack_out, team=True, version='2.1.0')

        # Install without explicit name: uses distribution.install_name
        project1, home1 = self.other_home('dev1')
        rep1 = install_pack(project1, str(pack_out), pin=True)
        self.assertEqual(rep1['collection'], 'engineering-standards')
        self.assertEqual(rep1['version'], '2.1.0')
        self.assertTrue(rep1['pinned'])
        self.assertEqual(rep1['pinned_version'], '2.1.0')
        folder1 = Library(project1).resolve(rep1['collection_id'])[0]
        self.assertTrue((folder1 / 'pack/INSTALL.md').is_file())
        origin1 = json.loads((folder1 / 'pack-origin.json').read_text(encoding='utf-8'))
        self.assertTrue(origin1['pinned'])
        self.assertEqual(origin1['pinned_version'], '2.1.0')

        # Install with --as flag
        project2, home2 = self.other_home('dev2')
        rep2 = install_pack(project2, str(pack_out), name='eng', pin=True)
        self.assertEqual(rep2['collection'], 'eng')
        self.assertTrue(rep2['pinned'])
        self.assertEqual(rep2['pinned_version'], '2.1.0')

    # ---- 2b. Pack version pinning and update
    def test_update_pack_when_already_up_to_date(self):
        self.prepared_collection('Frontend Rules', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack_v1 = self.base / 'fe-v1.lectic'
        build_pack(self.author, 'Frontend Rules', pack_v1, team=True, version='1.0.0')

        project, home = self.other_home('fe-dev')
        install_pack(project, str(pack_v1), name='frontend', pin=True)

        # Checking update against the same pack
        up_res = update_pack(project, 'frontend')
        self.assertEqual(up_res['phase'], 'up_to_date')
        self.assertIn('already up to date', up_res['message'])

    def test_update_pack_with_newer_version_updates_in_place_and_reports_diff(self):
        self.prepared_collection('Frontend Rules', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack_path = self.base / 'fe.lectic'
        build_pack(self.author, 'Frontend Rules', pack_path, team=True, version='1.0.0')

        project, home = self.other_home('fe-dev')
        rep = install_pack(project, str(pack_path), name='frontend', pin=True)
        cid = rep['collection_id']

        # Now author compiles version 1.1.0 under author home
        author_home = self.home
        with at_home(author_home):
            build_pack(self.author, 'Frontend Rules', pack_path, team=True, version='1.1.0')

        # Dev runs update
        up_res = update_pack(project, 'frontend')
        self.assertEqual(up_res['phase'], 'installed')
        self.assertIn('update', up_res)
        self.assertEqual(up_res['update']['from_version'], '1.0.0')
        self.assertEqual(up_res['update']['to_version'], '1.1.0')
        self.assertIn('Updated frontend from 1.0.0 to 1.1.0', up_res['summary_message'])

        # Verify collection_id is retained (updated in-place)
        folder_dev = Library(project).resolve('frontend')[0]
        origin = json.loads((folder_dev / 'pack-origin.json').read_text(encoding='utf-8'))
        self.assertEqual(origin['version'], '1.1.0')
        self.assertTrue(origin['pinned'])

    # ---- 2c. Publish
    def test_publish_generic_http_put_and_webhook(self):
        self.prepared_collection('API Standards', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack_path = self.base / 'api.lectic'
        build_pack(self.author, 'API Standards', pack_path, team=True, version='3.0.0')

        uploaded = []
        webhook_received = []

        class TestServer(http.server.BaseHTTPRequestHandler):
            def do_PUT(self):
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                uploaded.append((self.path, body))
                self.send_response(200)
                self.end_headers()

            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length).decode('utf-8'))
                webhook_received.append((self.path, body))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args, **kwargs):
                pass

        httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), TestServer)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close); self.addCleanup(httpd.shutdown)

        port = httpd.server_address[1]
        upload_url = f'http://127.0.0.1:{port}/packs/api.lectic'
        webhook_url = f'http://127.0.0.1:{port}/webhook/slack'

        res = publish_pack(self.author, str(pack_path), upload_url, webhook_url=webhook_url)

        self.assertEqual(res['phase'], 'published')
        self.assertEqual(res['version'], '3.0.0')
        self.assertEqual(res['install_name'], 'api-standards')
        self.assertEqual(res['download_url'], upload_url)
        self.assertIn('Published API Standards v3.0.0', res['message'])
        self.assertIn(f'lectic install {upload_url} --as api-standards', res['install_command'])
        self.assertTrue(res['webhook_sent'])

        self.assertEqual(len(uploaded), 1)
        self.assertEqual(uploaded[0][0], '/packs/api.lectic')
        self.assertEqual(len(webhook_received), 1)
        self.assertEqual(webhook_received[0][1]['pack']['version'], '3.0.0')
        self.assertIn('lectic install', webhook_received[0][1]['text'])

    def test_publish_presigned_s3_url_strips_query_string(self):
        self.prepared_collection('Storage Rules', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack_path = self.base / 'storage.lectic'
        build_pack(self.author, 'Storage Rules', pack_path, team=True, version='1.0.0')

        class PutHandler(http.server.BaseHTTPRequestHandler):
            def do_PUT(self):
                length = int(self.headers.get('Content-Length', 0))
                self.rfile.read(length)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args, **kwargs):
                pass

        httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), PutHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close); self.addCleanup(httpd.shutdown)

        port = httpd.server_address[1]
        presigned = f'http://127.0.0.1:{port}/storage.lectic?X-Amz-Algorithm=AWS4-HMAC-SHA256&Signature=abcdef'
        res = publish_pack(self.author, str(pack_path), presigned)

        self.assertEqual(res['download_url'], f'http://127.0.0.1:{port}/storage.lectic')
        self.assertNotIn('Signature', res['download_url'])

    def test_publish_github_requires_token(self):
        self.prepared_collection('GH Rules', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack_path = self.base / 'gh.lectic'
        build_pack(self.author, 'GH Rules', pack_path, team=True, version='1.0.0')

        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(ec.Invalid, 'Publishing to GitHub Releases requires a token'):
                publish_pack(self.author, str(pack_path), 'https://github.com/myorg/myrepo/releases/tag/v1.0.0')

    def test_publish_github_releases_upload(self):
        self.prepared_collection('GH Rules 2', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        pack_path = self.base / 'gh2.lectic'
        build_pack(self.author, 'GH Rules 2', pack_path, team=True, version='1.0.0')

        calls = []
        class FakeResp:
            def __init__(self, data, status=200):
                self._data = data
                self.status = status
            def read(self, *args):
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        def fake_urlopen(req, *args, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req
            method = req.get_method() if hasattr(req, 'get_method') else 'GET'
            calls.append((method, url))
            if 'releases/tags/v1.0.0' in url:
                return FakeResp(json.dumps({
                    'id': 12345,
                    'tag_name': 'v1.0.0',
                    'upload_url': 'https://uploads.github.com/repos/myorg/myrepo/releases/12345/assets{?name,label}',
                    'assets': [{'id': 99, 'name': 'gh2.lectic', 'url': 'https://api.github.com/repos/myorg/myrepo/releases/assets/99'}]
                }).encode('utf-8'))
            if 'releases/assets/99' in url and method == 'DELETE':
                return FakeResp(b'', 204)
            if 'uploads.github.com' in url and method == 'POST':
                return FakeResp(json.dumps({
                    'id': 100,
                    'name': 'gh2.lectic',
                    'browser_download_url': 'https://github.com/myorg/myrepo/releases/download/v1.0.0/gh2.lectic'
                }).encode('utf-8'))
            return FakeResp(b'{}')

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            res = publish_pack(self.author, str(pack_path), 'https://github.com/myorg/myrepo/releases/tag/v1.0.0', token='test-token')

        self.assertEqual(res['phase'], 'published')
        self.assertEqual(res['download_url'], 'https://github.com/myorg/myrepo/releases/download/v1.0.0/gh2.lectic')
        self.assertIn('lectic install https://github.com/myorg/myrepo/releases/download/v1.0.0/gh2.lectic --as gh-rules-2', res['install_command'])
        self.assertTrue(any(m == 'DELETE' and 'assets/99' in u for m, u in calls))
        self.assertTrue(any(m == 'POST' and 'uploads.github.com' in u for m, u in calls))

    # ---- CLI integration tests
    def run_cli(self, *args):
        out = io.StringIO()
        with patch('sys.stdin', io.StringIO()), patch('cli.Path.cwd', return_value=self.author), patch('os.getcwd', return_value=str(self.author)):
            with redirect_stdout(out):
                code = cli.main(list(args))
        return code, out.getvalue()

    def test_cli_pack_team_and_install_with_as_and_pin(self):
        self.prepared_collection('Backend Patterns', {'debugging.srt': ec.ROOT / 'fixtures/debugging/debugging.srt'})
        out_file = self.base / 'backend.lectic'

        code, out = self.run_cli('pack', 'Backend Patterns', '--team', '--version', '2.5.0', '--out', str(out_file))
        self.assertEqual(code, 0, out)
        self.assertIn('Packed Backend Patterns v2.5.0 (team pack)', out)
        self.assertIn('--as backend-patterns --pin', out)

        # CLI install with --as and --pin
        code, out = self.run_cli('install', str(out_file), '--as', 'backend', '--pin')
        self.assertEqual(code, 0, out)
        self.assertIn('Installed backend [pinned: v2.5.0]', out)

        # CLI status shows pinned collection
        code, out = self.run_cli('status')
        self.assertEqual(code, 0, out)
        self.assertIn('backend  v2.5.0 [pinned]', out)

        # CLI update when up to date
        code, out = self.run_cli('update', 'backend')
        self.assertEqual(code, 0, out)
        self.assertIn('already up to date', out)


if __name__ == '__main__':
    unittest.main()
