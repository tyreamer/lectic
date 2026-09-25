"""Knowledge packs: one file that carries a collection's compiled expertise to another person.

A pack holds the knowledge (checkpoints, IR, the author's reconciliation receipt), the
evidence excerpts every unit cites, the latest Capability Map and built methods as
readable records, a rendered README, and a manifest with hashes. Sources travel as
links by default: on install, Lectic retrieves them again on the recipient's own
network and verifies the bytes against the pack, so the knowledge is validated against
their copy and nothing is redistributed. `include_sources` bundles full text for
material you own. What cannot be verified drops out, and the install says so.
"""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit
import urllib.request
import zipfile

from ec import (ROOT, VERSION, Invalid, assemble, digest, fingerprint, normalize, read, require, safe_child,
                text_write, validate_ir, validate_schema, validate_sources, validate_units, write)
from collection_store import Library
from home import storage_root
from store import LocalStore

PACK_VERSION = '1.0'
SUFFIX = '.lectic'
MAX_PACK_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
SHARE_NOTE = ('Compiled knowledge with evidence excerpts. Source links point at the original material; citation does not '
              'grant redistribution rights, and installing a pack retrieves sources on the installer\'s own network.')


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:48] or 'pack'


def render_install_md(manifest, name, version, install_name, unit_count):
    lines = [
        f'# Installing {name} (v{version})',
        '',
        f'This is a Lectic knowledge pack compiled for team distribution. It carries {unit_count} verified knowledge units and complete sources.',
        '',
        '## Quick Install (Lectic CLI)',
        '',
        '```bash',
        'pip install lectic',
        f'lectic install <pack-file-or-url> --as {install_name} --pin',
        '```',
        '',
        'Once installed, every connected assistant on your machine immediately has access to this team knowledge.',
        '',
        '---',
        '',
        '## Using with Assistants',
        '',
        '### 1. Claude Code',
        'Run setup in your terminal:',
        '```bash',
        'lectic setup',
        '```',
        f'Then ask Claude in any project:',
        f'> "Use our {name} standards to review this file."',
        '',
        '### 2. Codex',
        'Add to `~/.codex/config.toml` (or run `lectic setup`):',
        '```toml',
        '[mcp_servers.lectic]',
        'command = "python"',
        'args = ["-m", "lectic.cli", "serve"]',
        '```',
        f'Then ask Codex:',
        f'> "Check this PR against our {name} standards."',
        '',
        '### 3. ChatGPT',
        '1. Run `lectic share` to get a connection link.',
        '2. In ChatGPT, go to **Settings > Apps & Connectors > Create** and paste the link.',
        '3. Ask ChatGPT:',
        f'> "Review this implementation using our {name} knowledge pack."',
        '',
        '---',
        f"*Compiled with Lectic {manifest.get('lectic_version', VERSION)}*",
        ''
    ]
    return '\n'.join(lines)


# ---------------------------------------------------------------- build

