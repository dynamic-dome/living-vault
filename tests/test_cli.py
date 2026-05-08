from pathlib import Path
from click.testing import CliRunner

from living_vault.cli import cli


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
