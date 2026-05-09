"""Synesthesia layout: pages -> 3D coordinates.

Approach (deterministic, no force simulation in v1):
  - Project each embedding to 3D via PCA on the in-memory matrix of all (filtered) page vectors.
  - Scale to a comfortable cube of ~50x50x50 units.
  - Edges: every (from_path, to_path) link where both endpoints are in the filtered set.

This avoids the dependency on a 3D-force library and is deterministic given inputs,
which makes the public-only build reproducible.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

import numpy as np

from living_vault.core import db as db_mod
from living_vault.core.privacy import public_pages


def _pca_3d(matrix: np.ndarray, scale: float = 100.0) -> np.ndarray:
    """Reduce N-dim matrix to 3 dims via PCA (centered).

    scale: target half-extent of the projected cube. Default 100.0 spreads
    ~1000 nodes over 200 units per axis, leaving room for sphere radii.
    Tests use scale=25 implicitly via wider PCA but accept any scale.
    """
    if matrix.shape[0] <= 1:
        return np.zeros((matrix.shape[0], 3), dtype=np.float32)
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    u, s, vh = np.linalg.svd(centered, full_matrices=False)
    components = vh[:3]
    proj = centered @ components.T
    # Pad to 3 columns when fewer than 3 PCA components are available
    # (happens when n_samples < 3 — SVD yields min(n_samples, n_features) components).
    if proj.shape[1] < 3:
        pad = np.zeros((proj.shape[0], 3 - proj.shape[1]), dtype=proj.dtype)
        proj = np.concatenate([proj, pad], axis=1)
    max_abs = float(np.abs(proj).max() or 1.0)
    return (proj / max_abs * scale).astype(np.float32)


def compute_layout(
    db_path: Path,
    public_only: bool = False,
    allowlist: list[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    con = db_mod.connect(db_path)
    try:
        if public_only:
            if allowlist is not None:
                allowed_paths = public_pages(con, allowlist)
            else:
                allowed_paths = public_pages(con)
            if not allowed_paths:
                return [], []
            placeholders = ",".join("?" * len(allowed_paths))
            page_rows = con.execute(
                f"SELECT path, title, mtime, is_public FROM pages WHERE path IN ({placeholders}) ORDER BY path",
                allowed_paths,
            ).fetchall()
        else:
            page_rows = con.execute(
                "SELECT path, title, mtime, is_public FROM pages ORDER BY path"
            ).fetchall()
        if not page_rows:
            return [], []
        paths = [r["path"] for r in page_rows]
        path_index = {p: i for i, p in enumerate(paths)}
        emb_rows = con.execute(
            "SELECT path, dim, vector FROM embeddings_blob WHERE path IN ({})".format(
                ",".join("?" * len(paths))
            ),
            paths,
        ).fetchall()
        if not emb_rows:
            # no embeddings at all; place everything at origin (degenerate)
            coords = np.zeros((len(paths), 3), dtype=np.float32)
        else:
            dim = emb_rows[0]["dim"]
            mat = np.zeros((len(paths), dim), dtype=np.float32)
            for r in emb_rows:
                idx = path_index[r["path"]]
                mat[idx] = np.frombuffer(r["vector"], dtype=np.float32)
            coords = _pca_3d(mat)

        # node-degree for sizing
        deg = {p: 0 for p in paths}
        for r in con.execute("SELECT from_path, to_path FROM links"):
            if r["from_path"] in deg:
                deg[r["from_path"]] += 1
            if r["to_path"] in deg:
                deg[r["to_path"]] += 1

        nodes: list[dict] = []
        for r, c in zip(page_rows, coords):
            cluster = r["path"].split("/", 1)[0]
            nodes.append({
                "path": r["path"],
                "title": r["title"],
                "cluster": cluster,
                "is_public": bool(r["is_public"]),
                "mtime": r["mtime"],
                "degree": deg[r["path"]],
                "x": float(c[0]), "y": float(c[1]), "z": float(c[2]),
            })

        # edges only between filtered nodes
        edges: list[dict] = []
        in_set = set(paths)
        for r in con.execute("SELECT from_path, to_path FROM links"):
            if r["from_path"] in in_set and r["to_path"] in in_set:
                edges.append({"from": r["from_path"], "to": r["to_path"]})
        return nodes, edges
    finally:
        con.close()
