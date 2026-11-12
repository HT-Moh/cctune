"""Fixtures for the cctune audit skill tests."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for d in (HERE.parent / "scripts", HERE.parent.parent / "cctune-apply" / "scripts"):
    sys.path.insert(0, str(d))
