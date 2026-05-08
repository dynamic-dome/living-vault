"""Staleness detection based on mtime."""
from __future__ import annotations
import sqlite3
import time


def stale_pages(con: sqlite3.Connection, days: int) -> list[str]:
    """Return relpaths of pages whose mtime is older than `days` days."""
    cutoff = time.time() - days * 86400
    rows = con.execute(
        "SELECT path FROM pages WHERE mtime < ? ORDER BY path",
        (cutoff,),
    ).fetchall()
    return [r[0] for r in rows]
