"""`waykit` (formerly `lectic`): turn what you learn into permanent AI expertise.

Daily Use & First Run:
    waykit start [SOURCE]   save trusted material (files, folder, or link) and start
    waykit prepare [NAME]   compile and verify knowledge from saved sources directly
    waykit setup            connect your AI assistants in seconds (Claude Code, Codex, ChatGPT)
    waykit try              try a sample playbook offline to see your AI in action
    waykit status           see your saved playbooks, drop folder, and connected AIs

Sharing & Maintenance:
    waykit share [NAME]     write a self-contained HTML page, or open a live tunnel (--tunnel)
    waykit share-artifact NAME  write one self-contained HTML page about a collection
    waykit refresh NAME --from PATH  save a fresh version of a collection's material
    waykit diff NAME        see what changed between two saved versions of a collection

Portability & Teams:
    waykit pack NAME        export a collection into one shareable playbook file (.waykit / .lectic)
    waykit install TARGET   add a playbook to your AI (from a link, file, or name)
    waykit verify [NAME]    check that every rule in a collection links to exact source quotes
    waykit inbox [--process] view or sort dropped links and files from your drop folder
    waykit backup [--out F] back up all your playbooks and sources in one file
    waykit restore FILE     restore your playbooks from a backup file
    waykit push LINK        sync your playbooks to another computer
    waykit pull LINK        bring your playbooks from another computer here
    waykit connect URL      connect your AI to a remote WayKit library
    waykit identity         set your author name for playbooks you share
    waykit search [QUERY]   find ready-to-use playbooks from creators and teams
    waykit inspect [TARGET] show your knowledge and its useful connections, or preview a pack
    waykit explain NAME     explain what a knowledge area knows and where it came from
    waykit context "TASK"   show the focused knowledge WayKit would use for a task
    waykit update NAME      get the latest updates for an installed playbook
    waykit publish NAME     share your playbook with your team or community
    waykit serve [--http]   start the AI connector (launched automatically by your AI)
    waykit cloud ...        hosted multi-tenant service, accounts, and server management
    waykit ec ...           internal developer utilities

Legacy `lectic` commands remain fully supported aliases.
Everything else happens naturally in conversation with your AI.
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

SERVER_NAME = 'waykit'
LEGACY_SERVER_NAME = 'lectic'


def server_command():
    """How an assistant launches the server: this interpreter, this package, no PATH assumptions."""
    try:
        import waykit  # noqa: F401  (installed package)
        return [sys.executable, '-m', 'waykit.cli', 'serve']
    except ImportError:
        try:
            import lectic  # noqa: F401
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
    return SERVER_NAME in servers or LEGACY_SERVER_NAME in servers


def connect_claude(runner=None, url=None):
    """Prefer Claude Code's own CLI; fall back to its user config when the CLI is not on PATH.

    With a URL, Claude Code is pointed at a WayKit running elsewhere instead of a local process.
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
    entry = {'type': 'http', 'url': url} if url else {'type': 'stdio', 'command': command[0], 'args': command[1:]}
    servers[SERVER_NAME] = entry
    servers[LEGACY_SERVER_NAME] = entry
    path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    return 'connected'


def codex_connected():
    path = codex_config_path()
    if not path.is_file(): return False
    text = path.read_text(encoding='utf-8')
    return f'[mcp_servers.{SERVER_NAME}]' in text or f'[mcp_servers.{LEGACY_SERVER_NAME}]' in text


def configured_spec(client):
    try:
        if client == 'Claude Code':
            data = json.loads(claude_config_path().read_text(encoding='utf-8'))
            servers = data.get('mcpServers', {})
            return servers.get(SERVER_NAME) or servers.get(LEGACY_SERVER_NAME)
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        data = tomllib.loads(codex_config_path().read_text(encoding='utf-8'))
        servers = data.get('mcp_servers', {})
        return servers.get(SERVER_NAME) or servers.get(LEGACY_SERVER_NAME)
    except (OSError, ValueError, AttributeError):
        return None


def spec_reach(spec):
    """Whether a configured assistant talks to a WayKit on this computer or to one over a link."""
    return 'remote link' if spec.get('url') or spec.get('type') == 'http' else 'local, this computer'


def checked_clients():
    from client_check import check_connection
    states = {}
    for client in ('Claude Code', 'Codex'):
        spec = configured_spec(client)
        states[client] = ((f'connected ({spec_reach(spec)}; restart required after setup)' if check_connection(spec)[0]
                          else f'configured ({spec_reach(spec)}), server UNREACHABLE') if spec else 'not connected')
    return states


