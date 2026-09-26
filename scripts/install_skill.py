"""Agent-operated clean local installation. No downloads, global config edits, or overwrites."""
import argparse
import shutil
import tempfile
from pathlib import Path
from ec import ROOT, Invalid, digest, require
from update_skill import SKILL_NAMES, UpdateError, installed_bytes

# A complete skill, including demo/acceptance data, without user runs or repository state.
PAYLOAD = ['SKILL.md', 'LICENSE', 'README.md', 'DESIGN.md', 'agents', 'scripts', 'schemas', 'prompts', 'fixtures', 'docs']


def payload_files(source):
    result = {}
    # Older source checkouts remain installable; include architecture guidance when present.
    names = PAYLOAD + [name for name in ('NORTH_STAR.md', 'registry') if (Path(source) / name).exists()]
    for name in names:
        item = Path(source) / name
        require(item.exists(), f'Incomplete skill: missing {name}')
        paths = item.rglob('*') if item.is_dir() else [item]
        for path in paths:
            require(not path.is_symlink(), f'Skill payload cannot contain symlinks: {path}')
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'}:
                result[path.relative_to(source).as_posix()] = path
    return result


def install(destination, source=ROOT):
    destination = Path(destination).expanduser().resolve()
    source = Path(source).resolve()
    require(destination.name in SKILL_NAMES, 'Skill folder must be named lectic (or legacy expertise-compiler)')
    require(not destination.is_relative_to(source), 'Install outside the source repository')
    files = payload_files(source)
    if destination.exists():
        expected = {name: digest(installed_bytes(name, p.read_bytes(), destination.name))
                    for name, p in files.items()}
        actual = {p.relative_to(destination).as_posix(): digest(p.read_bytes()) for p in destination.rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.pyo'}}
        require(expected == actual, 'An existing installation differs; preserve it and choose an explicit update plan')
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.expertise-install-', dir=destination.parent))
    try:
        for name, path in files.items():
            target = temp / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(installed_bytes(name, path.read_bytes(), destination.name))
        temp.rename(destination)
    finally:
        if temp.exists(): shutil.rmtree(temp)
    return destination


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dest', required=True)
    args = p.parse_args()
    try: print(install(args.dest))
    except (Invalid, UpdateError, OSError) as exc: p.exit(1, f'Error: {exc}\n')
