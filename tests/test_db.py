"""Tests for core.db — schema initialization."""
from pathlib import Path
import sqlite3
import pytest

from living_vault.core import db as db_mod


def test_initialize_creates_all_tables(db_path: Path):
    db_mod.initialize(db_path)
    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    con.close()
    names = {r[0] for r in rows}
    assert "pages" in names
    assert "links" in names
    assert "personas" in names
    assert "runs" in names


def test_initialize_is_idempotent(db_path: Path):
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call must not raise
    assert db_path.exists()


def test_connect_returns_open_connection(db_path: Path):
    db_mod.initialize(db_path)
    con = db_mod.connect(db_path)
    assert con.execute("SELECT 1").fetchone() == (1,)
    con.close()
