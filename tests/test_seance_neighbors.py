"""Phase-10a: consult_neighbor handler tests."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.apps.seance_ui import store
from living_vault.apps.seance_ui.neighbors import (
    BODY_EXCERPT_CHARS,
    MAX_CONSULT_CALLS_PER_TURN,
    make_consult_neighbor_handler,
)


def _setup(vault_copy: Path, db_path: Path) -> tuple[int, str]:
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    page_path = "concepts/note-a.md"
    sid = store.new_session(db_path, page_path)
    return sid, page_path


def test_handler_rejects_non_neighbor(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    out = handler("consult_neighbor", {"neighbor_path": "concepts/secret.md"})
    assert isinstance(out, dict) and out.get("is_error") is True
    assert "not a neighbor" in out["content"].lower()


def test_handler_returns_excerpt_for_allowed_neighbor(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    out = handler("consult_neighbor", {"neighbor_path": "concepts/note-b.md"})
    assert isinstance(out, str)
    assert len(out) > 0
    assert len(out) <= BODY_EXCERPT_CHARS


def test_handler_persists_tool_event(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    handler("consult_neighbor", {"neighbor_path": "concepts/note-b.md"})
    detail = store.get_session_detail(db_path, sid)
    assert any(m["role"] == "tool_use" for m in detail["messages"])
    tool_msg = next(m for m in detail["messages"] if m["role"] == "tool_use")
    payload = json.loads(tool_msg["content"])
    assert payload["tool_name"] == "consult_neighbor"
    assert payload["tool_args"]["neighbor_path"] == "concepts/note-b.md"
    assert payload["tool_result_summary"]["chars"] >= 0
    assert tool_msg["persona_path"] == page_path


def test_handler_missing_page_returns_is_error(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    # allowlist contains a path that exists in graph but file is missing
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/ghost.md"},
    )
    out = handler("consult_neighbor", {"neighbor_path": "concepts/ghost.md"})
    assert isinstance(out, dict) and out.get("is_error") is True


def test_handler_soft_cap_after_n_calls(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    # Force MAX_CONSULT_CALLS_PER_TURN successful calls, then one more
    for _ in range(MAX_CONSULT_CALLS_PER_TURN):
        out = handler("consult_neighbor", {"neighbor_path": "concepts/note-b.md"})
        assert isinstance(out, str)
    # the (N+1)th call must be is_error budget-exhausted
    out_over = handler("consult_neighbor", {"neighbor_path": "concepts/note-b.md"})
    assert isinstance(out_over, dict) and out_over.get("is_error") is True
    assert "budget" in out_over["content"].lower()


def test_handler_invalid_args_returns_is_error(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    # missing required field
    out = handler("consult_neighbor", {})
    assert isinstance(out, dict) and out.get("is_error") is True
    assert "neighbor_path" in out["content"].lower()
