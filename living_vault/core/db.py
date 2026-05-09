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

CREATE TABLE IF NOT EXISTS seance_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    page_path   TEXT NOT NULL,
    started_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seance_page ON seance_sessions(page_path);

CREATE TABLE IF NOT EXISTS seance_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES seance_sessions(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seance_msgs_session ON seance_messages(session_id);
"""


# Phase-9 additive columns. SQLite has no `ADD COLUMN IF NOT EXISTS` —
# we probe with PRAGMA table_info first.
_PHASE_9_PAGES_COLUMNS = [
    ("voice_features", "TEXT"),    # JSON blob, deterministic stylometric
    ("voice_distilled", "TEXT"),   # 3-5 sentence LLM voice description, NULL until extract-voice runs
]

# Phase-10a additive columns for seance_messages.
_PHASE_10A_SEANCE_MESSAGES_COLUMNS = [
    ("persona_path", "TEXT"),  # NULL for user messages, set for assistant + tool_use
]

# Phase-10b additive columns + new tables.
_PHASE_10B_SEANCE_SESSIONS_COLUMNS = [
    ("mode", "TEXT NOT NULL DEFAULT 'single'"),
]

_PHASE_10B_NEW_TABLES = """
CREATE TABLE IF NOT EXISTS seance_session_personas (
    session_id   INTEGER NOT NULL REFERENCES seance_sessions(id),
    persona_path TEXT NOT NULL,
    color        TEXT NOT NULL,
    seat_idx     INTEGER NOT NULL,
    PRIMARY KEY (session_id, persona_path)
);
CREATE INDEX IF NOT EXISTS idx_ssp_session ON seance_session_personas(session_id);
"""


def _column_exists(con: sqlite3.Connection, table: str, col: str) -> bool:
    return any(r[1] == col for r in con.execute(f"PRAGMA table_info({table})"))


def initialize(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(SCHEMA)
        # Note: executescript issues an implicit COMMIT before running. ALTER TABLE in SQLite
        # is auto-committed; the con.commit() below is a no-op safety net. Migration is safe-to-retry
        # because _column_exists() guards each ADD COLUMN. Do NOT add non-DDL logic here expecting rollback.
        for col, sqltype in _PHASE_9_PAGES_COLUMNS:
            if not _column_exists(con, "pages", col):
                con.execute(f"ALTER TABLE pages ADD COLUMN {col} {sqltype}")
        for col, sqltype in _PHASE_10A_SEANCE_MESSAGES_COLUMNS:
            if not _column_exists(con, "seance_messages", col):
                con.execute(f"ALTER TABLE seance_messages ADD COLUMN {col} {sqltype}")
        # Phase-10b: new tables (idempotent via IF NOT EXISTS)
        con.executescript(_PHASE_10B_NEW_TABLES)
        # Phase-10b: additive columns on seance_sessions
        for col, sqltype in _PHASE_10B_SEANCE_SESSIONS_COLUMNS:
            if not _column_exists(con, "seance_sessions", col):
                con.execute(f"ALTER TABLE seance_sessions ADD COLUMN {col} {sqltype}")
        con.commit()
    finally:
        con.close()


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con
