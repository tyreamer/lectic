"""WayKit: turn trusted content into reusable, evidence-preserving expertise your AI assistants share."""
from __future__ import annotations

from pathlib import Path
import sys

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
_scripts = _root / 'scripts'
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

try:
    from scripts.release_version import VERSION as __version__
except ImportError:
    try:
        from release_version import VERSION as __version__
    except ImportError:
        __version__ = "0.3.2"
