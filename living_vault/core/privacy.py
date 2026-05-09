"""Privacy filter: pages with frontmatter `public: true` are public, all others private."""
from __future__ import annotations
import sqlite3
from pathlib import Path


def public_pages(con: sqlite3.Connection, allowlist: list[str] | None = None) -> list[str]:
    """Pages that are public via frontmatter (is_public=1) OR via allowlist.

    Returns sorted, deduplicated list.
    """
    if not allowlist:
        rows = con.execute(
            "SELECT path FROM pages WHERE is_public = 1 ORDER BY path"
        ).fetchall()
        return [r[0] for r in rows]
    placeholders = ",".join("?" * len(allowlist))
    rows = con.execute(
        f"SELECT path FROM pages WHERE is_public = 1 OR path IN ({placeholders}) ORDER BY path",
        allowlist,
    ).fetchall()
    return [r[0] for r in rows]


def load_allowlist(path: Path) -> list[str]:
    """Parse allowlist file. One relpath per line.

    Lines starting with '#' are comments (skipped).
    Empty/whitespace-only lines are skipped.
    Trailing/leading whitespace stripped from each path.
    Returns ordered list (file order preserved, no dedup at parse time).
    """
    result: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            result.append(stripped)
    return result


def allowlist_skipped(con: sqlite3.Connection, allowlist: list[str]) -> list[str]:
    """Paths in allowlist that don't exist in pages table.

    Returns sorted list, no duplicates.
    """
    if not allowlist:
        return []
    placeholders = ",".join("?" * len(allowlist))
    rows = con.execute(
        f"SELECT path FROM pages WHERE path IN ({placeholders})",
        allowlist,
    ).fetchall()
    existing = {r[0] for r in rows}
    return sorted(set(allowlist) - existing)


def is_public(con: sqlite3.Connection, path: str) -> bool:
    row = con.execute("SELECT is_public FROM pages WHERE path = ?", (path,)).fetchone()
    return bool(row and row[0])
