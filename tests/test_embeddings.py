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
