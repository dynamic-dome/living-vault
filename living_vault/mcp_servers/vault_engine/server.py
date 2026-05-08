"""vault-engine-mcp — FastMCP server exposing core/ functionality.

Configuration via env vars:
  LIVING_VAULT_ROOT  - absolute path to the vault root (e.g. C:\\Users\\domes\\wiki\\wiki)
  LIVING_VAULT_DB    - absolute path to the SQLite db (default: <root>/../.vault-engine.db)

Tools exposed:
  read_page, search_semantic, neighbors, backlinks, similar,
  stale_pages, public_pages, reindex
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

# Windows MCP encoding hardening (per project memory reference)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastmcp import FastMCP

from living_vault.core import db as db_mod
from living_vault.core import reader, graph, embeddings, decay, privacy
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import (
    index_embeddings,
    search_semantic as _search_semantic,
    similar as _similar,
)


mcp = FastMCP("vault-engine")


def _vault_root() -> Path:
    p = os.environ.get("LIVING_VAULT_ROOT")
    if not p:
        raise RuntimeError("LIVING_VAULT_ROOT env var is not set")
    return Path(p)


def _db_path() -> Path:
    p = os.environ.get("LIVING_VAULT_DB")
    if p:
        return Path(p)
    return _vault_root().parent / ".vault-engine.db"


# ---- tool implementations as plain functions (testable) ----

def _tool_read_page(path: str) -> dict:
    page = reader.read_page(_vault_root() / path, _vault_root())
    return {
        "relpath": page.relpath,
        "title": page.title,
        "body": page.body,
        "frontmatter": page.frontmatter,
        "is_public": page.is_public,
        "mtime": page.mtime,
    }


def _tool_neighbors(path: str) -> list[str]:
    con = db_mod.connect(_db_path())
    try:
        return graph.neighbors(con, path)
    finally:
        con.close()


def _tool_backlinks(path: str) -> list[str]:
    con = db_mod.connect(_db_path())
    try:
        return graph.backlinks(con, path)
    finally:
        con.close()


def _tool_similar(path: str, k: int = 10) -> list[dict]:
    con = db_mod.connect(_db_path())
    try:
        rows = _similar(con, path, k=k)
        return [{"path": p, "score": s} for p, s in rows]
    finally:
        con.close()


def _tool_search_semantic(query: str, k: int = 10) -> list[dict]:
    con = db_mod.connect(_db_path())
    try:
        rows = _search_semantic(con, query, k=k)
        return [{"path": p, "score": s} for p, s in rows]
    finally:
        con.close()


def _tool_stale_pages(days: int = 90) -> list[str]:
    con = db_mod.connect(_db_path())
    try:
        return decay.stale_pages(con, days=days)
    finally:
        con.close()


def _tool_public_pages() -> list[str]:
    con = db_mod.connect(_db_path())
    try:
        return privacy.public_pages(con)
    finally:
        con.close()


def _tool_reindex(force: bool = False) -> dict:
    db_mod.initialize(_db_path())
    if force:
        # blow away embeddings + pages, force rebuild
        con = db_mod.connect(_db_path())
        try:
            con.execute("DELETE FROM embeddings_blob")
            con.execute("DELETE FROM pages")
            con.execute("DELETE FROM links")
            con.commit()
        finally:
            con.close()
    stats = index_vault(_vault_root(), _db_path())
    n = index_embeddings(_vault_root(), _db_path())
    return {**stats, "embeddings_updated": n}


# ---- MCP tool registration ----

@mcp.tool()
def read_page(path: str) -> dict:
    """Read one page by vault-relative path."""
    return _tool_read_page(path)


@mcp.tool()
def neighbors(path: str) -> list[str]:
    """Outgoing links from path."""
    return _tool_neighbors(path)


@mcp.tool()
def backlinks(path: str) -> list[str]:
    """Incoming links to path."""
    return _tool_backlinks(path)


@mcp.tool()
def similar(path: str, k: int = 10) -> list[dict]:
    """Top-k similar pages by embedding cosine."""
    return _tool_similar(path, k)


@mcp.tool()
def search_semantic(query: str, k: int = 10) -> list[dict]:
    """Top-k pages by semantic similarity to a free-text query."""
    return _tool_search_semantic(query, k)


@mcp.tool()
def stale_pages(days: int = 90) -> list[str]:
    """Pages with mtime older than `days` days."""
    return _tool_stale_pages(days)


@mcp.tool()
def public_pages() -> list[str]:
    """Pages with frontmatter `public: true`."""
    return _tool_public_pages()


@mcp.tool()
def reindex(force: bool = False) -> dict:
    """Re-walk the vault and refresh pages/links/embeddings tables."""
    return _tool_reindex(force)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
