"""`lectic`: the one command a person needs.

    lectic setup            connect the assistants on this machine, verify the connection, offer YouTube support
    lectic identity         set or show the identity that signs your packs (lectic identity set "Name" --contact x)
    lectic share            give ChatGPT, Claude, Gemini or any hosted assistant one link to your knowledge
    lectic connect URL      point Claude Code and Codex at a Lectic running elsewhere
    lectic pack NAME        one shareable file carrying a collection's knowledge (--team, --version, --include-sources)
    lectic install FILE|URL add someone's pack to your knowledge (--as NAME, --pin, --inspect)
    lectic update NAME      check pack origin for newer version and update
    lectic publish NAME     upload pack to team host (--to URL, --webhook URL)
    lectic verify [NAME]    check that a collection's evidence is fully anchored (exit 0 = verified, 1 = issues)
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


def git_config_value(key):
    try:
        res = subprocess.run(['git', 'config', key], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return ''


def offer_identity(interactive):
    sys.path.insert(0, str(SCRIPTS))
    from identity import load_identity, save_identity
    existing = load_identity('.')
    if existing:
        return f"{existing['name']} <{existing['contact']}> (key: {existing['key_id']})"
    default_name = git_config_value('user.name') or os.environ.get('USERNAME') or os.environ.get('USER') or ''
    default_email = git_config_value('user.email') or ''
    if not interactive:
        if default_name:
            rec = save_identity('.', default_name, default_email)
            return f"{default_name} <{default_email}> (auto-configured, key: {rec['key_id']})"
        return 'not set (run: lectic identity set "Name" --contact email)'
    prompt = f'  Name for signing your packs [{default_name}]: ' if default_name else '  Name for signing your packs (or Enter to skip): '
    name = input(prompt).strip() or default_name
    if not name:
        return 'skipped (run: lectic identity set any time)'
    email_prompt = f'  Contact / email? [{default_email}]: ' if default_email else '  Contact / email (optional): '
    email = input(email_prompt).strip() or default_email
    record = save_identity('.', name, email)
    return f"{record['name']} <{record['contact']}> (key: {record['key_id']})"


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
    print(f'  {"Identity":<12} {offer_identity(interactive)}')
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
        library = Library(Path.cwd())
        names = [c['name'] for c in library.index['collections']]
        print(f'Collections {len(names)}' + (': ' + ', '.join(names[:6]) + (' …' if len(names) > 6 else '') if names else ''))
        # Installed packs: version and pinned status
        if names:
            for entry in library.index['collections']:
                resolved = library.resolve(entry['collection_id'])
                if resolved:
                    origin_file = resolved[0] / 'pack-origin.json'
                    if origin_file.is_file():
                        try:
                            ometa = json.loads(origin_file.read_text(encoding='utf-8'))
                            v = ometa.get('version') or ometa.get('pinned_version') or 'unversioned'
                            pinned = ometa.get('pinned', False)
                            p_str = 'pinned' if pinned else 'unpinned'
                            print(f"  {entry['name']}  v{v} [{p_str}]")
                        except Exception:
                            pass
        # Evidence health summary for compiled collections
        if names and '--evidence' in argv:
            from verify import verify_collection
            print()
            for entry in library.index['collections']:
                try:
                    report = verify_collection(Path.cwd(), entry['collection_id'])
                    u = report['units']
                    symbol = {'verified': 'OK', 'partial': '~', 'issues_found': '!'}.get(report['overall'], '?')
                    print(f'  [{symbol}] {entry["name"]}: {u["verified"]}/{u["total"]} units evidence-backed  [{report["overall"]}]')
                except Exception:
                    pass  # collection may not be compiled yet
    except Exception as exc:  # a damaged index is reported, never hidden
        print(f'Collections unreadable: {exc}')
    # Identity
    try:
        from identity import load_identity
        ident = load_identity(Path.cwd())
        if ident:
            print(f'Identity    {ident["name"]} <{ident["contact"]}>  key: {ident["key_id"]}')
        else:
            print(f'Identity    not set (run: lectic identity set "Name" --contact email)')
    except Exception:
        pass
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


def identity(argv):
    """Manage the local signing identity used when building packs."""
    from identity import save_identity, show_identity
    sub = argv[0] if argv else 'show'
    if sub in ('show', ) or not argv:
        print(show_identity(os.getcwd()))
        return 0
    if sub == 'set':
        rest = argv[1:]
        name = next((a for a in rest if not a.startswith('--') and a != option(rest, '--contact')), None)
        contact = option(rest, '--contact')
        if not name or not contact:
            print('Usage: lectic identity set "Your Name" --contact your@email.com')
            return 2
        record = save_identity(os.getcwd(), name, contact)
        print('Identity saved.')
        print(f'  Name:    {record["name"]}')
        print(f'  Contact: {record["contact"]}')
        print(f'  Key ID:  {record["key_id"]}')
        print('\nYour packs will be signed with this identity. The signing key stays on your machine.')
        return 0
    print('Usage: lectic identity [show | set "Name" --contact email]')
    return 2


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
    flags_with_val = {'--out', '--version'}
    def is_flag_val(a):
        return any(option(argv, f) == a for f in flags_with_val)
    name = next((a for a in argv if not a.startswith('--') and not is_flag_val(a)), None)
    if not name:
        print('Usage: lectic pack "Collection Name" [--out FILE] [--include-sources] [--team] [--version VER]')
        return 2
    out = option(argv, '--out')
    version = option(argv, '--version')
    team = '--team' in argv
    inc_sources = '--include-sources' in argv or team
    result = build_pack(os.getcwd(), name, out, include_sources=inc_sources, team=team, version=version)
    team_note = " (team pack)" if team else ""
    ver_note = f" v{result['version']}" if result.get('version') else ""
    print(f"Packed {result['name']}{ver_note}{team_note}: {result['units']} knowledge units, {result['sources']} sources, {result['methods']} methods -> {result['pack']} ({result['bytes'] // 1024} KB)")
    if result.get('publisher'):
        print(f"  {result['publisher']}")
    else:
        print('  Unsigned — run `lectic identity set "Name" --contact email` to sign packs')
    print(result['share_note'])
    if team:
        dist = result.get('distribution', {})
        install_as = dist.get('install_name', 'standards')
        print(f"\nTeam pack ready. Recipients install with:\n  lectic install <file or link> --as {install_as} --pin")
    else:
        print('\nShare the file or a link to it. Anyone with Lectic installs it with:  lectic install <file or link>')
    return 0


def install(argv):
    from packs import inspect_pack, install_pack
    flags_with_val = {'--name', '--as'}
    def is_flag_val(a):
        return any(option(argv, f) == a for f in flags_with_val)
    location = next((a for a in argv if not a.startswith('--') and not is_flag_val(a)), None)
    if not location:
        print('Usage: lectic install FILE|URL [--as NAME | --name NAME] [--pin] [--inspect]')
        return 2
    if '--inspect' in argv:
        info = inspect_pack(location)
        print(info['readme'])
        if info.get('install_md'):
            print("\n---\n" + info['install_md'])
        print(f"\n{info['publisher_info']}")
        return 0
    as_name = option(argv, '--as') or option(argv, '--name')
    pin = '--pin' in argv
    report = install_pack(os.getcwd(), location, name=as_name, pin=pin)
    state = 'verified' if report['verification'] == 'verified' else f"partial: {report['sources_verified']} of {report['sources_total']} sources, {report['units_installed']} of {report['units_in_pack']} units"
    pin_note = f" [pinned: v{report['pinned_version']}]" if report.get('pinned') else ""
    print(f"Installed {report['collection']}{pin_note} ({state}).")
    print(f"  {report['publisher_info']}")
    for item in report['sources_unavailable']: print(f"  could not verify {item['source']}: {item['reason']}")
    if report['methods']: print('Ready methods: ' + ', '.join(m['title'] for m in report['methods']))
    print(f"\nOpen any connected assistant and say: Use my {report['collection']} to ...")
    return 0


def update(argv):
    """Check a collection's pack origin for a newer version and update."""
    from packs import update_pack
    name = next((a for a in argv if not a.startswith('--')), None)
    if not name:
        print('Usage: lectic update <collection-name> [--force]')
        return 2
    try:
        report = update_pack(os.getcwd(), name, force='--force' in argv)
    except Exception as exc:
        print(f'Update failed: {exc}')
        return 1
    if report.get('phase') == 'up_to_date':
        print(report['message'])
        return 0
    print(report['summary_message'])
    return 0


