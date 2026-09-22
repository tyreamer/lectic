"""`lectic`: the one command a person needs.

    lectic setup     connect the assistants on this machine, verify the connection, offer YouTube support
    lectic status    where knowledge lives, what is saved, which assistants are connected
    lectic serve     run the MCP server (what the assistants launch; you rarely run it yourself)
    lectic ec ...    the deterministic utilities, for contributors

Everything else happens in conversation with the connected assistant.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))

SERVER_NAME = 'lectic'


def server_command():
    """How an assistant launches the server: this interpreter, this package, no PATH assumptions."""
    try:
        import lectic  # noqa: F401  (installed package)
        return [sys.executable, '-m', 'lectic.cli', 'serve']
    except ImportError:  # running from a checkout
        return [sys.executable, str(Path(__file__).resolve()), 'serve']


# ----------------------------------------------------------------- clients

def claude_config_path():
    return Path.home() / '.claude.json'


def codex_config_path():
    return Path.home() / '.codex' / 'config.toml'


def claude_connected():
    path = claude_config_path()
    if not path.is_file(): return False
    try:
        servers = json.loads(path.read_text(encoding='utf-8')).get('mcpServers', {})
    except (ValueError, AttributeError):
        return False
    return SERVER_NAME in servers


def connect_claude(runner=None):
    """Prefer Claude Code's own CLI; fall back to its user config when the CLI is not on PATH."""
    runner = runner or subprocess.run
    command = server_command()
    claude = shutil.which('claude')
    if claude:
        for attempt in range(2):
            result = runner([claude, 'mcp', 'add', '--scope', 'user', SERVER_NAME, '--'] + command,
                            capture_output=True, text=True)
            if result.returncode == 0: return 'connected'
            if 'already exists' in (result.stdout + result.stderr) and attempt == 0:
                runner([claude, 'mcp', 'remove', '--scope', 'user', SERVER_NAME], capture_output=True, text=True)
                continue
            return 'failed: ' + ' '.join((result.stderr or result.stdout).split())[:300]
    path = claude_config_path()
    if not path.is_file(): return 'not installed'
    try:
        config = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return 'failed: ~/.claude.json is not valid JSON'
    servers = config.setdefault('mcpServers', {})
    servers[SERVER_NAME] = {'type': 'stdio', 'command': command[0], 'args': command[1:]}
    path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return 'connected'


def codex_connected():
    path = codex_config_path()
    return path.is_file() and f'[mcp_servers.{SERVER_NAME}]' in path.read_text(encoding='utf-8')


def connect_codex():
    path = codex_config_path()
    if not path.parent.is_dir(): return 'not installed'
    existing = path.read_text(encoding='utf-8') if path.is_file() else ''
    if f'[mcp_servers.{SERVER_NAME}]' in existing: return 'connected'
    command = server_command()
    literal = lambda value: "'" + str(value).replace("'", "''") + "'"
    block = (f'\n[mcp_servers.{SERVER_NAME}]\ncommand = {literal(command[0])}\n'
             f'args = [{", ".join(literal(a) for a in command[1:])}]\n')
    path.write_text(existing.rstrip('\n') + ('\n' if existing else '') + block, encoding='utf-8')
    return 'connected'


# ----------------------------------------------------------------- checks

def verify_server():
    """Prove the assistants will get a working server: run a real handshake and one tool call."""
    from lectic_mcp import Server
    server = Server(Path.cwd())
    init = server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}})
    call = server.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'lectic_home', 'arguments': {}}})
    ok = 'result' in init and 'result' in call and not call['result']['isError']
    return ok, json.loads(call['result']['content'][0]['text']) if ok else None


def youtube_available():
    if shutil.which('yt-dlp'): return True
    try:
        import importlib.util
        return importlib.util.find_spec('yt_dlp') is not None
    except (ImportError, ValueError):
        return False


def offer_youtube(interactive):
    if youtube_available(): return 'ready'
    if not interactive: return 'not installed (pip install yt-dlp)'
    answer = input('  Add YouTube support so links turn into captions? [Y/n] ').strip().lower()
    if answer and answer != 'y': return 'skipped (pip install yt-dlp any time)'
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', 'yt-dlp'], capture_output=True, text=True)
    return 'ready' if result.returncode == 0 else 'install failed: ' + ' '.join((result.stderr or result.stdout).split())[:200]


# ----------------------------------------------------------------- commands

def setup(argv):
    interactive = sys.stdin.isatty() and '--yes' not in argv
    print('Connecting Lectic to the assistants on this machine.\n')
    ok, home = verify_server()
    if not ok:
        print('  The Lectic server did not start correctly. Run `lectic status` for details.'); return 1
    results = {'Claude Code': connect_claude(), 'Codex': connect_codex()}
    for name, state in results.items():
        print(f'  {name:<12} {state}')
    print(f'  {"YouTube":<12} {offer_youtube(interactive)}')
    print(f'\nKnowledge lives in {home["home"]} and is shared by every project and assistant here.')
    if any(s == 'connected' for s in results.values()):
        print('\nOpen a connected assistant, in any folder, and try one of these:\n')
        for line in ('Save this for later: https://www.youtube.com/watch?v=...',
                     'What could my saved material become?',
                     'Use my Sales Training to review this call transcript.'):
            print('  ' + line)
        print('\nIf the assistant was already open, restart it once so it sees the new connection.')
    else:
        print('\nNo supported assistant was found. Install Claude Code or Codex, then run `lectic setup` again,')
        print('or connect any MCP client with:  ' + ' '.join(server_command()))
    return 0


def status(argv):
    from home import describe
    from collection_store import Library
    info = describe(Path.cwd())
    print(f'Python      {sys.version.split()[0]}  ({sys.executable})')
    print(f'Knowledge   {info["home"]}  [{info["mode"]}]')
    try:
        names = [c['name'] for c in Library(Path.cwd()).index['collections']]
        print(f'Collections {len(names)}' + (': ' + ', '.join(names[:6]) + (' …' if len(names) > 6 else '') if names else ''))
    except Exception as exc:  # a damaged index is reported, never hidden
        print(f'Collections unreadable: {exc}')
    print(f'Claude Code {"connected" if claude_connected() else "not connected"}')
    print(f'Codex       {"connected" if codex_connected() else "not connected"}')
    print(f'YouTube     {"ready" if youtube_available() else "not installed"}')
    ok, _ = verify_server()
    print(f'Server      {"ok" if ok else "FAILED"}')
    if not (claude_connected() or codex_connected()): print('\nRun `lectic setup` to connect an assistant.')
    return 0


def serve(argv):
    from lectic_mcp import serve as run_server
    project = argv[argv.index('--project') + 1] if '--project' in argv else os.getcwd()
    run_server(project); return 0


def ec(argv):
    sys.argv = ['ec.py'] + argv
    import ec as core
    return core.main()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else 'status'
    handlers = {'setup': setup, 'status': status, 'serve': serve, 'ec': ec}
    if command in {'-h', '--help', 'help'} or command not in handlers:
        print(__doc__.strip()); return 0 if command in {'-h', '--help', 'help'} else 2
    return handlers[command](argv[1:])


if __name__ == '__main__':
    sys.exit(main())
