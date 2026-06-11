"""Build the seance website bundle: persona cards + demo conversations.

Fail-closed: every persona MUST be on the allowlist; neighbors are
stripped to allowlist members; the export aborts on validator findings.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from living_vault.core import db as db_mod
from living_vault.core.graph import neighbors
from living_vault.core.persona import build_persona
from living_vault.core.privacy import load_allowlist


class SeanceExportError(Exception):
    """Raised when the bundle cannot be exported safely."""


def _build_card(vault_root: Path, db_path: Path, relpath: str, allowed: set[str]) -> dict:
    persona = build_persona(vault_root, db_path, relpath)
    if persona is None:
        raise SeanceExportError(f"persona page not found in index: {relpath}")
    con = db_mod.connect(db_path)
    try:
        stripped_neighbors = sorted(n for n in neighbors(con, relpath) if n in allowed)
    finally:
        con.close()
    return {
        "id": relpath,
        "title": persona["title"],
        "era_marker": persona["era_marker"],
        "themes": persona["themes"],
        "neighbors": stripped_neighbors,
        "voice": {
            "distilled": persona.get("voice_distilled"),
            "features": persona.get("voice_features") or {},
        },
        "body_excerpt": persona["body_excerpt"],
    }


def build_seance_bundle(
    *,
    vault_root: Path,
    db_path: Path,
    allowlist_path: Path,
    persona_paths: list[str],
    demo_path: Path | None = None,
    now: datetime | None = None,
) -> dict:
    allowed = set(load_allowlist(allowlist_path))
    off_list = [p for p in persona_paths if p not in allowed]
    if off_list:
        raise SeanceExportError(f"personas not on allowlist (fail-closed): {off_list}")
    cards = [_build_card(vault_root, db_path, p, allowed) for p in persona_paths]
    demo = _load_demo(demo_path) if demo_path is not None else []
    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "personas": cards,
        "demo_conversations": demo,
    }


def _load_demo(demo_path: Path) -> list:
    raw = json.loads(demo_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SeanceExportError("demo file must be a JSON list of conversations")
    for conv in raw:
        if not isinstance(conv, dict) or "title" not in conv or "turns" not in conv:
            raise SeanceExportError("demo conversation needs 'title' and 'turns'")
    return raw
