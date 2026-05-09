"""Smoke test for the real_wiki_guard autouse fixture: it must refuse
any open() against ~/wiki/. This guarantees test isolation is real, not
just a comment in conftest."""
from __future__ import annotations
from pathlib import Path

import pytest


def test_guard_blocks_real_wiki_open():
    """Confirm the autouse guard blocks open() against ~/wiki/."""
    real_wiki = Path.home() / "wiki" / "index.md"  # may or may not exist
    with pytest.raises(RuntimeError, match="REFUSING to touch real wiki path"):
        open(str(real_wiki), "r")


def test_guard_allows_other_paths(tmp_path: Path):
    """Confirm the guard does NOT block paths outside ~/wiki/."""
    p = tmp_path / "ok.txt"
    p.write_text("hello")
    # this should NOT raise
    with open(str(p), "r") as f:
        assert f.read() == "hello"
