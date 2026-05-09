"""Persona Schicht 3 — full voice extractor with caching.

Pipeline:
    read_page → extract_stylometric → load_or_distill → assemble_persona

Read-path (`build_persona`) NEVER calls the LLM. The LLM-distilled voice is
populated only when a caller explicitly runs `living-vault extract-voice`
(see `cli.py`).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from living_vault.core import db as db_mod
from living_vault.core.reader import read_page
from living_vault.core.voice.stylometric import extract_stylometric


_BODY_EXCERPT_CHARS = 500


def assemble_persona(
    *,
    path: str,
    title: str,
    frontmatter: dict,
    body_excerpt: str,
    voice_features: Optional[dict],
    voice_distilled: Optional[str],
) -> dict:
    """Pure dict-builder. Same signature regardless of voice-block case."""
    era = str(frontmatter.get("created", "") or "")
    themes = list(frontmatter.get("tags", []) or [])
    return {
        "path": path,
        "title": title,
        "era_marker": era,
        "themes": themes,
        "frontmatter": dict(frontmatter),
        "body_excerpt": body_excerpt,
        "voice_features": voice_features,
        "voice_distilled": voice_distilled,
    }


def _load_voice_features_from_db(con, path: str) -> Optional[dict]:
    row = con.execute(
        "SELECT voice_features FROM pages WHERE path = ?", (path,)
    ).fetchone()
    if row is None or row["voice_features"] is None:
        return None
    try:
        return json.loads(row["voice_features"])
    except json.JSONDecodeError:
        return None


def _store_voice_features(con, path: str, features: dict) -> None:
    con.execute(
        "UPDATE pages SET voice_features = ? WHERE path = ?",
        (json.dumps(features), path),
    )
    con.commit()


def _load_voice_distilled_from_db(con, path: str) -> Optional[str]:
    row = con.execute(
        "SELECT voice_distilled FROM pages WHERE path = ?", (path,)
    ).fetchone()
    return row["voice_distilled"] if row is not None else None


def build_persona(
    vault_root: Path, db_path: Path, relpath: str
) -> Optional[dict]:
    """Read-path. Never calls the LLM. Falls back gracefully if voice columns are NULL."""
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT path, frontmatter FROM pages WHERE path = ?", (relpath,)
        ).fetchone()
        if row is None:
            return None

        fm = json.loads(row["frontmatter"]) if row["frontmatter"] else {}
        page = read_page(vault_root / relpath, vault_root)
        body_excerpt = (page.body or "").strip()[:_BODY_EXCERPT_CHARS]

        # voice_features: try cache; if absent, extract on-demand and persist
        voice_features = _load_voice_features_from_db(con, relpath)
        if voice_features is None:
            voice_features = extract_stylometric(page.body or "")
            _store_voice_features(con, relpath, voice_features)

        voice_distilled = _load_voice_distilled_from_db(con, relpath)

        return assemble_persona(
            path=relpath,
            title=page.title,
            frontmatter=fm,
            body_excerpt=body_excerpt,
            voice_features=voice_features,
            voice_distilled=voice_distilled,
        )
    finally:
        con.close()
