import datetime as dt
from pathlib import Path
from click.testing import CliRunner

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.apps.portfolio_sync.sync import (
    cli, plan_sync, render_freshness,
)


def test_render_freshness_recent():
    now = dt.datetime(2026, 5, 8, tzinfo=dt.timezone.utc).timestamp()
    badge = render_freshness(now - 3 * 86400, now=now)
    assert "3 day" in badge or "tag" in badge.lower()


def test_render_freshness_old():
    now = dt.datetime(2026, 5, 8, tzinfo=dt.timezone.utc).timestamp()
    badge = render_freshness(now - 100 * 86400, now=now)
    assert "month" in badge.lower() or "monat" in badge.lower()


def test_plan_sync_lists_only_public(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    plan = plan_sync(vault_copy, db_path)
    rels = [p["relpath"] for p in plan]
    assert rels == ["concepts/note-b.md"]


def test_cli_sync_dry_run(vault_copy: Path, db_path: Path, tmp_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(cli, ["sync", "--vault", str(vault_copy), "--db", str(db_path), "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "would write 1 page" in res.output.lower()
    # no files created
    assert not (tmp_path / "wiki-pages").exists()


def test_cli_sync_apply_writes_pages(vault_copy: Path, db_path: Path, tmp_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(cli, ["sync", "--vault", str(vault_copy), "--db", str(db_path)])
    assert res.exit_code == 0, res.output
    out = tmp_path / "wiki-pages" / "concepts" / "note-b.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Note B" in text
    # private pages must not be written
    priv = tmp_path / "wiki-pages" / "concepts" / "note-a.md"
    assert not priv.exists()
