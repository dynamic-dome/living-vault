"""SQLite schema for the vault engine.

Storage: one file at ~/wiki/.vault-engine.db (default) or any explicit Path.
Embedding storage strategy is decided in core.embeddings based on spike outcome.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    path           TEXT PRIMARY KEY,
    title          TEXT,
    mtime          REAL,
    created_at     TEXT,
    updated_at     TEXT,
    frontmatter    TEXT,
    content_hash   TEXT,
    is_public      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pages_public ON pages(is_public);
CREATE INDEX IF NOT EXISTS idx_pages_mtime  ON pages(mtime);

CREATE TABLE IF NOT EXISTS links (
    from_path  TEXT NOT NULL,
    to_path    TEXT NOT NULL,
    link_text  TEXT,
    PRIMARY KEY (from_path, to_path, link_text)
);
CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_path);

CREATE TABLE IF NOT EXISTS personas (
    path           TEXT PRIMARY KEY,
    voice_sample   TEXT,
    themes         TEXT,
    era_marker     TEXT,
    hash           TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    action        TEXT NOT NULL,
    pages_seen    INTEGER DEFAULT 0,
    pages_updated INTEGER DEFAULT 0,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS embeddings_blob (
    path     TEXT PRIMARY KEY,
    model    TEXT NOT NULL,
    dim      INTEGER NOT NULL,
    vector   BLOB NOT NULL
);
"""


def initialize(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con
