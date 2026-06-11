"""Tests for the seance website bundle export (apps/seance_ui/bundle.py)."""
from pathlib import Path

import json
import subprocess
import sys
import pytest

from click.testing import CliRunner

from living_vault.cli import cli
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


# ---------------------------------------------------------------------------
# NEW TESTS — code-review findings (written FIRST, expected to fail before fix)
# ---------------------------------------------------------------------------

# ---- CRITICAL 1: backslash Windows paths bypass ----

def test_validator_flags_backslash_windows_path_via_json_dumps():
    """CRITICAL 1a: json.dumps doubles the backslash → raw text has C:\\\\Users\\\\...
    The pattern must tolerate 1-2 separators and the parsed-value sweep must
    also catch the original single-backslash value."""
    payload = {"a": "C:\\Users\\domes\\geheim.md"}
    # json.dumps produces: {"a": "C:\\Users\\domes\\geheim.md"}
    # raw text contains C:\\Users (double backslash)
    text = json.dumps(payload)
    findings = validate_bundle_text(text)
    assert len(findings) >= 1
    assert any("machine-path" in f for f in findings)


def test_validator_flags_unicode_escaped_windows_path():
    """CRITICAL 1b: /  in raw JSON text (unicode-escaped slash)
    must be caught by the parsed-value sweep."""
    # Build the raw JSON string manually so it contains the literal escape
    # C:/Users/domes  where / is written as \/
    raw_json = '{"a": "C:\\/Users\\/domes\\/geheim.md"}'
    findings = validate_bundle_text(raw_json)
    assert len(findings) >= 1
    assert any("machine-path" in f for f in findings)


def test_validator_no_duplicate_findings_for_backslash_path():
    """CRITICAL 1c: raw sweep + parsed sweep must NOT produce duplicate findings
    for the exact same path (same label + same snippet after dedup)."""
    payload = {"a": "C:\\Users\\domes\\geheim.md"}
    text = json.dumps(payload)
    findings = validate_bundle_text(text)
    # Count how many machine-path (windows) findings exist
    windows_findings = [f for f in findings if "machine-path (windows)" in f]
    assert len(windows_findings) == 1, (
        f"Expected exactly 1 windows-path finding, got {len(windows_findings)}: {findings}"
    )


# ---- IMPORTANT 2: invalid JSON fail-closed ----

def test_validator_invalid_json_with_allowed_returns_finding():
    """IMPORTANT 2: invalid JSON with allowed set must return exactly one finding
    containing 'invalid bundle JSON', not silently skip the wikilink check."""
    findings = validate_bundle_text("{not json", allowed={"a.md"})
    assert len(findings) == 1
    assert "invalid bundle JSON" in findings[0]


def test_validator_invalid_json_without_allowed_still_clean():
    """IMPORTANT 2b: invalid JSON WITHOUT allowed → no crash, no wikilink finding
    (pattern check may still fire, but no JSON-error finding expected when
    allowed is None since the wikilink check is skipped entirely)."""
    findings = validate_bundle_text("{not json", allowed=None)
    assert all("invalid bundle JSON" not in f for f in findings)


# ---- IMPORTANT 3: non-wiki/ wikilinks ----

def test_validator_flags_shorthand_wikilink_as_unresolvable():
    """IMPORTANT 3a: [[concepts/secret]] has no wiki/ prefix → resolve_target
    returns None → must be flagged as unresolvable wikilink."""
    bundle_text = json.dumps({"body": "See [[concepts/secret]] here."})
    allowed = {"concepts/note-a.md"}
    findings = validate_bundle_text(bundle_text, allowed=allowed)
    assert any("unresolvable wikilink" in f for f in findings)
    assert any("concepts/secret" in f for f in findings)


def test_validator_flags_bare_page_name_wikilink_as_unresolvable():
    """IMPORTANT 3b: [[Geheime Notiz]] (bare page name) → unresolvable."""
    bundle_text = json.dumps({"body": "Refer to [[Geheime Notiz]] somehow."})
    allowed = {"concepts/note-a.md"}
    findings = validate_bundle_text(bundle_text, allowed=allowed)
    assert any("unresolvable wikilink" in f for f in findings)
    assert any("Geheime Notiz" in f for f in findings)


def test_validator_flags_traversal_wikilink():
    """IMPORTANT 3c: [[../escape]] path traversal → unresolvable."""
    bundle_text = json.dumps({"body": "Evil [[../escape]] link."})
    allowed = {"concepts/note-a.md"}
    findings = validate_bundle_text(bundle_text, allowed=allowed)
    assert any("unresolvable wikilink" in f or "wikilink" in f for f in findings)


def test_validator_no_unresolvable_findings_when_allowed_is_none():
    """IMPORTANT 3d: unresolvable wikilink check only fires when allowed is not None."""
    bundle_text = json.dumps({"body": "See [[concepts/secret]] here."})
    findings = validate_bundle_text(bundle_text, allowed=None)
    assert all("unresolvable wikilink" not in f for f in findings)


# ---- MINOR M1: secret snippet truncation ----

def test_validator_secret_finding_does_not_leak_full_value():
    """MINOR M1: the snippet in a secret-like-key finding must be truncated —
    it must NOT contain the full secret past the first 12 chars of the match."""
    bad = json.dumps({"k": "sk-ant-api03-SUPERSECRET1234567890"})
    findings = validate_bundle_text(bad)
    secret_findings = [f for f in findings if "secret-like key" in f]
    assert len(secret_findings) >= 1
    # The full secret tail must not appear verbatim in any finding
    assert all("SUPERSECRET1234567890" not in f for f in secret_findings)


