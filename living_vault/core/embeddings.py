"""Embedding backends.

Two implementations:
  - SentenceTransformerBackend: uses all-MiniLM-L6-v2 (384 dim) — preferred.
  - NumpyBackend: deterministic hash-of-tokens fallback (256 dim, normalized).

get_backend() returns the best available backend at runtime. The numpy backend
is always available; it is *not* a high-quality embedder, but it lets the
indexer and consumers run without the heavy ML dependency.
"""
from __future__ import annotations
import hashlib
import re
from typing import Iterable

import numpy as np


class BackendNotAvailable(Exception):
    pass


class _Backend:
    name: str = "abstract"
    dim: int = 0

    def encode(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class NumpyBackend(_Backend):
    """Deterministic hash-bag: tokenize, hash each token to a bucket, normalize.

    Quality: low. Purpose: works without ML deps, gives stable vectors so the
    rest of the pipeline (storage, similarity) can be tested end-to-end.
    """
    name = "numpy-hashbag"
    dim = 256

    _TOKEN = re.compile(r"[A-Za-z]{2,}")

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in self._TOKEN.findall(t.lower()):
                h = int(hashlib.blake2b(tok.encode("utf-8"), digest_size=4).hexdigest(), 16)
                out[i, h % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class SentenceTransformerBackend(_Backend):
    name = "sentence-transformers/all-MiniLM-L6-v2"
    dim = 384

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise BackendNotAvailable(f"sentence-transformers not importable: {e}")
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def encode(self, texts: list[str]) -> np.ndarray:
        v = self._model.encode(texts, normalize_embeddings=True)
        return np.asarray(v, dtype=np.float32)


def get_backend() -> _Backend:
    """Return SentenceTransformerBackend if available, else NumpyBackend."""
    try:
        return SentenceTransformerBackend()
    except BackendNotAvailable:
        return NumpyBackend()


import sqlite3
from pathlib import Path

from living_vault.core.reader import walk_vault
from living_vault.core import db as db_mod


def _vec_to_blob(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()


def _blob_to_vec(b: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32).reshape((dim,))


def index_embeddings(vault_root: Path, db_path: Path) -> int:
    """Compute and store embeddings for pages whose content_hash differs from stored.

    Returns number of pages whose embedding was (re-)computed.
    """
    backend = get_backend()
    con = db_mod.connect(db_path)
    try:
        # existing embeddings: path -> model name
        existing = {
            row["path"]: row["model"]
            for row in con.execute("SELECT path, model FROM embeddings_blob")
        }
        # current content hashes from pages table
        page_hashes = {
            row["path"]: row["content_hash"]
            for row in con.execute("SELECT path, content_hash FROM pages")
        }
        # find pages that need (re)embedding
        candidates: list[tuple[str, str]] = []  # (relpath, body)
        for page in walk_vault(vault_root):
            stored_model = existing.get(page.relpath)
            need = True
            if stored_model == backend.name:
                # same model — skip only if content_hash matches pages table
                stored_hash = page_hashes.get(page.relpath)
                if stored_hash is not None and stored_hash == page.content_hash_value:
                    need = False
            if need:
                candidates.append((page.relpath, page.body))
        if not candidates:
            return 0
        vecs = backend.encode([b for _, b in candidates])
        for (relpath, _), v in zip(candidates, vecs):
            con.execute(
                "INSERT OR REPLACE INTO embeddings_blob(path, model, dim, vector) "
                "VALUES (?, ?, ?, ?)",
                (relpath, backend.name, backend.dim, _vec_to_blob(v)),
            )
        con.commit()
        return len(candidates)
    finally:
        con.close()


def similar(
    con: sqlite3.Connection, path: str, k: int = 10
) -> list[tuple[str, float]]:
    """Return top-k similar pages (including self) ordered by descending cosine similarity."""
    row = con.execute(
        "SELECT model, dim, vector FROM embeddings_blob WHERE path = ?", (path,)
    ).fetchone()
    if row is None:
        return []
    model, dim, query_blob = row[0], row[1], row[2]
    q = _blob_to_vec(query_blob, dim)
    others = con.execute(
        "SELECT path, vector FROM embeddings_blob WHERE model = ?", (model,)
    ).fetchall()
    scored: list[tuple[str, float]] = []
    for r in others:
        v = _blob_to_vec(r[1], dim)
        scored.append((r[0], float(np.dot(q, v))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def search_semantic(
    con: sqlite3.Connection, query: str, k: int = 10
) -> list[tuple[str, float]]:
    """Encode `query` and return top-k pages by cosine similarity."""
    backend = get_backend()
    q = backend.encode([query])[0]
    rows = con.execute(
        "SELECT path, model, dim, vector FROM embeddings_blob WHERE model = ?",
        (backend.name,),
    ).fetchall()
    scored: list[tuple[str, float]] = []
    for r in rows:
        v = _blob_to_vec(r[3], r[2])
        scored.append((r[0], float(np.dot(q, v))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
