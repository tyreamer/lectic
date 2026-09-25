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

from ec import Invalid, require, safe_child
from home import storage_root


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
            'match_reason': top_cand['reason'] if top_cand else 'No strong candidate match',
            'candidates': cand.get('candidates', []),
            'suggested_action': cand.get('suggested_action', 'ask_user')
        })

    return {
        'inbox_folder': str(folder),
        'count': len(items),
        'items': items
    }


def route_inbox_item(project, filename_or_path, collection_name=None):
    """Route a single inbox item into a collection and move it to .processed."""
    folder = ensure_inbox_folder(project)
    p = Path(filename_or_path)
    if not p.is_file():
        p = folder / filename_or_path
    require(p.is_file(), f"Inbox item not found: {filename_or_path}")

    parsed = parse_drop_file(p)
    target_col = collection_name
    if not target_col:
        # Match candidate collection
        from candidate_collections import find_candidate_collections
        cand = find_candidate_collections(
            project,
            url=parsed['url'],
            text=parsed['text'],
            title=parsed['title'],
            files=parsed['files']
        )
        if cand.get('candidates'):
            target_col = cand['candidates'][0]['name']
        else:
            target_col = 'Inbox'

    # Save capture directly into the target collection
    from capture_write import save_capture
    from capture_store import CaptureStore
    store = CaptureStore(project)
    staging = storage_root(project) / 'capture-drop'
    record = save_capture(
        staging,
        url=parsed['url'],
        text=parsed['text'],
        files=parsed['files'],
        title=parsed['title'],
        collections=[target_col],
        note=f"Captured from Lectic Drop Inbox: {p.name}",
        origin='drop-inbox'
    )
    import_report = store.import_folder(staging)

    # Move processed drop file to .processed/
    processed_dir = folder / '.processed'
    processed_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dest = processed_dir / f"{ts}_{p.name}"
    try:
        shutil.move(str(p), str(dest))
    except Exception:
        pass

    return {
        'phase': 'routed',
        'file': p.name,
        'collection': target_col,
        'url': parsed['url'],
        'title': parsed['title'],
        'archived_to': str(dest)
    }


def route_all_inbox(project=None, mapping=None):
    """Route all items in the inbox folder according to mapping or candidate matches."""
    folder = ensure_inbox_folder(project)
    mapping = mapping or {}
    report = scan_inbox(project)
    results = []

    for item in report['items']:
        fn = item['filename']
        target = mapping.get(fn) or item.get('suggested_collection') or 'Inbox'
        res = route_inbox_item(project, fn, collection_name=target)
        results.append(res)

    return {
        'phase': 'inbox_processed',
        'folder': str(folder),
        'processed_count': len(results),
        'items': results
    }
