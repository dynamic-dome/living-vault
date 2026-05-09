"""Tests for the transport-neutral séance orchestrator (Phase 12.2)."""
from __future__ import annotations
from pathlib import Path

import pytest

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.apps.seance_ui import orchestrator
from living_vault.apps.seance_ui.orchestrator import SéanceError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup(vault_copy: Path, db_path: Path) -> None:
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)


# ---------------------------------------------------------------------------
# 1. summon_session — single page, mode='single'
# ---------------------------------------------------------------------------

def test_summon_single_page_returns_valid_dict(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    _setup(vault_copy, db_path)
    result = orchestrator.summon_session(
        db_path, vault_copy, page_paths=["concepts/note-a.md"]
    )
    assert "session_id" in result
    assert result["mode"] == "single"
    assert len(result["personas"]) == 1
    assert result["personas"][0]["persona_path"] == "concepts/note-a.md"
    assert "persona" in result  # backward-compat field


# ---------------------------------------------------------------------------
# 2. summon_session — empty page_paths raises SéanceError(400)
# ---------------------------------------------------------------------------

def test_summon_empty_paths_raises_400(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    _setup(vault_copy, db_path)
    with pytest.raises(SéanceError) as exc_info:
        orchestrator.summon_session(db_path, vault_copy, page_paths=[])
    assert exc_info.value.code == 400
    assert "at least one page" in str(exc_info.value.detail).lower()


# ---------------------------------------------------------------------------
# 3. summon_session — 9 paths raises SéanceError(413)
# ---------------------------------------------------------------------------

def test_summon_too_many_paths_raises_413(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    _setup(vault_copy, db_path)
    nine_paths = ["concepts/note-a.md"] * 9
    with pytest.raises(SéanceError) as exc_info:
        orchestrator.summon_session(db_path, vault_copy, page_paths=nine_paths)
    assert exc_info.value.code == 413


# ---------------------------------------------------------------------------
# 4. summon_session — multi-path with mode='single' coerces to 'roundrobin'
# ---------------------------------------------------------------------------

def test_summon_multi_path_single_mode_coerces_to_roundrobin(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    _setup(vault_copy, db_path)
    result = orchestrator.summon_session(
        db_path, vault_copy,
        page_paths=["concepts/note-a.md", "concepts/note-b.md"],
        mode="single",
    )
    assert result["mode"] == "roundrobin"


# ---------------------------------------------------------------------------
# 5. summon_session — 1 path with mode='moderator' coerces to 'single'
# ---------------------------------------------------------------------------

def test_summon_one_path_moderator_coerces_to_single(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    _setup(vault_copy, db_path)
    result = orchestrator.summon_session(
        db_path, vault_copy,
        page_paths=["concepts/note-a.md"],
        mode="moderator",
    )
    assert result["mode"] == "single"


# ---------------------------------------------------------------------------
# 6. summon_session — non-existent page raises SéanceError(404)
# ---------------------------------------------------------------------------

def test_summon_nonexistent_page_raises_404(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    _setup(vault_copy, db_path)
    with pytest.raises(SéanceError) as exc_info:
        orchestrator.summon_session(
            db_path, vault_copy,
            page_paths=["does/not/exist.md"],
        )
    assert exc_info.value.code == 404


# ---------------------------------------------------------------------------
# 7. say_single — happy path with FakeLLM returns {reply, tool_events}
# ---------------------------------------------------------------------------

def test_say_single_happy_path(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup(vault_copy, db_path)

    session = orchestrator.summon_session(
        db_path, vault_copy,
        page_paths=["concepts/note-a.md"],
    )
    sid = session["session_id"]

    result = orchestrator.say_single(
        db_path, vault_copy, session_id=sid, text="who are you?"
    )
    assert "reply" in result
    assert "tool_events" in result
    assert isinstance(result["reply"], str)
    assert len(result["reply"]) > 0


# ---------------------------------------------------------------------------
# 8. say() — text longer than 8000 chars raises SéanceError(413)
# ---------------------------------------------------------------------------

def test_say_oversized_text_raises_413(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup(vault_copy, db_path)

    session = orchestrator.summon_session(
        db_path, vault_copy,
        page_paths=["concepts/note-a.md"],
    )
    sid = session["session_id"]

    huge_text = "x" * 50_000
    with pytest.raises(SéanceError) as exc_info:
        orchestrator.say(db_path, vault_copy, session_id=sid, text=huge_text)
    assert exc_info.value.code == 413
    assert "too long" in str(exc_info.value.detail).lower()


# ---------------------------------------------------------------------------
# 9. say() — unknown session_id raises SéanceError(404)
# ---------------------------------------------------------------------------

def test_say_unknown_session_raises_404(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup(vault_copy, db_path)

    with pytest.raises(SéanceError) as exc_info:
        orchestrator.say(db_path, vault_copy, session_id=99999, text="hello")
    assert exc_info.value.code == 404


# ---------------------------------------------------------------------------
# 10. say() — dispatches single vs roundtable based on session.mode
# ---------------------------------------------------------------------------

def test_say_dispatches_single_vs_roundtable(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup(vault_copy, db_path)

    # Single-mode session → response has 'reply' key
    single_session = orchestrator.summon_session(
        db_path, vault_copy,
        page_paths=["concepts/note-a.md"],
    )
    single_sid = single_session["session_id"]
    single_result = orchestrator.say(db_path, vault_copy, session_id=single_sid, text="hi")
    assert "reply" in single_result
    assert "replies" not in single_result

    # Roundtable session → response has 'replies' key
    rt_session = orchestrator.summon_session(
        db_path, vault_copy,
        page_paths=["concepts/note-a.md", "concepts/note-b.md"],
        mode="freeforall",
    )
    rt_sid = rt_session["session_id"]
    rt_result = orchestrator.say(db_path, vault_copy, session_id=rt_sid, text="hello all")
    assert "replies" in rt_result
    assert "reply" not in rt_result


# ---------------------------------------------------------------------------
# 11. summon_session — unknown mode raises SéanceError(400)
# ---------------------------------------------------------------------------

def test_summon_unknown_mode_raises_400(vault_copy, db_path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    _setup(vault_copy, db_path)
    with pytest.raises(SéanceError) as exc_info:
        orchestrator.summon_session(
            db_path, vault_copy,
            page_paths=["concepts/note-a.md"],
            mode="wibble",
        )
    assert exc_info.value.code == 400


# ---------------------------------------------------------------------------
# 12. SéanceError — code and detail attributes are accessible
# ---------------------------------------------------------------------------

def test_seance_error_attributes():
    err = SéanceError(404, "not found")
    assert err.code == 404
    assert err.detail == "not found"
    assert str(err) == "not found"

    # Also works with dict detail (502 path)
    d = {"error": "boom", "partial_replies": []}
    err2 = SéanceError(502, d)
    assert err2.code == 502
    assert err2.detail is d
