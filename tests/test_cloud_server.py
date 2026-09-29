"""Integration tests for Lectic Cloud HTTP Server and Remote MCP Adapter.

Verifies:
1. OAuth 2.0 RFC 8414 metadata and authorization code flow with PKCE.
2. Authenticated MCP JSON-RPC 2.0 Streamable HTTP transport.
3. Multi-tenant security and authorization over HTTP.
4. Save -> Learn -> Organize -> Context -> Apply -> Export tool execution.
5. Phone capture endpoint.
"""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from account_service import AccountStore
from cloud_server import serve_cloud


class CloudServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)

        # Start cloud server on random available port
        cls.httpd = serve_cloud(cls.root, host='127.0.0.1', port=0)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

        port = cls.httpd.server_address[1]
        cls.origin = f"http://127.0.0.1:{port}"

        # Create test users
        cls.accounts = AccountStore(cls.root)
        cls.alice = cls.accounts.create_account('alice@example.com', 'password123', 'Alice')
        cls.bob = cls.accounts.create_account('bob@example.com', 'password123', 'Bob')

        cls.tok_alice = cls.accounts.create_access_token(cls.alice['account_id'], client_name='ChatGPT Alice')['token']
        cls.tok_bob = cls.accounts.create_access_token(cls.bob['account_id'], client_name='ChatGPT Bob')['token']

    @classmethod
    def tearDownClass(cls):
        try:
            cls.httpd.shutdown()
        except Exception:
            pass
        try:
            cls.httpd.server_close()
        except Exception:
            pass
        cls.temp.cleanup()

    def request(self, path, body=None, method=None, headers=None, content_type='application/json'):
        url = self.origin + path
        data = None
        if body is not None:
            if isinstance(body, bytes):
                data = body
            elif isinstance(body, str):
                data = body.encode('utf-8')
            else:
                data = json.dumps(body).encode('utf-8')

        req = urllib.request.Request(
            url,
            data=data,
            method=method or ('POST' if data is not None else 'GET'),
            headers={'Content-Type': content_type, **(headers or {})}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read()
                parsed = json.loads(raw) if (raw and 'application/json' in response.headers.get('Content-Type', '')) else raw
                return response.status, parsed, dict(response.headers)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            parsed = json.loads(raw) if (raw and 'application/json' in exc.headers.get('Content-Type', '')) else raw
            return exc.code, parsed, dict(exc.headers)

    def test_health_and_oauth_discovery(self):
        status, body, _ = self.request('/health')
        self.assertEqual(status, 200)
        self.assertIn(body['service'], ('waykit-cloud', 'lectic-cloud'))

        status, oauth_meta, _ = self.request('/.well-known/oauth-authorization-server')
        self.assertEqual(status, 200)
        self.assertEqual(oauth_meta['authorization_endpoint'], f"{self.origin}/oauth/authorize")
        self.assertEqual(oauth_meta['token_endpoint'], f"{self.origin}/oauth/token")
        self.assertIn('code', oauth_meta['response_types_supported'])

    def test_oauth_authorization_code_flow_via_http(self):
        verifier = 'test-code-verifier-string-for-pkce-12345678'
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')

        # 1. User submits consent form at /oauth/authorize
        form_data = urllib.parse.urlencode({
            'client_id': 'chatgpt',
            'redirect_uri': 'https://chatgpt.com/callback',
            'response_type': 'code',
            'scope': 'library:read library:write',
            'state': 'state123',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'email': 'alice@example.com',
            'password': 'password123'
        }).encode('utf-8')

        req = urllib.request.Request(f"{self.origin}/oauth/authorize", data=form_data, method='POST',
                                     headers={'Content-Type': 'application/x-www-form-urlencoded'})
        # Avoid following redirect automatically
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        try:
            res = opener.open(req)
            redirect_url = res.headers.get('Location')
        except urllib.error.HTTPError as exc:
            redirect_url = exc.headers.get('Location')

        self.assertIsNotNone(redirect_url)
        self.assertIn('https://chatgpt.com/callback', redirect_url)
        parsed_url = urllib.parse.urlparse(redirect_url)
        qs = urllib.parse.parse_qs(parsed_url.query)
        self.assertIn('code', qs)
        self.assertEqual(qs['state'][0], 'state123')
        auth_code = qs['code'][0]

        # 2. Client exchanges code for access token at /oauth/token
        token_payload = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': 'chatgpt',
            'redirect_uri': 'https://chatgpt.com/callback',
            'code_verifier': verifier
        }
        status, token_res, _ = self.request('/oauth/token', body=token_payload)
        self.assertEqual(status, 200)
        self.assertIn('access_token', token_res)
        self.assertEqual(token_res['token_type'], 'Bearer')

        issued_token = token_res['access_token']
        # 3. Use issued token on /mcp
        mcp_msg = {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}
        status, ping_res, _ = self.request('/mcp', body=mcp_msg, headers={'Authorization': f'Bearer {issued_token}'})
        self.assertEqual(status, 200)
        self.assertEqual(ping_res['result'], {})

    def test_mcp_authentication_enforcement(self):
        # Missing token
        status, body, _ = self.request('/mcp', body={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'})
        self.assertEqual(status, 401)

        # Invalid token
        status, body, _ = self.request('/mcp', body={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
                                       headers={'Authorization': 'Bearer bad_token'})
        self.assertEqual(status, 401)

        # Valid token
        status, body, _ = self.request('/mcp', body={'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
                                       headers={'Authorization': f'Bearer {self.tok_alice}'})
        self.assertEqual(status, 200)
        self.assertEqual(body['result'], {})

    def test_remote_mcp_vertical_slice(self):
        headers = {'Authorization': f'Bearer {self.tok_alice}'}

        # 1. initialize handshake
        init_msg = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}}
        status, init_res, h = self.request('/mcp', body=init_msg, headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(init_res['result']['protocolVersion'], '2025-06-18')
        self.assertIn('Mcp-Session-Id', h)

        # 2. tools/list
        list_msg = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
        status, list_res, _ = self.request('/mcp', body=list_msg, headers=headers)
        self.assertEqual(status, 200)
        tool_names = [t['name'] for t in list_res['result']['tools']]
        self.assertIn('save_knowledge', tool_names)
        self.assertIn('learn_from_source', tool_names)
        self.assertIn('organize_knowledge', tool_names)
        self.assertIn('get_relevant_context', tool_names)
        self.assertIn('apply_knowledge', tool_names)
        self.assertIn('search_knowledge', tool_names)
        self.assertIn('export_library', tool_names)

        # 3. save_knowledge
        save_msg = {
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/call',
            'params': {
                'name': 'save_knowledge',
                'arguments': {
                    'text': 'Photography advice: Use spot metering when shooting high-contrast portraits in backlit conditions.',
                    'title': 'Portrait Exposure Guide',
                    'collections': ['Photography']
                }
            }
        }
        status, save_res, _ = self.request('/mcp', body=save_msg, headers=headers)
        self.assertEqual(status, 200)
        save_data = json.loads(save_res['result']['content'][0]['text'])
        self.assertTrue(save_data['saved'])
        capture_id = save_data['capture_id']

        # 4. learn_from_source
        learn_msg = {
            'jsonrpc': '2.0',
            'id': 4,
            'method': 'tools/call',
            'params': {
                'name': 'learn_from_source',
                'arguments': {
                    'capture_id': capture_id,
                    'collection': 'Photography'
                }
            }
        }
        status, learn_res, _ = self.request('/mcp', body=learn_msg, headers=headers)
        self.assertEqual(status, 200)
        learn_data = json.loads(learn_res['result']['content'][0]['text'])
        self.assertEqual(learn_data['phase'], 'learned')
        self.assertGreater(learn_data['units_learned'], 0)

        # 5. get_relevant_context
        ctx_msg = {
            'jsonrpc': '2.0',
            'id': 5,
            'method': 'tools/call',
            'params': {
                'name': 'get_relevant_context',
                'arguments': {
                    'intent': 'Help me take a portrait in sunny afternoon backlight'
                }
            }
        }
        status, ctx_res, _ = self.request('/mcp', body=ctx_msg, headers=headers)
        self.assertEqual(status, 200)
        ctx_data = json.loads(ctx_res['result']['content'][0]['text'])
        self.assertIn('Photography', [c['name'] for c in ctx_data['using']])
        self.assertIn('spot metering', ctx_data['portable_context'].lower())

        # 6. apply_knowledge
        apply_msg = {
            'jsonrpc': '2.0',
            'id': 6,
            'method': 'tools/call',
            'params': {
                'name': 'apply_knowledge',
                'arguments': {
                    'intent': 'Review portrait camera settings for backlight'
                }
            }
        }
        status, apply_res, _ = self.request('/mcp', body=apply_msg, headers=headers)
        self.assertEqual(status, 200)
        apply_data = json.loads(apply_res['result']['content'][0]['text'])
        self.assertEqual(apply_data['phase'], 'applied')
        self.assertIn('spot metering', apply_data['applied_result'].lower())

        # 7. export_library
        export_msg = {
            'jsonrpc': '2.0',
            'id': 7,
            'method': 'tools/call',
            'params': {
                'name': 'export_library',
                'arguments': {}
            }
        }
        status, export_res, _ = self.request('/mcp', body=export_msg, headers=headers)
        self.assertEqual(status, 200)
        export_data = json.loads(export_res['result']['content'][0]['text'])
        self.assertEqual(export_data['phase'], 'library_exported')
        self.assertGreater(export_data['archive_size_bytes'], 0)

    def test_multi_user_isolation_over_remote_mcp(self):
        # Alice saves confidential data via MCP
        headers_alice = {'Authorization': f'Bearer {self.tok_alice}'}
        headers_bob = {'Authorization': f'Bearer {self.tok_bob}'}

        learn_msg = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'learn_from_source',
                'arguments': {
                    'text': 'Internal confidential engineering secret: Code red release on Friday at midnight.',
                    'title': 'Confidential Ops',
                    'collection': 'Confidential Ops'
                }
            }
        }
        self.request('/mcp', body=learn_msg, headers=headers_alice)

        # Bob attempts search_knowledge
        search_msg = {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/call',
            'params': {
                'name': 'search_knowledge',
                'arguments': {'query': 'Code red release'}
            }
        }
        status, bob_res, _ = self.request('/mcp', body=search_msg, headers=headers_bob)
        self.assertEqual(status, 200)
        search_data = json.loads(bob_res['result']['content'][0]['text'])
        self.assertEqual(search_data['total_matches'], 0)

        # Bob attempts get_relevant_context
        ctx_msg = {
            'jsonrpc': '2.0',
            'id': 3,
            'method': 'tools/call',
            'params': {
                'name': 'get_relevant_context',
                'arguments': {'intent': 'What is the plan for code red release?'}
            }
        }
        status, ctx_res, _ = self.request('/mcp', body=ctx_msg, headers=headers_bob)
        self.assertEqual(status, 200)
        ctx_data = json.loads(ctx_res['result']['content'][0]['text'])
        self.assertEqual(len(ctx_data['knowledge']), 0)
        self.assertNotIn('Confidential Ops', [c['name'] for c in ctx_data['using']])

    def test_phone_capture_endpoint(self):
        # Post text capture to /t/<token>/capture
        path = f"/t/{self.tok_alice}/capture"
        status, res, _ = self.request(path, body='https://www.youtube.com/watch?v=dQw4w9WgXcQ', content_type='text/plain')
        self.assertEqual(status, 200)
        self.assertTrue(res['saved'])
        self.assertIn('capture_id', res)


if __name__ == '__main__':
    unittest.main()
