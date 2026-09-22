"""`lectic`: the one command a person needs.

    lectic setup            connect the assistants on this machine, verify the connection, offer YouTube support
    lectic share            give ChatGPT, Claude, Gemini or any hosted assistant one link to your knowledge
    lectic connect URL      point Claude Code and Codex at a Lectic running elsewhere
    lectic pack NAME        one shareable file carrying a collection's knowledge (add --include-sources for your own material)
    lectic install FILE|URL add someone's pack to your knowledge (--inspect to look first)
    lectic backup [--out F] every collection, source and build in one archive file
    lectic push LINK        move this knowledge onto a Lectic running elsewhere
    lectic pull LINK        bring that Lectic's knowledge here
    lectic restore FILE     merge a backup archive into this knowledge
    lectic status           where knowledge lives, what is saved, which assistants are connected
    lectic serve [--http]   run the MCP server (what the assistants launch; you rarely run it yourself)
    lectic ec ...           the deterministic utilities, for contributors

Everything else happens in conversation with the connected assistant.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

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


def connect_claude(runner=None, url=None):
    """Prefer Claude Code's own CLI; fall back to its user config when the CLI is not on PATH.

    With a URL, Claude Code is pointed at a Lectic running elsewhere instead of a local process.
    """
    runner = runner or subprocess.run
    command = server_command()
    claude = shutil.which('claude')
    if claude:
        spec = ['--transport', 'http', SERVER_NAME, url] if url else [SERVER_NAME, '--'] + command
        for attempt in range(2):
            result = runner([claude, 'mcp', 'add', '--scope', 'user'] + spec, capture_output=True, text=True)
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
    servers[SERVER_NAME] = {'type': 'http', 'url': url} if url else {'type': 'stdio', 'command': command[0], 'args': command[1:]}
    path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return 'connected'


def codex_connected():
    path = codex_config_path()
    return path.is_file() and f'[mcp_servers.{SERVER_NAME}]' in path.read_text(encoding='utf-8')


CODEX_BLOCK = re.compile(r'\n?\[mcp_servers\.' + SERVER_NAME + r'\]\n(?:(?!\[).*\n?)*')


def connect_codex(url=None):
    path = codex_config_path()
    if not path.parent.is_dir(): return 'not installed'
    existing = path.read_text(encoding='utf-8') if path.is_file() else ''
    literal = lambda value: "'" + str(value).replace("'", "''") + "'"
    if url:
        block = f'\n[mcp_servers.{SERVER_NAME}]\nurl = {literal(url)}\n'
    else:
        command = server_command()
        block = (f'\n[mcp_servers.{SERVER_NAME}]\ncommand = {literal(command[0])}\n'
                 f'args = [{", ".join(literal(a) for a in command[1:])}]\n')
    if block.strip() in existing: return 'connected'
    existing = CODEX_BLOCK.sub('\n', existing)  # replace an earlier Lectic entry, keep everything else
    path.write_text(existing.rstrip('\n') + ('\n' if existing.strip() else '') + block, encoding='utf-8')
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


def youtube_route():
    """What `lectic status` shows: how this machine reaches YouTube."""
    sys.path.insert(0, str(SCRIPTS))
    from ingestors.youtube import network_options
    try:
        _, using = network_options()
    except Exception as exc:  # a bad cookies path is a status line, not a crash
        return 'misconfigured: ' + str(exc)
    return 'via ' + ' + '.join(using) if using else 'direct (set LECTIC_YTDLP_PROXY or LECTIC_YTDLP_COOKIES if YouTube blocks this network)'


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
        print('\nOne step left: restart the assistant so it picks up the connection.')
        print('Then open it in any folder and just talk:\n')
        for line in ('Save this for later: https://www.youtube.com/watch?v=...',
                     'What could my saved material become?',
                     'Use my Sales Training to review this call transcript.'):
            print('  ' + line)
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
    print(f'YouTube     {"ready, " + youtube_route() if youtube_available() else "not installed"}')
    link = live_link(info['home'])
    print(f'Share link  {link + "  (live)" if link else "not sharing (run: lectic share)"}')
    ok, _ = verify_server()
    print(f'Server      {"ok" if ok else "FAILED"}')
    if not (claude_connected() or codex_connected()): print('\nRun `lectic setup` to connect an assistant.')
    return 0


def option(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def serve(argv):
    from lectic_mcp import serve as run_server, serve_http
    project = option(argv, '--project', os.getcwd())
    if '--http' not in argv:
        run_server(project); return 0
    from lectic_mcp import connect_url
    public = option(argv, '--public', os.environ.get('LECTIC_PUBLIC_URL') or None)
    httpd = serve_http(project, option(argv, '--host', '127.0.0.1'), int(option(argv, '--port', '8787')),
                       option(argv, '--token', os.environ.get('LECTIC_TOKEN') or None), announce=None)
    print('Lectic link: ' + (connect_url(public, httpd.token) if public else connect_url(f'http://127.0.0.1:{httpd.server_address[1]}', httpd.token)), flush=True)
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    return 0


HOSTED_HELP = '''
Paste that link where the assistant lets you add a connector:

  ChatGPT      Settings > Apps & Connectors > Create. Authentication: none. (Developer mode may need enabling.)
  Claude       Settings > Connectors > Add custom connector.
  Gemini CLI   gemini mcp add --transport http lectic <link>
  Claude Code  lectic connect <link>      (also Codex)

Anyone with the link can read and change your knowledge. Keep it private; `lectic share --new-link` makes a new one.
'''


def share(argv):
    """Serve over HTTP and open a tunnel, so hosted assistants reach this machine's knowledge."""
    from home import storage_root
    from lectic_mcp import connect_url, serve_http
    project = os.getcwd()
    if '--new-link' in argv:
        (storage_root(project) / 'server.json').unlink(missing_ok=True)
    port = int(option(argv, '--port', '8787'))
    httpd = serve_http(project, '127.0.0.1', port, announce=None)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    local = f'http://127.0.0.1:{httpd.server_address[1]}'
    public = option(argv, '--public')
    tunnel = None
    if not public:
        cloudflared = shutil.which('cloudflared')
        if not cloudflared:
            print('Lectic is serving on ' + connect_url(local, httpd.token))
            print('\nTo reach it from ChatGPT, Claude or Gemini you need a public address. Install Cloudflare Tunnel once:')
            print('  Windows: winget install Cloudflare.cloudflared      macOS: brew install cloudflared')
            print('then run `lectic share` again. Already have a public address for this machine? `lectic share --public https://...`')
            httpd.shutdown(); httpd.server_close(); return 1
        name = option(argv, '--tunnel')
        args = [cloudflared, '--no-autoupdate', 'tunnel'] + (['run', '--url', local, name] if name else ['--url', local])
        tunnel = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        print('Opening a secure tunnel' + (' ' + name if name else '') + '...', flush=True)
        if name:
            public = option(argv, '--hostname') or None
            if not public:
                print('A named tunnel needs its hostname: lectic share --tunnel NAME --hostname https://lectic.example.com'); tunnel.terminate(); tunnel.stdout.close(); httpd.shutdown(); httpd.server_close(); return 1
        else:
            deadline = time.time() + 45
            for line in tunnel.stdout:
                found = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line)
                if found: public = found.group(0); break
                if time.time() > deadline: break
            if not public:
                print('The tunnel did not come up. Check your connection and try again.'); tunnel.terminate(); tunnel.stdout.close(); httpd.shutdown(); httpd.server_close(); return 1
    link = connect_url(public, httpd.token)
    # Publish it where `lectic status` and any assistant can find it, rather than only on this screen.
    record = storage_root(project) / 'share-link.json'
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({'link': link, 'local': local, 'started_at': time.strftime('%Y-%m-%dT%H:%M:%S')}), encoding='utf-8')
    print('\nYour Lectic link:\n\n  ' + link + '\n' + HOSTED_HELP)
    if tunnel and not option(argv, '--tunnel'):
        print('This link lasts while `lectic share` is running; a quick tunnel gets a new address each time. For a permanent one see docs/CLOUD.md.')
    print('\nSharing. Press Ctrl+C to stop.', flush=True)
    try:
        while True:
            time.sleep(1)
            if tunnel and tunnel.poll() is not None:
                print('The tunnel closed.'); break
    except KeyboardInterrupt:
        pass
    finally:
        record.unlink(missing_ok=True)
        if tunnel:
            if tunnel.poll() is None: tunnel.terminate()
            tunnel.stdout.close()
        httpd.shutdown(); httpd.server_close()
    return 0


