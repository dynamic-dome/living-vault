"""RAG-assisted roundtable suggestions for the séance UI."""
from __future__ import annotations

from pathlib import Path

from living_vault.apps.seance_ui.rag_summon import (
    MAX_RAG_SUMMON_QUERY_CHARS,
    RAGSummonError,
)
from living_vault.core import db as db_mod
from living_vault.core.embeddings import search_semantic
from living_vault.core.graph import neighbors as graph_neighbors


MAX_CONSTELLATIONS = 3
MAX_CONSTELLATION_SIZE = 5


def _clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_CONSTELLATIONS))


def _clamp_size(size: int) -> int:
    return max(2, min(int(size), MAX_CONSTELLATION_SIZE))


def _validate_query(query: str) -> str:
    q = query.strip()
    if not q:
        raise RAGSummonError(400, "query must not be empty")
    if len(q) > MAX_RAG_SUMMON_QUERY_CHARS:
        raise RAGSummonError(
            413,
            f"query too long ({len(q)} chars, max {MAX_RAG_SUMMON_QUERY_CHARS})",
        )
    return q


def _titles_for_paths(con, paths: list[str]) -> list[str]:
    titles: list[str] = []
    for path in paths:
        row = con.execute("SELECT title FROM pages WHERE path = ?", (path,)).fetchone()
        titles.append((row["title"] if row and row["title"] else Path(path).stem))
    return titles


def suggest_constellations(
    db_path: Path,
    query: str,
    *,
    limit: int = MAX_CONSTELLATIONS,
    size: int = 3,
) -> dict:
    """Return metadata-only candidate circles for a query."""
    q = _validate_query(query)
    capped_limit = _clamp_limit(limit)
    capped_size = _clamp_size(size)

    con = db_mod.connect(db_path)
    try:
        semantic_rows = [
            (path, score)
            for path, score in search_semantic(con, q, k=max(12, capped_limit * capped_size * 2))
            if score > 0
            and con.execute("SELECT 1 FROM pages WHERE path = ?", (path,)).fetchone()
            is not None
        ]
        semantic_paths = [path for path, _ in semantic_rows]
        constellations: list[dict] = []
        seen_groups: set[tuple[str, ...]] = set()

        for seed in semantic_paths:
            group: list[str] = [seed]
            for nbr in graph_neighbors(con, seed):
                if nbr not in group:
                    group.append(nbr)
                if len(group) >= capped_size:
                    break
            for candidate in semantic_paths:
                if candidate not in group:
                    group.append(candidate)
                if len(group) >= capped_size:
                    break
            if len(group) < 2:
                continue
            key = tuple(sorted(group))
            if key in seen_groups:
                continue
            seen_groups.add(key)
            titles = _titles_for_paths(con, group)
            constellations.append({
                "label": f"{Path(group[0]).stem} + {len(group) - 1}",
                "reason": "semantic seed with graph and archive complements",
                "paths": group,
                "titles": titles,
            })
            if len(constellations) >= capped_limit:
                break
        return {"query": q, "constellations": constellations}
    finally:
        con.close()
