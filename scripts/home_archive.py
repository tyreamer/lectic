"""Move a whole Lectic home: to an always-on server, to another machine, or to a backup file.

The home is already content-addressed, so a transfer is archive → send → merge by
identity. Blobs dedupe by hash, collections by ID, capture records are immutable
envelopes. Nothing is overwritten: a collection that exists on both sides and
differs is reported as diverged and left alone.

What never travels: the destination's own secret (`server.json`), the ephemeral
`share-link.json`, and per-project `sessions/` pointers, which mean nothing on
another machine.
"""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from release_version import VERSION as RELEASE_VERSION
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile

from ec import VERSION, Invalid, digest, fingerprint, read, require, safe_child, validate_schema, write
from collection_store import Library
from home import storage_root
from store import LocalStore, home_transaction

ARCHIVE_VERSION = '1.0'
SUFFIX = '.lectic-home'
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MACHINE_LOCAL = {'server.json', 'share-link.json'}
MACHINE_LOCAL_DIRS = {'sessions', '.locks'}
AREAS = {'blobs', 'collections', 'capture', 'capabilities', 'exports', 'evaluations', 'runs', 'use-guides', 'inbox'}


def portable(relative):
    """Everything except this machine's own identity, locks and scratch."""
    parts = relative.split('/')
    if parts[0] in MACHINE_LOCAL or parts[0] in MACHINE_LOCAL_DIRS: return False
    if any(part.startswith('.') for part in parts): return False
    return parts[0] == 'library.json' or parts[0] in AREAS


# ---------------------------------------------------------------- write

