"""Opt-in Lectic skill updates. Standalone stdlib runner; never opens project data."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
from urllib.request import Request, urlopen
import uuid
import zipfile


REPOSITORY = 'tyreamer/lectic'
REF = 'main'
# Same clean payload as install_skill.py; installed receipts/backups live outside it.
PAYLOAD = ['SKILL.md', 'LICENSE', 'README.md', 'DESIGN.md', 'agents', 'scripts',
           'schemas', 'prompts', 'fixtures', 'docs']
OPTIONAL = ['NORTH_STAR.md']
LIMIT = 32 * 1024 * 1024


class UpdateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise UpdateError(message)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    """Replace metadata on the same volume, without leaving partial JSON."""
    path = Path(path)
    temp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def ordinary(path):
    """Reject symlinks and Windows junctions before resolving any managed path."""
    path = Path(path).expanduser().absolute()
    for part in [path, *path.parents]:
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not
                    (getattr(info, 'st_file_attributes', 0) & 0x400),
                    f'Linked paths are not supported by the updater: {part}')
    return path.resolve()


def locations(destination, state_dir=None):
    dest = ordinary(destination)
    require(dest.name == 'expertise-compiler', 'Skill folder must be named expertise-compiler')
    state = ordinary(state_dir or dest.parent.parent / 'lectic-updates' / dest.name)
    require(not state.is_relative_to(dest.parent) and not dest.is_relative_to(state),
            'Update state and backups must live outside the skills directory')
    return dest, state


def inventory(folder):
    result = {}
    require(folder.is_dir(), f'Installation is missing: {folder}')
    require(not any((folder / name).exists() for name in ('.git', '.expertise-compiler', 'workspace')),
            'This folder contains a checkout or project data; manage only a dedicated installed skill')
    for path in folder.rglob('*'):
        ordinary(path)
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'}:
            result[path.relative_to(folder).as_posix()] = sha(path.read_bytes())
    return result


def validate_candidate(folder):
    for name in PAYLOAD:
        require((folder / name).exists(), f'Incomplete update: missing {name}')
    skill = (folder / 'SKILL.md').read_text(encoding='utf-8')
    require(skill.startswith('---\n') and '\n---' in skill[4:], 'Missing skill metadata')
    header = skill[4:].split('\n---', 1)[0]
    require(re.search(r'^name: expertise-compiler\s*$', header, re.M) and
            re.search(r'^description: \S', header, re.M), 'Unexpected skill identity or description')
    for path in folder.rglob('*'):
        if path.suffix == '.py':
            compile(path.read_bytes(), str(path), 'exec')  # Parse, never execute downloaded code here.
        elif path.suffix == '.json':
            read(path)
    require((folder / 'scripts/update_skill.py').is_file(), 'Update runner is missing')
    return inventory(folder)


def download(url, limit=LIMIT):
    request = Request(url, headers={'User-Agent': 'Lectic-Skill-Updater/1', 'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=30) as response:
        require(response.geturl().startswith(('https://api.github.com/', 'https://codeload.github.com/')),
                'Unexpected download host')
        data = response.read(limit + 1)
    require(len(data) <= limit, 'Update download exceeds size limit')
    return data


def latest_commit():
    commit = json.loads(download(f'https://api.github.com/repos/{REPOSITORY}/commits/{REF}', 1024 * 1024))['sha']
    require(isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit), 'Invalid GitHub commit')
    return commit


def unpack(data, commit, folder):
    """Read only the allowed payload from an immutable commit archive."""
    prefix = f'lectic-{commit}'
    seen = set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        require(len(entries) <= 10000 and sum(i.file_size for i in entries) <= LIMIT * 2,
                'Update archive exceeds size limit')
        for entry in entries:
            path = PurePosixPath(entry.filename)
            require(path.parts and path.parts[0] == prefix and not path.is_absolute() and
                    '\\' not in entry.filename and ':' not in entry.filename and
                    '..' not in path.parts and not stat.S_ISLNK(entry.external_attr >> 16),
                    'Unsafe update archive path')
            require(all(p and not p.endswith((' ', '.')) and not re.search(r'[<>"|?*\x00-\x1f]', p)
                        and p.split('.')[0].upper() not in
                        {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(10)], *[f'LPT{i}' for i in range(10)]}
                        for p in path.parts), 'Unsupported archive filename')
            key = path.as_posix().casefold()
            require(key not in seen, 'Duplicate archive path')
            seen.add(key)
            if len(path.parts) < 2 or path.parts[1] not in PAYLOAD + OPTIONAL or entry.is_dir():
                continue
            target = folder.joinpath(*path.parts[1:])
            require(target.resolve().is_relative_to(folder.resolve()), 'Archive escaped staging folder')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
    return validate_candidate(folder)


@contextmanager
def locked(state):
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'update.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise UpdateError('Another Lectic update is running') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def load_state(dest, state):
    value = read(state / 'state.json')
    require(value['schema_version'] == '1.0' and value['destination'] == str(dest) and
            value['repository'] == REPOSITORY and value['ref'] == REF, 'Update receipt does not match installation')
    return value


def install_runner(dest, state):
    target = state / 'runner.py'
    temp = state / 'runner.tmp'
    temp.write_bytes((dest / 'scripts/update_skill.py').read_bytes())
    os.replace(temp, target)


def recover(dest, state):
    """Finish a committed swap or restore the old directory after interruption."""
    journal = state / 'transaction.json'
    if not journal.exists():
        return
    tx = read(journal)
    require(tx['next_state']['destination'] == str(dest), 'Unexpected update transaction')
    backup, stage = ordinary(tx['backup']), ordinary(tx['stage'])
    require(backup.parent == state / 'backups' and stage.parent == dest.parent and
            stage.name.startswith('.lectic-stage-'), 'Unexpected transaction paths')
    if dest.exists() and inventory(dest) == tx['next_state']['files']:
        write(state / 'state.json', tx['next_state'])
        install_runner(dest, state)
    elif not dest.exists() and backup.exists():
        os.replace(backup, dest)
    else:
        prior = load_state(dest, state)
        require(dest.exists() and inventory(dest) == prior['files'],
                'Interrupted update needs inspection; existing files were preserved')
    if stage.exists():
        shutil.rmtree(stage)  # Validated direct staging child, never a computed user-data path.
    journal.unlink()


def replace_install(dest, state, current, stage, commit, files):
    """Two directory renames with a recovery journal; backups are never pruned."""
    require(inventory(dest) == current['files'], 'Installed files changed during download; update paused')
    backup = state / 'backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8])
    backup.parent.mkdir(exist_ok=True)
    write(backup.with_suffix('.receipt.json'), current)
    next_state = dict(current, installed_commit=commit, files=files, last_success=timestamp(),
                      last_result='updated', message='Installed the published Lectic revision',
                      backups=[*current.get('backups', []), {'path': str(backup),
                               'commit': current.get('installed_commit'), 'created_at': timestamp()}])
    write(state / 'transaction.json', {'backup': str(backup), 'stage': str(stage), 'next_state': next_state})
    try:
        os.replace(dest, backup)
        os.replace(stage, dest)
    except OSError:
        recover(dest, state)
        raise
    recover(dest, state)
    return next_state


def status(dest, state):
    if not (state / 'state.json').exists():
        return {'status': 'unmanaged', 'destination': str(dest), 'automatic_updates': False}
    value = load_state(dest, state)
    actual = inventory(dest) if dest.exists() else {}
    changes = sorted(k for k in actual.keys() | value['files'].keys() if actual.get(k) != value['files'].get(k))
    return {k: v for k, v in value.items() if k != 'files'} | {
        'status': 'local_changes' if changes else 'managed', 'changed_files': changes,
        'recovery_pending': (state / 'transaction.json').exists(), 'state_directory': str(state)}


def operate(action, destination, state_dir=None, adopt=False, interval=24, task_name=None):
    dest, state = locations(destination, state_dir)
    if action == 'status':
        return status(dest, state)
    require(dest.is_dir() or (state / 'transaction.json').exists(),
            'Install Lectic first; the updater only manages an existing installation')
    with locked(state):
        recover(dest, state)
        if not (state / 'state.json').exists():
            require(action == 'update' and adopt,
                    'Unmanaged installation: use update --adopt once to back it up and enroll it')
            current = {'schema_version': '1.0', 'destination': str(dest), 'repository': REPOSITORY,
                       'ref': REF, 'installed_commit': None, 'files': inventory(dest), 'backups': [],
                       'automatic_updates': False, 'interval_hours': 24, 'last_check': None}
            write(state / 'state.json', current)
        current = load_state(dest, state)
        if action in {'enable', 'pause'}:
            require(current.get('installed_commit'), 'Update this installation before enabling a schedule')
            require(1 <= interval <= 24 * 30, 'Check interval must be between 1 and 720 hours')
            current['automatic_updates'] = action == 'enable'
            if action == 'enable':
                require(inventory(dest) == current['files'], 'Review local edits before enabling updates')
                install_runner(dest, state)
                current['interval_hours'] = interval
                if task_name:
                    current['task_name'] = task_name
            write(state / 'state.json', current)
            return status(dest, state)
        if action == 'run':
            if not current['automatic_updates']:
                return {'status': 'paused'}
            if current['last_check'] and datetime.now(timezone.utc) < (
                    datetime.fromisoformat(current['last_check']) + timedelta(hours=current['interval_hours'])):
                return {'status': 'not_due'}
        require(action in {'update', 'run'}, 'Unknown update action')
        current['last_check'] = timestamp()
        stage = None
        try:
            require(inventory(dest) == current['files'],
                    'Local edits detected; restore or review them before updating. No installed files were replaced.')
            commit = latest_commit()
            current['last_seen_commit'] = commit
            if commit == current.get('installed_commit'):
                current.update(last_result='current', message='Already at the published revision')
                write(state / 'state.json', current)
                install_runner(dest, state)
                return status(dest, state)
            stage = Path(tempfile.mkdtemp(prefix='.lectic-stage-', dir=dest.parent)).resolve()
            data = download(f'https://codeload.github.com/{REPOSITORY}/zip/{commit}')
            files = unpack(data, commit, stage)
            current = replace_install(dest, state, current, stage, commit, files)
            return status(dest, state)
        except Exception as exc:
            # A successful directory swap may precede a receipt write failure. Keep
            # its journal so the independent runner can finalize it on the next try.
            current.update(last_result='needs_attention', message=str(exc))
            write(state / 'state.json', current)
            raise
        finally:
            if stage is not None and stage.exists() and not (state / 'transaction.json').exists():
                require(ordinary(stage).parent == dest.parent and stage.name.startswith('.lectic-stage-'),
                        'Unexpected staging path')
                shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'update', 'run', 'enable', 'pause'])
    parser.add_argument('--dest', required=True)
    parser.add_argument('--state-dir')
    parser.add_argument('--adopt', action='store_true', help='Enroll an existing copy, preserving it in a backup')
    parser.add_argument('--interval-hours', type=int, default=24)
    parser.add_argument('--task-name', help='Receipt label only; schedule creation is a separate OS operation')
    args = parser.parse_args()
    try:
        result = operate(args.action, args.dest, args.state_dir, args.adopt, args.interval_hours, args.task_name)
    except Exception as exc:
        if sys.stderr is not None:
            print(f'Lectic update: {exc}', file=sys.stderr)
        return 1
    if sys.stdout is not None:
        print(json.dumps(result, indent=2))  # ASCII transport also works in legacy Windows shells.
    return 0


if __name__ == '__main__':
    sys.exit(main())
