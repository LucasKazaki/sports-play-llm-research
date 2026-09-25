"""Compatibility entry point for the standalone :mod:`footballmaster` package.

New code should run ``python -m footballmaster`` or import ``footballmaster``.
This wrapper preserves the original prototype command and test import surface
without duplicating any training, evaluation, indexing, or retrieval logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from footballmaster import pipeline as _pipeline


# Preserve the complete historical module surface, including private helpers
# used by regression tests, while maintaining exactly one implementation.
globals().update({
    name: getattr(_pipeline, name)
    for name in dir(_pipeline)
    if not name.startswith("__")
})


if __name__ == "__main__":
    raise SystemExit(_pipeline.main())
