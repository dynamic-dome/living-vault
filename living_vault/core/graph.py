"""Wikilink graph: extraction, neighbors, backlinks."""
from __future__ import annotations
import re
from typing import Iterable

WIKILINK_RE = re.compile(r"\[\[(wiki/[^\]\|]+?)(?:\|([^\]]+))?\]\]")


def extract_wikilinks(body: str) -> list[tuple[str, str | None]]:
    """Return list of (target, alias|None) tuples in document order, no dedup."""
    out: list[tuple[str, str | None]] = []
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        alias = m.group(2).strip() if m.group(2) else None
        out.append((target, alias))
    return out


def resolve_target(target: str) -> str | None:
    """Map a wikilink target like 'wiki/concepts/foo' to vault relpath 'concepts/foo.md'.

    Wiki convention: vault root is ~/wiki/wiki/, but wikilinks include the leading 'wiki/'
    segment because the vault is itself nested inside a 'wiki/' directory.
    """
    if not target.startswith("wiki/"):
        return None
    stripped = target[len("wiki/"):]
    if not stripped.endswith(".md"):
        stripped = stripped + ".md"
    return stripped


import sqlite3


def neighbors(con: sqlite3.Connection, path: str) -> list[str]:
    """Outgoing edges: pages that path links to."""
    rows = con.execute(
        "SELECT DISTINCT to_path FROM links WHERE from_path = ? ORDER BY to_path",
        (path,),
    ).fetchall()
    return [r[0] for r in rows]


def backlinks(con: sqlite3.Connection, path: str) -> list[str]:
    """Incoming edges: pages that link to path."""
    rows = con.execute(
        "SELECT DISTINCT from_path FROM links WHERE to_path = ? ORDER BY from_path",
        (path,),
    ).fetchall()
    return [r[0] for r in rows]
