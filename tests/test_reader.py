from pathlib import Path
from living_vault.core.reader import read_page, content_hash


def test_read_page_parses_frontmatter(fixture_vault_root: Path):
    p = read_page(fixture_vault_root / "concepts" / "note-a.md", fixture_vault_root)
    assert p.title == "note-a"
    assert p.frontmatter["type"] == "concept"
    assert p.frontmatter["public"] is False
    assert "alpha" in p.frontmatter["tags"]
    assert "[[wiki/concepts/note-b]]" in p.body


def test_read_page_relative_path(fixture_vault_root: Path):
    p = read_page(fixture_vault_root / "concepts" / "note-b.md", fixture_vault_root)
    assert p.relpath == "concepts/note-b.md"


def test_read_page_public_flag(fixture_vault_root: Path):
    p_priv = read_page(fixture_vault_root / "concepts" / "note-a.md", fixture_vault_root)
    p_pub = read_page(fixture_vault_root / "concepts" / "note-b.md", fixture_vault_root)
    p_unset = read_page(fixture_vault_root / "synthesis" / "syn-1.md", fixture_vault_root)
    assert p_priv.is_public is False
    assert p_pub.is_public is True
    assert p_unset.is_public is False  # missing key defaults to private


def test_content_hash_stable():
    h1 = content_hash("hello world")
    h2 = content_hash("hello world")
    assert h1 == h2
    assert h1 != content_hash("hello world ")
    assert len(h1) == 64  # sha256 hex