CODEX_BLOCK = re.compile(r'\n?\[mcp_servers\.(?:' + SERVER_NAME + r'|' + LEGACY_SERVER_NAME + r')\]\n(?:(?!\[).*\n?)*')


def connect_codex(url=None):
    path = codex_config_path()
    if not path.parent.is_dir(): return 'not installed'
    existing = path.read_text(encoding='utf-8') if path.is_file() else ''
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    try:
        tomllib.loads(existing)
    except ValueError:
        return 'failed: Codex config is not valid TOML; it was left unchanged'
    literal = lambda value: json.dumps(str(value), ensure_ascii=False)
    if url:
        block = (f'\n[mcp_servers.{SERVER_NAME}]\nurl = {literal(url)}\n\n'
                 f'[mcp_servers.{LEGACY_SERVER_NAME}]\nurl = {literal(url)}\n')
    else:
        command = server_command()
        block = (f'\n[mcp_servers.{SERVER_NAME}]\ncommand = {literal(command[0])}\n'
                 f'args = [{", ".join(literal(a) for a in command[1:])}]\n\n'
                 f'[mcp_servers.{LEGACY_SERVER_NAME}]\ncommand = {literal(command[0])}\n'
                 f'args = [{", ".join(literal(a) for a in command[1:])}]\n')
    if f'[mcp_servers.{SERVER_NAME}]' in existing and f'[mcp_servers.{LEGACY_SERVER_NAME}]' in existing and block.strip() in existing:
        return 'connected'
    kept, skip = [], False
    for line in existing.splitlines(keepends=True):
        if re.match(r'^\s*\[', line):
            skip = bool(re.match(r'^\s*\[mcp_servers\.(?:waykit|"waykit"|\'waykit\'|lectic|"lectic"|\'lectic\')(?:\.|\])', line))
        if not skip: kept.append(line)
    updated = ''.join(kept).rstrip('\n') + block
    tomllib.loads(updated)
    path.write_text(updated, encoding='utf-8')
    return 'connected'


# ----------------------------------------------------------------- checks

def verify_server():
    """Prove the assistants will get a working server: run a real handshake and one tool call."""
    from client_check import check_connection
    command = server_command()
    return check_connection({'command': command[0], 'args': command[1:]}, cwd=Path.cwd())


def youtube_route():
    """What `lectic status` shows: how this machine reaches YouTube."""
    sys.path.insert(0, str(SCRIPTS))
    from ingestors.youtube import network_options
    try:
        _, using = network_options()
    except Exception as exc:  # a bad cookies path is a status line, not a crash
        return 'misconfigured: ' + str(exc)
    return 'via ' + ' + '.join(using) if using else 'direct (set WAYKIT_YTDLP_PROXY or WAYKIT_YTDLP_COOKIES if YouTube blocks this network)'


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
        return 'not set (run: waykit identity set "Name" --contact email)'
    prompt = f'  Author name for playbooks you share [{default_name}]: ' if default_name else '  Author name for playbooks you share (or Enter to skip): '
    name = input(prompt).strip() or default_name
    if not name:
        return 'skipped (run: waykit identity set any time)'
    email_prompt = f'  Contact / email? [{default_email}]: ' if default_email else '  Contact / email (optional): '
    email = input(email_prompt).strip() or default_email
    record = save_identity('.', name, email)
    return f"{record['name']} <{record['contact']}> (key: {record['key_id']})"


# ----------------------------------------------------------------- commands

def setup(argv):
    interactive = sys.stdin.isatty() and '--yes' not in argv
    print('Connecting WayKit to the AI assistants on your computer.\n')
    ok, home = verify_server()
    if not ok:
        print('  The WayKit service did not start correctly. Run `waykit status` for details.'); return 1
    results = {'Claude Code': connect_claude(), 'Codex': connect_codex()}
    checks = checked_clients()
    results = {name: checks[name] if state == 'connected' else state for name, state in results.items()}
    for name, state in results.items():
        print(f'  {name:<12} {state}')
    print(f'  {"Author":<12} {offer_identity(interactive)}')
    print(f'  {"YouTube":<12} {offer_youtube(interactive)}')
    from inbox import ensure_inbox_folder
    inbox_dir = ensure_inbox_folder(Path.cwd())
    print(f'  {"Drop Folder":<12} {inbox_dir}')
    print(f'  {"Hosted chat":<12} {hosted_reach(home["home"])}')
    print(f'\nKnowledge lives in {home["home"]} and is shared by every project and assistant here.')
    if any(s.startswith('connected') for s in results.values()):
        print('\nOne step left: restart your AI assistant so it picks up the connection.')
        print('Then open it in any folder and just talk:\n')
        for line in ('Save this for later: https://www.youtube.com/watch?v=...',
                     'Drop any video, note, or link into your WayKit folder',
                     'Use my Sales Training to review this call transcript.'):
            print('  ' + line)
    else:
        print('\nNo supported assistant was found. Install Claude Code or Codex, then run `waykit setup` again,')
        print('or connect any MCP client with:  ' + ' '.join(server_command()))
    return 0 if any(state.startswith('connected') for state in results.values()) and not any(
        state.startswith('failed') or 'UNREACHABLE' in state for state in results.values()) else 1


