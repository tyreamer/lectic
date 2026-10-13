"""Durable central home behind an ephemeral, free Python service. Stdlib only.

The filesystem is a cache. A tool response is acknowledged only after a durable
manifest commit. Immutable objects deduplicate; a lease and revision prevent
two servers from overwriting each other's changes. Phone saves stay in durable
storage until their import and the manifest are committed together.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import secrets
import sys
import time
import urllib.error
import urllib.request
import zlib

from ec import Invalid, digest, fingerprint, read, require, safe_child, write
from home import home_scope
from home_archive import portable
from privacy import require_shareable
from store import LocalStore

CHUNK = 48 * 1024


def persistent(path):
    # A restarted container is the same logical server. Its signing identity
    # and resume pointers survive there, while backups still exclude them.
    return portable(path) or path == 'identity.json' or path.startswith('sessions/')


class RemoteHome:
    def __init__(self, root, url, token):
        self.root = Path(root).resolve()
        self.url = url.rstrip('/')
        self.token = token
        require(token and self.url.startswith(('https://', 'http://127.0.0.1:', 'http://localhost:')),
                'A private HTTPS store address and token are required')
        self.marker = self.root / '.remote-cache.json'
        binding = digest(self.url.encode('utf-8'))
        if self.marker.is_file():
            require(read(self.marker).get('store') == binding, 'This cache belongs to another central store')
        else:
            require(not self.root.exists() or not any(self.root.iterdir()),
                    'A remote cache must be empty; never use your existing knowledge home as a cache')
            self.root.mkdir(parents=True, exist_ok=True)
            write(self.marker, {'store': binding})
        self.revision = None

    def request(self, path, value=None):
        data = None if value is None else json.dumps(value, separators=(',', ':')).encode('utf-8')
        req = urllib.request.Request(self.url + '/' + path, data=data,
              headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.token,
                       'User-Agent': 'WayKit/0.3.2'})
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read(2000).decode('utf-8', 'replace')
            raise Invalid(f'Central storage refused the operation ({exc.code}): {detail}') from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise Invalid('Central storage is unavailable; nothing has been acknowledged as saved') from exc

    def files(self):
        return {p.relative_to(self.root).as_posix(): p for p in self.root.rglob('*')
                if p.is_file() and not p.is_symlink() and persistent(p.relative_to(self.root).as_posix())}

    @staticmethod
    def groups(entries, max_bytes=180000, max_items=12):
        group, size = [], 0
        for entry in entries:
            length = entry.get('encoded_size', 0)
            if group and (size + length > max_bytes or len(group) >= max_items):
                yield group; group, size = [], 0
            group.append(entry); size += length
        if group: yield group

    def hydrate(self, state):
        needed = {}
        files = self.files()
        for path, item in state['files'].items():
            require(persistent(path), 'Central inventory contains a runtime-local path')
            safe_child(self.root, path)
            if path not in files or digest(files[path].read_bytes()) != item['hash']:
                needed.setdefault(item['object'], item)
        groups = list(self.groups([{'id': ident, **item} for ident, item in needed.items()]))

        def fetch(group):
            return self.request('get-objects', {'ids': [o['id'] for o in group]})['objects']

        received = {}
        if groups:
            with ThreadPoolExecutor(max_workers=8) as pool:
                for objects in pool.map(fetch, groups):
                    for o in objects:
                        encoded = b''.join(base64.b64decode(part, validate=True) for part in o['data'])
                        require(digest(encoded) == o['id'] and len(encoded) == o['encoded_size'], 'Central object bytes were altered')
                        require(o['encoding'] == 'zlib', 'Unsupported central object encoding')
                        inflater = zlib.decompressobj()
                        raw = inflater.decompress(encoded, o['raw_size'] + 1)
                        require(inflater.eof and len(raw) == o['raw_size'] and digest(raw) == o['raw_hash'], 'Central knowledge bytes were altered')
                        received[o['id']] = raw
        # All received bytes validate before any cache replacement. The cache
        # marker binds this directory; the user's actual local home is untouched.
        for path, item in state['files'].items():
            if item['object'] in received:
                target = safe_child(self.root, path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(received[item['object']])
        for path, file in files.items():
            if path not in state['files']:
                require(file.resolve().is_relative_to(self.root), 'Cache cleanup escaped its directory')
                file.unlink()
        self.revision = state['revision']

    def inventory(self, state):
        inventory, objects = {}, {}
        known = {o['hash']: o for o in state['files'].values()}
        for path, file in self.files().items():
            if path != 'identity.json': require_shareable(file, self.root)
            raw = file.read_bytes()
            require(len(raw) <= 64 * 1024 * 1024, 'Knowledge file exceeds the portable size limit')
            raw_hash = digest(raw)
            if raw_hash in known:
                inventory[path] = known[raw_hash]
                continue
            encoded = zlib.compress(raw, 6)
            ident = digest(encoded)
            inventory[path] = {'hash': raw_hash, 'object': ident, 'size': len(raw), 'encoded_size': len(encoded)}
            objects[ident] = {'id': ident, 'raw_hash': raw_hash, 'raw_size': len(raw), 'encoded_size': len(encoded),
                 'parts': (len(encoded) + CHUNK - 1) // CHUNK, 'encoding': 'zlib',
                 'data': [{'part': i // CHUNK, 'body': base64.b64encode(encoded[i:i + CHUNK]).decode('ascii')}
                          for i in range(0, len(encoded), CHUNK)]}
            known[raw_hash] = inventory[path]
        return inventory, objects

    def upload(self, objects):
        batch, size = [], 0
        for o in objects.values():
            for part in o['data']:
                record = {**o, 'data': [part]}
                n = len(part['body']) + 300
                if batch and (size + n > 180000 or len(batch) >= 16):
                    self.request('objects', {'objects': batch}); batch, size = [], 0
                batch.append(record); size += n
        if batch: self.request('objects', {'objects': batch})

    def import_phone(self, project):
        from capture_store import CaptureStore
        from capture_write import save_capture
        from phone_capture import decode_share
        pending = self.request('queue')['items']
        for item in pending:
            payload = decode_share(json.dumps(item).encode('utf-8'), 'application/json')
            record = save_capture(self.root / 'capture-drop', **payload, capture_id=item['id'],
                         captured_at=item['captured_at'], adapter='iphone-direct', origin='phone-share')
            CaptureStore(project).import_record(record)
        return [item['id'] for item in pending]

    def summary(self, server, state=None, files=None):
        previous = (state or {}).get('library', {})
        changed = {path for path in set((state or {}).get('files', {})) | set(files or {})
                   if (state or {}).get('files', {}).get(path) != (files or {}).get(path)}
        capture_only = state is not None and 'references' in previous and all(
            path == 'identity.json' or path.startswith(('capture/', 'blobs/', 'sessions/')) for path in changed)
        if capture_only:
            # Source runs and methods are byte-identical to the last checked
            # snapshot. Refresh capture availability without revalidating every
            # transcript and build just to acknowledge a cheap phone save.
            from capture_store import CaptureStore
            from library_guide import render_library
            result = json.loads(json.dumps(previous))
            captures = CaptureStore(server.project).listing()['items']
            for row in result['collections']:
                row['captures'] = [c for c in captures if row['name'] in c['collections']]
            result['scope'] = str(server.project)
            base = {k: v for k, v in result.items() if k not in {'binding_hash', 'markdown'} and not k.startswith('inbox_')}
            result['binding_hash'] = fingerprint(base)
            result['markdown'] = render_library(result)
        else:
            result = server.tool_library()
        # A setup cache can live on another OS. Tool paths must name the stable
        # cache directory used by the hosted service, not the setup machine.
        serialized = json.dumps(result, ensure_ascii=False)
        for spelling in (str(self.root), self.root.as_posix()):
            serialized = serialized.replace(spelling.replace('\\', '\\\\'), '/tmp/waykit-cache')
        return json.loads(serialized)

    @contextmanager
    def operation(self, server):
        owner = secrets.token_hex(16)
        started = time.monotonic()
        def progress(stage):
            print(f'WayKit central storage: {stage} ({time.monotonic() - started:.1f}s)', file=sys.stderr, flush=True)
        progress('acquiring central lease')
        state = self.request('lease', {'owner': owner})
        try:
            with home_scope(self.root), LocalStore(self.root).transaction('knowledge', reentrant=True):
                progress('restoring cache')
                self.hydrate(state)
                progress('importing phone shares')
                ack = self.import_phone(server.project)
                progress('running assistant task')
                yield
                progress('checking changes')
                files, objects = self.inventory(state)
                if files != state['files'] or ack:
                    progress('committing changes')
                    self.upload(objects)
                    committed = self.request('commit', {'owner': owner, 'revision': state['revision'],
                                'files': files, 'ack': ack, 'library': self.summary(server, state, files)})
                    self.revision = committed['revision']
                progress('complete')
        finally:
            try: self.request('release', {'owner': owner})
            except Invalid: pass  # Expiry recovers a dead server; never hide a failed commit.
