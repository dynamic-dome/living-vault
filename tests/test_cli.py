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
