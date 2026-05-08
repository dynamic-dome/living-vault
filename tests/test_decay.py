import time
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.decay import stale_pages


def test_stale_pages_returns_old(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    # backdate one file
    target = vault_copy / "concepts" / "note-a.md"
    old = time.time() - 90 * 86400  # 90 days ago
    import os
    os.utime(target, (old, old))
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    stale = stale_pages(con, days=60)
    con.close()
    assert "concepts/note-a.md" in stale


def test_stale_pages_excludes_recent(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    stale = stale_pages(con, days=60)
    con.close()
    # all fixture files are fresh in the copy (mtime = now)
    assert stale == []
