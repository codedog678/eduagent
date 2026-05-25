"""Bootstrap package imports when the project is loaded from the repo root."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
package_root_str = str(PACKAGE_ROOT)

if package_root_str not in sys.path:
    sys.path.insert(0, package_root_str)
