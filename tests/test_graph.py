from living_vault.core.graph import extract_wikilinks


def test_extract_wikilinks_single():
    body = "see [[wiki/concepts/foo]] and [[wiki/concepts/bar]]."
    links = extract_wikilinks(body)
    assert ("wiki/concepts/foo", None) in links
    assert ("wiki/concepts/bar", None) in links


def test_extract_wikilinks_with_alias():
    body = "see [[wiki/synthesis/abc|the synthesis]]"
    links = extract_wikilinks(body)
    assert ("wiki/synthesis/abc", "the synthesis") in links


def test_extract_wikilinks_handles_escaped_pipe_in_alias():
    # Phase-11 follow-up #1: source markdown sometimes escapes the alias pipe
    # as "\|". The escape backslash must NOT leak into the target path (which
    # produced a broken edge "...barkhausenrauschen\.md" in the live DB).
    body = "[[wiki/concepts/barkhausenrauschen\\|Barkhausenrauschen]]"
    links = extract_wikilinks(body)
    assert ("wiki/concepts/barkhausenrauschen", "Barkhausenrauschen") in links
    # the backslash-tainted target must not appear at all
    targets = [t for t, _ in links]
    assert "wiki/concepts/barkhausenrauschen\\" not in targets


def test_extract_wikilinks_ignores_non_wiki():
    body = "[[foo]] is not a wiki link, but [[wiki/x]] is."
    links = extract_wikilinks(body)
    targets = [t for t, _ in links]
    assert "wiki/x" in targets
    assert "foo" not in targets


def test_extract_wikilinks_dedup():
    body = "[[wiki/a]] and again [[wiki/a]]."
    links = extract_wikilinks(body)
    assert links.count(("wiki/a", None)) == 2  # not deduped at this level


from living_vault.core.graph import resolve_target


def test_resolve_target_strips_wiki_prefix():
    assert resolve_target("wiki/concepts/note-a") == "concepts/note-a.md"


def test_resolve_target_passes_md_extension_through():
    assert resolve_target("wiki/concepts/note-a.md") == "concepts/note-a.md"


def test_resolve_target_returns_none_for_non_wiki():
    assert resolve_target("concepts/note-a") is None


import sqlite3
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.graph import neighbors, backlinks


def test_neighbors_returns_outgoing(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    n = neighbors(con, "concepts/note-a.md")
    con.close()
    assert "concepts/note-b.md" in n
    assert "synthesis/syn-1.md" in n


def test_backlinks_returns_incoming(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    b = backlinks(con, "concepts/note-a.md")
    con.close()
    assert "concepts/note-b.md" in b
    assert "synthesis/syn-1.md" in b


def test_neighbors_empty_for_leaf(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    n = neighbors(con, "does-not-exist.md")
    con.close()
    assert n == []
