"""Shared pytest configuration for the Jantar test suite.

Guarantees the `jantar` package is importable from `src/` regardless of how
pytest is invoked, and keeps test output quiet.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the src-layout package is importable even without an editable install.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Make the tests directory importable so shared `helpers` can be imported.
_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

# Tests assert on behavior, not log spam — keep the root logger quiet.
logging.getLogger().setLevel(logging.CRITICAL)