def status(argv):
    from home import describe
    from collection_store import Library
    info = describe(Path.cwd())
    print(f'Python      {sys.version.split()[0]}  ({sys.executable})')
    print(f'Knowledge   {info["home"]}  [{info["mode"]}]')
    try:
        from inbox import ensure_inbox_folder, scan_inbox
        inbox_info = scan_inbox(Path.cwd())
        count_str = f"{inbox_info['count']} item{'s' if inbox_info['count'] != 1 else ''} waiting" if inbox_info['count'] else "empty"
        print(f'Drop Inbox  {inbox_info["inbox_folder"]} ({count_str})')
    except Exception:
        pass
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
            print(f'Identity    not set (run: waykit identity set "Name" --contact email)')
    except Exception:
        pass
    connections = checked_clients()
    for name, state in connections.items(): print(f'{name:<12}{state}')
    print(f'YouTube     {"ready, " + youtube_route() if youtube_available() else "not installed"}')
    link = live_link(info['home'])
    print(f'Share link  {link + "  (live)" if link else "not sharing (run: waykit share)"}')
    print(f'Hosted chat {hosted_reach(info["home"])}')
    ok, _ = verify_server()
    print(f'Server      {"ok" if ok else "FAILED"}')
    if not (claude_connected() or codex_connected()): print('\nRun `waykit setup` to connect an assistant.')
    return 0 if ok and not any('UNREACHABLE' in state for state in connections.values()) else 1


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
            print('Usage: waykit identity set "Your Name" --contact your@email.com')
            return 2
        record = save_identity(os.getcwd(), name, contact)
        print('Identity saved.')
        print(f'  Name:    {record["name"]}')
        print(f'  Contact: {record["contact"]}')
        print(f'  Key ID:  {record["key_id"]}')
        print('\nYour packs will be signed with this identity. The signing key stays on your machine.')
        return 0
    print('Usage: waykit identity [show | set "Name" --contact email]')
    return 2


def serve(argv):
    from lectic_mcp import serve as run_server, serve_http
    project = option(argv, '--project', os.getcwd())
    if '--http' not in argv:
        run_server(project); return 0
    from lectic_mcp import connect_url
    public = option(argv, '--public', os.environ.get('WAYKIT_PUBLIC_URL') or os.environ.get('LECTIC_PUBLIC_URL') or None)
    httpd = serve_http(project, option(argv, '--host', '127.0.0.1'), int(option(argv, '--port', '8787')),
                       option(argv, '--token', os.environ.get('WAYKIT_TOKEN') or os.environ.get('LECTIC_TOKEN') or None), announce=None)
    print('WayKit link: ' + (connect_url(public, httpd.token) if public else connect_url(f'http://127.0.0.1:{httpd.server_address[1]}', httpd.token)), flush=True)
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    return 0


HOSTED_HELP = '''
Paste that link where the assistant lets you add a connector:

  ChatGPT      Settings > Apps & Connectors > Create. Authentication: none. (Developer mode may need enabling.)
  Claude       Settings > Connectors > Add custom connector.
  Gemini CLI   gemini mcp add --transport http waykit <link>
  Claude Code  waykit connect <link>      (also Codex)

Anyone with the link can read and change your knowledge. Keep it private; `waykit share --new-link` makes a new one.
'''


def share(argv):
    """Write one portable HTML page about a collection, or open a live tunnel if no collection is named."""
    tunnel_flags = {'--tunnel', '--live', '--server', '--mcp', '--new-link', '--public', '--hostname'}
    has_tunnel_flag = any(f in argv for f in tunnel_flags)
    names = positional(argv, {'--port', '--public', '--tunnel', '--hostname', '--out', '--build'})
    if names and not has_tunnel_flag:
        return share_artifact(argv)
    return share_tunnel(argv)