def build_pack(project, collection, destination=None, include_sources=False, team=False, version=None):
    library = Library(project)
    resolved = library.resolve(collection)
    require(resolved is not None, 'Name a saved collection to pack')
    folder, data = resolved
    run = library.run(folder, data)
    corpus, docs, segments = validate_sources(run)
    require((run / 'ir.json').is_file(), 'Prepare the collection first: a pack carries compiled knowledge, and this collection has none yet')
    ir = validate_ir(run)
    require(ir['units'], 'This collection has no reusable knowledge to share yet')
    receipt = read(run / 'reconciliation.json') if (run / 'reconciliation.json').is_file() else None
    if team:
        include_sources = True
    version = str(version).strip() if version else datetime.now(timezone.utc).strftime('%Y-%m-%d')
    files = {}
    files['knowledge/ir.json'] = ir
    for part in sorted((run / 'units').glob('*.json')):
        files['knowledge/units/' + part.name] = read(part)
    if receipt: files['knowledge/reconciliation.json'] = receipt
    from scoped_export import selected_excerpts
    files['sources/excerpts.json'] = selected_excerpts(ir['units'], docs, segments)
    sources = []
    for entry in corpus['sources']:
        doc = docs[entry['source_id']]
        sources.append({'source_id': doc['source_id'], 'filename': doc['filename'], 'title': doc['title'], 'creator': doc['creator'],
                        'url': doc['url'], 'caption_type': doc['caption_type'], 'content_hash': doc['content_hash'],
                        'document_hash': entry['document_hash']})
        if include_sources:
            files['sources/documents/' + doc['source_id'] + '.json'] = doc
            files['sources/' + doc['raw_path']] = safe_child(run, doc['raw_path']).read_bytes()
    maps = []
    index_path = folder / 'maps/index.json'
    if index_path.is_file():
        from capability_maps import load_map, render_map
        shown = read(index_path).get('last_shown')
        if shown:
            record = load_map(folder, data, shown)
            files['maps/' + shown + '.json'] = record; files['maps/' + shown + '.md'] = render_map(record); maps.append(shown)
    methods = []
    from goal_workflow import validate_build
    from outcomes import render_method
    seen = set()
    for build_id in reversed(data['builds']):
        build = safe_child(folder / 'builds', build_id)
        try: validate_build(build)
        except Invalid: continue
        cap = read(build / 'method.json')['capability']
        if cap['capability_id'] in seen: continue
        seen.add(cap['capability_id'])
        selected = [u for u in ir['units'] if u['unit_id'] in cap['unit_ids']]
        if len(selected) != len(cap['unit_ids']): continue  # built from an earlier knowledge revision
        files[f'methods/{build_id}/method.json'] = cap
        files[f'methods/{build_id}/method.md'] = render_method(cap)
        files[f'methods/{build_id}/knowledge.json'] = selected
        methods.append({'build_id': build_id, 'title': cap['title'], 'description': cap['description']})
    encoded = {path: (value if isinstance(value, bytes) else value.encode('utf-8') if isinstance(value, str)
                      else (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')) for path, value in files.items()}
    manifest = {'schema_version': PACK_VERSION, 'pack_id': 'pack-' + '0' * 24, 'name': data['name'],
                'created_at': datetime.now(timezone.utc).isoformat(), 'lectic_version': VERSION,
                'version': version,
                'corpus_id': corpus['corpus_id'], 'ir_hash': fingerprint(ir), 'unit_count': len(ir['units']),
                'sources_included': bool(include_sources), 'sources': sources, 'maps': maps, 'methods': methods,
                'share_note': SHARE_NOTE, 'files': {}}
    if team:
        manifest['distribution'] = {
            'scope': 'team',
            'install_name': slug(data['name']),
            'pinned_version': version
        }
    readme = render_readme(manifest, ir, files, maps, methods)
    encoded['README.md'] = readme.encode('utf-8')
    if team:
        install_md = render_install_md(manifest, data['name'], version, slug(data['name']), len(ir['units']))
        encoded['INSTALL.md'] = install_md.encode('utf-8')
    manifest['files'] = {path: digest(raw) for path, raw in sorted(encoded.items())}
    manifest['pack_id'] = 'pack-' + fingerprint({k: v for k, v in manifest.items() if k not in {'pack_id', 'created_at'}})[:24]
    validate_schema(manifest, 'pack')
    # Sign with local identity if one exists — adds a publisher block after schema validation
    # so the schema passes on the base fields, then we attach the publisher (also schema-valid).
    try:
        from identity import load_identity, sign_manifest
        identity = load_identity(project)
        if identity:
            manifest['publisher'] = sign_manifest(manifest, identity)
            validate_schema(manifest, 'pack')  # re-validate with publisher block
    except Exception:
        pass  # signing is best-effort; never block pack creation
    destination = Path(destination) if destination else Path(project) / (slug(data['name']) + SUFFIX)
    destination = destination.resolve()
    if destination.is_dir(): destination = destination / (slug(data['name']) + SUFFIX)
    if destination.suffix != SUFFIX: destination = destination.with_name(destination.name + SUFFIX)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.tmp', delete=False) as handle:
        temp = Path(handle.name)
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('pack.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        for path, raw in sorted(encoded.items()): archive.writestr(path, raw)
    temp.replace(destination)
    publisher_note = ''
    if manifest.get('publisher'):
        p = manifest['publisher']
        publisher_note = f"Signed by \"{p['name']}\" (key: {p['key_id']})"
    share_instructions = (
        f"Give the '{destination.name}' pack file (or a link to it) to your recipient. "
        "Tell them to simply paste it into their assistant (Claude, Codex, or ChatGPT) and say: 'Install this pack'."
    )
    return {'phase': 'packed', 'pack': str(destination), 'pack_id': manifest['pack_id'], 'name': data['name'],
            'version': manifest.get('version'), 'distribution': manifest.get('distribution'), 'team': bool(team),
            'units': len(ir['units']), 'sources': len(sources), 'sources_included': bool(include_sources),
            'methods': len(methods), 'maps': len(maps), 'bytes': destination.stat().st_size,
            'publisher': publisher_note,
            'share_instructions': share_instructions,
            'share_note': SHARE_NOTE if not include_sources else 'Full source text is included; share only material you may redistribute.'}



def render_readme(manifest, ir, files, maps, methods):
    lines = ['# ' + manifest['name'], '',
             f"A Lectic knowledge pack: {manifest['unit_count']} evidence-backed knowledge units compiled from "
             f"{len(manifest['sources'])} source{'s' if len(manifest['sources']) != 1 else ''}. Install it and every connected assistant can apply it.", '',
             '```', 'pip install lectic', 'lectic install <this file or its link>', '```', '']
    for map_id in maps:
        record = files['maps/' + map_id + '.json']
        opportunities = {o['opportunity_id']: o for o in record['draft']['opportunities']}
        if record['recommended_ids']:
            lines += ['## What it can do', '']
            for uid in record['recommended_ids']:
                o = opportunities[uid]
                lines += [f"- **{o['title']}** — {o['transformation']}"]
            lines.append('')
    if methods:
        lines += ['## Ready methods', ''] + [f"- **{m['title']}** — {m['description']}" for m in methods] + ['']
    kinds = {}
    for unit in ir['units']: kinds[unit['type']] = kinds.get(unit['type'], 0) + 1
    lines += ['## Knowledge', '', ', '.join(f'{n} {k}{"s" if n != 1 else ""}' for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])) + '.',
              'Every unit cites exact source passages; source statements are kept distinct from inference.', '',
              '## Sources', '']
    for s in manifest['sources']:
        label = s['title'] or s['filename']
        if s['creator']: label += ' — ' + s['creator']
        lines.append(f"- [{label}]({s['url']})" if s['url'] else f'- {label}')
    lines += ['', '## Provenance', '',
              f"Knowledge revision `{manifest['ir_hash'][:16]}…` over source revision `{manifest['corpus_id'][7:23]}…`, "
              f"built with Lectic {manifest['lectic_version']}. "
              + ('Full source text is included.' if manifest['sources_included'] else
                 'Sources are not included: installing retrieves them on your own network and verifies them against this pack.'),
              '', manifest['share_note'], '']
    return '\n'.join(lines)


# ---------------------------------------------------------------- read

def fetch(location):
    """A local file or an https link, bounded in size."""
    if re.match(r'https?://', str(location)):
        require(urlsplit(location).scheme == 'https' or urlsplit(location).hostname in {'localhost', '127.0.0.1'}, 'Packs are fetched over https')
        with urllib.request.urlopen(urllib.request.Request(location, headers={'User-Agent': 'lectic/' + VERSION}), timeout=60) as response:
            raw = response.read(MAX_PACK_BYTES + 1)
    else:
        path = Path(location).expanduser().resolve()
        require(path.is_file(), 'No such pack: ' + str(path))
        raw = path.read_bytes()
    require(len(raw) <= MAX_PACK_BYTES, 'Pack exceeds the supported size')
    return raw


def open_pack(raw):
    """Verify the archive is safe and self-consistent before anything is read from it."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise Invalid('Not a Lectic pack (not a zip archive)') from exc
    members = {}
    for info in archive.infolist():
        name = info.filename
        require(not name.startswith('/') and '\\' not in name and '..' not in name.split('/') and ':' not in name and not info.is_dir(),
                'Pack contains an unsafe path: ' + name)
        require(info.file_size <= MAX_MEMBER_BYTES, 'Pack member exceeds the supported size: ' + name)
        members[name] = archive.read(name)
    require('pack.json' in members, 'Not a Lectic pack (no pack.json)')
    manifest = json.loads(members['pack.json'].decode('utf-8'))
    validate_schema(manifest, 'pack')
    require(set(manifest['files']) == set(members) - {'pack.json'}, 'Pack file inventory differs from its manifest')
    for path, expected in manifest['files'].items():
        require(digest(members[path]) == expected, 'Pack file was altered: ' + path)
    identity = 'pack-' + fingerprint({k: v for k, v in manifest.items() if k not in {'pack_id', 'created_at', 'publisher'}})[:24]
    require(manifest['pack_id'] == identity, 'Pack identity does not match its contents')
    return manifest, members


def inspect_pack(location):
    manifest, members = open_pack(fetch(location))
    from identity import check_manifest_signature
    sig_status, sig_msg = check_manifest_signature(manifest)
    res = {'phase': 'pack', 'name': manifest['name'], 'pack_id': manifest['pack_id'], 'created_at': manifest['created_at'],
           'version': manifest.get('version'), 'distribution': manifest.get('distribution'),
           'units': manifest['unit_count'], 'sources': [{k: s[k] for k in ('title', 'creator', 'url')} for s in manifest['sources']],
           'sources_included': manifest['sources_included'], 'methods': manifest['methods'], 'maps': manifest['maps'],
           'publisher_status': sig_status, 'publisher_info': sig_msg,
           'readme': members['README.md'].decode('utf-8')}
    if 'INSTALL.md' in members:
        res['install_md'] = members['INSTALL.md'].decode('utf-8')
    return res


# ---------------------------------------------------------------- install

def retrieve_source(source, members, manifest, home, retriever=None):
    """Bytes for one source: from the pack when included, else from the link on this network."""
    if manifest['sources_included']:
        raw = members['sources/raw/' + source['source_id'] + Path(source['filename']).suffix.lower()]
    else:
        require(source['url'], 'no link to retrieve it from')
        from linked_sources import resolver_for, retrieve
        adapter = resolver_for(source['url'])
        require(adapter is not None, 'no retriever for this link')
        acquired = (retriever or retrieve)(adapter, home / 'capture', LocalStore(home))
        record = next((r for r in acquired.records if r.filename == source['filename']), None)
        require(record is not None, 'retrieved captions do not match the pack (different caption track)')
        raw = record.raw
    require(digest(raw) == source['content_hash'], 'content differs from the pack (the source changed since it was packed)')
    return raw


def install_pack(project, location, name=None, retriever=None, pin=False, collection_id=None):
    project = Path(project).resolve(); home = storage_root(project); library = Library(project)
    manifest, members = open_pack(fetch(location))
    target_cid = collection_id
    if target_cid:
        resolved = library.resolve(target_cid)
        require(resolved is not None, f"Collection '{target_cid}' not found")
        _, existing_data = resolved
        name = existing_data['name']
    else:
        name = name or manifest.get('distribution', {}).get('install_name') or manifest['name']
        taken = {c['name'].casefold() for c in library.index['collections']}
        if name.casefold() in taken:
            base, n = name, 2
            while name.casefold() in taken: name = f'{base} ({n})'; n += 1
    ir = json.loads(members['knowledge/ir.json'].decode('utf-8'))
    parts = {}
    for path, raw in members.items():
        if path.startswith('knowledge/units/'): parts[path[len('knowledge/units/'):-5]] = json.loads(raw.decode('utf-8'))
    require(set(parts) == {s['source_id'] for s in manifest['sources']}, 'Pack checkpoints do not cover its sources')
    available, unavailable = {}, {}
    for source in manifest['sources']:
        try:
            available[source['source_id']] = retrieve_source(source, members, manifest, home, retriever)
        except (Invalid, ValueError, OSError, KeyError) as exc:
            unavailable[source['source_id']] = str(exc)
    labels = {s['source_id']: s['title'] or s['filename'] for s in manifest['sources']}
    require(available, 'None of the pack\'s sources could be obtained on this machine, so its knowledge cannot be verified here. '
            + '; '.join(f'{labels[sid]}: {reason}' for sid, reason in unavailable.items()))
    home.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.install-', dir=str(home)))
    try:
        run = staging / 'run'; (run / 'units').mkdir(parents=True)
        docs, entries = {}, []
        for source in manifest['sources']:
            sid = source['source_id']
            if sid not in available: continue
            raw = available[sid]; suffix = Path(source['filename']).suffix.lower()
            doc = {'schema_version': VERSION, 'source_id': sid, 'filename': source['filename'], 'title': source['title'],
                   'creator': source['creator'], 'url': source['url'], 'caption_type': source['caption_type'],
                   'content_hash': source['content_hash'], 'raw_path': f'raw/{sid}{suffix}', 'segments': normalize(raw, suffix)}
            require(fingerprint(doc) == source['document_hash'], 'Rebuilt source differs from the pack: ' + source['filename'])
            write(run / f'sources/{sid}.json', doc)
            LocalStore(home).materialize(LocalStore(home).put_blob(raw), run / doc['raw_path'])
            docs[sid] = doc; entries.append({'source_id': sid, 'path': f'sources/{sid}.json', 'document_hash': source['document_hash']})
        corpus = {'schema_version': VERSION, 'sources': entries, 'corpus_id': 'corpus-' + fingerprint(entries)}
        write(run / 'corpus.json', corpus)
        _, docs, segments = validate_sources(run)
        # Keep every unit whose evidence and relations survive; drop the rest and everything that leans on it.
        kept = {}
        for sid in docs:
            for unit in parts[sid]['units']:
                try: validate_units([unit], docs, segments, check_relations=False); kept[unit['unit_id']] = unit
                except Invalid: pass
        while True:
            invalid = {uid for uid, u in kept.items() if any(r['target'] not in kept for r in u['relations'])}
            if not invalid: break
            for uid in invalid: kept.pop(uid)
        for sid in docs:
            part = parts[sid]
            units = [u for u in part['units'] if u['unit_id'] in kept]
            note = part['note'] if (units or part['note'].strip()) else 'Units from this source could not be verified against the retrieved copy.'
            write(run / f'units/{sid}.json', {'schema_version': VERSION, 'corpus_id': corpus['corpus_id'], 'source_id': sid, 'note': note, 'units': units})
        packed_ids = {u['unit_id'] for u in ir['units']}
        dropped = sorted(packed_ids - set(kept))
        complete = not unavailable and not dropped and 'knowledge/reconciliation.json' in members
        if complete:
            # The author's cross-source review still applies: the checkpoints are byte-for-byte theirs, re-bound to this corpus.
            checkpoints = [read(run / f'units/{sid}.json') for sid in sorted(docs)]
            write(run / 'reconciliation.json', {'schema_version': VERSION, 'checkpoint_hash': fingerprint(checkpoints)})
        installed_ir = assemble(run)
        if target_cid:
            folder, data = library.archive(adopt=run, collection=target_cid, name=name)
        else:
            folder, data = library.archive(adopt=run, name=name)
        for path, raw in members.items():
            if path.startswith(('maps/', 'methods/')) or path in {'README.md', 'INSTALL.md'}:
                target = safe_child(folder / 'pack', path); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        from identity import check_manifest_signature
        sig_status, sig_msg = check_manifest_signature(manifest)
        is_pinned = bool(pin)
        pack_version = manifest.get('version')
        report = {'phase': 'installed', 'collection': name, 'collection_id': data['collection_id'], 'pack_id': manifest['pack_id'],
                  'version': pack_version, 'pinned': is_pinned, 'pinned_version': pack_version if is_pinned else None,
                  'distribution': manifest.get('distribution'),
                  'verification': 'verified' if complete else 'partial',
                  'sources_verified': len(available), 'sources_total': len(manifest['sources']),
                  'sources_unavailable': [{'source': labels[sid], 'reason': reason} for sid, reason in unavailable.items()],
                  'units_installed': len(installed_ir['units']), 'units_in_pack': manifest['unit_count'], 'units_dropped': dropped,
                  'knowledge_matches_pack': fingerprint(installed_ir) == manifest['ir_hash'],
                  'reconciliation': 'carried from the pack' if complete else 'needed before goal work: sources or units differ from the pack',
                  'publisher_status': sig_status, 'publisher_info': sig_msg,
                  'readable': str(folder / 'pack' / 'README.md'), 'methods': manifest['methods'], 'installed_at': datetime.now(timezone.utc).isoformat()}
        origin_record = {
            'location': str(location),
            'source_url': str(location) if re.match(r'https?://', str(location)) else None,
            'version': pack_version,
            'pinned': is_pinned,
            'pinned_version': pack_version if is_pinned else None,
            'distribution': manifest.get('distribution'),
            'manifest': {k: v for k, v in manifest.items() if k != 'files'},
            'install': report
        }
        write(folder / 'pack-origin.json', origin_record)
        return report
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# ---------------------------------------------------------------- update

def update_pack(project, collection_name_or_id, force=False, retriever=None):
    project = Path(project).resolve(); library = Library(project)
    resolved = library.resolve(collection_name_or_id)
    require(resolved is not None, f"Collection '{collection_name_or_id}' not found")
    folder, data = resolved
    origin_path = folder / 'pack-origin.json'
    require(origin_path.is_file(), f"Collection '{data['name']}' was not installed from a pack")
    origin = read(origin_path)
    source_location = origin.get('source_url') or origin.get('location')
    require(source_location, f"Collection '{data['name']}' has no recorded origin location")

    candidate_location = source_location
    if re.search(r'github\.com/[^/]+/[^/]+/releases/download/', str(source_location)):
        candidate_location = re.sub(r'releases/download/[^/]+/', 'releases/latest/download/', str(source_location))

    try:
        raw = fetch(candidate_location)
    except Exception:
        raw = fetch(source_location)
        candidate_location = source_location

    manifest, members = open_pack(raw)
    remote_version = manifest.get('version', '')
    current_version = origin.get('version', '')
    is_pinned = origin.get('pinned', False)

    run = library.run(folder, data)
    current_ir = read(run / 'ir.json') if (run / 'ir.json').is_file() else {'units': []}
    new_ir = json.loads(members['knowledge/ir.json'].decode('utf-8'))

    current_units = {u['unit_id']: u for u in current_ir.get('units', [])}
    new_units = {u['unit_id']: u for u in new_ir.get('units', [])}
    added_ids = set(new_units) - set(current_units)
    removed_ids = set(current_units) - set(new_units)
    common_ids = set(current_units) & set(new_units)
    modified_ids = {uid for uid in common_ids if fingerprint(new_units[uid]) != fingerprint(current_units[uid])}

    if not force and not added_ids and not removed_ids and not modified_ids and (current_version == remote_version):
        return {
            'phase': 'up_to_date',
            'collection': data['name'],
            'version': current_version,
            'message': f"Collection '{data['name']}' is already up to date at version {current_version or 'unknown'}."
        }

    report = install_pack(project, candidate_location, name=data['name'], retriever=retriever, pin=is_pinned, collection_id=data['collection_id'])

    parts = []
    if added_ids:
        unit_types = {new_units[uid].get('type', 'convention') for uid in added_ids}
        noun = unit_types.pop() if len(unit_types) == 1 else 'unit'
        parts.append(f"{len(added_ids)} new {noun}{'s' if len(added_ids) != 1 else ''} added")
    if modified_ids:
        parts.append(f"{len(modified_ids)} modified")
    if removed_ids:
        parts.append(f"{len(removed_ids)} removed")
    diff_str = ', '.join(parts) if parts else 'knowledge refreshed'
    summary_msg = f"Updated {data['name']} from {current_version or 'initial'} to {remote_version or 'latest'} — {diff_str}"

    report['update'] = {
        'phase': 'updated',
        'from_version': current_version,
        'to_version': remote_version,
        'added': len(added_ids),
        'modified': len(modified_ids),
        'removed': len(removed_ids),
        'message': summary_msg
    }
    report['summary_message'] = summary_msg
    return report
