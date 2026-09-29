"""Lectic compatibility release_check forwarding to waykit.scripts.release_check."""
from __future__ import annotations

import json
import sys
from waykit.scripts.release_check import check_release

if __name__ == '__main__':
    print(json.dumps(check_release(), indent=2))