def share_tunnel(argv):
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
            print('WayKit is serving on ' + connect_url(local, httpd.token))
            print('\nTo reach it from ChatGPT, Claude or Gemini you need a public address. Install Cloudflare Tunnel once:')
            print('  Windows: winget install Cloudflare.cloudflared      macOS: brew install cloudflared')
            print('then run `waykit share` again. Already have a public address for this machine? `waykit share --public https://...`')
            httpd.shutdown(); httpd.server_close(); return 1
        name = option(argv, '--tunnel')
        args = [cloudflared, '--no-autoupdate', 'tunnel'] + (['run', '--url', local, name] if name else ['--url', local])
        tunnel = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        print('Opening a secure tunnel' + (' ' + name if name else '') + '...', flush=True)
        if name:
            public = option(argv, '--hostname') or None
            if not public:
                print('A named tunnel needs its hostname: waykit share --tunnel NAME --hostname https://waykit.example.com'); tunnel.terminate(); tunnel.stdout.close(); httpd.shutdown(); httpd.server_close(); return 1
        else:
            deadline = time.time() + 45
            for line in tunnel.stdout:
                found = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line)
                if found: public = found.group(0); break
                if time.time() > deadline: break
            if not public:
                print('The tunnel did not come up. Check your connection and try again.'); tunnel.terminate(); tunnel.stdout.close(); httpd.shutdown(); httpd.server_close(); return 1
    link = connect_url(public, httpd.token)
    # Publish it where `waykit status` and any assistant can find it, rather than only on this screen.
    record = storage_root(project) / 'share-link.json'
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({'link': link, 'local': local, 'started_at': time.strftime('%Y-%m-%dT%H:%M:%S')}), encoding='utf-8')
    print('\nYour WayKit link:\n\n  ' + link + '\n' + HOSTED_HELP)
    if tunnel and not option(argv, '--tunnel'):
        print('This link lasts while `waykit share` is running; a quick tunnel gets a new address each time. For a permanent one see docs/CLOUD.md.')
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
    from client_check import check_connection
    if not check_connection({'url': url})[0]:
        print('The remote Lectic server did not complete a connection check. Existing assistant settings were left unchanged.')
        return 1
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


def hosted_reach(home):
    """ChatGPT, Gemini and Claude on the web run on someone else's computer.

    They can only reach this home through a link, never through a local process.
    """
    if live_link(home):
        return 'reachable: paste the share link above into ChatGPT, Claude on the web or Gemini'
    return 'NOT reachable: ChatGPT, Gemini and other hosted chats cannot see a local server (run: waykit share)'


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
    if '--include-sources' in argv and '--exclude-sources' in argv:
        print('Choose either --include-sources or --exclude-sources.'); return 2
    inc_sources = False if '--exclude-sources' in argv else '--include-sources' in argv or team
    result = build_pack(os.getcwd(), name, out, include_sources=inc_sources, team=team, version=version)
    team_note = " (team pack)" if team else ""
    ver_note = f" v{result['version']}" if result.get('version') else ""
    print(f"Packed {result['name']}{ver_note}{team_note}: {result['units']} knowledge units, {result['sources']} sources, {result['methods']} methods -> {result['pack']} ({result['bytes'] // 1024} KB)")
    if result.get('publisher'):
        print(f"  {result['publisher']}")
    else:
        print('  Unsigned — run `lectic identity set "Name" --contact email` to sign packs')
    print(result['share_note'])
    for warning in result.get('warnings', []): print('  ' + warning)
    if team:
        dist = result.get('distribution', {})
        install_as = dist.get('install_name', 'standards')
        print(f"\nTeam pack ready. Recipients install with:\n  lectic install <file or link> --as {install_as} --pin")
    else:
        print('\nShare the file or a link to it. Anyone with Lectic installs it with:  lectic install <file or link>')
    return 0


def search(argv):
    """Search the Lectic Expertise Marketplace registry."""
    from registry import search_registry, format_search_results
    flags_with_val = {'--tag'}
    def is_flag_val(a):
        return any(option(argv, f) == a for f in flags_with_val)
    tag = option(argv, '--tag')
    query = next((a for a in argv if not a.startswith('--') and not is_flag_val(a)), None)
    as_json = '--json' in argv
    try:
        results = search_registry(query=query, project=os.getcwd(), tag=tag)
    except Exception as exc:
        if as_json:
            print(json.dumps({'error': str(exc)}))
        else:
            print(f"Registry search failed: {exc}")
        return 1
    if as_json:
        print(json.dumps(results, indent=2))
    else:
        print(format_search_results(results, query=query))
    return 0


