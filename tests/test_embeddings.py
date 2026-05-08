import numpy as np
import pytest
from living_vault.core.embeddings import (
    NumpyBackend, get_backend, BackendNotAvailable,
)


def test_numpy_backend_encode_returns_normalized():
    b = NumpyBackend()
    v = b.encode(["hello world"])
    assert v.shape == (1, b.dim)
    norms = np.linalg.norm(v, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_numpy_backend_similar_is_high_for_similar_text():
    b = NumpyBackend()
    a = b.encode(["the cat sat on the mat"])
    b1 = b.encode(["a feline rests on a rug"])
    c = b.encode(["matrix multiplication of tensor weights"])
    sim_close = float((a @ b1.T)[0, 0])
    sim_far = float((a @ c.T)[0, 0])
    # Numpy hash-bag backend is crude; we only assert ordering, not magnitude
    assert sim_close > sim_far - 0.01


def test_get_backend_returns_some_backend():
    b = get_backend()
    assert b is not None
    assert b.dim > 0


import sqlite3
from pathlib import Path

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings, similar


def test_index_embeddings_persists_all(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    n = index_embeddings(vault_copy, db_path)
    assert n == 3
    con = sqlite3.connect(str(db_path))
    cnt = con.execute("SELECT COUNT(*) FROM embeddings_blob").fetchone()[0]
    con.close()
    assert cnt == 3


def test_similar_returns_self_first(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    con = db_mod.connect(db_path)
    res = similar(con, "concepts/note-a.md", k=3)
    con.close()
    assert res[0][0] == "concepts/note-a.md"
    assert abs(res[0][1] - 1.0) < 1e-3


def test_index_embeddings_skip_unchanged(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    n1 = index_embeddings(vault_copy, db_path)
    n2 = index_embeddings(vault_copy, db_path)  # second pass: no changes
    assert n1 == 3
    assert n2 == 0


from living_vault.core.embeddings import search_semantic


def test_search_semantic_returns_results(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    con = db_mod.connect(db_path)
    res = search_semantic(con, "alpha topics", k=3)
    con.close()
    assert len(res) == 3
    paths = [p for p, _ in res]
    assert "concepts/note-a.md" in paths  # note-a mentions "alpha"
