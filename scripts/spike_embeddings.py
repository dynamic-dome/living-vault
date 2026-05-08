"""Spike: verify sentence-transformers + sqlite-vec on Windows.

Exit codes:
  0 - both libraries work; use them
  1 - sentence-transformers fails; fall back to numpy+cosine
  2 - sqlite-vec fails; embeddings work but BLOB-column fallback needed
  3 - both fail; numpy+cosine + BLOB column
"""
from __future__ import annotations
import sys
import sqlite3
import tempfile
from pathlib import Path


def try_sentence_transformers() -> bool:
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer("all-MiniLM-L6-v2")
        v = m.encode(["hello world"], normalize_embeddings=True)
        ok = v.shape == (1, 384)
        print(f"[st] OK shape={v.shape}")
        return ok
    except Exception as e:
        print(f"[st] FAIL {type(e).__name__}: {e}")
        return False


def try_sqlite_vec() -> bool:
    try:
        import sqlite_vec
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.db"
            con = sqlite3.connect(str(p))
            con.enable_load_extension(True)
            sqlite_vec.load(con)
            con.execute("CREATE VIRTUAL TABLE v USING vec0(embedding float[384])")
            con.close()
        print("[vec] OK")
        return True
    except Exception as e:
        print(f"[vec] FAIL {type(e).__name__}: {e}")
        return False


def main() -> int:
    st_ok = try_sentence_transformers()
    vec_ok = try_sqlite_vec()
    if st_ok and vec_ok:
        return 0
    if not st_ok and vec_ok:
        return 1
    if st_ok and not vec_ok:
        return 2
    return 3


if __name__ == "__main__":
    sys.exit(main())
