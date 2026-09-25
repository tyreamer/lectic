"""One secret link serves MCP to hosted assistants and captures from a phone; nothing else gets in."""
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from support import isolate_home
import ec
from lectic_mcp import connect_url, ensure_token, serve_http


class HttpTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve(); self.project = self.base / 'Project'; self.project.mkdir()
        self.home = isolate_home(self, self.base)
        self.httpd = serve_http(self.project, port=0, announce=None, allowed_origins=['app.example'])
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close); self.addCleanup(self.httpd.shutdown)
        self.origin = f'http://127.0.0.1:{self.httpd.server_address[1]}'
        self.link = connect_url(self.origin, self.httpd.token)

    def request(self, url, body=None, method=None, headers=None, content_type='application/json'):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode('utf-8'))
        req = urllib.request.Request(url, data=data, method=method or ('POST' if data is not None else 'GET'),
                                     headers={'Content-Type': content_type, 'Accept': 'application/json, text/event-stream', **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read(); return response.status, (json.loads(raw) if raw else None), dict(response.headers)
        except urllib.error.HTTPError as exc:
            raw = exc.read(); return exc.code, (json.loads(raw) if raw else None), dict(exc.headers)

    def test_secret_link_is_the_only_way_in(self):
        from release_version import VERSION
        self.assertEqual(self.request(self.origin + '/health')[0:2], (200, {'ok': True, 'server': 'lectic', 'version': VERSION}))
        self.assertEqual(self.request(self.origin + '/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})[0], 401)
        self.assertEqual(self.request(self.origin + '/t/wrong-token/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})[0], 401)
        self.assertEqual(self.request(self.origin + '/t/' + self.httpd.token + '/nope', {})[0], 404)
        # The secret works in the path (hosted chat connectors) or as a bearer header (CLI clients).
        self.assertEqual(self.request(self.link, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})[1]['result'], {})
        status, body, _ = self.request(self.origin + '/mcp', {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
                                       headers={'Authorization': 'Bearer ' + self.httpd.token})
        self.assertEqual((status, body['result']), (200, {}))
        # A browser page from elsewhere cannot drive a server bound to this machine.
        self.assertEqual(self.request(self.link, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, headers={'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.request(self.link, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, headers={'Origin': 'https://app.example'})[0], 200)
        self.assertEqual(self.request(self.link, method='GET')[0], 405)
        self.assertEqual(self.request(self.link, method='DELETE')[0], 204)
        self.assertEqual(self.request(self.link, b'not json')[0], 400)

    def test_streamable_http_semantics(self):
        status, body, headers = self.request(self.link, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}})
        self.assertEqual(status, 200); self.assertEqual(body['result']['protocolVersion'], '2025-06-18')
        self.assertIn('Mcp-Session-Id', headers); self.assertEqual(headers['Content-Type'], 'application/json')
        status, body, _ = self.request(self.link, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual((status, body), (202, None))
        status, body, _ = self.request(self.link, [{'jsonrpc': '2.0', 'id': 2, 'method': 'ping'}, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list'}])
        self.assertEqual([m['id'] for m in body], [2, 3]); self.assertTrue(any(t['name'] == 'lectic_work' for t in body[1]['result']['tools']))
        status, body, _ = self.request(self.link, {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'lectic_work', 'arguments': {'action': 'list'}}})
        self.assertEqual(json.loads(body['result']['content'][0]['text'])['home'], str(self.home.resolve()))

    def test_phone_capture_endpoint_saves_and_never_retrieves(self):
        capture = self.origin + '/t/' + self.httpd.token + '/capture'
        status, body, _ = self.request(capture, b'https://www.youtube.com/watch?v=o64cI6tebnU', content_type='text/plain')
        self.assertEqual(status, 200); self.assertTrue(body['saved'] and body['new']); self.assertEqual(body['collections'], ['Inbox'])
        status, body2, _ = self.request(capture, {'value': 'Remember: ask about budget before demo', 'note': 'from a sales talk', 'collection': 'Sales'})
        self.assertEqual(status, 200); self.assertEqual(body2['collections'], ['Sales']); self.assertNotEqual(body2['capture_id'], body['capture_id'])
        self.assertEqual(self.request(capture, {'note': 'nothing shared'})[0], 400)
        self.assertEqual(self.request(self.origin + '/capture', b'x', content_type='text/plain')[0], 401)
        rows = self.request(self.link, {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'lectic_capture', 'arguments': {'action': 'list'}}})[1]
        items = {r['capture_id']: r for r in json.loads(rows['result']['content'][0]['text'])['items']}
        self.assertEqual(items[body['capture_id']]['processing_status'], 'awaiting_retrieval')  # a link is saved, never fetched
        self.assertEqual(items[body2['capture_id']]['user_context'][0]['note'], 'from a sales talk')
        self.assertFalse(list(self.home.rglob('ir.json')))

    def test_token_is_made_once_per_home_and_reused(self):
        token = ensure_token(self.home)
        self.assertEqual(self.httpd.token, token); self.assertEqual(ensure_token(self.home), token)
        self.assertGreaterEqual(len(token), 32)
        other = serve_http(self.project, port=0, token='explicit-token-for-a-hosted-deployment', announce=None)
        self.assertEqual(other.token, 'explicit-token-for-a-hosted-deployment'); other.server_close()


if __name__ == '__main__':
    unittest.main()
