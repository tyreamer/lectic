"""Where WayKit keeps knowledge: one store per user, with projects as working contexts.

Resolution order:
  1. An explicitly scoped home supplied by authenticated account internals.
  2. WAYKIT_HOME or LECTIC_HOME (explicit; also how tests isolate storage).
  3. ~/.waykit, or an existing ~/.lectic for backwards compatibility.

A project is where the user is working, not a silo: collections saved from one
project are visible from every other project that resolves to the same home.
"""
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from ec import Invalid, fingerprint, require, safe_child

LEGACY_DIRNAME = '.expertise-compiler'
LEGACY_MARKERS = ('library.json', 'session.json', 'runs', 'collections', 'capture', 'capabilities')
DEFAULT_DIRNAME = '.waykit'
LEGACY_LECTIC_DIRNAME = '.lectic'
ENV = 'WAYKIT_HOME'
LEGACY_ENV = 'LECTIC_HOME'
_SCOPED_HOME = ContextVar('waykit_home', default=None)


@contextmanager
def home_scope(root):
    """Bind account operations without changing process-wide environment variables."""
    token = _SCOPED_HOME.set(Path(root).resolve())
    try:
        yield
    finally:
        _SCOPED_HOME.reset(token)


def storage_root(project='.'):
    scoped = _SCOPED_HOME.get()
    if scoped is not None: return scoped
    explicit = os.environ.get(ENV) or os.environ.get(LEGACY_ENV)
    if explicit:
        return Path(explicit).expanduser().resolve()
    # An old project library must never override the shared home. setup/centralize
    # imports it additively, retaining the original and a recoverable archive.
    waykit_home = (Path.home() / DEFAULT_DIRNAME).resolve()
    lectic_home = (Path.home() / LEGACY_LECTIC_DIRNAME).resolve()
    if not waykit_home.exists() and lectic_home.exists():
        return lectic_home
    return waykit_home


def storage_mode(root, project='.'):
    if _SCOPED_HOME.get() is not None or os.environ.get(ENV) or os.environ.get(LEGACY_ENV): return 'explicit'
    return 'user'


def project_key(project='.'):
    """Stable, opaque identity for per-project state that lives inside a shared home."""
    return fingerprint(Path(project).resolve().as_posix())[:16]


def session_path(root, project='.'):
    """Per-project resume pointers belong inside the central home."""
    root = Path(root)
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
