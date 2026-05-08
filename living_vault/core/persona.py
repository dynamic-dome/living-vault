"""Persona — Phase 1 lite implementation.

Phase 2 will replace this with a richer voice extractor across page history.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from living_vault.core import db as db_mod
from living_vault.core.reader import read_page


def build_persona_lite(
    vault_root: Path, db_path: Path, relpath: str
) -> Optional[dict]:
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT path, frontmatter FROM pages WHERE path = ?", (relpath,)
        ).fetchone()
        if row is None:
            return None
        fm = json.loads(row["frontmatter"]) if row["frontmatter"] else {}
        page = read_page(vault_root / relpath, vault_root)
        sample = page.body.strip()[:500]
        era = str(fm.get("created", ""))
        themes = list(fm.get("tags", [])) or [page.relpath.split("/", 1)[0]]
        return {
            "path": relpath,
            "title": page.title,
            "era_marker": era,
            "themes": themes,
            "voice_sample": sample,
            "frontmatter": fm,
        }
    finally:
        con.close()
