"""Offline release gate. Run from a checkout or `python -m lectic.scripts.release_check`.

Uses only temporary homes and a loopback HTTP server. No live user configuration,
remote publishing, YouTube access or model API calls.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ec import ROOT, digest, fingerprint, read, require, validate_schema, write
from release_version import VERSION
from client_check import check_connection
from collection_store import Library
from goal_workflow import validate_build, work
from home_archive import archive_home, merge_archive, open_archive
from identity import save_identity
from lectic_mcp import serve_http
from packs import build_pack, install_pack, open_pack, update_pack
from registry import registry_pack_location
from starter import NAME, try_starter


def check_release():
    report = {'version': VERSION, 'package_root': str(ROOT), 'checks': []}
    for relative in ('SKILL.md', 'prompts/extract.md', 'schemas/pack.schema.json',
                     'fixtures/demo_capabilities.json', 'registry/index.json', 'fixtures/packs/debugging-starter.lectic'):
        require((ROOT / relative).is_file(), 'Missing packaged resource: ' + relative)
    report['checks'].append('packaged resources present')
    registry = read(ROOT / 'registry/index.json')
    validate_schema(registry, 'registry')
    for entry in registry['packs']:
        require(entry.get('sha256'), 'Catalog entry has no artifact checksum')
        require(entry.get('bundled_path'), 'Offline release gate needs a bundled copy of each catalog artifact')
        pack = Path(registry_pack_location(entry))
        manifest, _ = open_pack(pack.read_bytes())
        require(manifest['unit_count'] == entry['units'], 'Catalog unit count differs from artifact')
        require([m['title'] for m in manifest['methods']] == entry['methods'], 'Catalog methods differ from artifact')
        if (ROOT / 'docs/registry/index.json').exists():
            require(read(ROOT / 'docs/registry/index.json') == registry, 'Website catalog differs from package catalog')
            require((ROOT / 'docs/packs' / pack.name).read_bytes() == pack.read_bytes(), 'Website pack differs from bundled pack')
    report['checks'].append('catalog schema, actual pack bytes, checksum and declared contents')
    previous = os.environ.get('LECTIC_HOME')
    try:
        with tempfile.TemporaryDirectory(prefix='lectic-release-gate-') as temp:
            base = Path(temp)
            author = base / 'first-project'; author.mkdir()
            home = base / 'author-home'
            os.environ['LECTIC_HOME'] = str(home)
            result = try_starter(author)
            require(len(result['reuse']['reused_units']) == 3 and not result['reuse']['new_units'], 'Starter did not reuse the saved knowledge')
            validate_build(Path(result['first_result']).parent)
            validate_build(Path(result['second_result']).parent)
            report['checks'].append('offline starter produces two validated results and reuses three units')

            other_project = base / 'second-project'; other_project.mkdir()
            # A distinct interpreter reads the already-saved library from another project.
            env = dict(os.environ)
            env['PYTHONPATH'] = str(ROOT / 'scripts')
            probe = subprocess.run([sys.executable, '-c', 'import json; from starter import try_starter; print(json.dumps(try_starter()))'],
                                   cwd=other_project, env=env, capture_output=True, text=True, timeout=30)
            require(probe.returncode == 0, 'Fresh-process starter failed: ' + probe.stderr)
            again = json.loads(probe.stdout)
            require(again['second_result'] == result['second_result'], 'Fresh-process reuse created a duplicate result')
            report['checks'].append('fresh interpreter and different project reuse the same saved results')

            httpd = serve_http(author, port=0, token='release-check-temporary-token-1234567890', announce=None)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
            url = f'http://127.0.0.1:{httpd.server_address[1]}/t/{httpd.token}/mcp'
            try:
                require(check_connection({'url': url})[0], 'HTTP handshake/home lookup failed')
                body = {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'lectic_starter', 'arguments': {}}}
                request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=20) as response: wire = json.loads(response.read())
                require(not wire['result']['isError'], 'Starter over HTTP failed')
                over_http = json.loads(wire['result']['content'][0]['text'])
                require(over_http['second_result'] == result['second_result'], 'HTTP call did not reuse the same library')
            finally:
                httpd.shutdown(); httpd.server_close(); thread.join(timeout=3)
            report['checks'].append('real HTTP handshake, home lookup and starter reuse')

            save_identity(author, 'Release test identity', 'temporary@example.test')
            pack = base / 'signed.lectic'
            build_pack(author, NAME, pack, include_sources=True, version='1.0.0')
            os.environ['LECTIC_HOME'] = str(base / 'recipient-home')
            recipient = base / 'recipient-project'; recipient.mkdir()
            installed = install_pack(recipient, str(pack), name=NAME, pin=True)
            require(installed['verification'] == 'verified' and installed['publisher_status'] == 'signed', 'Signed transfer did not verify')
            library = Library(recipient); folder, data = library.resolve(NAME)
            prior_run = library.run(folder, data); prior_hash = fingerprint(read(prior_run / 'ir.json'))
            os.environ['LECTIC_HOME'] = str(home)
            library = Library(author); folder, data = library.resolve(NAME); run = library.run(folder, data)
            checkpoint = next((run / 'units').glob('*.json'))
            part = read(checkpoint); part['units'][0]['statement'] += ' Respect the cited conditions.'; write(checkpoint, part)
            work(project=author, collection=NAME, action='prepare', reconciled=True)
            build_pack(author, NAME, pack, include_sources=True, version='1.0.1')
            require(not open_pack(pack.read_bytes())[0]['methods'], 'Update carried methods reviewed against earlier knowledge')
            os.environ['LECTIC_HOME'] = str(base / 'recipient-home')
            updated = update_pack(recipient, NAME)
            require(updated['knowledge_matches_pack'], 'Update did not persist the declared knowledge')
            require(fingerprint(read(prior_run / 'ir.json')) == prior_hash, 'Update changed historical knowledge')
            report['checks'].append('public signature verification, same-source interpretation update and preserved history')

            archive = archive_home(base / 'recipient-home')
            _, members = open_archive(archive)
            require(not any('identity.json' in name or 'server.json' in name for name in members), 'Backup exposed credentials')
            os.environ['LECTIC_HOME'] = str(base / 'restored-home')
            restored = merge_archive(recipient, archive)
            repeated = merge_archive(recipient, archive)
            require(restored['collections_added'] and repeated['collections_present'] and not repeated['collections_added'], 'Restore was not idempotent')
            report['checks'].append('knowledge backup/restore and repeated additive merge')
    finally:
        if previous is None: os.environ.pop('LECTIC_HOME', None)
        else: os.environ['LECTIC_HOME'] = previous
    report['status'] = 'passed'
    return report


if __name__ == '__main__':
    print(json.dumps(check_release(), indent=2))
