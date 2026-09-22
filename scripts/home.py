"""Where Lectic keeps knowledge: one store per user, with projects as working contexts.

Resolution order:
  1. LECTIC_HOME environment variable (explicit; also how tests isolate storage).
  2. PROJECT/.expertise-compiler when it already exists (legacy project-local storage).
  3. ~/.lectic (default for new installations).

A project is where the user is working, not a silo: collections saved from one
project are visible from every other project that resolves to the same home.
"""
import os
from pathlib import Path

from ec import Invalid, fingerprint, require, safe_child

LEGACY_DIRNAME = '.expertise-compiler'
DEFAULT_DIRNAME = '.lectic'
ENV = 'LECTIC_HOME'


def storage_root(project='.'):
    project = Path(project).resolve()
    explicit = os.environ.get(ENV)
    if explicit:
        return Path(explicit).expanduser().resolve()
    legacy = project / LEGACY_DIRNAME
    if legacy.is_dir():
        return legacy
    return (Path.home() / DEFAULT_DIRNAME).resolve()


def storage_mode(root, project='.'):
    if os.environ.get(ENV): return 'explicit'
    if Path(root).resolve() == (Path(project).resolve() / LEGACY_DIRNAME): return 'project-local'
    return 'user'


def project_key(project='.'):
    """Stable, opaque identity for per-project state that lives inside a shared home."""
    return fingerprint(Path(project).resolve().as_posix())[:16]


def session_path(root, project='.'):
    """Legacy numbered-capability sessions stay where existing installs expect them."""
    root = Path(root)
    if storage_mode(root, project) == 'project-local':
        return root / 'session.json'
    return root / 'sessions' / (project_key(project) + '.json')


def describe(project='.'):
    root = storage_root(project)
    return {'home': str(root), 'mode': storage_mode(root, project), 'project': str(Path(project).resolve())}


def relative_run(root, project, run):
    """Record a run relative to the home when it lives there, else relative to the project.

    Explicit legacy outputs may sit anywhere inside the project; runs the compiler
    chooses always live inside the home, so they stay valid when the home moves.
    """
    root, project, run = Path(root).resolve(), Path(project).resolve(), Path(run).resolve()
    if run.is_relative_to(root): return run.relative_to(root).as_posix()
    require(run.is_relative_to(project), 'Compilation output must be inside the selected project or the Lectic home')
    return run.relative_to(project).as_posix()


def resolve_run(root, project, recorded):
    """Inverse of relative_run; also accepts session values written by project-local installs."""
    root, project = Path(root).resolve(), Path(project).resolve()
    candidates = [(root, recorded), (project, recorded)]
    if recorded.startswith(LEGACY_DIRNAME + '/'):
        candidates.insert(0, (root, recorded[len(LEGACY_DIRNAME) + 1:]))
    last = None
    for base, relative in candidates:
        try:
            path = safe_child(base, relative)
        except Invalid as exc:
            last = exc; continue
        if (path / 'corpus.json').is_file(): return path
        last = last or Invalid('Recorded run no longer exists: ' + recorded)
    raise last
