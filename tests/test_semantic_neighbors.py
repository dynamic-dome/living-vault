from __future__ import annotations

from living_vault.apps.seance_ui.semantic_neighbors import semantic_neighbors_for_persona
from living_vault.core import db as db_mod
from living_vault.core import embeddings as embeddings_mod
from living_vault.core.embeddings import NumpyBackend, index_embeddings
from living_vault.core.indexer import index_vault


def test_semantic_neighbors_exclude_self_graph_neighbors_and_cap(
    vault_copy, db_path, monkeypatch
):
    for idx in range(5):
        (vault_copy / "concepts" / f"semantic-alpha-{idx}.md").write_text(
            "---\ntype: concept\nstatus: active\n---\n\n"
            f"# Semantic Alpha {idx}\n\n"
            "Alpha alpha alpha archive context with no wikilinks.\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)

    paths = semantic_neighbors_for_persona(
        db_path,
        "concepts/note-a.md",
        exclude=["concepts/note-b.md", "synesthetic-experiences/syn-1.md"],
    )

    assert len(paths) == 3
    assert "concepts/note-a.md" not in paths
    assert "concepts/note-b.md" not in paths
    assert "synesthetic-experiences/syn-1.md" not in paths
    assert all(paths.count(path) == 1 for path in paths)
