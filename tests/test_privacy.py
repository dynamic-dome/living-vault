from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.privacy import allowlist_skipped, load_allowlist, public_pages


def test_public_pages_returns_only_public(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    pub = public_pages(con)
    con.close()
    assert pub == ["concepts/note-b.md"]


def test_public_pages_union_with_allowlist(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    pub = public_pages(con, allowlist=["concepts/note-a.md"])
    con.close()
    assert pub == ["concepts/note-a.md", "concepts/note-b.md"]


def test_load_allowlist_strips_comments_and_blanks(tmp_path: Path):
    f = tmp_path / "allowlist.txt"
    f.write_text("# comment\n\n   \nconcepts/note-a.md\n", encoding="utf-8")
    result = load_allowlist(f)
    assert result == ["concepts/note-a.md"]


def test_load_allowlist_handles_unicode_paths(tmp_path: Path):
    f = tmp_path / "allowlist.txt"
    f.write_text("cöncepts/Ümlaut.md\n", encoding="utf-8")
    result = load_allowlist(f)
    assert result == ["cöncepts/Ümlaut.md"]


def test_allowlist_with_nonexistent_paths_skipped_silently(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    pub = public_pages(con, allowlist=["nope.md", "concepts/note-a.md"])
    skipped = allowlist_skipped(con, ["nope.md", "concepts/note-a.md"])
    con.close()
    assert "concepts/note-a.md" in pub
    assert "nope.md" not in pub
    assert skipped == ["nope.md"]


def test_public_pages_no_duplicates_when_path_in_both_sources(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    pub = public_pages(con, allowlist=["concepts/note-b.md"])
    con.close()
    assert pub.count("concepts/note-b.md") == 1
