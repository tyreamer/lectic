"""Lectic CLI compatibility entry point forwarding to main cli."""
from __future__ import annotations

from pathlib import Path
import sys

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
_scripts = _root / 'scripts'
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

import cli

def main() -> None:
    cli.main()

if __name__ == '__main__':
    main()
