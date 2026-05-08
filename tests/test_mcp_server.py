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
