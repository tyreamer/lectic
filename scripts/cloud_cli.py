"""WayKit Cloud CLI subcommands.

Provides:
    waykit cloud serve [--host H] [--port P] [--root R]
    waykit cloud create-user <email> [--password P] [--name N] [--root R]
    waykit cloud list-users [--root R] [--json]
    waykit cloud token <email-or-id> [--client NAME] [--root R] [--json]
    waykit cloud export <email-or-id> [--out PATH] [--root R]

Legacy `lectic cloud ...` commands remain supported aliases.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sys
from typing import List, Optional

from account_service import AccountStore, AccountError
from cloud_library import CloudLibrary
from cloud_server import serve_cloud


def _get_cloud_root(argv: List[str]) -> Path:
    for i, a in enumerate(argv):
        if a in ('--root', '-r') and i + 1 < len(argv):
            return Path(argv[i + 1]).resolve()
    env = os.environ.get('WAYKIT_CLOUD_ROOT') or os.environ.get('LECTIC_CLOUD_ROOT')
    if env:
        return Path(env).resolve()
    default_waykit = Path.home() / '.waykit-cloud'
    default_lectic = Path.home() / '.lectic-cloud'
    if not default_waykit.exists() and default_lectic.exists():
        return default_lectic
    return default_waykit


def _get_opt(argv: List[str], flag: str, default: Optional[str] = None) -> Optional[str]:
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def cloud_cmd(argv: List[str]) -> int:
    """Entrypoint for `waykit cloud ...` subcommands."""
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(__doc__.strip())
        return 0

    sub = argv[0]
    rest = argv[1:]
    root = _get_cloud_root(rest)

    if sub == 'serve':
        host = _get_opt(rest, '--host', '127.0.0.1')
        port = int(_get_opt(rest, '--port', '8787'))
        httpd = serve_cloud(root, host=host, port=port)
        actual_port = httpd.server_address[1]
        origin = f"http://{host}:{actual_port}"
        print(f"WayKit Cloud running at: {origin}")
        print(f"  OAuth Metadata:  {origin}/.well-known/oauth-authorization-server")
        print(f"  MCP Endpoint:    {origin}/mcp")
        print(f"  Web Dashboard:   {origin}/account/dashboard")
        print(f"  Storage Root:    {root}")
        print("\nPress Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down WayKit Cloud.")
        return 0

    accounts = AccountStore(root)

    if sub == 'create-user':
        email = next((a for a in rest if not a.startswith('-') and a != _get_opt(rest, '--password')
                      and a != _get_opt(rest, '--name') and a != _get_opt(rest, '--root')), None)
        if not email:
            print("Usage: waykit cloud create-user <email> [--password PASSWORD] [--name NAME] [--root ROOT]")
            return 2
        password = _get_opt(rest, '--password') or secrets.token_urlsafe(12)
        name = _get_opt(rest, '--name', email.split('@')[0].capitalize())

        try:
            acc = accounts.create_account(email, password, name)
            tok_res = accounts.create_access_token(acc['account_id'], client_name='CLI Admin')
            if '--json' in rest:
                print(json.dumps({'account': acc, 'initial_token': tok_res['token'], 'password': password}, indent=2))
                return 0
            print("Account created successfully:")
            print(f"  Account ID: {acc['account_id']}")
            print(f"  Email:      {acc['email']}")
            print(f"  Name:       {acc.get('display_name', '')}")
            print(f"  Password:   {password}")
            print(f"  Token:      {tok_res['token']}")
            print("\nConnect with ChatGPT or Claude using OAuth or token-based connection.")
            return 0
        except AccountError as exc:
            print(f"Error creating account: {exc}")
            return 1

    if sub == 'list-users':
        user_list = accounts.list_accounts()
        if '--json' in rest:
            print(json.dumps(user_list, indent=2))
            return 0
        if not user_list:
            print(f"No accounts registered in {root}.")
            return 0
        print(f"Registered Accounts ({len(user_list)} in {root}):")
        for u in user_list:
            display = u.get('display_name', '')
            print(f"  {u['account_id']}  {u['email']:<30}  {display:<15}  Created: {u['created_at'][:10]}")
        return 0

    if sub == 'token':
        target = next((a for a in rest if not a.startswith('-') and a != _get_opt(rest, '--client')
                       and a != _get_opt(rest, '--root')), None)
        if not target:
            print("Usage: waykit cloud token <email-or-id> [--client CLIENT_NAME] [--root ROOT]")
            return 2
        client = _get_opt(rest, '--client', 'CLI Token')
        acc = accounts.get_account_by_email(target) or accounts.get_account(target)
        if not acc:
            print(f"No account found matching '{target}'.")
            return 1
        tok_res = accounts.create_access_token(acc['account_id'], client_name=client)
        if '--json' in rest:
            print(json.dumps(tok_res, indent=2))
            return 0
        print(f"Created token for {acc['email']} ({client}):")
        print(f"  Token: {tok_res['token']}")
        print(f"  Expires: {tok_res['expires_at']}")
        return 0

    if sub == 'export':
        target = next((a for a in rest if not a.startswith('-') and a != _get_opt(rest, '--out')
                       and a != _get_opt(rest, '--root')), None)
        if not target:
            print("Usage: waykit cloud export <email-or-id> [--out ARCHIVE.waykit-home] [--root ROOT]")
            return 2
        acc = accounts.get_account_by_email(target) or accounts.get_account(target)
        if not acc:
            print(f"No account found matching '{target}'.")
            return 1
        lib = CloudLibrary(acc['account_id'], root, accounts)
        archive_bytes = lib.export_library()
        out_path = Path(_get_opt(rest, '--out') or f"waykit-cloud-{acc['account_id']}.waykit-home").resolve()
        out_path.write_bytes(archive_bytes)
        print(f"Exported library for {acc['email']}:")
        print(f"  File: {out_path} ({len(archive_bytes)} bytes)")
        print(f"  Restore locally with:  waykit restore \"{out_path}\"")
        return 0

    print(f"Unknown cloud command: {sub}")
    print(__doc__.strip())
    return 2
