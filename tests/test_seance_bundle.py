"""Tests for the seance website bundle export (apps/seance_ui/bundle.py)."""
from pathlib import Path

import pytest

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.apps.seance_ui.bundle import (
    SeanceExportError,
    build_seance_bundle,
)


def _write_allowlist(tmp_path: Path, lines: list[str]) -> Path:
    p = tmp_path / "seance-allowlist.txt"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def indexed(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    return vault_copy, db_path


def test_bundle_builds_persona_cards_with_contract_keys(indexed, tmp_path):
    vault, db = indexed
    allow = _write_allowlist(tmp_path, ["concepts/note-a.md"])
    bundle = build_seance_bundle(
        vault_root=vault, db_path=db, allowlist_path=allow,
        persona_paths=["concepts/note-a.md"],
    )
    assert set(bundle) == {"generated_at", "personas", "demo_conversations"}
    card = bundle["personas"][0]
    assert set(card) == {
        "id", "title", "era_marker", "themes",
        "neighbors", "voice", "body_excerpt",
    }
    assert card["id"] == "concepts/note-a.md"
    assert set(card["voice"]) == {"distilled", "features"}
    assert bundle["demo_conversations"] == []


def test_persona_not_on_allowlist_fails_closed(indexed, tmp_path):
    vault, db = indexed
    allow = _write_allowlist(tmp_path, ["concepts/note-b.md"])
    with pytest.raises(SeanceExportError, match="allowlist"):
        build_seance_bundle(
            vault_root=vault, db_path=db, allowlist_path=allow,
            persona_paths=["concepts/note-a.md"],
        )


def test_unknown_persona_page_raises(indexed, tmp_path):
    vault, db = indexed
    allow = _write_allowlist(tmp_path, ["nope/missing.md"])
    with pytest.raises(SeanceExportError, match="missing.md"):
        build_seance_bundle(
            vault_root=vault, db_path=db, allowlist_path=allow,
            persona_paths=["nope/missing.md"],
        )
