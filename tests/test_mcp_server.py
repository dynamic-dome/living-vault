"""MCP server tests — call the underlying functions directly via the FastMCP app object.

We do not start a transport here; we exercise the registered tool callables.
"""
from pathlib import Path
import os

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.mcp_servers.vault_engine import server as srv


def test_tool_read_page(vault_copy: Path, db_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    out = srv._tool_read_page("concepts/note-a.md")
    assert out["title"] == "note-a"
    assert "alpha" in out["frontmatter"]["tags"]


def test_tool_neighbors(vault_copy: Path, db_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    out = srv._tool_neighbors("concepts/note-a.md")
    assert "concepts/note-b.md" in out
    assert "synthesis/syn-1.md" in out


def test_tool_public_pages(vault_copy: Path, db_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    out = srv._tool_public_pages()
    assert out == ["concepts/note-b.md"]


def test_tool_page_history_no_git_returns_empty(vault_copy: Path, db_path: Path, monkeypatch):
    """vault_copy is a tmp dir, not a git repo — page_history returns []."""
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    from living_vault.core import history as history_mod
    history_mod.clear_cache()
    assert srv._tool_page_history("concepts/note-a.md") == []


def test_tool_page_history_with_git_repo(tmp_path: Path, monkeypatch):
    """vault_root is a real git repo with one commit — page_history returns 1 row."""
    import shutil, subprocess
    if shutil.which("git") is None:
        import pytest as _pt; _pt.skip("git binary not on PATH")

    repo = tmp_path / "wiki"
    repo.mkdir()
    page = repo / "concepts" / "x.md"
    page.parent.mkdir(parents=True)
    page.write_text("hi", encoding="utf-8")
    for cmd in (
        ["git", "-C", str(repo), "init", "-q", "-b", "main"],
        ["git", "-C", str(repo), "config", "--local", "user.email", "t@e.com"],
        ["git", "-C", str(repo), "config", "--local", "user.name", "T"],
        ["git", "-C", str(repo), "config", "--local", "commit.gpgsign", "false"],
        ["git", "-C", str(repo), "add", "concepts/x.md"],
        ["git", "-C", str(repo), "commit", "-q", "-m", "hello"],
    ):
        subprocess.run(cmd, check=True, capture_output=True)

    monkeypatch.setenv("LIVING_VAULT_ROOT", str(repo))
    monkeypatch.setenv("LIVING_VAULT_DB", str(tmp_path / ".db"))
    from living_vault.core import history as history_mod
    history_mod.clear_cache()
    rows = srv._tool_page_history("concepts/x.md", limit=5)
    assert len(rows) == 1
    assert rows[0]["subject"] == "hello"
