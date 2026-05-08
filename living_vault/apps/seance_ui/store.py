"""Persistence for séance conversations."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from living_vault.core import db as db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session(db_path: Path, page_path: str) -> int:
    con = db_mod.connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO seance_sessions(page_path, started_at) VALUES (?, ?)",
            (page_path, _now()),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def add_message(db_path: Path, session_id: int, role: str, content: str) -> None:
    con = db_mod.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seance_messages(session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )
        con.commit()
    finally:
        con.close()


def get_history(db_path: Path, session_id: int) -> list[tuple[str, str]]:
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT role, content FROM seance_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [(r["role"], r["content"]) for r in rows]
    finally:
        con.close()


def list_sessions(db_path: Path) -> list[dict]:
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT id, page_path, started_at FROM seance_sessions ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