def inspect_cmd(argv):
    """Inspect local knowledge, or a pack from the registry, local file, or URL."""
    from packs import inspect_pack
    from registry import inspect_registry_pack, format_inspect_report
    location = next((a for a in argv if not a.startswith('--')), None)
    if not location:
        from intelligence import knowledge_graph
        info = knowledge_graph(os.getcwd())
        if '--json' in argv:
            print(json.dumps(info, indent=2)); return 0
        print('Your Lectic knowledge')
        if not info['collections']:
            print('  Nothing has been saved yet.'); return 0
        for item in info['collections']:
            kind = 'personal preferences' if item['layer'] == 'personal' else 'reusable knowledge'
            print(f"  {item['name']} — {item['knowledge_units']} useful idea(s), {kind}")
        if info['relationships']:
            names = {x['collection_id']:x['name'] for x in info['collections']}
            print('\nUseful connections')
            for rel in info['relationships']:
                print(f"  {names[rel['from']]} → {names[rel['to']]}: {rel['reason']}")
        return 0
    try:
        if location.startswith('registry:'):
            info = inspect_registry_pack(location, project=os.getcwd())
            print(format_inspect_report(info))
        else:
            info = inspect_pack(location)
            print(info['readme'])
            if info.get('install_md'):
                print('\n---\n' + info['install_md'])
            print(f"\n{info['publisher_info']}")
    except Exception as exc:
        print(f"Inspect failed: {exc}")
        return 1
    return 0


def explain_cmd(argv):
    from intelligence import explain_collection
    names = [a for a in argv if not a.startswith('--')]
    if not names:
        print('Usage: lectic explain "Knowledge name"'); return 2
    try: info = explain_collection(os.getcwd(), ' '.join(names))
    except Exception as exc:
        print('Explain failed: ' + str(exc)); return 1
    if '--json' in argv:
        print(json.dumps(info, indent=2)); return 0
    print(info['summary'])
    if info['knows']:
        print('\nWhat it knows')
        for title in info['knows']: print('  ' + title)
    if info['relationships']:
        print('\nWhy it connects')
        for rel in info['relationships']: print('  ' + rel['reason'])
    if info['sources']:
        print('\nLearned from')
        for source in info['sources']: print('  ' + source['title'])
    return 0


def context_cmd(argv):
    from intelligence import compose_context
    intent = ' '.join(a for a in argv if not a.startswith('--'))
    if not intent:
        print('Usage: lectic context "describe the task"'); return 2
    try: result = compose_context(os.getcwd(), intent)
    except Exception as exc:
        print('Context failed: ' + str(exc)); return 1
    if '--json' in argv:
        print(json.dumps(result, indent=2)); return 0
    print(result['summary'])
    print('\nUsing for this task')
    for item in result['using']: print(f"  {item['name']} — {item['why']}")
    print(f"  {result['task_context']['label']} — {result['task_context']['reason']}")
    print(f"\nSelected {len(result['knowledge'])} relevant idea(s); unrelated collections were left out.")
    return 0


