"""Phase-10a: end-to-end say() with tool-use, using FakeLLMWithTools."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi.testclient import TestClient

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core import embeddings as embeddings_mod
from living_vault.core.embeddings import NumpyBackend, index_embeddings
from living_vault.core.llm import FakeLLMWithTools
from living_vault.apps.seance_ui import store


def _client_with_scripted_llm(vault: Path, db: Path, monkeypatch, script: list[dict]):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db))
    # Belt-and-suspenders: env var forces FakeLLM if monkeypatch below ever
    # fails to take effect (e.g. import-order regression). Prevents accidental
    # real Anthropic calls during tests.
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    # The real override: get_llm returns our scripted FakeLLMWithTools.
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


def _add_semantic_only_alpha_page(vault_copy: Path) -> str:
    rel = "concepts/semantic-alpha.md"
    path = vault_copy / rel
    path.write_text(
        "---\ntype: concept\nstatus: active\n---\n\n"
        "# Semantic Alpha\n\n"
        "Alpha alpha alpha archive context with no wikilinks.\n",
        encoding="utf-8",
    )
    return rel


def test_semantic_neighbor_consult_blocked_without_opt_in(vault_copy, db_path, monkeypatch):
    semantic_path = _add_semantic_only_alpha_page(vault_copy)
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    c, _ = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, [
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": semantic_path}},
        {"type": "text", "text": "I could not use it."},
    ])
    sid = c.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]

    r = c.post("/api/say", json={"session_id": sid, "text": "alpha"})

    assert r.status_code == 200, r.text
    ev = r.json()["tool_events"][0]
    assert "error" in ev["tool_result_summary"]
    assert r.json()["evidence"]["semantic_paths"] == []


def test_semantic_neighbor_consult_allowed_with_opt_in(vault_copy, db_path, monkeypatch):
    semantic_path = _add_semantic_only_alpha_page(vault_copy)
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    c, _ = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, [
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": semantic_path}},
        {"type": "text", "text": "I used semantic archive."},
    ])
    sid = c.post("/api/summon", json={
        "path": "concepts/note-a.md",
        "semantic_neighbors": True,
    }).json()["session_id"]

    r = c.post("/api/say", json={"session_id": sid, "text": "alpha"})

    assert r.status_code == 200, r.text
    body = r.json()
    ev = body["tool_events"][0]
    assert "error" not in ev["tool_result_summary"]
    assert semantic_path in body["evidence"]["semantic_paths"]
    assert body["evidence"]["consulted_paths"] == [semantic_path]


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
    # rejection MUST be captured: exactly one tool_events entry with is_error
    assert len(body["tool_events"]) == 1
    ev = body["tool_events"][0]
    assert ev["tool_name"] == "consult_neighbor"
    assert ev["tool_args"]["neighbor_path"] == "concepts/totally-unrelated.md"
    assert "error" in ev["tool_result_summary"]
    assert "not a neighbor" in ev["tool_result_summary"]["error"].lower()
    assert "answer" in body["reply"].lower() or "had to" in body["reply"].lower()


def test_say_max_iterations_cap_limits_loop(vault_copy, db_path, monkeypatch):
    """The LLM-loop max_iterations=5 takes effect FIRST, before the handler's
    MAX_CONSULT_CALLS_PER_TURN=10 budget. A script with 11 tool_use steps will
    only see 5 actually executed because the loop short-circuits at iteration
    5 with the budget-exhausted fallback string."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
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
    # max_iterations=5 (hardcoded in say()) caps tool calls at 5
    detail = store.get_session_detail(db_path, sid)
    tool_rows = [m for m in detail["messages"] if m["role"] == "tool_use"]
    successful = [
        m for m in tool_rows
        if "error" not in json.loads(m["content"])["tool_result_summary"]
    ]
    assert len(successful) == 5
    # response also captures exactly 5 events (no error events because the
    # loop just stops, it doesn't call the handler with a budget-rejection)
    assert len(body["tool_events"]) == 5
    # the reply is the budget-exhausted fallback string from FakeLLMWithTools
    assert "budget exhausted" in body["reply"].lower()


def test_say_soft_cap_when_iterations_is_high_enough(vault_copy, db_path, monkeypatch):
    """When the LLM-loop is generous enough (we monkey-patch say() to use a
    larger max_iterations), the handler's MAX_CONSULT_CALLS_PER_TURN=10 budget
    becomes the binding constraint. The 11th call returns is_error from the
    soft-cap path and that error event surfaces in the response."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    script = [
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "concepts/note-b.md"}}
        for _ in range(11)
    ] + [{"type": "text", "text": "I have read enough."}]
    client, fake = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, script)

    # Patch the FakeLLMWithTools instance to report a higher iteration cap so
    # the soft-cap (handler-level) becomes the binding constraint, not the
    # LLM-loop cap. We do this by overriding respond_with_tools on the fake
    # to force max_iterations=15.
    original = fake.respond_with_tools
    def _generous(system, history, tools, tool_handler, max_iterations=5):
        return original(system, history, tools, tool_handler, max_iterations=15)
    fake.respond_with_tools = _generous

    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "consult everything"})
    assert r.status_code == 200
    body = r.json()
    from living_vault.apps.seance_ui.neighbors import MAX_CONSULT_CALLS_PER_TURN
    detail = store.get_session_detail(db_path, sid)
    tool_rows = [m for m in detail["messages"] if m["role"] == "tool_use"]
    successful = [
        m for m in tool_rows
        if "error" not in json.loads(m["content"])["tool_result_summary"]
    ]
    # Now 10 calls succeed, the 11th hits the soft-cap inside the handler.
    assert len(successful) == MAX_CONSULT_CALLS_PER_TURN
    # response captures all 11 (10 success + 1 soft-cap rejection)
    assert len(body["tool_events"]) == 11
    is_error_events = [ev for ev in body["tool_events"] if "error" in ev["tool_result_summary"]]
    assert len(is_error_events) == 1
    assert "budget" in is_error_events[0]["tool_result_summary"]["error"].lower()
