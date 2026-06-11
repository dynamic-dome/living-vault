"""Build the seance website bundle: persona cards + demo conversations.

Fail-closed: every persona MUST be on the allowlist; neighbors are
stripped to allowlist members. NOTE: body_excerpt may still contain
[[wikilinks]] to non-allowlisted pages — the bundle validator
(validate_bundle_text, Task A3) MUST check wikilink targets against
the allowlist before any deploy.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from living_vault.core import db as db_mod
from living_vault.core.graph import extract_wikilinks, neighbors, resolve_target
from living_vault.core.persona import build_persona
from living_vault.core.privacy import load_allowlist


# ---------------------------------------------------------------------------
# Bundle validator (Task A3)
# ---------------------------------------------------------------------------

_FORBIDDEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[A-Za-z]:[\\/](?:Users|home)\b"), "machine-path (windows)"),
    # Negative lookbehind (?<![A-Za-z]:) excludes "/Users" that is the slash-segment of
    # a Windows path like "C:/Users" — the drive letter + colon occupy exactly the 2
    # chars immediately before the "/" that starts the match.
    (re.compile(r"(?<![A-Za-z]:)/(?:Users|home)/[A-Za-z]"), "machine-path (posix)"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"), "secret-like key"),
    (re.compile(r"\bANTHROPIC_API_KEY\b"), "secret env name"),
]


def _extract_string_values(obj: object) -> list[str]:
    """Recursively collect all string leaf values from a parsed JSON object."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        out: list[str] = []
        for v in obj.values():
            out.extend(_extract_string_values(v))
        return out
    if isinstance(obj, list):
        out = []
        for item in obj:
            out.extend(_extract_string_values(item))
        return out
    return []


def validate_bundle_text(text: str, allowed: set[str] | None = None) -> list[str]:
    """Sweep a serialized bundle JSON for things that must never go public.

    Check 1 — forbidden patterns (machine paths / secrets):
        Scans the raw JSON text for patterns that indicate private machine paths
        or secret credentials.

    Check 2 — allowlist-aware wikilink check (only when allowed is not None):
        Parses the JSON and extracts all string values, then uses the repo's
        existing extract_wikilinks() + resolve_target() (from graph.py) to find
        wikilink targets. Every resolved relpath not present in ``allowed`` is
        flagged. This approach scans parsed string values rather than raw JSON
        text so that JSON escaping (e.g. ``\\|`` for alias pipes) is handled
        transparently by the json.loads step.

    Returns a list of finding strings. Empty list = clean.
    """
    findings: list[str] = []

    # Check 1: forbidden pattern sweep over raw JSON text
    for pattern, label in _FORBIDDEN:
        for m in pattern.finditer(text):
            start = max(0, m.start() - 25)
            snippet = text[start:m.end() + 25]
            findings.append(f"{label}: ...{snippet}...")

    # Check 2: wikilink allowlist check (skipped when allowed is None)
    if allowed is not None:
        try:
            bundle = json.loads(text)
        except json.JSONDecodeError:
            # If we can't parse the JSON, skip the wikilink check — check 1
            # already covers the raw text for the most sensitive patterns.
            return findings

        for value in _extract_string_values(bundle):
            for target, _alias in extract_wikilinks(value):
                resolved = resolve_target(target)
                if resolved is not None and resolved not in allowed:
                    findings.append(
                        f"wikilink outside allowlist: {resolved} (from [[{target}]])"
                    )

    return findings


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
    seen: set[str] = set()
    duplicates = [p for p in persona_paths if p in seen or seen.add(p)]  # type: ignore[func-returns-value]
    if duplicates:
        raise SeanceExportError(f"duplicate persona_paths (would collide card ids): {duplicates}")
    cards = [_build_card(vault_root, db_path, p, allowed) for p in persona_paths]
    demo = _load_demo(demo_path) if demo_path is not None else []
    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "personas": cards,
        "demo_conversations": demo,
    }


def _load_demo(demo_path: Path) -> list:
    try:
        raw = json.loads(demo_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SeanceExportError(f"cannot load demo file {demo_path}: {e}") from e
    if not isinstance(raw, list):
        raise SeanceExportError("demo file must be a JSON list of conversations")
    for conv in raw:
        if not isinstance(conv, dict) or "title" not in conv or "turns" not in conv:
            raise SeanceExportError("demo conversation needs 'title' and 'turns'")
    return raw