# ---- MINOR M2: posix pattern username widening ----

def test_validator_flags_posix_home_config_path():
    """MINOR M2: /home/.config/ — username starts with dot → must be flagged."""
    bad = json.dumps({"p": "/home/.config/secret"})
    findings = validate_bundle_text(bad)
    assert any("machine-path" in f for f in findings)


def test_validator_flags_posix_home_numeric_user():
    """MINOR M2: /home/4user/ — username starts with digit → must be flagged."""
    bad = json.dumps({"p": "/home/4user/projects"})
    findings = validate_bundle_text(bad)
    assert any("machine-path" in f for f in findings)


def test_validator_clean_content_still_passes_after_m2():
    """MINOR M2 regression: clean content (no home paths) must still return []."""
    ok = json.dumps({
        "a": "MCP-Server bauen: Transport via stdio, JSON-RPC 2.0.",
        "b": "Zeitplan 10:30 Uhr, Verhältnis 1:5",
    })
    assert validate_bundle_text(ok) == []


# ---- MINOR M3: tilde home paths ----

def test_validator_flags_tilde_home_path():
    """MINOR M3: ~/projects/secret must be flagged as machine-path (home tilde)."""
    bad = json.dumps({"p": "~/projects/secret"})
    findings = validate_bundle_text(bad)
    assert any("home tilde" in f for f in findings)


def test_validator_tilde_backslash_home_path():
    """MINOR M3: ~\\ path (Windows tilde) must also be flagged."""
    bad = json.dumps({"p": "~\\projects\\secret"})
    findings = validate_bundle_text(bad)
    assert any("home tilde" in f for f in findings)


def test_validator_clean_content_no_tilde_false_positive():
    """MINOR M3 regression: clean content without ~/ must not be flagged."""
    ok = json.dumps({"a": "Approximately ~10 items, cost ~5 EUR"})
    assert validate_bundle_text(ok) == []


# ---- BUG FIX: dedup key must use full path span, not prefix fragment ----

def test_validator_two_distinct_windows_paths_produce_two_findings():
    """Dedup bug: two DISTINCT Windows paths must each produce their own finding.

    Before the fix the dedup key was (label, m.group()) where the windows-path
    pattern only matched the C:\\Users prefix — so C:\\Users\\domes\\geheim.md
    and C:\\Users\\alice\\note.md both produced the same key and the second
    finding was silently dropped.  After the fix the pattern captures the full
    path token, so the keys are distinct and both findings are present.
    """
    payload = {
        "a": "C:\\Users\\domes\\geheim.md",
        "b": "C:\\Users\\alice\\note.md",
    }
    text = json.dumps(payload)
    findings = validate_bundle_text(text)
    windows_findings = [f for f in findings if "machine-path (windows)" in f]
    assert len(windows_findings) == 2, (
        f"Expected 2 distinct windows-path findings, got {len(windows_findings)}: {findings}"
    )
    all_text = " ".join(windows_findings)
    assert "domes" in all_text, "domes path finding missing"
    assert "alice" in all_text, "alice path finding missing"


# ---------------------------------------------------------------------------
# Task A4: CLI export-seance-bundle command + entrypoint smoke
# note-a body links to [[wiki/concepts/note-b]] → concepts/note-b.md
#                    and [[wiki/synthesis/syn-1]]  → synthesis/syn-1.md
# Both must be on the allowlist so the wikilink validator does not fire.
# ---------------------------------------------------------------------------

def test_cli_export_writes_bundle_and_aborts_on_findings(indexed, tmp_path):
    """Happy path: clean bundle with all wikilink targets allowlisted → exit 0."""
    vault, db = indexed
    # note-a links to note-b and syn-1 — all three must be on allowlist
    allow = _write_allowlist(
        tmp_path,
        ["concepts/note-a.md", "concepts/note-b.md", "synthesis/syn-1.md"],
    )
    out = tmp_path / "seance-bundle.json"
    r = CliRunner().invoke(cli, [
        "export-seance-bundle",
        "--vault", str(vault), "--db", str(db),
        "--allowlist", str(allow),
        "--persona", "concepts/note-a.md",
        "--out", str(out),
    ])
    assert r.exit_code == 0, r.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["personas"][0]["id"] == "concepts/note-a.md"


def test_cli_export_fails_on_validator_finding(indexed, tmp_path):
    """Validator gate: machine path injected into page body → exit non-zero, no output file."""
    vault, db = indexed
    # Plant a Windows machine path into note-a's body and re-index
    page = vault / "concepts" / "note-a.md"
    page.write_text(
        page.read_text(encoding="utf-8") + "\n\nLokal: C:/Users/domes/x.md\n",
        encoding="utf-8",
    )
    index_vault(vault, db)
    allow = _write_allowlist(
        tmp_path,
        ["concepts/note-a.md", "concepts/note-b.md", "synthesis/syn-1.md"],
    )
    out = tmp_path / "bundle.json"
    r = CliRunner().invoke(cli, [
        "export-seance-bundle",
        "--vault", str(vault), "--db", str(db),
        "--allowlist", str(allow),
        "--persona", "concepts/note-a.md",
        "--out", str(out),
    ])
    assert r.exit_code != 0
    assert "machine-path" in r.output
    assert not out.exists()


def test_cli_entrypoint_smoke_subprocess():
    """Entrypoint smoke: python -m living_vault.cli export-seance-bundle --help works."""
    r = subprocess.run(
        [sys.executable, "-m", "living_vault.cli", "export-seance-bundle", "--help"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0
    assert "allowlist" in r.stdout
