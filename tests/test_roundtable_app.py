"""Phase-10b: end-to-end roundtable through FastAPI."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi.testclient import TestClient

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.llm import FakeLLMWithTools
from living_vault.apps.seance_ui import store


def _client_with_iter_llms(vault: Path, db: Path, monkeypatch, scripts: list[list[dict]]):
    """Install N FakeLLMWithTools so each call to get_llm() yields the next one.
    Use this when roundtable will call get_llm() once per persona."""
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    fakes = [FakeLLMWithTools(s) for s in scripts]
    fakes_iter = iter(fakes)
    monkeypatch.setattr(app_mod, "get_llm", lambda: next(fakes_iter))
    return TestClient(app_mod.app), fakes


def test_roundtable_summon_freeforall_three_personas(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [
        [{"type": "text", "text": "I am note-a"}],
        [{"type": "text", "text": "I am note-b"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    r = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    })
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]

    r2 = client.post("/api/say", json={"session_id": sid, "text": "hello all"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert "replies" in body
    assert len(body["replies"]) == 2
    assert body["replies"][0]["persona_path"] == "concepts/note-a.md"
    assert body["replies"][0]["text"] == "I am note-a"
    assert body["replies"][1]["persona_path"] == "concepts/note-b.md"
    assert body["replies"][1]["text"] == "I am note-b"


def test_roundtable_persists_with_persona_path_per_reply(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [
        [{"type": "text", "text": "A"}],
        [{"type": "text", "text": "B"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    client.post("/api/say", json={"session_id": sid, "text": "hi"})

    detail = store.get_session_detail(db_path, sid)
    assistants = [m for m in detail["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 2
    assert assistants[0]["persona_path"] == "concepts/note-a.md"
    assert assistants[0]["content"] == "A"
    assert assistants[1]["persona_path"] == "concepts/note-b.md"


def test_roundrobin_alternates_speakers_across_turns(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # 3 turns × 1 speaker each = 3 fakes
    scripts = [
        [{"type": "text", "text": "A1"}],
        [{"type": "text", "text": "B1"}],
        [{"type": "text", "text": "A2"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "roundrobin",
    }).json()["session_id"]

    r1 = client.post("/api/say", json={"session_id": sid, "text": "q1"})
    r2 = client.post("/api/say", json={"session_id": sid, "text": "q2"})
    r3 = client.post("/api/say", json={"session_id": sid, "text": "q3"})

    assert r1.json()["replies"][0]["persona_path"] == "concepts/note-a.md"
    assert r2.json()["replies"][0]["persona_path"] == "concepts/note-b.md"
    assert r3.json()["replies"][0]["persona_path"] == "concepts/note-a.md"  # wrap


def test_moderator_at_mention_picks_one_persona(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [[{"type": "text", "text": "A says hi"}]]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "moderator",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "@note-a what?"})
    body = r.json()
    assert len(body["replies"]) == 1
    assert body["replies"][0]["persona_path"] == "concepts/note-a.md"


def test_moderator_no_mention_falls_back_to_one_speaker(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [[{"type": "text", "text": "First persona answer"}]]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "moderator",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "no mention here"})
    body = r.json()
    assert len(body["replies"]) == 1  # round-robin fallback picks 1


def test_freeforall_personas_get_color_in_response(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [
        [{"type": "text", "text": "A"}],
        [{"type": "text", "text": "B"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "hi"})
    body = r.json()
    assert body["replies"][0]["color"].startswith("#")
    assert body["replies"][1]["color"].startswith("#")


def test_say_single_mode_still_works_after_phase10b(vault_copy, db_path, monkeypatch):
    """Phase-10a single-mode path is still served correctly."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [[{"type": "text", "text": "I am the page."}]]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "who are you?"})
    assert r.status_code == 200
    body = r.json()
    # Phase-10a response shape: {reply, tool_events}
    assert "reply" in body
    assert body["reply"] == "I am the page."
    assert "tool_events" in body


def test_cross_persona_consult_is_allowed(vault_copy, db_path, monkeypatch):
    """A roundtable persona can consult_neighbor on a teammate's path even if
    the teammate isn't a graph neighbor."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # Persona A consults B (teammate, not necessarily wiki-neighbor), then text.
    scripts = [
        [
            {"type": "tool_use", "name": "consult_neighbor",
             "input": {"neighbor_path": "concepts/note-b.md"}},
            {"type": "text", "text": "I read B's content"},
        ],
        [{"type": "text", "text": "B replies"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "react"})
    assert r.status_code == 200, r.text
    body = r.json()
    # consult succeeded — at least one tool_event captured for A
    assert len(body["tool_events"]) >= 1
    # the consulted neighbor was B (teammate)
    consult_events = [e for e in body["tool_events"] if e["tool_name"] == "consult_neighbor"]
    assert any(e["tool_args"]["neighbor_path"] == "concepts/note-b.md" for e in consult_events)


def test_skip_broken_persona_other_two_still_reply(vault_copy, db_path, monkeypatch):
    """If one of three personas' build_persona fails, the other two must still answer."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # Two replies for the two surviving personas; the broken one is skipped via persona_skipped event.
    scripts = [
        [{"type": "text", "text": "A reply"}],
        [{"type": "text", "text": "C reply"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    # Summon with a non-existent path mid-list
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    # Manually delete note-b from the pages table to simulate page-gone-since-summon
    import sqlite3
    con = sqlite3.connect(str(db_path))
    con.execute("DELETE FROM pages WHERE path = ?", ("concepts/note-b.md",))
    con.commit()
    con.close()

    r = client.post("/api/say", json={"session_id": sid, "text": "go"})
    assert r.status_code == 200, r.text
    body = r.json()
    # only A replied; B was skipped
    replies_paths = [reply["persona_path"] for reply in body["replies"]]
    assert "concepts/note-a.md" in replies_paths
    assert "concepts/note-b.md" not in replies_paths
    # tool_events contains a persona_skipped for B
    skipped = [e for e in body["tool_events"] if e["tool_name"] == "persona_skipped"]
    assert len(skipped) == 1
    assert skipped[0]["tool_args"]["persona_path"] == "concepts/note-b.md"


def test_roundtable_response_has_tool_events_aggregated(vault_copy, db_path, monkeypatch):
    """tool_events from all personas are merged into one response list."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [
        [
            {"type": "tool_use", "name": "consult_neighbor",
             "input": {"neighbor_path": "concepts/note-b.md"}},
            {"type": "text", "text": "A done"},
        ],
        [
            {"type": "tool_use", "name": "consult_neighbor",
             "input": {"neighbor_path": "concepts/note-a.md"}},
            {"type": "text", "text": "B done"},
        ],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "go"})
    body = r.json()
    consult_events = [e for e in body["tool_events"] if e["tool_name"] == "consult_neighbor"]
    assert len(consult_events) == 2  # one from A, one from B
