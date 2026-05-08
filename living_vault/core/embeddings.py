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
