"""Lectic CLI compatibility entry point forwarding to waykit.cli."""
from __future__ import annotations

import sys
from waykit.cli import main

if __name__ == '__main__':
    sys.exit(main())
