"""Privacy regression: verify no private path appears in public builds.

This is a high-stakes test. If it ever fails, do NOT merge — investigate.
"""
from pathlib import Path
from click.testing import CliRunner

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.apps.synesthesia.render import cli as render_cli
from living_vault.core.privacy import public_pages
from living_vault.core import db as db_mod2


def test_no_private_path_in_public_synesthesia_build(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "pub.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(render_cli, ["--db", str(db), "--output", str(out), "--public-only"])
    assert res.exit_code == 0
    text = out.read_text(encoding="utf-8")

    con = db_mod2.connect(db)
    public = set(public_pages(con))
    all_pages = {r[0] for r in con.execute("SELECT path FROM pages")}
    private = all_pages - public
    con.close()

    for priv in private:
        assert priv not in text, f"PRIVACY LEAK: private path {priv} found in public build"


from living_vault.apps.portfolio_sync.sync import cli as portfolio_cli


def test_no_private_in_portfolio_sync(vault_copy: Path, tmp_path: Path, monkeypatch):
    db = tmp_path / ".vault-engine.db"
    target = tmp_path / "site"
    target.mkdir()
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(target))
    runner = CliRunner()
    res = runner.invoke(
        portfolio_cli,
        ["sync", "--vault", str(vault_copy), "--db", str(db)],
    )
    assert res.exit_code == 0, res.output
    # Private pages must NEVER appear under target
    private_paths = ["concepts/note-a.md", "synthesis/syn-1.md"]
    for priv in private_paths:
        candidate = target / "wiki-pages" / priv
        assert not candidate.exists(), f"PRIVACY LEAK: {candidate} written"
