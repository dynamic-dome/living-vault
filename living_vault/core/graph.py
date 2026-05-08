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
