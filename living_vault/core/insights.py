"""Insights — persisted reflections gained from séance sessions.

Phase-12 addition. The `insights` table is created in core.db.SCHEMA;
this module is the only writer/reader for it.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from living_vault.core import db as db_mod


_LIST_LIMIT_CAP = 100
_DEFAULT_LIST_LIMIT = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_session_id(con, session_id: int) -> None:
    row = con.execute(
        "SELECT 1 FROM seance_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"session_id {session_id} does not exist")


def insert_insight(
    db_path: Path,
    *,
    page_path: str,
    persona_path: str,
    question: str,
    insight: str,
    session_id: int | None = None,
) -> int:
    """Persist one insight; returns the new insight_id.

    Raises ValueError on empty fields or invalid session_id.
    """
    page_path = page_path.strip()
    persona_path = persona_path.strip()
    question = question.strip()
    insight = insight.strip()
    if not (page_path and persona_path and question and insight):
        raise ValueError(
            "page_path, persona_path, question, and insight must be non-empty"
        )

    con = db_mod.connect(db_path)
    try:
        if session_id is not None:
            _validate_session_id(con, session_id)
        cur = con.execute(
            "INSERT INTO insights"
            "(page_path, persona_path, question, insight, session_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (page_path, persona_path, question, insight, session_id, _now()),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def get_insight(db_path: Path, insight_id: int) -> dict | None:
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT id, page_path, persona_path, question, insight, "
            "session_id, created_at FROM insights WHERE id = ?",
            (insight_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def list_insights(
    db_path: Path,
    *,
    page_path: str | None = None,
    persona_path: str | None = None,
    limit: int = _DEFAULT_LIST_LIMIT,
) -> list[dict]:
    """Recent insights ordered by created_at DESC, optionally filtered."""
    if limit < 1:
        limit = 1
    if limit > _LIST_LIMIT_CAP:
        limit = _LIST_LIMIT_CAP

    clauses: list[str] = []
    params: list = []
    if page_path is not None:
        clauses.append("page_path = ?")
        params.append(page_path)
    if persona_path is not None:
        clauses.append("persona_path = ?")
        params.append(persona_path)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            f"SELECT id, page_path, persona_path, question, insight, "
            f"session_id, created_at FROM insights {where} "
            f"ORDER BY created_at DESC, id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
