"""RAG-assisted persona suggestions for the séance UI.

This module only helps pick which pages to summon. It does not add retrieved
context to the answer loop, so the existing persona and consult-neighbor
boundaries stay intact.
"""
from __future__ import annotations

from pathlib import Path

from living_vault.core import db as db_mod
from living_vault.core.embeddings import search_semantic


MAX_RAG_SUMMON_QUERY_CHARS = 1000
MAX_RAG_SUMMON_CANDIDATES = 8


class RAGSummonError(ValueError):
    """Validation error for RAG-summon requests."""

    def __init__(self, code: int, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


def _clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_RAG_SUMMON_CANDIDATES))


def suggest_personas(db_path: Path, query: str, *, limit: int = MAX_RAG_SUMMON_CANDIDATES) -> dict:
    """Return semantic page candidates that can be summoned as personas.

    The response intentionally contains metadata only: no body snippets and no
    absolute filesystem paths.
    """
    q = query.strip()
    if not q:
        raise RAGSummonError(400, "query must not be empty")
    if len(q) > MAX_RAG_SUMMON_QUERY_CHARS:
        raise RAGSummonError(
            413,
            f"query too long ({len(q)} chars, max {MAX_RAG_SUMMON_QUERY_CHARS})",
        )

    capped_limit = _clamp_limit(limit)
    con = db_mod.connect(db_path)
    try:
        rows = search_semantic(con, q, k=capped_limit)
        candidates: list[dict] = []
        for path, score in rows:
            page = con.execute(
                "SELECT path, title FROM pages WHERE path = ?",
                (path,),
            ).fetchone()
            if page is None:
                continue
            candidates.append({
                "path": page["path"],
                "title": page["title"] or Path(page["path"]).stem,
                "score": score,
                "reason": "semantic match",
            })
        return {"query": q, "candidates": candidates[:capped_limit]}
    finally:
        con.close()
