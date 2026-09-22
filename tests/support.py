"""Shared test helpers. Every test points Lectic at a throwaway home, never ~/.lectic."""
from contextlib import contextmanager
import os
from pathlib import Path

ENV = 'LECTIC_HOME'


def isolate_home(testcase, base, name='lectic-home'):
    """Set LECTIC_HOME under base for this test (and its subprocesses); restore on cleanup."""
    home = Path(base) / name
    previous = os.environ.get(ENV)
    os.environ[ENV] = str(home)
    def restore():
        if previous is None: os.environ.pop(ENV, None)
        else: os.environ[ENV] = previous
    testcase.addCleanup(restore)
    return home


@contextmanager
def at_home(home):
    """Act as the machine whose home this is. LECTIC_HOME is process-wide, so tests
    that involve two homes must say which one each operation belongs to."""
    previous = os.environ.get(ENV)
    os.environ[ENV] = str(home)
    try:
        yield Path(home)
    finally:
        if previous is None: os.environ.pop(ENV, None)
        else: os.environ[ENV] = previous
