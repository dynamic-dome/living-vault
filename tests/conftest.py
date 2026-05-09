"""Shared pytest fixtures.

ABSOLUTE RULE: tests must never touch ~/wiki/ or the real .vault-engine.db.
Every fixture below uses tmp_path or the static fixtures/vault/ tree.
"""
from __future__ import annotations
import shutil
import sqlite3
from pathlib import Path
import pytest

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"


@pytest.fixture
def fixture_vault_root() -> Path:
    """The static, read-only fixture vault. Tests must not write into it."""
    assert FIXTURE_VAULT.exists(), f"missing fixture vault at {FIXTURE_VAULT}"
    return FIXTURE_VAULT


@pytest.fixture
def vault_copy(tmp_path: Path, fixture_vault_root: Path) -> Path:
    """A writable copy of the fixture vault under tmp_path."""
    dst = tmp_path / "vault"
    shutil.copytree(fixture_vault_root, dst)
    return dst


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A fresh sqlite db file path under tmp_path."""
    return tmp_path / ".vault-engine.db"


@pytest.fixture(autouse=True)
def real_wiki_guard(monkeypatch):
    """Hard guard: any attempt to open ~/wiki paths raises."""
    real_root = (Path.home() / "wiki").resolve()
    real_open = open

    def guarded_open(file, *a, **k):
        try:
            p = Path(file).resolve()
        except Exception:
            return real_open(file, *a, **k)
        if str(p).startswith(str(real_root)):
            raise RuntimeError(f"REFUSING to touch real wiki path: {p}")
        return real_open(file, *a, **k)

    monkeypatch.setattr("builtins.open", guarded_open)
