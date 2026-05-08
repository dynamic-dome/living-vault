from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.privacy import public_pages


def test_public_pages_returns_only_public(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    pub = public_pages(con)
    con.close()
    assert pub == ["concepts/note-b.md"]
