"""Shared test helpers. Every test points Lectic at a throwaway home, never ~/.lectic."""
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
