"""Tests for the seance website bundle export (apps/seance_ui/bundle.py)."""
from pathlib import Path

import json
import pytest

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.apps.seance_ui.bundle import (
    SeanceExportError,
    build_seance_bundle,
    validate_bundle_text,
    _load_demo,
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


# ---------------------------------------------------------------------------
# Fix 2: _load_demo tests
# ---------------------------------------------------------------------------

def test_load_demo_happy_path(tmp_path):
    """Valid demo list lands in bundle demo_conversations."""
    demo_file = tmp_path / "demo.json"
    demo_data = [{"title": "Chat 1", "turns": [{"role": "user", "text": "hi"}]}]
    demo_file.write_text(json.dumps(demo_data), encoding="utf-8")
    result = _load_demo(demo_file)
    assert result == demo_data


def test_load_demo_non_list_json_raises(tmp_path):
    """Non-list JSON (e.g. a dict) raises SeanceExportError."""
    demo_file = tmp_path / "demo.json"
    demo_file.write_text(json.dumps({"title": "oops"}), encoding="utf-8")
    with pytest.raises(SeanceExportError, match="JSON list"):
        _load_demo(demo_file)


def test_load_demo_missing_title_or_turns_raises(tmp_path):
    """Conversation missing 'title' or 'turns' raises SeanceExportError."""
    demo_file = tmp_path / "demo.json"
    demo_file.write_text(json.dumps([{"title": "no turns here"}]), encoding="utf-8")
    with pytest.raises(SeanceExportError, match="title.*turns|turns.*title"):
        _load_demo(demo_file)


def test_load_demo_malformed_json_raises(tmp_path):
    """Malformed JSON file raises SeanceExportError (proves Fix 1 exception wrap)."""
    demo_file = tmp_path / "demo.json"
    demo_file.write_text("{this is not json!!!", encoding="utf-8")
    with pytest.raises(SeanceExportError, match="cannot load demo file"):
        _load_demo(demo_file)


def test_load_demo_missing_file_raises(tmp_path):
    """Missing file raises SeanceExportError (proves Fix 1 exception wrap)."""
    missing = tmp_path / "no-such-file.json"
    with pytest.raises(SeanceExportError, match="cannot load demo file"):
        _load_demo(missing)


# ---------------------------------------------------------------------------
# Fix 3: duplicate persona_paths
# ---------------------------------------------------------------------------

def test_duplicate_persona_paths_raises(indexed, tmp_path):
    """Duplicate entries in persona_paths raises SeanceExportError."""
    vault, db = indexed
    allow = _write_allowlist(tmp_path, ["concepts/note-a.md"])
    with pytest.raises(SeanceExportError, match="duplicate"):
        build_seance_bundle(
            vault_root=vault, db_path=db, allowlist_path=allow,
            persona_paths=["concepts/note-a.md", "concepts/note-a.md"],
        )


# ---------------------------------------------------------------------------
# Task A2: neighbor-stripping proof
# note-a links to [[wiki/concepts/note-b]] → concepts/note-b.md
#                 [[wiki/synthesis/syn-1]]  → synthesis/syn-1.md
# ---------------------------------------------------------------------------

def test_neighbors_are_stripped_to_allowlist(indexed, tmp_path):
    vault, db = indexed
    # Allowlist contains ONLY note-a → both outgoing neighbors must be stripped
    allow = _write_allowlist(tmp_path, ["concepts/note-a.md"])
    bundle = build_seance_bundle(
        vault_root=vault, db_path=db, allowlist_path=allow,
        persona_paths=["concepts/note-a.md"],
    )
    assert bundle["personas"][0]["neighbors"] == []

    # With note-b also allowlisted, exactly it appears (syn-1 still stripped)
    allow2 = _write_allowlist(tmp_path, ["concepts/note-a.md", "concepts/note-b.md"])
    bundle2 = build_seance_bundle(
        vault_root=vault, db_path=db, allowlist_path=allow2,
        persona_paths=["concepts/note-a.md"],
    )
    assert bundle2["personas"][0]["neighbors"] == ["concepts/note-b.md"]


# ---------------------------------------------------------------------------
# Task A3: validate_bundle_text
# ---------------------------------------------------------------------------

def test_validator_flags_machine_paths_and_secrets():
    """Check 1: machine paths (Windows + POSIX) and secret-like keys are flagged."""
    bad = json.dumps({
        "a": "siehe C:/Users/domes/geheim.md",
        "b": "/Users/alice/note",
        "c": "key sk-ant-abc12345xyz",
    })
    findings = validate_bundle_text(bad)
    assert len(findings) == 3
    assert any("machine-path" in f for f in findings)
    assert any("secret" in f for f in findings)


def test_validator_passes_clean_public_content():
    """Check 1: clean content with time-like colons and ratios must not be flagged."""
    ok = json.dumps({
        "a": "MCP-Server bauen: Transport via stdio, JSON-RPC 2.0.",
        "b": "Zeitplan 10:30 Uhr, Verhältnis 1:5",
    })
    assert validate_bundle_text(ok) == []


def test_validator_flags_wikilink_outside_allowlist():
    """Check 2: body_excerpt with wikilink to page NOT in allowed → flagged."""
    # note-a links to [[wiki/concepts/note-b]] → resolves to concepts/note-b.md
    bundle_text = json.dumps({
        "body_excerpt": "See [[wiki/concepts/note-b]] for more details.",
    })
    # Only note-a in allowlist, note-b is NOT allowed
    allowed = {"concepts/note-a.md"}
    findings = validate_bundle_text(bundle_text, allowed=allowed)
    assert len(findings) == 1
    assert "wikilink outside allowlist" in findings[0]
    assert "concepts/note-b.md" in findings[0]


def test_validator_passes_wikilink_inside_allowlist():
    """Check 2: wikilink to a page IN allowed → no finding."""
    bundle_text = json.dumps({
        "body_excerpt": "See [[wiki/concepts/note-b]] for more details.",
    })
    allowed = {"concepts/note-a.md", "concepts/note-b.md"}
    findings = validate_bundle_text(bundle_text, allowed=allowed)
    assert findings == []


def test_validator_skips_wikilink_check_when_allowed_is_none():
    """Check 2: allowed=None → wikilink check is skipped entirely."""
    bundle_text = json.dumps({
        "body_excerpt": "See [[wiki/concepts/note-b]] and [[wiki/synthesis/syn-1]].",
    })
    # No allowlist provided → only pattern check runs, no wikilink findings
    findings = validate_bundle_text(bundle_text, allowed=None)
    assert all("wikilink" not in f for f in findings)


def test_validator_flags_alias_form_wikilink_outside_allowlist():
    """Check 2: alias form [[target|alias]] → target is checked, alias ignored."""
    bundle_text = json.dumps({
        "body_excerpt": "See [[wiki/synthesis/syn-1|the synthesis]] here.",
    })
    allowed = {"concepts/note-a.md", "concepts/note-b.md"}  # syn-1 NOT in allowed
    findings = validate_bundle_text(bundle_text, allowed=allowed)
    assert len(findings) == 1
    assert "wikilink outside allowlist" in findings[0]
    assert "synthesis/syn-1.md" in findings[0]


def test_validator_flags_secret_env_name():
    """Check 1: ANTHROPIC_API_KEY in bundle text is flagged as secret env name."""
    bad = json.dumps({"config": "export ANTHROPIC_API_KEY=abc123"})
    findings = validate_bundle_text(bad)
    assert any("secret env name" in f for f in findings)


def test_validator_flags_posix_home_path():
    """Check 1: /home/user path is flagged as machine-path (posix)."""
    bad = json.dumps({"path": "/home/dominic/projects/secret"})
    findings = validate_bundle_text(bad)
    assert any("machine-path" in f for f in findings)
