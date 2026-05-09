"""Persistence for séance conversations."""
from __future__ import annotations
import json as _json
from datetime import datetime, timezone
from pathlib import Path

from living_vault.core import db as db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session(db_path: Path, page_path: str, mode: str = "single") -> int:
    con = db_mod.connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO seance_sessions(page_path, started_at, mode) VALUES (?, ?, ?)",
            (page_path, _now(), mode),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def add_message(
    db_path: Path,
    session_id: int,
    role: str,
    content: str,
    persona_path: str | None = None,
) -> None:
    con = db_mod.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seance_messages(session_id, role, content, created_at, persona_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, _now(), persona_path),
        )
        con.commit()
    finally:
        con.close()


def add_tool_event(
    db_path: Path,
    session_id: int,
    *,
    persona_path: str,
    tool_name: str,
    tool_args: dict,
    tool_result_summary: dict,
) -> None:
    """Persist a tool-use event as a seance_messages row with role='tool_use'.

    The content column carries a JSON payload {tool_name, tool_args, tool_result_summary}
    so the UI and exporter can render it without parsing free-form text.
    """
    payload = _json.dumps({
        "tool_name": tool_name,
        "tool_args": tool_args,
        "tool_result_summary": tool_result_summary,
    })
    con = db_mod.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seance_messages(session_id, role, content, created_at, persona_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, "tool_use", payload, _now(), persona_path),
        )
        con.commit()
    finally:
        con.close()


def get_history(db_path: Path, session_id: int) -> list[tuple[str, str]]:
    """Return only user + assistant messages for LLM replay.

    Tool-use rows are intentionally excluded (Phase-10a asymmetry: DB has everything,
    replay has only user+assistant). The full transcript is available via
    get_session_detail for export and UI rendering.
    """
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT role, content FROM seance_messages "
            "WHERE session_id = ? AND role IN ('user', 'assistant') "
            "ORDER BY id",
            (session_id,),
        ).fetchall()
        return [(r["role"], r["content"]) for r in rows]
    finally:
        con.close()


def list_sessions(db_path: Path) -> list[dict]:
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT s.id, s.page_path, s.started_at,
                   COUNT(m.id) AS message_count,
                   MAX(m.created_at) AS last_message_at
            FROM seance_sessions s
            LEFT JOIN seance_messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_session_detail(db_path: Path, session_id: int) -> dict | None:
    """Return {id, page_path, started_at, messages: [{role, content, persona_path}, ...]} or None."""
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT id, page_path, started_at FROM seance_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        msg_rows = con.execute(
            "SELECT role, content, created_at, persona_path FROM seance_messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return {
            "id": row["id"],
            "page_path": row["page_path"],
            "started_at": row["started_at"],
            "messages": [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "persona_path": r["persona_path"],
                }
                for r in msg_rows
            ],
        }
    finally:
        con.close()


def add_session_persona(
    db_path: Path,
    session_id: int,
    persona_path: str,
    *,
    color: str,
    seat_idx: int,
) -> None:
    con = db_mod.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seance_session_personas(session_id, persona_path, color, seat_idx) "
            "VALUES (?, ?, ?, ?)",
            (session_id, persona_path, color, seat_idx),
        )
        con.commit()
    finally:
        con.close()


def get_session_personas(db_path: Path, session_id: int) -> list[dict]:
    """Return personas in seat order. Each row: {persona_path, color, seat_idx}."""
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT persona_path, color, seat_idx FROM seance_session_personas "
            "WHERE session_id = ? ORDER BY seat_idx",
            (session_id,),
        ).fetchall()
        return [
            {"persona_path": r["persona_path"], "color": r["color"], "seat_idx": r["seat_idx"]}
            for r in rows
        ]
    finally:
        con.close()


def count_user_turns(db_path: Path, session_id: int) -> int:
    """How many user-role messages exist in this session."""
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM seance_messages "
            "WHERE session_id = ? AND role = 'user'",
            (session_id,),
        ).fetchone()
        return int(row[0])
    finally:
        con.close()


def get_session_mode(db_path: Path, session_id: int) -> str | None:
    """Return the mode of a session, or None if session not found."""
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT mode FROM seance_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return row["mode"] if row else None
    finally:
        con.close()