def connect(argv):
    """Point the assistants on this machine at a Lectic that runs somewhere else."""
    url = next((a for a in argv if a.startswith('http')), None)
    if not url:
        print('Usage: lectic connect https://host/t/TOKEN/mcp   (the link `lectic share` or your server printed)'); return 2
    results = {'Claude Code': connect_claude(url=url), 'Codex': connect_codex(url=url)}
    for name, state in results.items(): print(f'  {name:<12} {state}')
    if any(v == 'connected' for v in results.values()):
        print('\nConnected. Restart the assistant once if it was already open. `lectic setup` switches back to this machine\'s own knowledge.')
    return 0


def live_link(home):
    """The link a running `lectic share` is serving, or None. Checked, never just believed."""
    import json as _json, urllib.error, urllib.request
    path = Path(home) / 'share-link.json'
    if not path.is_file(): return None
    try:
        record = _json.loads(path.read_text(encoding='utf-8'))
        with urllib.request.urlopen(record['local'] + '/health', timeout=2) as response:
            if response.status != 200: return None
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return None
    return record['link']


def pack(argv):
    from packs import build_pack
    name = next((a for a in argv if not a.startswith('--') and a != option(argv, '--out')), None)
    if not name: print('Usage: lectic pack "Collection Name" [--out FILE] [--include-sources]'); return 2
    result = build_pack(os.getcwd(), name, option(argv, '--out'), '--include-sources' in argv)
    print(f"Packed {result['name']}: {result['units']} knowledge units, {result['sources']} sources, {result['methods']} methods -> {result['pack']} ({result['bytes'] // 1024} KB)")
    print(result['share_note'])
    print('\nShare the file or a link to it. Anyone with Lectic installs it with:  lectic install <file or link>')
    return 0


