"""End-to-end test: vault_copy + indexed DB + build_persona() returns the
expected dict shape, with caching of voice_features into the DB.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

import pytest

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.persona import build_persona


def test_build_persona_returns_full_struct(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    p = build_persona(vault_copy, db_path, "concepts/note-a.md")
    assert p is not None
    assert p["path"] == "concepts/note-a.md"
    assert p["title"]
    # era from frontmatter `created:`
    assert p["era_marker"].startswith("2026-01") or p["era_marker"].startswith("2026-04")
    # themes pulled from tags
    assert "alpha" in p["themes"] or "example" in p["themes"]
    # body_excerpt populated, voice_features computed deterministically,
    # voice_distilled is None until extract-voice runs
    assert isinstance(p["body_excerpt"], str)
    assert p["body_excerpt"]
    assert isinstance(p["voice_features"], dict)
    assert "avg_sentence_length" in p["voice_features"]
    assert p["voice_distilled"] is None


def test_build_persona_unknown_path_returns_none(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    assert build_persona(vault_copy, db_path, "does/not/exist.md") is None


def test_build_persona_caches_voice_features_in_db(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    # first call → extracts and caches
    build_persona(vault_copy, db_path, "concepts/note-a.md")

    con = sqlite3.connect(str(db_path))
    row = con.execute(
        "SELECT voice_features FROM pages WHERE path = ?", ("concepts/note-a.md",)
    ).fetchone()
    con.close()
    assert row[0] is not None
    cached = json.loads(row[0])
    assert "avg_sentence_length" in cached


def test_build_persona_uses_cached_voice_features_from_db(
    vault_copy: Path, db_path: Path
):
    """Second call must read voice_features from DB, not recompute."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    sentinel = {
        "avg_sentence_length": 99999.99,
        "sentence_length_stddev": 0,
        "question_rate": 0,
        "exclamation_rate": 0,
        "first_person_rate": 0,
        "second_person_rate": 0,
        "preferred_separator": "$$",
        "list_density": 0,
        "code_density": 0,
        "wikilink_density": 0,
        "top_phrases": ["sentinel"],
        "register": "unknown",
    }
    con = sqlite3.connect(str(db_path))
    con.execute(
        "UPDATE pages SET voice_features = ? WHERE path = ?",
        (json.dumps(sentinel), "concepts/note-a.md"),
    )
    con.commit()
    con.close()

    p = build_persona(vault_copy, db_path, "concepts/note-a.md")
    # Cache is honored — sentinel persists
    assert p["voice_features"]["avg_sentence_length"] == 99999.99
    assert "sentinel" in p["voice_features"]["top_phrases"]


def test_build_persona_returns_distilled_when_present(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = sqlite3.connect(str(db_path))
    con.execute(
        "UPDATE pages SET voice_distilled = ? WHERE path = ?",
        ("Speaks crisp short sentences.", "concepts/note-a.md"),
    )
    con.commit()
    con.close()

    p = build_persona(vault_copy, db_path, "concepts/note-a.md")
    assert p["voice_distilled"] == "Speaks crisp short sentences."
