"""Privacy filter: pages with frontmatter `public: true` are public, all others private."""
from __future__ import annotations
import sqlite3


def public_pages(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT path FROM pages WHERE is_public = 1 ORDER BY path"
    ).fetchall()
    return [r[0] for r in rows]


def is_public(con: sqlite3.Connection, path: str) -> bool:
    row = con.execute("SELECT is_public FROM pages WHERE path = ?", (path,)).fetchone()
    return bool(row and row[0])
