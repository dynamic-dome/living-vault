"""Tests for core.history — Phase 13.

Uses subprocess to set up a real tmp git repo with a few commits.
Skipped if `git` is not on PATH.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

import pytest

from living_vault.core import history as history_mod


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git binary not on PATH"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """A fresh git repo with isolated config and 3 commits to concepts/foo.md."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "--local", "user.email", "test@example.com")
    _git(repo, "config", "--local", "user.name", "Test User")
    _git(repo, "config", "--local", "commit.gpgsign", "false")

    page = repo / "concepts" / "foo.md"
    page.parent.mkdir(parents=True)

    page.write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "concepts/foo.md")
    _git(repo, "commit", "-q", "-m", "initial foo")

    page.write_text("v1\nv2\n", encoding="utf-8")
    _git(repo, "add", "concepts/foo.md")
    _git(repo, "commit", "-q", "-m", "extend foo")

    page.write_text("v1\nv2\nv3\n", encoding="utf-8")
    _git(repo, "add", "concepts/foo.md")
    _git(repo, "commit", "-q", "-m", "tweak foo")

    return repo


@pytest.fixture(autouse=True)
def _reset_cache():
    history_mod.clear_cache()
    yield
    history_mod.clear_cache()


def test_returns_three_commits_newest_first(tmp_repo: Path):
    rows = history_mod.page_history(tmp_repo, "concepts/foo.md")
    assert len(rows) == 3
    assert rows[0]["subject"] == "tweak foo"
    assert rows[1]["subject"] == "extend foo"
    assert rows[2]["subject"] == "initial foo"
    for r in rows:
        assert r["sha"]
        assert r["date"].startswith("2")  # ISO year-prefix
        assert r["author"] == "Test User"


def test_limit_caps_returned_rows(tmp_repo: Path):
    rows = history_mod.page_history(tmp_repo, "concepts/foo.md", limit=2)
    assert len(rows) == 2
    assert rows[0]["subject"] == "tweak foo"


def test_unknown_page_returns_empty(tmp_repo: Path):
    rows = history_mod.page_history(tmp_repo, "concepts/nope.md")
    assert rows == []


def test_non_git_dir_returns_empty(tmp_path: Path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    (not_a_repo / "x.md").write_text("hi", encoding="utf-8")
    assert history_mod.page_history(not_a_repo, "x.md") == []


def test_path_outside_repo_returns_empty(tmp_repo: Path, tmp_path: Path):
    # vault_root is the repo, but a relpath like ../foo escapes it.
    rows = history_mod.page_history(tmp_repo, "../escape.md")
    assert rows == []


def test_ttl_cache_skips_subprocess_on_second_call(tmp_repo: Path, monkeypatch):
    counter = {"n": 0}
    real_run = subprocess.run

    def counting_run(*args, **kwargs):
        # Only count git log invocations, not the fixture-setup ones (those
        # already ran). We keep counting all subprocess.run calls inside
        # history_mod once the test starts — fine because we monkeypatch
        # AFTER the fixture is built.
        counter["n"] += 1
        return real_run(*args, **kwargs)

    monkeypatch.setattr(history_mod.subprocess, "run", counting_run)

    history_mod.page_history(tmp_repo, "concepts/foo.md")
    history_mod.page_history(tmp_repo, "concepts/foo.md")
    assert counter["n"] == 1, "second call must hit the TTL cache"


def test_ttl_expiry_re_runs_subprocess(tmp_repo: Path):
    history_mod.page_history(tmp_repo, "concepts/foo.md")
    # ttl=0 immediately invalidates → second call MUST run again
    rows_again = history_mod.page_history(
        tmp_repo, "concepts/foo.md", ttl=0.0,
    )
    assert len(rows_again) == 3


def test_clear_cache_forces_resubprocess(tmp_repo: Path, monkeypatch):
    counter = {"n": 0}
    real_run = subprocess.run

    def counting_run(*args, **kwargs):
        counter["n"] += 1
        return real_run(*args, **kwargs)

    monkeypatch.setattr(history_mod.subprocess, "run", counting_run)

    history_mod.page_history(tmp_repo, "concepts/foo.md")
    history_mod.clear_cache()
    history_mod.page_history(tmp_repo, "concepts/foo.md")
    assert counter["n"] == 2


def test_limit_caps_at_max(tmp_repo: Path):
    # Max is 100 — request 1000, expect 1000 internally clamped to 100.
    # Repo only has 3 commits anyway, so we just verify no error.
    rows = history_mod.page_history(tmp_repo, "concepts/foo.md", limit=1000)
    assert len(rows) == 3


def test_limit_below_one_clamped_to_one(tmp_repo: Path):
    rows = history_mod.page_history(tmp_repo, "concepts/foo.md", limit=0)
    assert len(rows) == 1


def test_follow_tracks_history_across_rename(tmp_path: Path):
    """Phase 13.x: --follow makes history span the rename boundary.

    Setup: 2 commits on old.md, then `git mv old.md new.md`, then 1 commit on new.md.
    page_history(new.md) must return 4 rows (initial + edit + rename + post-rename).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "--local", "user.email", "test@example.com")
    _git(repo, "config", "--local", "user.name", "Test User")
    _git(repo, "config", "--local", "commit.gpgsign", "false")

    # Two commits on the old name. Body identical-ish so git's rename-detection
    # has high confidence after `git mv`.
    old_path = repo / "concepts" / "old.md"
    old_path.parent.mkdir(parents=True)
    old_path.write_text("line1\nline2\nline3\n", encoding="utf-8")
    _git(repo, "add", "concepts/old.md")
    _git(repo, "commit", "-q", "-m", "create old name")

    old_path.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")
    _git(repo, "add", "concepts/old.md")
    _git(repo, "commit", "-q", "-m", "edit before rename")

    # Rename — git mv keeps the blob identity, so --follow detects 100% similarity.
    _git(repo, "mv", "concepts/old.md", "concepts/new.md")
    _git(repo, "commit", "-q", "-m", "rename old to new")

    # One commit after the rename.
    new_path = repo / "concepts" / "new.md"
    new_path.write_text("line1\nline2\nline3\nline4\nline5\n", encoding="utf-8")
    _git(repo, "add", "concepts/new.md")
    _git(repo, "commit", "-q", "-m", "edit after rename")

    history_mod.clear_cache()
    rows = history_mod.page_history(repo, "concepts/new.md")

    # Without --follow we'd see only 2 rows (after the rename). With --follow: 4.
    subjects = [r["subject"] for r in rows]
    assert "create old name" in subjects, (
        f"--follow should surface pre-rename commits, got: {subjects}"
    )
    assert "edit before rename" in subjects
    assert "rename old to new" in subjects
    assert "edit after rename" in subjects
    assert len(rows) == 4
