import json
from pathlib import Path
import sqlite3

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault


def test_index_vault_populates_pages(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    stats = index_vault(vault_copy, db_path)
    assert stats["pages_seen"] == 3
    assert stats["pages_updated"] == 3
    con = sqlite3.connect(str(db_path))
    rows = con.execute("SELECT path, is_public FROM pages ORDER BY path").fetchall()
    con.close()
    paths = {r[0] for r in rows}
    assert paths == {
        "concepts/note-a.md",
        "concepts/note-b.md",
        "synthesis/syn-1.md",
    }
    public_map = {r[0]: r[1] for r in rows}
    assert public_map["concepts/note-b.md"] == 1
    assert public_map["concepts/note-a.md"] == 0
    assert public_map["synthesis/syn-1.md"] == 0


def test_index_vault_populates_links(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = sqlite3.connect(str(db_path))
    rows = con.execute("SELECT from_path, to_path FROM links").fetchall()
    con.close()
    pairs = {(r[0], r[1]) for r in rows}
    assert ("concepts/note-a.md", "concepts/note-b.md") in pairs
    assert ("concepts/note-a.md", "synthesis/syn-1.md") in pairs
    assert ("concepts/note-b.md", "concepts/note-a.md") in pairs
    assert ("synthesis/syn-1.md", "concepts/note-a.md") in pairs
    assert ("synthesis/syn-1.md", "concepts/note-b.md") in pairs


def test_index_vault_skip_unchanged(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    stats2 = index_vault(vault_copy, db_path)
    assert stats2["pages_seen"] == 3
    assert stats2["pages_updated"] == 0  # nothing changed -> no updates
