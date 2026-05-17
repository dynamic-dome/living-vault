"""Phase-9 DB migration: voice_features + voice_distilled columns must be added
to legacy DBs without data loss.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

from living_vault.core import db as db_mod


def _legacy_pages_schema() -> str:
    """The Phase-1 schema for `pages` (without voice_* columns)."""
    return """
    CREATE TABLE pages (
        path           TEXT PRIMARY KEY,
        title          TEXT,
        mtime          REAL,
        created_at     TEXT,
        updated_at     TEXT,
        frontmatter    TEXT,
        content_hash   TEXT,
        is_public      INTEGER NOT NULL DEFAULT 0
    );
    """


def test_initialize_adds_voice_columns_to_legacy_pages_table(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    # arrange: write a legacy DB with one pre-existing page row
    con = sqlite3.connect(str(db_path))
    con.executescript(_legacy_pages_schema())
    con.execute(
        "INSERT INTO pages (path, title, content_hash, is_public) "
        "VALUES (?, ?, ?, ?)",
        ("legacy.md", "Legacy", "deadbeef", 1),
    )
    con.commit()
    con.close()

    # act: run Phase-9 initialize on the legacy DB
    db_mod.initialize(db_path)

    # assert: columns now exist, original row preserved
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(pages)")}
    assert "voice_features" in cols
    assert "voice_distilled" in cols
    row = con.execute(
        "SELECT path, title, voice_features, voice_distilled FROM pages "
        "WHERE path = ?",
        ("legacy.md",),
    ).fetchone()
    assert row[0] == "legacy.md"
    assert row[1] == "Legacy"
    assert row[2] is None  # voice_features
    assert row[3] is None  # voice_distilled
    con.close()


def test_initialize_is_idempotent_on_phase9_schema(tmp_path: Path):
    """Running initialize() twice on an already-migrated DB must not raise."""
    db_path = tmp_path / ".vault-engine.db"
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call — must NOT try to re-add columns
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(pages)")}
    assert "voice_features" in cols
    assert "voice_distilled" in cols
    con.close()


def test_initialize_adds_persona_path_to_legacy_seance_messages(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    # arrange: legacy DB with seance_messages but without persona_path
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE seance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_path TEXT NOT NULL,
            started_at TEXT NOT NULL
        );
        CREATE TABLE seance_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES seance_sessions(id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    con.execute(
        "INSERT INTO seance_sessions (page_path, started_at) VALUES (?, ?)",
        ("legacy/page.md", "2026-05-08T00:00:00Z"),
    )
    con.execute(
        "INSERT INTO seance_messages (session_id, role, content, created_at) "
        "VALUES (?, ?, ?, ?)",
        (1, "user", "hello", "2026-05-08T00:00:00Z"),
    )
    con.commit()
    con.close()

    # act
    db_mod.initialize(db_path)

    # assert: column exists, legacy row preserved with NULL persona_path
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(seance_messages)")}
    assert "persona_path" in cols
    row = con.execute(
        "SELECT role, content, persona_path FROM seance_messages WHERE id = 1"
    ).fetchone()
    assert row[0] == "user"
    assert row[1] == "hello"
    assert row[2] is None
    con.close()


def test_initialize_persona_path_idempotent(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call must not raise duplicate-column
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(seance_messages)")}
    assert "persona_path" in cols
    con.close()


def test_initialize_adds_mode_to_legacy_seance_sessions(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    # arrange: legacy DB with seance_sessions but without mode
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE seance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_path TEXT NOT NULL,
            started_at TEXT NOT NULL
        );
    """)
    con.execute(
        "INSERT INTO seance_sessions (page_path, started_at) VALUES (?, ?)",
        ("legacy/page.md", "2026-05-08T00:00:00Z"),
    )
    con.commit()
    con.close()

    # act
    db_mod.initialize(db_path)

    # assert: column added, legacy row has default 'single'
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(seance_sessions)")}
    assert "mode" in cols
    row = con.execute(
        "SELECT page_path, mode FROM seance_sessions WHERE id = 1"
    ).fetchone()
    assert row[0] == "legacy/page.md"
    assert row[1] == "single"
    con.close()


def test_initialize_creates_seance_session_personas_table(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    db_mod.initialize(db_path)

    con = sqlite3.connect(str(db_path))
    # table exists
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "seance_session_personas" in tables

    # columns match spec
    cols = {r[1] for r in con.execute(
        "PRAGMA table_info(seance_session_personas)"
    )}
    assert cols == {"session_id", "persona_path", "color", "seat_idx"}

    # primary key on (session_id, persona_path)
    pk_cols = [
        r[1] for r in con.execute("PRAGMA table_info(seance_session_personas)")
        if r[5] > 0  # pk column index > 0 means part of PK
    ]
    assert set(pk_cols) == {"session_id", "persona_path"}
    con.close()


def test_phase_10b_migrations_idempotent(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call must not raise
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(seance_sessions)")}
    assert "mode" in cols
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "seance_session_personas" in tables
    con.close()


def test_initialize_adds_content_hash_to_legacy_embeddings_blob(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE embeddings_blob (
            path     TEXT PRIMARY KEY,
            model    TEXT NOT NULL,
            dim      INTEGER NOT NULL,
            vector   BLOB NOT NULL
        );
    """)
    con.execute(
        "INSERT INTO embeddings_blob(path, model, dim, vector) VALUES (?, ?, ?, ?)",
        ("legacy.md", "numpy-hashbag", 1, b"\x00\x00\x00\x00"),
    )
    con.commit()
    con.close()

    db_mod.initialize(db_path)
    db_mod.initialize(db_path)

    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(embeddings_blob)")}
    assert "content_hash" in cols
    row = con.execute(
        "SELECT path, model, content_hash FROM embeddings_blob WHERE path = ?",
        ("legacy.md",),
    ).fetchone()
    assert row[0] == "legacy.md"
    assert row[1] == "numpy-hashbag"
    assert row[2] is None
    con.close()
