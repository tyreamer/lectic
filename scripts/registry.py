"""Lectic Expertise Marketplace Registry: discover, inspect, and install packs by name."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import urllib.request
import urllib.error

from ec import ROOT, VERSION, Invalid, digest, require, safe_child, validate_schema, write
from home import storage_root
from packs import inspect_pack, slug

REGISTRY_DEFAULT_URL = 'https://raw.githubusercontent.com/tyreamer/lectic/main/registry/index.json'
CACHE_TTL_SECONDS = 3600


def get_registry_url():
    return os.environ.get('LECTIC_REGISTRY_URL') or REGISTRY_DEFAULT_URL


def fetch_registry(project=None, refresh=False):
    """Fetch the registry index, using local cache when fresh, falling back to bundled index if offline."""
    bundled = ROOT / 'registry/index.json'
    if not os.environ.get('LECTIC_REGISTRY_URL') and not refresh:
        data = json.loads(bundled.read_text(encoding='utf-8'))
        validate_schema(data, 'registry')
        return data
    home = storage_root(Path(project).resolve() if project else Path.cwd())
    cache_path = home / 'registry-cache.json'

    # Check cache if not forcing refresh
    if not refresh and not os.environ.get('LECTIC_REGISTRY_URL') and cache_path.is_file():
        try:
            cached_data = json.loads(cache_path.read_text(encoding='utf-8'))
            cache_time = cache_path.stat().st_mtime
            if (datetime.now().timestamp() - cache_time) < CACHE_TTL_SECONDS:
                validate_schema(cached_data, 'registry')
                return cached_data
        except Exception:
            pass

    url = get_registry_url()
    registry_data = None
    fetch_error = None

    try:
        req = urllib.request.Request(url, headers={'User-Agent': f'lectic/{VERSION}'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read(2 * 1024 * 1024 + 1)
            require(len(raw) <= 2 * 1024 * 1024, 'Registry is too large')
            registry_data = json.loads(raw.decode('utf-8'))
    except Exception as exc:
        fetch_error = exc

    # Fallback to local file in repo if fetch failed
    if registry_data is None and not os.environ.get('LECTIC_REGISTRY_URL'):
        local_bundled = ROOT / 'registry/index.json'
        if local_bundled.is_file():
            try:
                registry_data = json.loads(local_bundled.read_text(encoding='utf-8'))
            except Exception:
                pass

    # Fallback to stale cache if available
    if registry_data is None and not os.environ.get('LECTIC_REGISTRY_URL') and cache_path.is_file():
        try:
            registry_data = json.loads(cache_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    require(registry_data is not None, f"Could not load Lectic registry from {url}: {fetch_error}")

    validate_schema(registry_data, 'registry')

    # Update cache
    try:
        home.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(registry_data, indent=2) + '\n', encoding='utf-8')
    except Exception:
        pass

    return registry_data


def search_registry(query=None, project=None, tag=None):
    """Search for packs matching query or tag."""
    registry = fetch_registry(project=project)
    packs = registry.get('packs', [])
    results = []

    q = str(query).strip().lower() if query else ''
    t = str(tag).strip().lower() if tag else ''

    for pack in packs:
        if t:
            pack_tags = [item.lower() for item in pack.get('tags', [])]
            if t not in pack_tags:
                continue

        if q:
            name = pack.get('name', '').lower()
            title = pack.get('title', '').lower()
            desc = pack.get('description', '').lower()
            pub = pack.get('publisher', '').lower()
            pack_tags = ' '.join(pack.get('tags', [])).lower()

            haystack = f"{name} {title} {desc} {pub} {pack_tags}"
            if q not in haystack:
                continue

        results.append(pack)

    return results


def resolve_registry_pack(pack_spec, project=None):
    """Resolve a 'registry:NAME' or 'NAME' spec to a pack entry."""
    spec = str(pack_spec).strip()
    if spec.lower().startswith('registry:'):
        spec = spec[len('registry:'):].strip()

    registry = fetch_registry(project=project)
    packs = registry.get('packs', [])

    match = next((p for p in packs if p.get('name', '').casefold() == spec.casefold()), None)
    if not match:
        available = ', '.join(p.get('name', '') for p in packs[:8])
        raise Invalid(f"Pack '{spec}' not found in registry. Run `lectic search` to explore available packs ({available}...)")

    return match


def inspect_registry_pack(pack_spec, project=None):
    """Inspect a pack directly from the registry without installing."""
    entry = resolve_registry_pack(pack_spec, project=project)
    raw_inspect = inspect_pack(registry_pack_location(entry, project))
    raw_inspect['registry_entry'] = entry
    raw_inspect['install_command'] = f"lectic install registry:{entry['name']} --as {entry.get('install_name', entry['name'])} --pin"
    return raw_inspect


def registry_pack_location(entry, project=None):
    """Resolve and validate actual pack bytes; never substitute catalog metadata."""
    from packs import fetch, open_pack
    expected = entry.get('sha256')
    if entry.get('bundled_path'):
        candidate = safe_child(ROOT / 'fixtures/packs', entry['bundled_path'])
        require(candidate.is_file(), 'Bundled catalog artifact is missing; reinstall Lectic')
        raw = candidate.read_bytes()
        require(expected and digest(raw) == expected, 'Bundled pack checksum differs from the catalog')
        open_pack(raw)
        return str(candidate)
    raw = fetch(entry['url'])
    require(not expected or digest(raw) == expected, 'Pack checksum differs from the registry')
    open_pack(raw)
    cache = storage_root(project or '.') / 'registry-packs' / (digest(raw) + '.lectic')
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists(): cache.write_bytes(raw)
    require(digest(cache.read_bytes()) == digest(raw), 'Cached pack was altered')
    return str(cache)


def format_search_results(packs, query=None):
    """Format registry search results for CLI display."""
    if not packs:
        msg = f"No packs found matching '{query}'." if query else "Registry is currently empty."
        return msg + "\nRun `lectic search` to view all packs, or `lectic publish NAME --registry` to submit one."

    lines = [f"Lectic Registry ({len(packs)} pack{'s' if len(packs) != 1 else ''} available):\n"]
    for p in packs:
        ver = f"v{p.get('version', '1.0')}"
        pub = p.get('publisher', 'Unknown')
        tags = ', '.join(p.get('tags', []))
        install_as = p.get('install_name') or p.get('name')
        cmd = f"lectic install registry:{p['name']} --as {install_as} --pin"

        lines.append(f"  {p['name']}  {ver}  by {pub}")
        lines.append(f"    {p.get('description', '')}")
        if tags:
            lines.append(f"    Tags: {tags}")
        lines.append(f"    Install: {cmd}\n")

    return '\n'.join(lines)


def format_inspect_report(info):
    """Format an inspect report for CLI display."""
    entry = info.get('registry_entry', {})
    sources_count = len(info.get('sources', []))
    sources_str = f" from {sources_count} source{'s' if sources_count != 1 else ''}" if sources_count else ""
    lines = [
        f"Pack:        {info['name']}" + (f" (v{info.get('version')})" if info.get('version') else ""),
        f"Publisher:   {info['publisher_info']}",
        f"Description: {entry.get('description', 'Evidence-backed knowledge pack')}",
        f"Knowledge:   {info.get('units', 0)} units{sources_str}",
    ]
    if info.get('methods'):
        method_names = ', '.join(m['title'] if isinstance(m, dict) else str(m) for m in info['methods'])
        lines.append(f"Methods:     {method_names}")

    cmd = info.get('install_command') or f"lectic install {info.get('name', 'pack')}"
    lines.append(f"Install:     {cmd}")
    if info.get('readme'):
        lines.append("\n---\n")
        lines.append(info.get('readme', ''))
    return '\n'.join(lines)


def prepare_registry_entry(project, pack_name_or_file, download_url, tags=None, install_name=None):
    """Prepare a valid JSON entry ready to be added to registry/index.json."""
    pack_path = Path(pack_name_or_file)
    if not pack_path.is_file():
        pack_path = Path(project) / (slug(pack_name_or_file) + '.lectic')

    require(pack_path.is_file(), f"Pack file not found: {pack_path}")
    from packs import open_pack
    manifest, members = open_pack(pack_path.read_bytes())

    from identity import check_manifest_signature
    require(check_manifest_signature(manifest)[0] == 'signed', "Registry submission requires a signed pack. Run `lectic identity set 'Name' --contact email` and re-pack.")

    version = manifest.get('version') or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    p_name = slug(manifest['name'])
    p_install = install_name or manifest.get('distribution', {}).get('install_name') or p_name
    tag_list = [t.strip().lower() for t in tags] if tags else ["general"]

    methods = [m['title'] for m in manifest.get('methods', [])]

    return {
        'name': p_name,
        'title': manifest['name'],
        'description': f"Evidence-backed {manifest['name']} knowledge compiled with Lectic.",
        'publisher': manifest['publisher']['name'],
        'url': download_url,
        'sha256': digest(pack_path.read_bytes()),
        'install_name': p_install,
        'version': version,
        'units': manifest.get('unit_count', 0),
        'methods': methods,
        'tags': tag_list
    }
