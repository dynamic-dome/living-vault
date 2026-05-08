"""Test the séance FastAPI app with a fake LLM."""
import os
from pathlib import Path
from fastapi.testclient import TestClient

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault


def _client(vault: Path, db: Path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    # import after env is set so module-level reads pick it up
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    return TestClient(app_mod.app)


def test_list_pages_returns_all(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.get("/api/pages")
    assert r.status_code == 200
    paths = [p["path"] for p in r.json()]
    assert "concepts/note-a.md" in paths


def test_summon_creates_session_and_responds(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "concepts/note-a.md"})
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    r2 = c.post(f"/api/say", json={"session_id": sid, "text": "who are you?"})
    assert r2.status_code == 200
    assert "fake echo" in r2.json()["reply"]


def test_summon_unknown_path_404(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "does/not/exist.md"})
    assert r.status_code == 404
