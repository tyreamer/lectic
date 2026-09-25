"""Zero-daemon intake drop folder for Lectic.

Allows users to drop web links (.url, .webloc, .desktop), text notes,
transcripts, or files into a single folder without running a background server.
Whenever an assistant or CLI connects, it scans the folder, matches items against
existing collections, and routes them with confirmation.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import plistlib
import re
import shutil
from urllib.parse import urlparse

from ec import Invalid, require, safe_child, digest, read
from home import storage_root
from store import home_transaction


README_CONTENT = """Lectic Drop Inbox
=================
Drop web shortcuts, YouTube links, notes, or transcripts here anytime.
No server needs to be running.

Whenever you open Claude Code, Codex, or ChatGPT, your assistant will notice
the new items and ask which collection to add them to!
"""


def inbox_folder_path(project=None):
    """Resolve the user-facing Lectic Inbox folder."""
    env_dir = os.environ.get('LECTIC_INBOX_DIR')
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    # Check for cloud sync folders first for effortless phone-to-computer sync
    # 1. Windows OneDrive
    onedrive = os.environ.get('OneDrive') or os.environ.get('OneDriveConsumer')
    if onedrive and Path(onedrive).is_dir():
        od_docs = Path(onedrive) / 'Documents'
        target_dir = od_docs if od_docs.is_dir() else Path(onedrive)
        return (target_dir / 'Lectic Inbox').resolve()

    # 2. macOS iCloud Drive
    icloud = Path.home() / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'
    if icloud.is_dir():
        return (icloud / 'Lectic Inbox').resolve()

    # 3. Standard Documents or Home folder
    docs = Path.home() / 'Documents'
    if docs.is_dir():
        return (docs / 'Lectic Inbox').resolve()

    return (Path.home() / 'Lectic Inbox').resolve()


def ensure_inbox_folder(project=None):
    """Ensure the Lectic Inbox folder and its processed subfolder exist."""
    folder = inbox_folder_path(project)
    folder.mkdir(parents=True, exist_ok=True)
    processed = folder / '.processed'
    processed.mkdir(parents=True, exist_ok=True)

    readme = folder / '_README.txt'
    if not readme.exists():
        try:
            readme.write_text(README_CONTENT, encoding='utf-8')
        except Exception:
            pass

    return folder


def parse_drop_file(path):
    """Parse a dropped file into url, text, title, and attachments."""
    p = Path(path).resolve()
    suffix = p.suffix.lower()
    title = p.stem.replace('-', ' ').replace('_', ' ').strip()
    url = ''
    text = ''
    files = []

    if suffix == '.url':
        # Windows Internet Shortcut (INI format)
        try:
            raw = p.read_text(encoding='utf-8', errors='ignore')
            m = re.search(r'URL=(https?://[^\s\r\n]+)', raw, re.IGNORECASE)
            if m:
                url = m.group(1).strip()
        except Exception:
            pass

    elif suffix == '.webloc':
        # macOS Safari Bookmark (plist format)
        try:
            data = plistlib.loads(p.read_bytes())
            if isinstance(data, dict) and 'URL' in data:
                url = str(data['URL']).strip()
        except Exception:
            pass

    elif suffix == '.desktop':
        # Linux Desktop Entry
        try:
            raw = p.read_text(encoding='utf-8', errors='ignore')
            m = re.search(r'^URL=(https?://[^\s\r\n]+)', raw, re.IGNORECASE | re.MULTILINE)
            if m:
                url = m.group(1).strip()
        except Exception:
            pass

    elif suffix in ('.txt', '.md'):
        try:
            raw = p.read_text(encoding='utf-8', errors='ignore').strip()
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            if lines:
                first = lines[0]
                if re.match(r'^https?://[^\s]+$', first):
                    url = first
                    text = '\n'.join(lines[1:]).strip()
                else:
                    text = raw
                    links = re.findall(r'https?://[^\s<>"]+', raw)
                    if links:
                        url = links[0].rstrip('.,;:!?')
        except Exception:
            pass

    elif suffix in ('.vtt', '.srt'):
        # Direct transcript files
        files.append(str(p))

    else:
        # Generic attachment
        files.append(str(p))

    return {
        'file_name': p.name,
        'path': str(p),
        'title': title,
        'url': url,
        'text': text,
        'files': files
    }


def scan_inbox(project=None):
    """Scan the inbox folder for pending dropped items and match candidate collections."""
    folder = ensure_inbox_folder(project)
    project_path = Path(project).resolve() if project else Path.cwd()
    from candidate_collections import find_candidate_collections

    items = []
    # Find all top-level files (ignoring hidden files and _README)
    for p in sorted(folder.iterdir()):
        if p.is_dir() or p.name.startswith(('.', '_')):
            continue

        parsed = parse_drop_file(p)
        cand = find_candidate_collections(
            project_path,
            url=parsed['url'],
            text=parsed['text'],
            title=parsed['title'],
            files=parsed['files']
        )

        top_cand = cand['candidates'][0] if cand.get('candidates') else None
        items.append({
            'filename': p.name,
            'path': str(p),
            'title': parsed['title'],
            'url': parsed['url'],
            'text': parsed['text'],
            'files': parsed['files'],
            'suggested_collection': top_cand['name'] if top_cand else None,
            'confidence': top_cand['score'] if top_cand else 0,
            'match_reason': '; '.join(top_cand.get('reasons', [])) if top_cand else 'No strong candidate match',
            'candidates': cand.get('candidates', []),
            'suggested_action': cand.get('suggested_action', 'ask_user')
        })

    return {
        'inbox_folder': str(folder),
        'count': len(items),
        'items': items
    }


@home_transaction
def route_inbox_item(project, filename_or_path, collection_name=None):
    """Route a single inbox item into a collection and move it to .processed."""
    folder = ensure_inbox_folder(project)
    p = Path(filename_or_path)
    if not p.is_absolute():
        p = folder / p
    require(not p.is_symlink(), 'Inbox items cannot be symbolic links')
    p = p.resolve()
    require(p.parent == folder.resolve() and not p.name.startswith(('.', '_')), 'Select a file inside the drop inbox')
    require(p.is_file(), f"Inbox item not found: {filename_or_path}")

    parsed = parse_drop_file(p)
    target_col = collection_name or 'Inbox'

    # Save capture directly into the target collection
    from capture_write import save_capture
    from capture_store import CaptureStore
    store = CaptureStore(project)
    staging = storage_root(project) / 'capture-drop'
    original_bytes = p.read_bytes()
    # A retry after import or archive failure uses the same immutable event.
    token = digest((str(p) + str(p.stat().st_mtime_ns) + target_col).encode() + original_bytes)
    capture_id = 'capture-' + token[:32]
    existing = staging / (capture_id + '.json')
    captured_at = read(existing)['captured_at'] if existing.is_file() else None
    record = save_capture(
        staging,
        url=parsed['url'],
        text=parsed['text'],
        files=parsed['files'],
        title=parsed['title'],
        collections=[target_col],
        note=f"Captured from Lectic Drop Inbox: {p.name}",
        origin='drop-inbox', capture_id=capture_id, captured_at=captured_at
    )
    import_report = store.import_folder(staging)
    imported = next((item for item in import_report.get('items', []) if item.get('capture_id') == capture_id), None)
    if not imported or not imported.get('saved') or imported.get('issues'):
        return {'phase': 'needs_attention', 'file': p.name, 'collection': target_col,
                'capture_id': capture_id, 'issues': (imported or {}).get('issues') or
                ['Import did not confirm a complete save. The original remains in the inbox; retry after fixing the reported problem.'],
                'import_report': import_report}
    if p.read_bytes() != original_bytes:
        return {'phase': 'needs_attention', 'file': p.name, 'capture_id': capture_id,
                'issues': ['The file changed during capture. Its original remains in the inbox.']}

    # Move processed drop file to .processed/
    processed_dir = folder / '.processed'
    processed_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dest = processed_dir / f"{ts}_{capture_id}_{p.name}"
    try:
        shutil.move(str(p), str(dest))
    except OSError as exc:
        return {'phase': 'captured_pending_archive', 'file': p.name, 'collection': target_col,
                'capture_id': capture_id, 'issues': [f'Saved, but could not archive the original: {exc}. Retry safely.']}

    return {
        'phase': 'routed',
        'capture_id': capture_id,
        'file': p.name,
        'collection': target_col,
        'url': parsed['url'],
        'title': parsed['title'],
        'archived_to': str(dest)
    }


@home_transaction
def route_all_inbox(project=None, mapping=None):
    """Route all items in the inbox folder according to mapping or candidate matches."""
    folder = ensure_inbox_folder(project)
    report = scan_inbox(project)
    if mapping is not None:
        require(isinstance(mapping, dict), 'Items must map inbox filenames to collection names')
        require(set(mapping) <= {item['filename'] for item in report['items']}, 'One or more selected inbox items no longer exist')
    results = []

    for item in report['items']:
        fn = item['filename']
        if mapping is not None and fn not in mapping:
            continue
        target = (mapping or {}).get(fn) or 'Inbox'
        try:
            res = route_inbox_item(project, fn, collection_name=target)
        except (OSError, ValueError) as exc:
            res = {'phase': 'needs_attention', 'file': fn, 'issues': [str(exc)]}
        results.append(res)

    return {
        'phase': 'inbox_processed',
        'folder': str(folder),
        'processed_count': sum(item['phase'] == 'routed' for item in results),
        'needs_attention_count': sum(item['phase'] != 'routed' for item in results),
        'items': results
    }
