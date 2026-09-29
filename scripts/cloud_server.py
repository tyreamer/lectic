"""Authenticated WayKit Cloud HTTP Server & Remote MCP Adapter.

Provides:
- OAuth 2.0 Authorization Server endpoints (RFC 8414 metadata, /oauth/authorize, /oauth/token, /oauth/revoke)
- Remote MCP JSON-RPC 2.0 endpoints over Streamable HTTP (/mcp and /t/<token>/mcp)
- Minimal web dashboard for connection consent, library export, and token revocation (/account/*)
- Direct phone capture endpoint (/t/<token>/capture)

Strictly verifies authentication on every request and sandboxes all operations in the verified account's library.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import http.cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any, Dict, List, Optional
import urllib.parse

from account_service import AccountStore, AuthenticationError, AuthorizationError, AccountError
from cloud_library import CloudLibrary
from cloud_mcp import CloudMcpHandler
from release_version import VERSION


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WayKit Cloud &middot; Account &amp; Library</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f141c; color: #e6edf3; margin: 0; padding: 40px 20px; }
  .container { max-width: 680px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 32px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
  h1 { font-size: 24px; font-weight: 600; margin-top: 0; color: #58a6ff; }
  h2 { font-size: 18px; font-weight: 600; margin-top: 28px; border-bottom: 1px solid #21262d; padding-bottom: 8px; }
  p, label { font-size: 14px; line-height: 1.5; color: #8b949e; }
  .user-badge { background: #21262d; padding: 10px 14px; border-radius: 6px; font-size: 14px; color: #c9d1d9; margin-bottom: 20px; }
  .btn { display: inline-block; background: #238636; color: #ffffff; text-decoration: none; padding: 9px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; border: none; cursor: pointer; }
  .btn:hover { background: #2ea043; }
  .btn-danger { background: #da3633; }
  .btn-danger:hover { background: #f85149; }
  .btn-secondary { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; }
  .btn-secondary:hover { background: #30363d; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
  th, td { text-align: left; padding: 10px; border-bottom: 1px solid #21262d; }
  th { color: #8b949e; font-weight: 500; }
  .token-link { background: #0d1117; padding: 8px 12px; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-all; color: #79c0ff; border: 1px solid #30363d; }
  .alert { padding: 12px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; }
  .alert-success { background: #1f3526; color: #3fb950; border: 1px solid #238636; }
  .alert-error { background: #3c1e1e; color: #f85149; border: 1px solid #da3633; }
</style>
</head>
<body>
<div class="container">
  <h1>WayKit Cloud Library</h1>
  <div class="user-badge">
    Signed in as <strong>{display_name}</strong> ({email}) &middot; Account ID: <code>{account_id}</code>
  </div>

  {notification_html}

  <h2>Private Library Status</h2>
  <p>Your knowledge is saved in private cloud storage, accessible only by your authorized assistants.</p>
  <p><strong>Packs:</strong> {pack_count} &nbsp;|&nbsp; <strong>Revisions:</strong> {revision_count}</p>
  <p>
    <a href="/account/export" class="btn">Export Library (.waykit-home)</a>
  </p>

  <h2>Connected Assistants &amp; Connectors</h2>
  <p>These clients can read and search your library. You can revoke access at any time.</p>
  {tokens_table_html}

  <h2>Direct Assistant Connection Link</h2>
  <p>Paste this URL into ChatGPT (Custom GPT / Connector) or Claude as an MCP server:</p>
  <div class="token-link">{connect_url}</div>

  <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #21262d; text-align: right;">
    <a href="/account/logout" class="btn btn-secondary">Sign Out</a>
  </div>
</div>
</body>
</html>
"""

