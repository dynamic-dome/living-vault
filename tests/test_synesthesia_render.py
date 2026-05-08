from pathlib import Path
import json
from click.testing import CliRunner

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.apps.synesthesia.render import cli


def test_render_writes_html(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "out.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(cli, ["--db", str(db), "--output", str(out)])
    assert res.exit_code == 0, res.output
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "concepts/note-a.md" in text
    assert "<canvas" in text or "renderer.domElement" in text


def test_render_public_only_excludes_private(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "pub.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(cli, ["--db", str(db), "--output", str(out), "--public-only"])
    assert res.exit_code == 0, res.output
    text = out.read_text(encoding="utf-8")
    assert "concepts/note-b.md" in text       # public
    assert "concepts/note-a.md" not in text   # private must NOT appear
    assert "synthesis/syn-1.md" not in text   # also private