@home_transaction
def archive_home(home):
    home = Path(home)
    members = {}
    if not home.is_dir(): raise Invalid('This home has nothing saved yet: ' + str(home))
    for path in sorted(home.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        relative = path.relative_to(home).as_posix()
        if not portable(relative): continue
        from privacy import require_shareable
        require_shareable(path, home)
        raw = path.read_bytes()
        require(len(raw) <= MAX_MEMBER_BYTES, 'Home file exceeds the supported size: ' + relative)
        members[relative] = raw
    require(members, 'This home has nothing saved yet: ' + str(home))
    library = read(home / 'library.json') if (home / 'library.json').is_file() else {'collections': []}
    manifest = {'schema_version': ARCHIVE_VERSION, 'created_at': datetime.now(timezone.utc).isoformat(),
                'lectic_version': RELEASE_VERSION, 'collections': [{'collection_id': c['collection_id'], 'name': c['name']}
                                                           for c in library.get('collections', [])],
                'blob_count': sum(1 for p in members if p.startswith('blobs/')),
                'files': {path: digest(raw) for path, raw in sorted(members.items())}}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('home.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        for path, raw in sorted(members.items()): archive.writestr(path, raw)
    raw = buffer.getvalue()
    require(len(raw) <= MAX_ARCHIVE_BYTES, 'Home archive exceeds the supported size')
    return raw


def open_archive(raw):
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise Invalid('Not a Lectic home archive (not a zip archive)') from exc
    members = {}
    for info in archive.infolist():
        name = info.filename
        require(not name.startswith('/') and '\\' not in name and '..' not in name.split('/') and ':' not in name and not info.is_dir(),
                'Archive contains an unsafe path: ' + name)
        require(info.file_size <= MAX_MEMBER_BYTES, 'Archive member exceeds the supported size: ' + name)
        members[name] = archive.read(name)
    require('home.json' in members, 'Not a Lectic home archive (no home.json)')
    manifest = json.loads(members.pop('home.json').decode('utf-8'))
    require(manifest.get('schema_version') == ARCHIVE_VERSION, 'Unsupported home archive version')
    require(set(manifest['files']) == set(members), 'Archive inventory differs from its manifest')
    for path, expected in manifest['files'].items():
        require(digest(members[path]) == expected, 'Archive file was altered: ' + path)
        require(portable(path), 'Archive carries a file that does not belong to a home: ' + path)
    return manifest, members


# ---------------------------------------------------------------- merge

@home_transaction
def merge_archive(project, raw, home=None):
    """Add what is missing; never overwrite, never silently reconcile a divergence."""
    home = Path(home) if home else storage_root(project)
    home.mkdir(parents=True, exist_ok=True)
    manifest, members = open_archive(raw)
    store = LocalStore(home)
    report = {'phase': 'home_merged', 'blobs_added': 0, 'collections_added': [], 'collections_present': [],
              'collections_diverged': [], 'captures_added': 0, 'other_files_added': 0, 'issues': []}
    # Blobs first: content-addressed, so adding them can never conflict.
    for path, raw_bytes in sorted(members.items()):
        if not path.startswith('blobs/'): continue
        blob_hash = path.split('/', 1)[1]
        if store.has_blob(blob_hash): continue
        require(digest(raw_bytes) == blob_hash, 'Archive blob does not match its name: ' + path)
        store.put_blob(raw_bytes); report['blobs_added'] += 1

    incoming_library = json.loads(members['library.json'].decode('utf-8')) if 'library.json' in members else {'collections': []}
    existing = Library(project, home=home).index if (home / 'library.json').is_file() else {'schema_version': VERSION, 'collections': [], 'active_collection': None}
    by_id = {c['collection_id']: c for c in existing['collections']}
    taken = {c['name'].casefold() for c in existing['collections']}
    for entry in incoming_library.get('collections', []):
        cid, folder = entry['collection_id'], entry['path']
        files = {p: raw_bytes for p, raw_bytes in members.items() if p.startswith(folder.rstrip('/') + '/')}
        if not files:
            report['issues'].append(f"{entry['name']}: the archive lists it but carries no files"); continue
        destination = safe_child(home, folder)
        if cid in by_id or destination.exists():
            here = {p: digest((home / p).read_bytes()) for p in files if (home / p).is_file()}
            if here == {p: digest(raw_bytes) for p, raw_bytes in files.items()}:
                report['collections_present'].append(entry['name'])
            else:
                report['collections_diverged'].append(entry['name'])
            continue
        name = entry['name']
        if name.casefold() in taken:
            base, n = name, 2
            while name.casefold() in taken: name = f'{base} ({n})'; n += 1
        write_files(home, files)
        # The collection's own record owns its name; keep both sides readable.
        data = read(destination / 'collection.json'); data['name'] = name
        write(destination / 'collection.json', data)
        existing['collections'].append({'collection_id': cid, 'name': name, 'path': folder})
        taken.add(name.casefold()); report['collections_added'].append(name)
    existing['schema_version'] = VERSION
    existing.setdefault('active_collection', None)
    if existing['active_collection'] not in {c['collection_id'] for c in existing['collections']}:
        existing['active_collection'] = None
    write(home / 'library.json', existing)

    # Everything else is immutable or content-addressed: add when absent, never replace.
    rest = {p: raw_bytes for p, raw_bytes in members.items()
            if p != 'library.json' and not p.startswith('blobs/') and not p.startswith('collections/')}
    added = write_files(home, rest, skip_existing=True)
    report['captures_added'] = sum(1 for p in added if p.startswith('capture/records/'))
    report['other_files_added'] = len(added) - report['captures_added']
    report['issues'] += verify(project, home)
    return report


def write_files(home, files, skip_existing=False):
    written = []
    for path, raw_bytes in sorted(files.items()):
        target = safe_child(home, path)
        if skip_existing and target.exists(): continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            handle.write(raw_bytes); temp = Path(handle.name)
        temp.replace(target); written.append(path)
    return written


def verify(project, home):
    """Report a home that does not hold together, rather than leaving it to fail later."""
    issues = []
    try:
        library = Library(project, home=home)
    except (Invalid, ValueError, OSError, KeyError) as exc:
        return ['The merged library does not validate: ' + str(exc)]
    for entry in library.index['collections']:
        try:
            library.resolve(entry['collection_id'])
        except (Invalid, ValueError, OSError, KeyError) as exc:
            issues.append(f"{entry['name']}: {exc}")
    return issues


# ---------------------------------------------------------------- over the link

def endpoint(link):
    require(isinstance(link, str) and re.match(r'https?://', link), 'Give the link a Lectic server printed (…/t/SECRET/mcp)')
    return re.sub(r'/(mcp|home|capture)/?$', '', link.rstrip('/')) + '/home'


def request(url, data=None, timeout=300):
    req = urllib.request.Request(url, data=data, method='POST' if data is not None else 'GET',
                                 headers={'Content-Type': 'application/zip', 'User-Agent': 'lectic/' + VERSION})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read(MAX_ARCHIVE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace')[:400]
        raise Invalid(f'The Lectic server refused ({exc.code}): {detail}') from exc
    except urllib.error.URLError as exc:
        raise Invalid('Could not reach that Lectic: ' + str(exc.reason)) from exc


def push(project, link):
    raw = archive_home(storage_root(project))
    report = json.loads(request(endpoint(link), raw).decode('utf-8'))
    return {**report, 'phase': 'pushed', 'destination': endpoint(link), 'sent_bytes': len(raw)}


def pull(project, link):
    raw = request(endpoint(link))
    report = merge_archive(project, raw)
    return {**report, 'phase': 'pulled', 'source': endpoint(link), 'received_bytes': len(raw)}


def backup(project, destination=None):
    home = storage_root(project)
    raw = archive_home(home)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    destination = (Path(destination) if destination else Path(project) / f'lectic-{stamp}{SUFFIX}').resolve()
    if destination.is_dir() or not destination.suffix:   # a folder, named or not yet made
        destination.mkdir(parents=True, exist_ok=True); destination = destination / f'lectic-{stamp}{SUFFIX}'
    elif destination.suffix != SUFFIX:
        destination = destination.with_name(destination.name + SUFFIX)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    manifest, _ = open_archive(raw)
    return {'phase': 'backed_up', 'file': str(destination), 'bytes': len(raw), 'home': str(home),
            'collections': [c['name'] for c in manifest['collections']], 'blobs': manifest['blob_count']}


def restore(project, location):
    if re.match(r'https?://', str(location)): return pull(project, str(location))
    path = Path(location).expanduser().resolve()
    require(path.is_file(), 'No such archive: ' + str(path))
    raw = path.read_bytes()
    require(len(raw) <= MAX_ARCHIVE_BYTES, 'Archive exceeds the supported size')
    return {**merge_archive(project, raw), 'phase': 'restored', 'source': str(path)}