CONSENT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Connect WayKit</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f141c; color: #e6edf3; margin: 0; padding: 40px 20px; }
  .container { max-width: 440px; margin: 40px auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 32px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
  h1 { font-size: 20px; font-weight: 600; margin-top: 0; color: #58a6ff; text-align: center; }
  p { font-size: 14px; line-height: 1.5; color: #8b949e; text-align: center; }
  .client-box { background: #21262d; border-radius: 6px; padding: 12px; margin: 16px 0; font-size: 13px; text-align: center; color: #c9d1d9; }
  .form-group { margin-bottom: 16px; text-align: left; }
  label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #c9d1d9; }
  input[type="text"], input[type="email"], input[type="password"] { width: 100%; box-sizing: border-box; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #e6edf3; font-size: 14px; }
  input:focus { outline: none; border-color: #58a6ff; }
  .btn { display: block; width: 100%; box-sizing: border-box; background: #238636; color: #ffffff; text-decoration: none; padding: 10px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; border: none; cursor: pointer; text-align: center; margin-top: 20px; }
  .btn:hover { background: #2ea043; }
  .alert-error { background: #3c1e1e; color: #f85149; border: 1px solid #da3633; padding: 10px; border-radius: 6px; font-size: 13px; margin-bottom: 16px; }
  .permissions { font-size: 12px; color: #8b949e; margin-top: 16px; text-align: left; }
  .permissions ul { padding-left: 20px; margin: 6px 0; }
</style>
</head>
<body>
<div class="container">
  <h1>Connect your WayKit Library</h1>
  <div class="client-box">
    <strong>{client_name}</strong> is requesting permission to access your private WayKit library.
  </div>

  {error_html}

  <form method="POST" action="/oauth/authorize">
    <input type="hidden" name="client_id" value="{client_id}">
    <input type="hidden" name="redirect_uri" value="{redirect_uri}">
    <input type="hidden" name="response_type" value="{response_type}">
    <input type="hidden" name="scope" value="{scope}">
    <input type="hidden" name="state" value="{state}">
    <input type="hidden" name="code_challenge" value="{code_challenge}">
    <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">

    <div class="form-group">
      <label for="email">Account Email</label>
      <input type="email" id="email" name="email" required placeholder="you@example.com" value="{email_value}">
    </div>

    <div class="form-group">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" required placeholder="Your account password">
    </div>

    <div class="permissions">
      This allows {client_name} to:
      <ul>
        <li>Save content and notes you share during conversation</li>
        <li>Learn reusable methods when requested</li>
        <li>Search and retrieve your knowledge to assist you</li>
      </ul>
      You can revoke access at any time from your account dashboard.
    </div>

    <button type="submit" class="btn">Sign In &amp; Connect</button>
  </form>
</div>
</body>
</html>
"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sign In &middot; WayKit Cloud</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f141c; color: #e6edf3; margin: 0; padding: 40px 20px; }
  .container { max-width: 380px; margin: 40px auto; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 32px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
  h1 { font-size: 20px; font-weight: 600; margin-top: 0; color: #58a6ff; text-align: center; }
  .form-group { margin-bottom: 16px; }
  label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #c9d1d9; }
  input[type="text"], input[type="email"], input[type="password"] { width: 100%; box-sizing: border-box; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #e6edf3; font-size: 14px; }
  input:focus { outline: none; border-color: #58a6ff; }
  .btn { display: block; width: 100%; box-sizing: border-box; background: #238636; color: #ffffff; text-decoration: none; padding: 10px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; border: none; cursor: pointer; text-align: center; margin-top: 20px; }
  .btn:hover { background: #2ea043; }
  .alert-error { background: #3c1e1e; color: #f85149; border: 1px solid #da3633; padding: 10px; border-radius: 6px; font-size: 13px; margin-bottom: 16px; }
  .switch-link { text-align: center; margin-top: 16px; font-size: 13px; color: #8b949e; }
  .switch-link a { color: #58a6ff; text-decoration: none; }
</style>
</head>
<body>
<div class="container">
  <h1>Sign In to WayKit Cloud</h1>
  {error_html}
  <form method="POST" action="/account/login">
    <div class="form-group">
      <label for="email">Email</label>
      <input type="email" id="email" name="email" required placeholder="you@example.com">
    </div>
    <div class="form-group">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" required placeholder="Your password">
    </div>
    <button type="submit" class="btn">Sign In</button>
  </form>
</div>
</body>
</html>
"""


class CloudHttpHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for WayKit Cloud."""

    server_version = f"WayKitCloud/{VERSION} LecticCloud/{VERSION}"

    @property
    def cloud_root(self) -> Path:
        return self.server.cloud_root

    @property
    def account_store(self) -> AccountStore:
        return self.server.account_store

    @property
    def public_origin(self) -> str:
        host = self.headers.get('Host') or f"127.0.0.1:{self.server.server_address[1]}"
        proto = self.headers.get('X-Forwarded-Proto', 'http')
        return f"{proto}://{host}"

    def _cors_headers(self) -> Dict[str, str]:
        return {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, DELETE',
            'Access-Control-Allow-Headers': 'Authorization, Content-Type, Mcp-Session-Id, Mcp-Token',
            'Access-Control-Expose-Headers': 'Mcp-Session-Id'
        }

    def _send_json(self, status: int, data: Any, extra_headers: Optional[Dict[str, str]] = None) -> None:
        raw = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        for k, v in self._cors_headers().items():
            self.send_header(k, v)
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, status: int, html_text: str, extra_headers: Optional[Dict[str, str]] = None) -> None:
        raw = html_text.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        for k, v in self._cors_headers().items():
            self.send_header(k, v)
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, status: int, raw_bytes: bytes, content_type: str, filename: str) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw_bytes)))
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        for k, v in self._cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw_bytes)

    def _read_body_bytes(self) -> bytes:
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length > 0 else b''

    def _read_body_json(self) -> Any:
        raw = self._read_body_bytes()
        if not raw:
            return None
        return json.loads(raw.decode('utf-8'))

    def _read_body_form(self) -> Dict[str, str]:
        raw = self._read_body_bytes().decode('utf-8')
        parsed = urllib.parse.parse_qs(raw)
        return {k: v[0] for k, v in parsed.items()}

    def _get_cookie_session(self) -> Optional[str]:
        cookie_header = self.headers.get('Cookie')
        if not cookie_header:
            return None
        cookies = http.cookies.SimpleCookie(cookie_header)
        for cookie_name in ('waykit_session', 'lectic_session'):
            if cookie_name in cookies:
                token = cookies[cookie_name].value
                try:
                    return self.account_store.verify_token(token)
                except AuthenticationError:
                    pass
        return None

    def _get_auth_token(self) -> Optional[str]:
        # Check Authorization header
        auth = self.headers.get('Authorization', '')
        if auth.lower().startswith('bearer '):
            return auth[7:].strip()
        if self.headers.get('Mcp-Token'):
            return self.headers.get('Mcp-Token').strip()

        # Check path token /t/<token>/...
        match = re.match(r'^/t/([^/]+)/', self.path)
        if match:
            return match.group(1)

        return None

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in self._cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    # -------------------------------------------------------------------------
    # GET Handlers
    # -------------------------------------------------------------------------
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path == '/health':
            self._send_json(200, {'ok': True, 'service': 'waykit-cloud', 'legacy_service': 'lectic-cloud', 'version': VERSION})
            return

        # OAuth 2.0 RFC 8414 Authorization Server Metadata
        if path in ('/.well-known/oauth-authorization-server', '/.well-known/openid-configuration'):
            origin = self.public_origin
            metadata = {
                'issuer': origin,
                'authorization_endpoint': f"{origin}/oauth/authorize",
                'token_endpoint': f"{origin}/oauth/token",
                'revocation_endpoint': f"{origin}/oauth/revoke",
                'response_types_supported': ['code'],
                'grant_types_supported': ['authorization_code'],
                'token_endpoint_auth_methods_supported': ['client_secret_post', 'client_secret_basic', 'none'],
                'code_challenge_methods_supported': ['S256', 'plain']
            }
            self._send_json(200, metadata)
            return

        # OAuth Authorization Consent UI
        if path == '/oauth/authorize':
            params = urllib.parse.parse_qs(url.query)
            client_id = params.get('client_id', ['Assistant Client'])[0]
            redirect_uri = params.get('redirect_uri', [''])[0]
            response_type = params.get('response_type', ['code'])[0]
            scope = params.get('scope', ['library:read library:write'])[0]
            state = params.get('state', [''])[0]
            code_challenge = params.get('code_challenge', [''])[0]
            code_challenge_method = params.get('code_challenge_method', ['S256'])[0]

            html = CONSENT_HTML.format(
                client_name=client_id,
                client_id=client_id,
                redirect_uri=redirect_uri,
                response_type=response_type,
                scope=scope,
                state=state,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                error_html='',
                email_value=''
            )
            self._send_html(200, html)
            return

        # Account Web Dashboard
        if path == '/account/dashboard':
            account_id = self._get_cookie_session()
            if not account_id:
                token = self._get_auth_token()
                if token:
                    try:
                        account_id = self.account_store.verify_token(token)
                    except AuthenticationError:
                        pass
            if not account_id:
                self.send_response(302)
                self.send_header('Location', '/account/login')
                self.end_headers()
                return

            acc = self.account_store.get_account(account_id)
            lib = CloudLibrary(account_id, self.cloud_root, self.account_store)
            tokens = self.account_store.list_account_tokens(account_id)

            pack_count = len(lib.library.index.get('collections', []))
            rev_count = sum(len(c.get('revisions', [])) for c in lib.library.index.get('collections', []))

            # Build tokens table
            rows = []
            for t in tokens:
                status_str = '<span style="color:#da3633;">Revoked</span>' if t['revoked'] else '<span style="color:#3fb950;">Active</span>'
                btn = (f'<form method="POST" action="/account/revoke" style="display:inline;">'
                       f'<input type="hidden" name="token" value="{t["token"]}">'
                       f'<button type="submit" class="btn btn-danger" style="padding:4px 8px;font-size:12px;">Revoke</button></form>'
                       if not t['revoked'] else '')
                rows.append(f'<tr><td>{t["client_name"]}</td><td><code>{t["token_preview"]}</code></td><td>{t["created_at"][:10]}</td><td>{status_str}</td><td>{btn}</td></tr>')

            tokens_table = ('<table><thead><tr><th>Client</th><th>Token</th><th>Created</th><th>Status</th><th>Action</th></tr></thead><tbody>' +
                            '\n'.join(rows) + '</tbody></table>' if rows else '<p>No connected assistants yet.</p>')

            # Use first active token or generate preview connect URL
            active_tokens = [t['token'] for t in tokens if not t['revoked']]
            first_tok = active_tokens[0] if active_tokens else 'waykit_tok_...'
            connect_url = f"{self.public_origin}/t/{first_tok}/mcp"

            html = DASHBOARD_HTML.format(
                display_name=acc['display_name'],
                email=acc['email'],
                account_id=acc['account_id'],
                notification_html='',
                pack_count=pack_count,
                revision_count=rev_count,
                tokens_table_html=tokens_table,
                connect_url=connect_url
            )
            self._send_html(200, html)
            return

        # Direct Library Export Download
        if path == '/account/export':
            account_id = self._get_cookie_session()
            if not account_id:
                token = self._get_auth_token()
                if token:
                    try:
                        account_id = self.account_store.verify_token(token)
                    except AuthenticationError:
                        pass
            if not account_id:
                self._send_json(401, {'error': 'Unauthorized'})
                return

            lib = CloudLibrary(account_id, self.cloud_root, self.account_store)
            archive_bytes = lib.export_library()
            filename = f"waykit-library-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.waykit-home"
            self._send_bytes(200, archive_bytes, 'application/zip', filename)
            return

        # Login page
        if path == '/account/login':
            self._send_html(200, LOGIN_HTML.format(error_html=''))
            return

        if path == '/account/logout':
            self.send_response(302)
            self.send_header('Set-Cookie', 'waykit_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
            self.send_header('Set-Cookie', 'lectic_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
            self.send_header('Location', '/account/login')
            self.end_headers()
            return

        self._send_json(404, {'error': 'Not found'})

    # -------------------------------------------------------------------------
    # POST Handlers
    # -------------------------------------------------------------------------
    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        # 1. MCP Endpoints: /mcp or /t/<token>/mcp
        if path == '/mcp' or re.match(r'^/t/[^/]+/mcp$', path):
            token = self._get_auth_token()
            if not token:
                self._send_json(401, {'jsonrpc': '2.0', 'error': {'code': -32000, 'message': 'Missing authentication token'}})
                return

            try:
                account_id = self.account_store.verify_token(token)
            except AuthenticationError as exc:
                self._send_json(401, {'jsonrpc': '2.0', 'error': {'code': -32000, 'message': str(exc)}})
                return

            body = self._read_body_json()
            if not body or not isinstance(body, dict):
                self._send_json(400, {'jsonrpc': '2.0', 'error': {'code': -32700, 'message': 'Parse error: invalid JSON'}})
                return

            response = self._handle_mcp_message(account_id, body)
            if response is None:
                # 202 Accepted for notifications
                self.send_response(202)
                for k, v in self._cors_headers().items():
                    self.send_header(k, v)
                self.end_headers()
            else:
                session_id = f"session_{hashlib.sha256(account_id.encode('utf-8')).hexdigest()[:16]}"
                self._send_json(200, response, extra_headers={'Mcp-Session-Id': session_id})
            return

        # 2. Phone capture endpoint: /t/<token>/capture
        capture_match = re.match(r'^/t/([^/]+)/capture$', path)
        if capture_match:
            token = capture_match.group(1)
            try:
                account_id = self.account_store.verify_token(token)
            except AuthenticationError as exc:
                self._send_json(401, {'error': str(exc)})
                return

            lib = CloudLibrary(account_id, self.cloud_root, self.account_store)
            content_type = self.headers.get('Content-Type', '')
            raw_bytes = self._read_body_bytes()

            if 'application/json' in content_type:
                try:
                    payload = json.loads(raw_bytes.decode('utf-8'))
                    value = payload.get('value') or payload.get('text') or payload.get('url') or ''
                    note = payload.get('note', '')
                    col = payload.get('collection')
                    cols = (col,) if col else ()
                except Exception:
                    self._send_json(400, {'error': 'Invalid JSON in capture request'})
                    return
            else:
                value = raw_bytes.decode('utf-8', errors='ignore').strip()
                note = ''
                cols = ()

            if not value:
                self._send_json(400, {'error': 'Empty share input'})
                return

            res = lib.save_knowledge(text=value if not value.startswith(('http://', 'https://')) else '',
                                     url=value if value.startswith(('http://', 'https://')) else '',
                                     note=note, collections=cols)
            self._send_json(200, res)
            return

        # 3. OAuth: /oauth/authorize (Form submission from consent UI)
        if path == '/oauth/authorize':
            form = self._read_body_form()
            email = form.get('email', '').strip()
            password = form.get('password', '').strip()
            client_id = form.get('client_id', 'Assistant Client')
            redirect_uri = form.get('redirect_uri', '')
            state = form.get('state', '')
            code_challenge = form.get('code_challenge')
            code_challenge_method = form.get('code_challenge_method')

            try:
                acc = self.account_store.authenticate(email, password)
                code = self.account_store.create_authorization_code(
                    account_id=acc['account_id'],
                    client_id=client_id,
                    redirect_uri=redirect_uri,
                    code_challenge=code_challenge,
                    code_challenge_method=code_challenge_method
                )
                sep = '&' if '?' in redirect_uri else '?'
                target = f"{redirect_uri}{sep}code={code}"
                if state:
                    target += f"&state={urllib.parse.quote(state)}"

                self.send_response(302)
                self.send_header('Location', target)
                self.end_headers()
                return

            except AuthenticationError as exc:
                html = CONSENT_HTML.format(
                    client_name=client_id,
                    client_id=client_id,
                    redirect_uri=redirect_uri,
                    response_type=form.get('response_type', 'code'),
                    scope=form.get('scope', ''),
                    state=state,
                    code_challenge=code_challenge or '',
                    code_challenge_method=code_challenge_method or 'S256',
                    error_html=f'<div class="alert-error">{exc}</div>',
                    email_value=email
                )
                self._send_html(200, html)
                return

        # 4. OAuth: /oauth/token (Exchange code for token)
        if path == '/oauth/token':
            content_type = self.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                payload = self._read_body_json() or {}
            else:
                payload = self._read_body_form()

            code = payload.get('code', '')
            client_id = payload.get('client_id', '')
            redirect_uri = payload.get('redirect_uri', '')
            code_verifier = payload.get('code_verifier')

            try:
                token_res = self.account_store.exchange_authorization_code(
                    code=code,
                    client_id=client_id,
                    redirect_uri=redirect_uri,
                    code_verifier=code_verifier
                )
                self._send_json(200, token_res)
                return
            except AuthenticationError as exc:
                self._send_json(400, {'error': 'invalid_grant', 'error_description': str(exc)})
                return

        # 5. OAuth: /oauth/revoke
        if path == '/oauth/revoke':
            payload = self._read_body_form()
            token = payload.get('token', '')
            self.account_store.revoke_token(token)
            self._send_json(200, {'status': 'revoked'})
            return

        # 6. Web Account Login: /account/login
        if path == '/account/login':
            form = self._read_body_form()
            email = form.get('email', '').strip()
            password = form.get('password', '').strip()

            try:
                acc = self.account_store.authenticate(email, password)
                token_rec = self.account_store.create_access_token(acc['account_id'], client_name='Web Session')
                self.send_response(302)
                self.send_header('Set-Cookie', f"waykit_session={token_rec['token']}; Path=/; HttpOnly; SameSite=Lax")
                self.send_header('Set-Cookie', f"lectic_session={token_rec['token']}; Path=/; HttpOnly; SameSite=Lax")
                self.send_header('Location', '/account/dashboard')
                self.end_headers()
                return
            except AuthenticationError as exc:
                self._send_html(200, LOGIN_HTML.format(error_html=f'<div class="alert-error">{exc}</div>'))
                return

        # 7. Web Account Revoke Action: /account/revoke
        if path == '/account/revoke':
            account_id = self._get_cookie_session()
            if not account_id:
                self.send_response(302)
                self.send_header('Location', '/account/login')
                self.end_headers()
                return

            form = self._read_body_form()
            token_to_revoke = form.get('token', '')
            try:
                self.account_store.revoke_token(token_to_revoke, account_id=account_id)
            except AuthorizationError:
                pass
            self.send_response(302)
            self.send_header('Location', '/account/dashboard')
            self.end_headers()
            return

        self._send_json(404, {'error': 'Not found'})

    # -------------------------------------------------------------------------
    # MCP JSON-RPC 2.0 Dispatcher
    # -------------------------------------------------------------------------
    def _handle_mcp_message(self, account_id: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        msg_id = message.get('id')
        method = message.get('method', '')
        params = message.get('params', {})

        if method == 'notifications/initialized':
            return None

        if method == 'ping':
            return {'jsonrpc': '2.0', 'id': msg_id, 'result': {}}

        if method == 'initialize':
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {
                    'protocolVersion': params.get('protocolVersion', '2025-06-18'),
                    'serverInfo': {'name': 'waykit-cloud', 'legacy_name': 'lectic-cloud', 'version': VERSION},
                    'capabilities': {
                        'tools': {'listChanged': False}
                    },
                    'instructions': 'You are connected to WayKit Cloud. Use save_knowledge, learn_from_source, organize_knowledge, get_relevant_context, and apply_knowledge to assist the user.'
                }
            }

        lib = CloudLibrary(account_id, self.cloud_root, self.account_store)
        handler = CloudMcpHandler(lib)

        if method == 'tools/list':
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {'tools': handler.list_tools()}
            }

        if method == 'tools/call':
            name = params.get('name', '')
            arguments = params.get('arguments', {})
            tool_result = handler.call_tool(name, arguments)
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': tool_result
            }

        return {
            'jsonrpc': '2.0',
            'id': msg_id,
            'error': {'code': -32601, 'message': f'Method not found: {method}'}
        }


def serve_cloud(cloud_root: Path | str, host: str = '127.0.0.1', port: int = 8787) -> ThreadingHTTPServer:
    """Create and return a running ThreadingHTTPServer for WayKit Cloud."""
    root = Path(cloud_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    account_store = AccountStore(root)

    server = ThreadingHTTPServer((host, port), CloudHttpHandler)
    server.cloud_root = root
    server.account_store = account_store
    return server
