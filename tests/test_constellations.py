from pathlib import Path

import pytest

from living_vault.apps.seance_ui.constellations import suggest_constellations
from living_vault.apps.seance_ui.rag_summon import RAGSummonError
from living_vault.core import db as db_mod
from living_vault.core import embeddings as embeddings_mod
from living_vault.core.embeddings import NumpyBackend, index_embeddings
from living_vault.core.indexer import index_vault


def test_suggest_constellations_groups_seed_with_complements(
    vault_copy: Path,
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)

    out = suggest_constellations(db_path, "alpha topics", limit=3, size=3)

    assert out["query"] == "alpha topics"
    assert out["constellations"]
    first = out["constellations"][0]
    assert set(first) == {"label", "reason", "paths", "titles"}
    assert 2 <= len(first["paths"]) <= 3
    assert len(first["paths"]) == len(set(first["paths"]))
    assert len(first["titles"]) == len(first["paths"])
    assert "concepts/note-a.md" in first["paths"]


def test_suggest_constellations_rejects_empty_query(db_path: Path):
    with pytest.raises(RAGSummonError) as exc_info:
        suggest_constellations(db_path, "   ")

    assert exc_info.value.code == 400
    assert "empty" in exc_info.value.detail


def test_suggest_constellations_returns_empty_without_embeddings(
    vault_copy: Path,
    db_path: Path,
):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    out = suggest_constellations(db_path, "alpha topics", limit=3, size=3)

    assert out == {"query": "alpha topics", "constellations": []}
