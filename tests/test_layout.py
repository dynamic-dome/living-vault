from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.apps.synesthesia.layout import compute_layout


def test_compute_layout_returns_one_node_per_page(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    nodes, edges = compute_layout(db_path, public_only=False)
    assert len(nodes) == 3
    paths = {n["path"] for n in nodes}
    assert paths == {
        "concepts/note-a.md",
        "concepts/note-b.md",
        "synthesis/syn-1.md",
    }


def test_compute_layout_public_only_filters(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    nodes, _ = compute_layout(db_path, public_only=True)
    assert len(nodes) == 1
    assert nodes[0]["path"] == "concepts/note-b.md"


def test_compute_layout_node_has_xyz(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    nodes, _ = compute_layout(db_path, public_only=False)
    for n in nodes:
        assert isinstance(n["x"], float)
        assert isinstance(n["y"], float)
        assert isinstance(n["z"], float)


def test_compute_layout_edges_are_existing_links(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    nodes, edges = compute_layout(db_path, public_only=False)
    pairs = {(e["from"], e["to"]) for e in edges}
    assert ("concepts/note-a.md", "concepts/note-b.md") in pairs