def install(argv):
    from packs import inspect_pack, install_pack
    flags_with_val = {'--name', '--as'}
    def is_flag_val(a):
        return any(option(argv, f) == a for f in flags_with_val)
    location = next((a for a in argv if not a.startswith('--') and not is_flag_val(a)), None)
    if not location:
        print('Usage: lectic install REGISTRY:NAME | FILE | URL [--as NAME | --name NAME] [--pin] [--inspect]')
        return 2
    if '--inspect' in argv:
        return inspect_cmd([location])
    as_name = option(argv, '--as') or option(argv, '--name')
    pin = '--pin' in argv
    origin_location = None
    if location.startswith('registry:'):
        from registry import resolve_registry_pack, registry_pack_location
        try:
            entry = resolve_registry_pack(location, project=os.getcwd())
            origin_location = entry['url']
            location = registry_pack_location(entry, os.getcwd())
            as_name = as_name or entry.get('install_name') or entry['name']
        except Exception as exc:
            print(f"Registry error: {exc}")
            return 1
    report = install_pack(os.getcwd(), location, name=as_name, pin=pin, origin_location=origin_location)
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
    """Publish a compiled pack to a team host or registry."""
    from publish import publish_pack
    flags_with_val = {'--to', '--token', '--webhook', '--tags', '--download-url'}
    def is_flag_val(a):
        return any(option(argv, f) == a for f in flags_with_val)
    name = next((a for a in argv if not a.startswith('--') and not is_flag_val(a)), None)
    to_url = option(argv, '--to')
    to_registry = '--registry' in argv
    if not name or (not to_url and not to_registry):
        print('Usage: lectic publish <collection-or-file> --to <URL> [--registry] [--token <TOKEN>] [--webhook <URL>]')
        return 2
    token = option(argv, '--token')
    webhook = option(argv, '--webhook')
    raw_tags = option(argv, '--tags')
    tags = [t.strip() for t in raw_tags.split(',')] if raw_tags else None

    download_url = option(argv, '--download-url') or to_url
    if to_url:
        try:
            res = publish_pack(os.getcwd(), name, to_url, token=token, webhook_url=webhook,
                               download_url=option(argv, '--download-url'), include_sources='--include-sources' in argv)
            download_url = res['download_url']
            print(res['message'])
            if res['phase'] != 'published': return 1
            if res.get('webhook_sent'):
                print(f"  Notified webhook: {webhook}")
            elif res.get('webhook_error'):
                print(f"  Webhook notification error: {res['webhook_error']}")
        except Exception as exc:
            print(f'Publish failed: {exc}')
            return 1

    if to_registry:
        from registry import prepare_registry_entry
        try:
            if not download_url:
                print('Supply a working recipient link with --download-url when preparing a registry entry.'); return 2
            reg_entry = prepare_registry_entry(os.getcwd(), name, download_url, tags=tags)
            print("\nRegistry Entry (for registry/index.json):")
            print(json.dumps(reg_entry, indent=2))
            print("\nTo submit this pack to the community marketplace:")
            print("  1. Submit a PR to https://github.com/tyreamer/lectic")
            print("  2. Add the JSON entry above to `registry/index.json` under `packs`")
        except Exception as exc:
            print(f"Registry entry generation failed: {exc}")
            return 1
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


def inbox_cmd(argv):
    """View or sort dropped links and files from your Lectic Inbox folder."""
    from inbox import ensure_inbox_folder, scan_inbox, route_all_inbox
    folder = ensure_inbox_folder(os.getcwd())
    if '--process' in argv or '--route' in argv:
        res = route_all_inbox(os.getcwd())
        if not res['items']:
            print(f"Lectic Inbox is empty ({folder}).")
            return 0
        print(f"Sorted {len(res['items'])} drop item{'s' if len(res['items']) != 1 else ''} into your collections:")
        for it in res['items']:
            print(f"  {it['file']} -> {it['collection']}")
        return 0

    scan = scan_inbox(os.getcwd())
    print(f"Lectic Drop Inbox: {scan['inbox_folder']}\n")
    if not scan['items']:
        print("Inbox is empty. Drop web shortcuts, YouTube links, notes, or files here anytime.")
        print("Your connected assistants will notice them and ask where to add them!")
        return 0

    print(f"{scan['count']} item{'s' if scan['count'] != 1 else ''} waiting to be sorted into collections:\n")
    for it in scan['items']:
        target = it['suggested_collection'] or 'Inbox'
        print(f"  {it['filename']}")
        if it['url']:
            print(f"    Link:       {it['url']}")
        print(f"    Suggested:  {target} ({it['match_reason']})")
    print("\nRun `lectic inbox --process` or ask your assistant: 'Sort my inbox drops'.")
    return 0


def ec(argv):
    sys.argv = ['ec.py'] + argv
    import ec as core
    return core.main()


def try_example(argv):
    from starter import try_starter
    result = try_starter(os.getcwd())
    if '--json' in argv:
        print(json.dumps(result, indent=2))
    else:
        print('Debugging Starter is ready.')
        print('This is a prewritten teaching example; no model was called.')
        print('\nWhat Lectic did:')
        print('  Input:   a short debugging lesson with three source-backed procedures')
        print('  Output:  a review, then a repeatable debugging checklist')
        print('  Reuse:   ' + str(len(result['reuse']['reused_units'])) + ' saved knowledge units were applied again')
        print('\nFirst use:  ' + result['first_result'])
        print('Second use: ' + result['second_result'])
        print('\nTry your own work with a connected assistant:\n  ' + result['next_prompt'])
    return 0


def positional(argv, flags_with_val=()):
    """Bare arguments, skipping the values that belong to the listed flags."""
    result = []
    skip_value = False
    for argument in argv:
        if skip_value:
            skip_value = False
        elif argument in flags_with_val:
            skip_value = True
        elif not argument.startswith('--'):
            result.append(argument)
    return result


