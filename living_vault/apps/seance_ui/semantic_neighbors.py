"""Semantic-neighbor selection for opt-in séance sessions."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from living_vault.core import db as db_mod
from living_vault.core.embeddings import similar


MAX_SEMANTIC_NEIGHBORS = 3


def semantic_neighbors_for_persona(
    db_path: Path,
    persona_path: str,
    *,
    exclude: Iterable[str] = (),
    limit: int = MAX_SEMANTIC_NEIGHBORS,
) -> list[str]:
    """Return opt-in semantic archive paths for one persona.

    Paths are metadata only; callers still need the existing allowlisted
    consult_neighbor tool to read excerpts.
    """
    blocked = {persona_path, *exclude}
    cap = max(0, min(limit, MAX_SEMANTIC_NEIGHBORS))
    if cap == 0:
        return []

    con = db_mod.connect(db_path)
    try:
        rows = similar(con, persona_path, k=cap + len(blocked) + 4)
        out: list[str] = []
        for path, score in rows:
            if path in blocked or score <= 0:
                continue
            page = con.execute("SELECT 1 FROM pages WHERE path = ?", (path,)).fetchone()
            if page is None:
                continue
            out.append(path)
            if len(out) >= cap:
                break
        return out
    finally:
        con.close()
