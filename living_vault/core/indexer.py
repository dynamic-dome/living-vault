"""Indexer: walk vault, populate pages + links tables, skip unchanged content."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from living_vault.core.reader import walk_vault, Page
from living_vault.core.graph import extract_wikilinks, resolve_target
from living_vault.core import db as db_mod


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def index_vault(vault_root: Path, db_path: Path) -> dict[str, int]:
    """Index every page under vault_root into db_path. Returns stats dict."""
    con = db_mod.connect(db_path)
    started = _utcnow()
    pages_seen = 0
    pages_updated = 0
    seen_paths: set[str] = set()
    gone: set[str] = set()
    try:
        existing = {
            row["path"]: row["content_hash"]
            for row in con.execute("SELECT path, content_hash FROM pages")
        }
        for page in walk_vault(vault_root):
            pages_seen += 1
            seen_paths.add(page.relpath)
            if existing.get(page.relpath) == page.content_hash_value:
                continue  # unchanged
            _upsert_page(con, page)
            _replace_links(con, page)
            pages_updated += 1
        # remove pages that no longer exist on disk
        gone = set(existing) - seen_paths
        for p in gone:
            con.execute("DELETE FROM pages WHERE path = ?", (p,))
            con.execute("DELETE FROM links WHERE from_path = ?", (p,))
        con.execute(
            "INSERT INTO runs(started_at, finished_at, action, pages_seen, pages_updated) "
            "VALUES (?, ?, ?, ?, ?)",
            (started, _utcnow(), "index_vault", pages_seen, pages_updated),
        )
        con.commit()
    finally:
        con.close()
    return {"pages_seen": pages_seen, "pages_updated": pages_updated, "pages_gone": len(gone)}


def _upsert_page(con: sqlite3.Connection, page: Page) -> None:
    con.execute(
        """
        INSERT INTO pages(path, title, mtime, created_at, updated_at,
                          frontmatter, content_hash, is_public)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            title=excluded.title,
            mtime=excluded.mtime,
            created_at=excluded.created_at,
            updated_at=excluded.updated_at,
            frontmatter=excluded.frontmatter,
            content_hash=excluded.content_hash,
            is_public=excluded.is_public
        """,
        (
            page.relpath,
            page.title,
            page.mtime,
            str(page.frontmatter.get("created", "")),
            str(page.frontmatter.get("updated", "")),
            json.dumps(page.frontmatter, default=str),
            page.content_hash_value,
            int(page.is_public),
        ),
    )


def _replace_links(con: sqlite3.Connection, page: Page) -> None:
    con.execute("DELETE FROM links WHERE from_path = ?", (page.relpath,))
    for target, alias in extract_wikilinks(page.body):
        resolved = resolve_target(target)
        if resolved is None:
            continue
        con.execute(
            "INSERT OR IGNORE INTO links(from_path, to_path, link_text) VALUES (?, ?, ?)",
            (page.relpath, resolved, alias),
        )
