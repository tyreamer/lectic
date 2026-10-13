"""Import an old project library into the shared home without deleting either copy."""
from datetime import datetime, timezone
from pathlib import Path

from ec import fingerprint, read, require, write
from home import LEGACY_DIRNAME, LEGACY_MARKERS, session_path, storage_root
from home_archive import archive_home, merge_archive


def centralize(project='.', source=None):
    project = Path(project).resolve()
    destination = storage_root(project)
    source = Path(source).expanduser().resolve() if source else project / LEGACY_DIRNAME
    if not source.is_dir() or not any((source / marker).exists() for marker in LEGACY_MARKERS):
        return {'phase': 'already_centralized', 'home': str(destination)}
    require(source != destination, 'That library is already the central home')
    raw = archive_home(source)
    backups = destination / 'backups'
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    archive = backups / f'project-import-{fingerprint(str(source))[:12]}-{stamp}.waykit-home'
    archive.write_bytes(raw)
    report = merge_archive(project, raw, home=destination)
    session_imported = False
    previous_session = source / 'session.json'
    current_session = session_path(destination, project)
    if previous_session.is_file() and not current_session.exists():
        # Preserve this project's resume pointer without importing machine secrets.
        write(current_session, read(previous_session))
        session_imported = True
    return {**report, 'phase': 'centralized', 'source': str(source), 'home': str(destination),
            'backup': str(archive), 'original_preserved': True, 'session_imported': session_imported}
