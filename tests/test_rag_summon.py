from pathlib import Path

import pytest

from living_vault.apps.seance_ui.rag_summon import (
    MAX_RAG_SUMMON_CANDIDATES,
    RAGSummonError,
    suggest_personas,
)
from living_vault.core import db as db_mod
from living_vault.core import embeddings as embeddings_mod
from living_vault.core.embeddings import NumpyBackend, index_embeddings
from living_vault.core.indexer import index_vault


def test_suggest_personas_returns_semantic_candidates(
    vault_copy: Path,
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)

    out = suggest_personas(db_path, "alpha topics", limit=8)

    assert out["query"] == "alpha topics"
    paths = [c["path"] for c in out["candidates"]]
    assert "concepts/note-a.md" in paths
    first = out["candidates"][0]
    assert set(first) == {"path", "title", "score", "reason"}
    assert first["reason"] == "semantic match"


def test_suggest_personas_rejects_empty_query(db_path: Path):
    with pytest.raises(RAGSummonError) as exc_info:
        suggest_personas(db_path, "   ")

    assert exc_info.value.code == 400
    assert "empty" in exc_info.value.detail


def test_suggest_personas_rejects_oversized_query(db_path: Path):
    huge_query = "x" * 1001

    with pytest.raises(RAGSummonError) as exc_info:
        suggest_personas(db_path, huge_query)

    assert exc_info.value.code == 413
    assert "too long" in exc_info.value.detail


def test_suggest_personas_caps_limit_to_eight(
    vault_copy: Path,
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)

    out = suggest_personas(db_path, "topics", limit=99)

    assert len(out["candidates"]) <= MAX_RAG_SUMMON_CANDIDATES


def test_suggest_personas_returns_empty_without_embeddings(
    vault_copy: Path,
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    out = suggest_personas(db_path, "alpha topics", limit=8)

    assert out == {"query": "alpha topics", "candidates": []}