def start_cmd(argv):
    """The smallest first run: two questions at most, then one real thing saved and one next step."""
    from start import start as run_start
    sources = positional(argv, {'--name', '--goal'})
    name = option(argv, '--name')
    goal = option(argv, '--goal')
    interactive = sys.stdin.isatty() and '--yes' not in argv and '--json' not in argv
    if interactive:
        try:
            if not sources:
                print("Lectic saves material you trust so your assistant can use it again later.\n")
                answer = input('  What do you want Lectic to learn from? A file, a folder, or a YouTube link.\n'
                               '  (press Enter to run the built-in sample instead): ').strip().strip('"')
                if answer: sources = [answer]
            if sources and not goal:
                goal = input('  What do you want to use this knowledge for?\n  ').strip() or None
        except (EOFError, KeyboardInterrupt):
            print('\nStart cancelled.')
            return 130
        print()
    result = run_start(os.getcwd(), sources, name, goal)
    if '--json' in argv:
        print(json.dumps(result, indent=2)); return 0
    if result['mode'] == 'sample':
        print('Created:   ' + result['created'] + ' called "' + result['collection'] + '"')
        print('Learned:   ' + result['learned'])
        print('Reuse:     ' + str(result['reused_units']) + ' saved knowledge units were applied to a second plan')
        print('\nFirst use:  ' + result['first_result'])
        print('Second use: ' + result['second_result'])
    else:
        print('Created:   ' + result['created'])
        print('Saved in:  ' + result['location'])
        print('Sources:   ' + ', '.join(result['sources'][:6]) + (' ...' if len(result['sources']) > 6 else ''))
        print('Learned:   ' + result['learned'])
    connected = [name for name, state in checked_clients().items() if state.startswith('connected')]
    print('\nNext:      ' + ('Open ' + connected[0] if connected else 'Run `waykit setup`, restart your assistant') +
          ' and say:\n             ' + result['next_prompt'])
    print('Share it:  ' + result['share_command'] + '   (one HTML page anyone can open)')
    print('           waykit pack "' + result['collection'] + '"   (a file another WayKit can install)')
    return 0


def prepare_cmd(argv):
    """Compile and verify knowledge from a collection's sources."""
    from goal_workflow import work
    from collection_store import Library
    names = positional(argv, {'--goal'})
    name = names[0] if names else None
    library = Library(os.getcwd())
    if not name:
        active = library.index.get('active_collection')
        if active:
            resolved = library.resolve(active)
            if resolved:
                name = resolved[1]['name']
    if not name:
        print('Usage: waykit prepare "Collection Name" [--reconcile] [--json]')
        print('Compiles saved sources into verified knowledge units.')
        return 2

    reconciled = '--reconcile' in argv
    result = work(project=os.getcwd(), collection=name, action='prepare', reconciled=reconciled)
    if '--json' in argv:
        print(json.dumps(result, indent=2)); return 0

    phase = result.get('phase')
    if phase == 'knowledge_saved':
        summary = result.get('summary', {})
        print(f"Prepared {result['collection']}:")
        print(f"  {summary.get('knowledge_units', 0)} knowledge units verified across {summary.get('source_count', 0)} sources")
        print(f"  Source revision: {result.get('source_revision')}")
        print(f"\nNext: Share it as a standalone page:")
        print(f"  waykit share \"{result['collection']}\"")
        return 0

    if phase == 'reconcile':
        result2 = work(project=os.getcwd(), collection=name, action='prepare', reconciled=True)
        if result2.get('phase') == 'knowledge_saved':
            summary = result2.get('summary', {})
            print(f"Prepared and reconciled {result2['collection']}:")
            print(f"  {summary.get('knowledge_units', 0)} knowledge units verified across {summary.get('source_count', 0)} sources")
            print(f"  Source revision: {result2.get('source_revision')}")
            print(f"\nNext: Share it as a standalone page:")
            print(f"  waykit share \"{result2['collection']}\"")
            return 0
        print(f"Collection {result['collection']} needs cross-source reconciliation.")
        print(f"Run: waykit prepare \"{name}\" --reconcile")
        return 0

    if phase == 'extract':
        task = result.get('agent_task', {})
        pending = len(task.get('pending_sources', []))
        print(f"Collection {result['collection']} has {pending} pending source(s) waiting for knowledge extraction.")
        print(f"Open your connected assistant and say:\n  Prepare my {result['collection']} collection.")
        return 0

    if phase == 'needs_sources':
        print(f"Collection {name} has no sources to prepare. Add sources with `waykit start` or `waykit refresh`.")
        return 1

    print(f"Prepare status for {name}: {phase}")
    if 'message' in result:
        print(f"  {result['message']}")
    return 0


