"""Fixtures for the cctune audit skill tests."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
for d in (HERE.parent / "scripts", HERE.parent.parent / "cctune-apply" / "scripts"):
    sys.path.insert(0, str(d))


@pytest.fixture
def tmp_home(tmp_path, monkeypatch) -> Path:
    """A fake HOME so the ledger and the tune dir never touch the real one."""
    home = tmp_path / "home"
    (home / ".claude" / "tune" / "plans").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home
