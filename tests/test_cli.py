import json
import sqlite3
from pathlib import Path
from click.testing import CliRunner

from living_vault.cli import cli
from living_vault.core import db as db_mod
from living_vault.core import embeddings as embeddings_mod
from living_vault.core.embeddings import NumpyBackend, index_embeddings
from living_vault.core.indexer import index_vault


def test_cli_index_runs(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["index", "--vault", str(vault_copy), "--db", str(db)],
    )
    assert result.exit_code == 0, result.output
    assert "pages_seen=3" in result.output
    assert db.exists()


def test_cli_history_no_git_repo(vault_copy: Path):
    """history on a non-git dir prints '(no history found)'."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["history", "concepts/note-a.md", "--vault", str(vault_copy)],
    )
    assert result.exit_code == 0, result.output
    assert "(no history found)" in result.output


def test_cli_history_with_git_repo(tmp_path: Path):
    """history on a real git repo prints the commit table."""
    import shutil, subprocess
    if shutil.which("git") is None:
        import pytest as _pt; _pt.skip("git not on PATH")
    from living_vault.core import history as history_mod
    history_mod.clear_cache()

    repo = tmp_path / "wiki"
    repo.mkdir()
    page = repo / "x.md"
    page.write_text("hi", encoding="utf-8")
    for cmd in (
        ["git", "-C", str(repo), "init", "-q", "-b", "main"],
        ["git", "-C", str(repo), "config", "--local", "user.email", "t@e.com"],
        ["git", "-C", str(repo), "config", "--local", "user.name", "T"],
        ["git", "-C", str(repo), "config", "--local", "commit.gpgsign", "false"],
        ["git", "-C", str(repo), "add", "x.md"],
        ["git", "-C", str(repo), "commit", "-q", "-m", "hello world"],
    ):
        subprocess.run(cmd, check=True, capture_output=True)

    runner = CliRunner()
    result = runner.invoke(cli, ["history", "x.md", "--vault", str(repo)])
    assert result.exit_code == 0, result.output
    assert "hello world" in result.output
    assert "sha" in result.output  # header


def test_cli_status_json_reports_clean_embeddings(
    vault_copy: Path, tmp_path: Path, monkeypatch
):
    db = tmp_path / ".vault-engine.db"
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)

    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--db", str(db), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["pages_total"] == 3
    assert payload["embeddings_total"] == 3
    assert payload["current"] == 3
    assert payload["stale"] == 0
    assert payload["unknown"] == 0
    assert payload["missing"] == 0
    assert payload["orphan"] == 0


def test_cli_status_json_reports_stale_unknown_missing_and_orphan(
    vault_copy: Path, tmp_path: Path, monkeypatch
):
    db = tmp_path / ".vault-engine.db"
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)

    con = db_mod.connect(db)
    stale_blob = con.execute(
        "SELECT model, dim, vector FROM embeddings_blob WHERE path = ?",
        ("concepts/note-a.md",),
    ).fetchone()
    con.execute(
        "UPDATE embeddings_blob SET content_hash = ? WHERE path = ?",
        ("stale-hash", "concepts/note-a.md"),
    )
    con.execute(
        "UPDATE embeddings_blob SET content_hash = NULL WHERE path = ?",
        ("concepts/note-b.md",),
    )
    con.execute("DELETE FROM embeddings_blob WHERE path = ?", ("synthesis/syn-1.md",))
    con.execute(
        "INSERT INTO embeddings_blob(path, model, dim, vector, content_hash) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            "gone.md",
            stale_blob["model"],
            stale_blob["dim"],
            stale_blob["vector"],
            "orphan-hash",
        ),
    )
    con.commit()
    con.close()

    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--db", str(db), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "needs-reembed"
    assert payload["stale"] == 1
    assert payload["unknown"] == 1
    assert payload["missing"] == 1
    assert payload["orphan"] == 1


def test_cli_status_legacy_schema_exits_nonzero(tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    con = sqlite3.connect(str(db))
    con.execute(
        """
        CREATE TABLE embeddings_blob (
            path TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector BLOB NOT NULL
        )
        """
    )
    con.commit()
    con.close()

    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--db", str(db), "--json"])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "legacy-schema"
