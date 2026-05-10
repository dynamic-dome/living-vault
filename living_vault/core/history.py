"""Git history lookup for vault pages (Phase 13).

Live `git log` via subprocess, memoized with a TTL-LRU cache so repeated
calls within a 60-second window do not respawn the subprocess.

Defensive: returns [] (not raises) when git is missing, the path is
outside any repo, or the file has no history. The MCP/CLI/build callers
treat empty history as a normal "no info available" signal.
"""
from __future__ import annotations
import subprocess
import time
from pathlib import Path


_DEFAULT_TTL_SECONDS = 60.0
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 100
_SUBPROCESS_TIMEOUT_SECONDS = 5.0

# (resolved_vault_root, relpath, limit) -> (timestamp, value)
_CACHE: dict[tuple, tuple[float, list[dict]]] = {}


def _find_git_root(start: Path) -> Path | None:
    """Walk upwards from `start` until a directory containing `.git` is found."""
    p = start.resolve()
    while True:
        if (p / ".git").exists():
            return p
        if p.parent == p:
            return None
        p = p.parent


def page_history(
    vault_root: Path,
    relpath: str,
    *,
    limit: int = _DEFAULT_LIMIT,
    ttl: float = _DEFAULT_TTL_SECONDS,
) -> list[dict]:
    """Return the last `limit` commits affecting `relpath`, newest first.

    Each row: {"sha", "date" (ISO-8601), "author", "subject"}.
    Returns [] for any failure mode (no git, no repo, path outside repo,
    no history, subprocess timeout/error).
    """
    if limit < 1:
        limit = 1
    if limit > _MAX_LIMIT:
        limit = _MAX_LIMIT

    key = (str(Path(vault_root).resolve()), relpath, limit)
    now = time.time()
    cached = _CACHE.get(key)
    if cached is not None and now - cached[0] < ttl:
        return cached[1]

    result = _git_log_for_path(Path(vault_root), relpath, limit)
    _CACHE[key] = (now, result)
    return result


def _git_log_for_path(vault_root: Path, relpath: str, limit: int) -> list[dict]:
    git_root = _find_git_root(vault_root)
    if git_root is None:
        return []

    abs_target = (vault_root / relpath).resolve()
    try:
        rel_to_repo = abs_target.relative_to(git_root)
    except ValueError:
        # path traverses out of repo
        return []

    sep = "\x1f"  # ASCII unit separator — won't collide with commit subjects
    fmt = sep.join(["%h", "%aI", "%an", "%s"])

    try:
        proc = subprocess.run(
            [
                "git", "-C", str(git_root), "log",
                "--follow",  # Phase 13.x: track history across renames
                "-n", str(limit),
                f"--format={fmt}",
                "--",
                str(rel_to_repo).replace("\\", "/"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if proc.returncode != 0:
        return []

    rows: list[dict] = []
    for line in proc.stdout.splitlines():
        parts = line.split(sep)
        if len(parts) != 4:
            continue
        sha, date, author, subject = parts
        rows.append({
            "sha": sha,
            "date": date,
            "author": author,
            "subject": subject,
        })
    return rows


def clear_cache() -> None:
    """Reset the in-memory TTL-LRU cache. Intended for tests and the build CLI."""
    _CACHE.clear()