def install(argv):
    from packs import inspect_pack, install_pack
    location = next((a for a in argv if not a.startswith('--') and a != option(argv, '--name')), None)
    if not location: print('Usage: lectic install FILE|URL [--name NAME] [--inspect]'); return 2
    if '--inspect' in argv:
        print(inspect_pack(location)['readme']); return 0
    report = install_pack(os.getcwd(), location, option(argv, '--name'))
    state = 'verified' if report['verification'] == 'verified' else f"partial: {report['sources_verified']} of {report['sources_total']} sources, {report['units_installed']} of {report['units_in_pack']} units"
    print(f"Installed {report['collection']} ({state}).")
    for item in report['sources_unavailable']: print(f"  could not verify {item['source']}: {item['reason']}")
    if report['methods']: print('Ready methods: ' + ', '.join(m['title'] for m in report['methods']))
    print(f"\nOpen any connected assistant and say: Use my {report['collection']} to ...")
    return 0


def describe_merge(report):
    if report.get('collections_added'): print('  added      ' + ', '.join(report['collections_added']))
    if report.get('collections_present'): print('  already there  ' + ', '.join(report['collections_present']))
    for name in report.get('collections_diverged', []):
        print(f'  kept apart {name}: it exists on both sides and differs, so neither copy was changed')
    counts = f"  {report.get('blobs_added', 0)} sources, {report.get('captures_added', 0)} captures, {report.get('other_files_added', 0)} other records added"
    print(counts)
    for issue in report.get('issues', []): print('  needs attention: ' + issue)


def backup(argv):
    from home_archive import backup as run
    result = run(os.getcwd(), option(argv, '--out'))
    names = ', '.join(result['collections']) or 'no named collections yet'
    print(f"Backed up {names} ({result['blobs']} sources) -> {result['file']} ({result['bytes'] // 1024} KB)")
    print('Restore it anywhere with:  lectic restore ' + Path(result['file']).name)
    return 0


def push(argv):
    from home_archive import push as run
    link = next((a for a in argv if a.startswith('http')), None)
    if not link: print('Usage: lectic push https://host/t/SECRET/mcp   (the link that Lectic printed)'); return 2
    report = run(os.getcwd(), link)
    print(f"Sent {report['sent_bytes'] // 1024} KB to {report['destination']}")
    describe_merge(report)
    print('\nThat Lectic now holds this knowledge. Point this machine at it with:  lectic connect ' + link)
    return 0


def pull(argv):
    from home_archive import pull as run
    link = next((a for a in argv if a.startswith('http')), None)
    if not link: print('Usage: lectic pull https://host/t/SECRET/mcp'); return 2
    report = run(os.getcwd(), link)
    print(f"Received {report['received_bytes'] // 1024} KB from {report['source']}")
    describe_merge(report)
    return 0


def restore(argv):
    from home_archive import restore as run
    location = next((a for a in argv if not a.startswith('--')), None)
    if not location: print('Usage: lectic restore FILE   (an archive from `lectic backup`)'); return 2
    report = run(os.getcwd(), location)
    print('Restored into ' + str(Path(os.getcwd())) + "'s knowledge home.")
    describe_merge(report)
    return 0


def ec(argv):
    sys.argv = ['ec.py'] + argv
    import ec as core
    return core.main()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else 'status'
    handlers = {'setup': setup, 'share': share, 'connect': connect, 'pack': pack, 'install': install,
                'backup': backup, 'push': push, 'pull': pull, 'restore': restore,
                'status': status, 'serve': serve, 'ec': ec}
    if command in {'-h', '--help', 'help'} or command not in handlers:
        print(__doc__.strip()); return 0 if command in {'-h', '--help', 'help'} else 2
    return handlers[command](argv[1:])


if __name__ == '__main__':
    sys.exit(main())