def publish(argv):
    """Publish a compiled pack to a team host (GitHub Releases, S3/R2 presigned PUT, HTTP PUT)."""
    from publish import publish_pack
    flags_with_val = {'--to', '--token', '--webhook'}
    def is_flag_val(a):
        return any(option(argv, f) == a for f in flags_with_val)
    name = next((a for a in argv if not a.startswith('--') and not is_flag_val(a)), None)
    to_url = option(argv, '--to')
    if not name or not to_url:
        print('Usage: lectic publish <collection-or-file> --to <URL> [--token <TOKEN>] [--webhook <URL>]')
        return 2
    token = option(argv, '--token')
    webhook = option(argv, '--webhook')
    try:
        res = publish_pack(os.getcwd(), name, to_url, token=token, webhook_url=webhook)
    except Exception as exc:
        print(f'Publish failed: {exc}')
        return 1
    print(res['message'])
    if res.get('webhook_sent'):
        print(f"  Notified webhook: {webhook}")
    elif res.get('webhook_error'):
        print(f"  Webhook notification error: {res['webhook_error']}")
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


def verify(argv):
    """Check that a collection's evidence is fully anchored in its sources.

    Exit 0 if all units are verified; exit 1 if any have broken or missing evidence.
    Use --json for machine-readable output (CI-friendly).
    """
    from verify import verify_collection, format_report
    name = next((a for a in argv if not a.startswith('--')), None)
    as_json = '--json' in argv
    try:
        report = verify_collection(os.getcwd(), name)
    except Exception as exc:
        if as_json:
            print(json.dumps({'error': str(exc)}))
        else:
            print(f'Error: {exc}')
        return 1
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))
    return 0 if report['overall'] == 'verified' else 1


def ec(argv):
    sys.argv = ['ec.py'] + argv
    import ec as core
    return core.main()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else 'status'
    handlers = {'setup': setup, 'identity': identity, 'share': share, 'connect': connect,
                'pack': pack, 'install': install, 'update': update, 'publish': publish, 'verify': verify,
                'backup': backup, 'push': push, 'pull': pull, 'restore': restore,
                'status': status, 'serve': serve, 'ec': ec}
    if command in {'-h', '--help', 'help'} or command not in handlers:
        print(__doc__.strip()); return 0 if command in {'-h', '--help', 'help'} else 2
    return handlers[command](argv[1:])


if __name__ == '__main__':
    sys.exit(main())
