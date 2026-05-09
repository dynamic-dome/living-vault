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


def test_list_sessions_returns_history(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "concepts/note-a.md"})
    sid = r.json()["session_id"]
    c.post("/api/say", json={"session_id": sid, "text": "first"})
    c.post("/api/say", json={"session_id": sid, "text": "second"})
    r2 = c.get("/api/sessions")
    assert r2.status_code == 200
    sessions = r2.json()
    assert len(sessions) == 1
    s = sessions[0]
    assert s["page_path"] == "concepts/note-a.md"
    # 2 user + 2 assistant = 4 messages
    assert s["message_count"] == 4


def test_get_session_detail(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "concepts/note-a.md"})
    sid = r.json()["session_id"]
    c.post("/api/say", json={"session_id": sid, "text": "hi"})
    r2 = c.get(f"/api/sessions/{sid}")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["page_path"] == "concepts/note-a.md"
    assert len(detail["messages"]) == 2  # 1 user + 1 assistant
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][0]["content"] == "hi"


def test_get_session_detail_404(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.get("/api/sessions/9999")
    assert r.status_code == 404


def test_export_session_writes_markdown(vault_copy, db_path, monkeypatch, tmp_path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_EXPORT_DIR", str(tmp_path))
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "concepts/note-a.md"})
    sid = r.json()["session_id"]
    c.post("/api/say", json={"session_id": sid, "text": "wer bist du?"})
    r2 = c.post(f"/api/sessions/{sid}/export")
    assert r2.status_code == 200, r2.text
    out_path = Path(r2.json()["exported_to"])
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert "concepts/note-a.md" in text
    assert "wer bist du?" in text
    assert "type: seance-transcript" in text  # frontmatter type


def test_export_session_404(vault_copy, db_path, monkeypatch, tmp_path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_EXPORT_DIR", str(tmp_path))
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/sessions/9999/export")
    assert r.status_code == 404


# === Cost/DoS regression tests (Codex Security finding 2026-05-09) ===


def test_say_rejects_oversized_text(vault_copy, db_path, monkeypatch):
    """A user message longer than the cap must return 413, not flow through to LLM."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "concepts/note-a.md"})
    sid = r.json()["session_id"]
    huge_text = "x" * 50_000  # well over 8K cap
    r2 = c.post("/api/say", json={"session_id": sid, "text": huge_text})
    assert r2.status_code == 413
    assert "too long" in r2.text.lower()


def test_say_caps_history_replay(vault_copy, db_path, monkeypatch):
    """After many turns, only the last N messages should be replayed to the LLM."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "concepts/note-a.md"})
    sid = r.json()["session_id"]
    # 60 turns — exceeds the 50-message cap
    for i in range(60):
        r_say = c.post("/api/say", json={"session_id": sid, "text": f"msg{i}"})
        assert r_say.status_code == 200
    # FakeLLM echoes the LAST user message it sees in history. If no cap was
    # enforced it would still see msg59. With the cap it also sees msg59 (the most
    # recent). The cap behavior is observable indirectly — we verify the function
    # `_cap_history` exists and works.
    from living_vault.apps.seance_ui.app import _cap_history, _MAX_HISTORY_MESSAGES
    history = [("user", f"x{i}") for i in range(100)]
    capped = _cap_history(history)
    assert len(capped) <= _MAX_HISTORY_MESSAGES


def test_cap_history_drops_oldest_when_total_chars_exceed(vault_copy, db_path, monkeypatch):
    """If a single huge message would push total over cap, drop oldest."""
    from living_vault.apps.seance_ui.app import _cap_history, _MAX_HISTORY_TOTAL_CHARS
    # Build a fake history with huge messages
    history = [("user", "x" * 5000) for _ in range(20)]  # 100k chars
    capped = _cap_history(history)
    total = sum(len(content) for _, content in capped)
    assert total <= _MAX_HISTORY_TOTAL_CHARS