def share_artifact(argv):
    """Write one static HTML page about a collection. `waykit share` is the live link; this is a file."""
    from artifact_page import write_page
    names = positional(argv, {'--out', '--build'})
    name = names[0] if names else None
    build = option(argv, '--build')
    if not name and not build:
        print('Usage: waykit share-artifact "Collection Name" [--out PATH] [--build BUILD_ID] [--no-quotes] [--json]')
        return 2
    result = write_page(os.getcwd(), name, option(argv, '--out'), build, include_quotes='--no-quotes' not in argv)
    if '--json' in argv:
        print(json.dumps(result, indent=2)); return 0
    print(f"Wrote a shareable page for {result['name']}: {result['file']} ({result['bytes'] // 1024 + 1} KB)")
    print(f"  {result['units']} knowledge units, {result['sources']} sources, {result['methods']} reusable methods")
    print('  Includes: ' + result['contains'])
    print('  Privacy:  ' + result['privacy'])
    print('\nOne file, no scripts and no internet needed. Open it in any browser, email it, or host it anywhere.')
    return 0


def refresh_cmd(argv):
    """Save a fresh version of a collection's material from a location you name."""
    from refresh import refresh as run_refresh
    names = positional(argv, {'--from'})
    name = names[0] if names else None
    source = option(argv, '--from')
    if not name or not source:
        print('Usage: waykit refresh "Collection Name" --from PATH_OR_LINK [--json]')
        print('WayKit never guesses where your material lives, so say where to read it from.')
        return 2
    result = run_refresh(os.getcwd(), name, source)
    if '--json' in argv:
        print(json.dumps(result, indent=2)); return 0
    print(result['message'])
    for label, key in (('added', 'added_sources'), ('changed', 'changed_sources'), ('removed', 'removed_sources')):
        for item in result[key]: print(f'  {label:<8} {item}')
    if not result['unchanged']:
        print(f"\nPrevious version {result['previous_revision']} is still saved. Compare them with:")
        print(f"  waykit diff \"{result['collection']}\"")
    return 0


def diff_cmd(argv):
    """Compare two saved versions of a collection without changing anything."""
    from refresh import diff as run_diff
    names = positional(argv, {'--before', '--after'})
    name = names[0] if names else None
    if not name:
        print('Usage: waykit diff "Collection Name" [--before REVISION] [--after REVISION] [--json]')
        return 2
    changes = run_diff(os.getcwd(), name, option(argv, '--before'), option(argv, '--after'))['changes']
    if '--json' in argv:
        print(json.dumps(changes, indent=2)); return 0
    print(f"{changes['before']}  ->  {changes['after']}")
    for label, key in (('added source', 'added_sources'), ('changed source', 'changed_sources'),
                       ('removed source', 'removed_sources')):
        for item in changes[key]: print(f'  {label:<15} {item}')
    if not changes['knowledge_comparison_available']:
        print('  Knowledge was not compared: one of these versions has no saved knowledge yet.')
    else:
        print(f"  knowledge      +{len(changes['added_units'])} new, ~{len(changes['changed_units'])} changed, "
              f"-{len(changes['removed_units'])} removed units")
    print(f"  {changes['preserved_builds']} saved build(s) preserved")
    return 0


def cloud(argv):
    """Run WayKit Cloud service commands (serve, create-user, list-users, token, export)."""
    from cloud_cli import cloud_cmd
    return cloud_cmd(argv)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else 'status'
    handlers = {'setup': setup, 'start': start_cmd, 'prepare': prepare_cmd, 'try': try_example,
                'identity': identity, 'share': share, 'share-artifact': share_artifact,
                'refresh': refresh_cmd, 'diff': diff_cmd, 'connect': connect,
                'pack': pack, 'install': install, 'update': update, 'publish': publish, 'verify': verify,
                'search': search, 'inspect': inspect_cmd, 'explain': explain_cmd, 'context': context_cmd, 'inbox': inbox_cmd,
                'backup': backup, 'push': push, 'pull': pull, 'restore': restore,
                'status': status, 'serve': serve, 'cloud': cloud, 'ec': ec}
    if command in {'-h', '--help', 'help'} or command not in handlers:
        print(__doc__.strip()); return 0 if command in {'-h', '--help', 'help'} else 2
    try:
        return handlers[command](argv[1:])
    except ModuleNotFoundError as exc:
        package = exc.name or 'a required package'
        print(f'WayKit needs the Python package `{package}` to run this command.')
        print('Install or repair WayKit with:  python -m pip install --upgrade waykit')
        return 1
    except (OSError, ValueError) as exc:
        print('WayKit could not finish: ' + str(exc))
        return 1


if __name__ == '__main__':
    sys.exit(main())
