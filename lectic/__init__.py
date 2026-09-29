"""Lectic backward compatibility package forwarding to waykit."""
from __future__ import annotations

import sys
import waykit
from waykit import __version__

# Aliases for lectic.scripts
try:
    import waykit.scripts as scripts
    sys.modules.setdefault('lectic.scripts', scripts)
except Exception:
    pass
