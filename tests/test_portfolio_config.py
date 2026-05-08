import os
from pathlib import Path
from living_vault.apps.portfolio_sync.config import resolve_target_dir


def test_resolve_target_dir_default(monkeypatch, tmp_path):
    monkeypatch.delenv("LIVING_VAULT_PORTFOLIO_DIR", raising=False)
    p = resolve_target_dir(default=tmp_path)
    assert p == tmp_path


def test_resolve_target_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(tmp_path))
    p = resolve_target_dir(default=Path("/should/not/be/used"))
    assert p == tmp_path
