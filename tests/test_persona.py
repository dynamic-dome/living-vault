from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.persona import build_persona_lite


def test_build_persona_lite_returns_struct(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    p = build_persona_lite(vault_copy, db_path, "concepts/note-a.md")
    assert p["path"] == "concepts/note-a.md"
    assert p["era_marker"].startswith("2026-01")  # created date
    assert "alpha" in p["themes"]
    assert "Note A" in p["voice_sample"] or "alpha" in p["voice_sample"]


def test_build_persona_lite_unknown_path(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    p = build_persona_lite(vault_copy, db_path, "does/not/exist.md")
    assert p is None
