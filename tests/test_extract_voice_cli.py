"""CLI tests for `living-vault extract-voice`. FakeLLM only — no API calls."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from living_vault.cli import cli
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault


def _setup_indexed_db(vault_copy: Path, db_path: Path) -> None:
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)


def test_extract_voice_with_yes_distills_pages_via_fakellm(
    vault_copy: Path, db_path: Path, monkeypatch
):
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup_indexed_db(vault_copy, db_path)
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["extract-voice", "--vault", str(vault_copy), "--db", str(db_path), "--yes"],
    )
    assert res.exit_code == 0, res.output

    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "SELECT path, voice_distilled FROM pages WHERE voice_distilled IS NOT NULL"
    ).fetchall()
    con.close()
    assert len(rows) >= 1
    for path, distilled in rows:
        assert distilled, f"empty distilled for {path}"


def test_extract_voice_limit_caps_pages_processed(
    vault_copy: Path, db_path: Path, monkeypatch
):
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup_indexed_db(vault_copy, db_path)
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "extract-voice",
            "--vault", str(vault_copy),
            "--db", str(db_path),
            "--limit", "1",
            "--yes",
        ],
    )
    assert res.exit_code == 0
    con = sqlite3.connect(str(db_path))
    n = con.execute(
        "SELECT COUNT(*) FROM pages WHERE voice_distilled IS NOT NULL"
    ).fetchone()[0]
    con.close()
    assert n == 1


def test_extract_voice_skips_already_distilled_unless_force(
    vault_copy: Path, db_path: Path, monkeypatch
):
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup_indexed_db(vault_copy, db_path)

    # pre-populate one page with a sentinel value
    con = sqlite3.connect(str(db_path))
    con.execute(
        "UPDATE pages SET voice_distilled = ? WHERE path = ?",
        ("PREEXISTING-SENTINEL", "concepts/note-a.md"),
    )
    con.commit()
    con.close()

    runner = CliRunner()
    # Without --force: sentinel should be preserved
    res = runner.invoke(
        cli,
        ["extract-voice", "--vault", str(vault_copy), "--db", str(db_path), "--yes"],
    )
    assert res.exit_code == 0
    con = sqlite3.connect(str(db_path))
    val = con.execute(
        "SELECT voice_distilled FROM pages WHERE path = ?", ("concepts/note-a.md",)
    ).fetchone()[0]
    con.close()
    assert val == "PREEXISTING-SENTINEL"  # not overwritten

    # With --force: sentinel should be replaced
    res = runner.invoke(
        cli,
        [
            "extract-voice",
            "--vault", str(vault_copy),
            "--db", str(db_path),
            "--force",
            "--yes",
        ],
    )
    assert res.exit_code == 0
    con = sqlite3.connect(str(db_path))
    val = con.execute(
        "SELECT voice_distilled FROM pages WHERE path = ?", ("concepts/note-a.md",)
    ).fetchone()[0]
    con.close()
    assert val != "PREEXISTING-SENTINEL"  # overwritten
    assert val  # non-empty


def test_extract_voice_aborts_when_user_says_no(
    vault_copy: Path, db_path: Path, monkeypatch
):
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup_indexed_db(vault_copy, db_path)
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["extract-voice", "--vault", str(vault_copy), "--db", str(db_path)],
        input="n\n",
    )
    # Click returns exit_code 1 when click.confirm is rejected with abort=True
    assert res.exit_code != 0 or "abort" in res.output.lower() or "aborted" in res.output.lower()
    con = sqlite3.connect(str(db_path))
    n = con.execute(
        "SELECT COUNT(*) FROM pages WHERE voice_distilled IS NOT NULL"
    ).fetchone()[0]
    con.close()
    assert n == 0
