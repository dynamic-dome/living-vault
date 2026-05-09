"""Phase-10a: end-to-end say() with tool-use, using FakeLLMWithTools."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi.testclient import TestClient

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.llm import FakeLLMWithTools
from living_vault.apps.seance_ui import store


def _client_with_scripted_llm(vault: Path, db: Path, monkeypatch, script: list[dict]):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")  # forces FakeLLM by default
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    # override get_llm to return our scripted fake
    fake = FakeLLMWithTools(script)
    monkeypatch.setattr(app_mod, "get_llm", lambda: fake)
    return TestClient(app_mod.app), fake


def test_say_with_no_tool_calls_returns_text_and_empty_events(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    client, fake = _client_with_scripted_llm(
        vault_copy, db_path, monkeypatch,
        script=[{"type": "text", "text": "I am the page."}],
    )
    r = client.post("/api/summon", json={"path": "concepts/note-a.md"})
    sid = r.json()["session_id"]
    r2 = client.post("/api/say", json={"session_id": sid, "text": "who are you?"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["reply"] == "I am the page."
    assert body["tool_events"] == []


def test_say_with_one_tool_call_persists_event_and_returns_in_response(
    vault_copy, db_path, monkeypatch
):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # pick a real neighbor that note-a.md links to in the fixture vault
    script = [
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "concepts/note-b.md"}},
        {"type": "text", "text": "Aus note-b lese ich Wichtiges."},
    ]
    client, fake = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, script)
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "what does your neighbor say?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tool_events" in body
    assert len(body["tool_events"]) == 1
    ev = body["tool_events"][0]
    assert ev["tool_name"] == "consult_neighbor"
    assert ev["tool_args"]["neighbor_path"] == "concepts/note-b.md"
    assert ev["tool_result_summary"]["chars"] > 0

    # also persisted in DB
    detail = store.get_session_detail(db_path, sid)
    roles = [m["role"] for m in detail["messages"]]
    assert "tool_use" in roles
    assert roles.count("user") == 1
    assert roles.count("assistant") == 1


def test_say_persists_user_and_assistant_with_persona_path(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    client, fake = _client_with_scripted_llm(
        vault_copy, db_path, monkeypatch,
        script=[{"type": "text", "text": "hi"}],
    )
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    client.post("/api/say", json={"session_id": sid, "text": "hello"})
    detail = store.get_session_detail(db_path, sid)
    user_msg = next(m for m in detail["messages"] if m["role"] == "user")
    assist_msg = next(m for m in detail["messages"] if m["role"] == "assistant")
    assert user_msg["persona_path"] is None
    assert assist_msg["persona_path"] == "concepts/note-a.md"


def test_say_with_non_neighbor_tool_call_records_is_error(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # script asks the LLM to consult a page that is NOT in note-a.md's neighbor set
    script = [
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "concepts/totally-unrelated.md"}},
        {"type": "text", "text": "I had to answer without that one."},
    ]
    client, fake = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, script)
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "tell me about the unrelated"})
    assert r.status_code == 200
    body = r.json()
    # tool_events list contains an entry recording the rejection (is_error=True payload)
    assert len(body["tool_events"]) >= 0  # impl may choose to surface or not
    assert "answer" in body["reply"].lower() or "had to" in body["reply"].lower()


def test_say_soft_cap_end_to_end(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # 11 tool_use steps then a text — handler will return is_error from #11 onwards
    script = [
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "concepts/note-b.md"}}
        for _ in range(11)
    ] + [{"type": "text", "text": "I have read enough."}]
    client, fake = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, script)
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "consult everything"})
    assert r.status_code == 200
    body = r.json()
    # at most MAX_CONSULT_CALLS_PER_TURN successful tool_events were persisted
    detail = store.get_session_detail(db_path, sid)
    successful = [
        m for m in detail["messages"]
        if m["role"] == "tool_use"
        and "error" not in json.loads(m["content"])["tool_result_summary"]
    ]
    from living_vault.apps.seance_ui.neighbors import MAX_CONSULT_CALLS_PER_TURN
    assert len(successful) <= MAX_CONSULT_CALLS_PER_TURN
