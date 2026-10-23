"""Filesystem locations used by the backend, resolved from this file (not the current directory)."""

from __future__ import annotations

from pathlib import Path
from typing import Final

BACKEND_DIR: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH: Final[Path] = BACKEND_DIR / "data" / "winrates.json"
