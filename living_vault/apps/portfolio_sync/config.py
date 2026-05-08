"""Resolve target directory for portfolio sync.

Default: C:\\Users\\domes\\desktop\\Claude-Projekte\\cv-dynamic-dome
Override via env LIVING_VAULT_PORTFOLIO_DIR.
"""
from __future__ import annotations
import os
from pathlib import Path

DEFAULT_TARGET = Path(r"C:\Users\domes\desktop\Claude-Projekte\cv-dynamic-dome")


def resolve_target_dir(default: Path | None = None) -> Path:
    env = os.environ.get("LIVING_VAULT_PORTFOLIO_DIR")
    if env:
        return Path(env)
    return Path(default) if default is not None else DEFAULT_TARGET
