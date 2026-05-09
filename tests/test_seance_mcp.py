"""Phase-12 séance MCP server tests.

Exercise the tool callables directly via the FastMCP server object (no stdio).
"""
from __future__ import annotations
from pathlib import Path

import pytest

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.mcp_servers.seance import server as srv


def _setup(vault_copy: Path, db_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")


# ---- summon ---------------------------------------------------------------

def test_summon_single_page(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    out = srv._tool_summon(["concepts/note-a.md"])
    assert out["mode"] == "single"
    assert out["session_id"] > 0
    assert len(out["personas"]) == 1
    assert out["personas"][0]["persona_path"] == "concepts/note-a.md"


def test_summon_empty_paths_raises_400(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    with pytest.raises(RuntimeError, match=r"\[400\]"):
        srv._tool_summon([])


def test_summon_unknown_path_raises_404(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    with pytest.raises(RuntimeError, match=r"\[404\]"):
        srv._tool_summon(["does/not/exist.md"])


def test_summon_too_many_paths_raises_413(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    nine = [f"concepts/note-a.md"] * 9  # dedup happens AFTER length check on raw input
    # All identical → length-9 → 413 before dedup, per app.py logic preserved in orchestrator.
    with pytest.raises(RuntimeError, match=r"\[413\]"):
        srv._tool_summon(nine)


# ---- say ------------------------------------------------------------------

def test_say_single_mode_returns_reply(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    summoned = srv._tool_summon(["concepts/note-a.md"])
    sid = summoned["session_id"]
    out = srv._tool_say(sid, "who are you?")
    assert "reply" in out
    assert "tool_events" in out
    assert "fake echo" in out["reply"]


def test_say_unknown_session_raises_404(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    with pytest.raises(RuntimeError, match=r"\[404\]"):
        srv._tool_say(99999, "hello")


def test_say_text_too_long_raises_413(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    summoned = srv._tool_summon(["concepts/note-a.md"])
    with pytest.raises(RuntimeError, match=r"\[413\]"):
        srv._tool_say(summoned["session_id"], "x" * 9000)


# ---- commit_insight ------------------------------------------------------

def test_commit_insight_roundtrip(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    out = srv._tool_commit_insight(
        page_path="concepts/note-a.md",
        persona_path="concepts/note-a.md",
        question="What is the core idea?",
        insight="Note-a teaches us that alpha precedes bravo.",
    )
    assert out["insight_id"] > 0
    assert out["created_at"]

    listed = srv._tool_list_insights(page_path="concepts/note-a.md")
    assert len(listed) == 1
    assert listed[0]["insight"] == "Note-a teaches us that alpha precedes bravo."


def test_commit_insight_with_session_id(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    summoned = srv._tool_summon(["concepts/note-a.md"])
    sid = summoned["session_id"]
    out = srv._tool_commit_insight(
        page_path="concepts/note-a.md",
        persona_path="concepts/note-a.md",
        question="q",
        insight="i",
        session_id=sid,
    )
    rows = srv._tool_list_insights()
    assert any(r["session_id"] == sid for r in rows)
    assert out["insight_id"] > 0


def test_commit_insight_empty_field_raises_400(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    with pytest.raises(RuntimeError, match=r"\[400\]"):
        srv._tool_commit_insight(
            page_path="x.md", persona_path="x.md",
            question="", insight="i",
        )


def test_commit_insight_too_long_raises_413(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    with pytest.raises(RuntimeError, match=r"\[413\]"):
        srv._tool_commit_insight(
            page_path="x.md", persona_path="x.md",
            question="q", insight="x" * 17_000,
        )


def test_commit_insight_invalid_session_raises_404(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    with pytest.raises(RuntimeError, match=r"\[404\]"):
        srv._tool_commit_insight(
            page_path="x.md", persona_path="x.md",
            question="q", insight="i", session_id=99999,
        )


# ---- list_sessions --------------------------------------------------------

def test_list_sessions_after_summon(vault_copy, db_path, monkeypatch):
    _setup(vault_copy, db_path, monkeypatch)
    srv._tool_summon(["concepts/note-a.md"])
    srv._tool_summon(["concepts/note-b.md"])
    sessions = srv._tool_list_sessions()
    assert len(sessions) == 2
    paths = {s["page_path"] for s in sessions}
    assert paths == {"concepts/note-a.md", "concepts/note-b.md"}


# ---- env-var hardening ----------------------------------------------------

def test_missing_vault_root_env_raises(monkeypatch, db_path):
    # Strip env explicitly — guarded conftest already prevents writing,
    # but we want to assert the helper raises a clear RuntimeError.
    monkeypatch.delenv("LIVING_VAULT_ROOT", raising=False)
    with pytest.raises(RuntimeError, match="LIVING_VAULT_ROOT"):
        srv._vault_root()
