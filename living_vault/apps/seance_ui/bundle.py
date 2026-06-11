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
    # Captures the full path token so two distinct paths (e.g. C:\Users\domes\...
    # and C:\Users\alice\...) produce different dedup keys and are not collapsed.
    # Tolerates 1-2 separators so json.dumps-doubled backslash (C:\\Users) is caught
    # by the raw-text sweep and the single-backslash parsed value deduplicates via
    # _normalise_match (separator-run collapse).
    (re.compile(r"[A-Za-z]:[\\/]{1,2}(?:Users|home)\b[^\s\"',)\]}]*"), "machine-path (windows)"),
    # Negative lookbehind (?<![A-Za-z]:) excludes "/Users" that is the slash-segment
    # of a Windows path like "C:/Users".  Captures the full posix path token so
    # /Users/domes/... and /Users/alice/... have distinct dedup keys.
    # MINOR M2 fix: widen username char class to [\w.] to catch /home/.config/ and
    # /home/4user/ (dot and digit prefixes).
    (re.compile(r"(?<![A-Za-z]:)/(?:Users|home)/[\w.][^\s\"',)\]}]*"), "machine-path (posix)"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"), "secret-like key"),
    (re.compile(r"\bANTHROPIC_API_KEY\b"), "secret env name"),
    # MINOR M3: tilde home paths (Unix ~/... or Windows ~\...) — full token captured.
    (re.compile(r"~[\\/][^\s\"',)\]}]*"), "machine-path (home tilde)"),
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


_PERMISSIVE_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def validate_bundle_text(text: str, allowed: set[str] | None = None) -> list[str]:
    """Sweep a serialized bundle JSON for things that must never go public.

    Check 1 — forbidden patterns (machine paths / secrets):
        Scans the raw JSON text for patterns that indicate private machine paths
        or secret credentials. When the text is valid JSON, the same pattern
        sweep is ALSO run over parsed string values (catches backslash-doubling
        from json.dumps and \\uXXXX-escape blind spots). Duplicate findings
        (same label + same snippet prefix) are deduplicated.

    Check 2 — allowlist-aware wikilink check (only when allowed is not None):
        Parses the JSON and extracts all string values, then uses the repo's
        existing extract_wikilinks() + resolve_target() (from graph.py) to find
        wikilink targets. Every resolved relpath not present in ``allowed`` is
        flagged. Additionally scans each string value with a permissive regex to
        catch non-wiki/ wikilinks; those that don't resolve are flagged as
        unresolvable (leak page names). Requires parseable JSON — if parsing
        fails, returns a single "invalid bundle JSON" finding.

    Returns a list of finding strings. Empty list = clean.
    """
    findings: list[str] = []
    # Dedup key: (label, normalised_matched_text) so raw-sweep and parsed-sweep hits on
    # the same underlying value collapse to a single finding regardless of snippet
    # context.  Windows-path matches normalise separator runs (C:\\Users → C:\Users)
    # so the doubled-backslash in raw JSON and the single-backslash in parsed values
    # deduplicate correctly.
    seen_match_keys: set[tuple[str, str]] = set()

    def _normalise_match(label: str, matched: str) -> str:
        """Normalise a matched string for dedup purposes."""
        if label == "machine-path (windows)":
            # Collapse consecutive separators (e.g. \\ → \) so raw+parsed dedup.
            return re.sub(r"[\\/]+", "\\\\", matched)
        return matched

    def _add_finding(label: str, matched: str, finding_str: str) -> None:
        """Add finding with (label, normalised_matched_text) deduplication."""
        key = (label, _normalise_match(label, matched))
        if key not in seen_match_keys:
            seen_match_keys.add(key)
            findings.append(finding_str)

    def _snippet_for(m: re.Match, source_text: str, label: str) -> str:
        """Build a snippet for a match, truncating secret-like key matches."""
        if label == "secret-like key":
            # MINOR M1: truncate matched span so secret value is not leaked
            matched_display = m.group()[:12] + "…"
            start = max(0, m.start() - 25)
            prefix = source_text[start:m.start()]
            return f"{label}: ...{prefix}{matched_display}..."
        else:
            start = max(0, m.start() - 25)
            snippet = source_text[start:m.end() + 25]
            return f"{label}: ...{snippet}..."

    # Check 1a: forbidden pattern sweep over raw JSON text
    for pattern, label in _FORBIDDEN:
        for m in pattern.finditer(text):
            _add_finding(label, m.group(), _snippet_for(m, text, label))

    # Check 1b: also sweep parsed string values (catches backslash-doubling and
    # unicode-escape blind spots).  Only attempted when JSON is valid.
    # Note: we attempt parse here regardless of `allowed` so Check 1 is complete.
    parsed_bundle: object = None
    json_parse_error: str | None = None
    try:
        parsed_bundle = json.loads(text)
    except json.JSONDecodeError as e:
        json_parse_error = str(e)

    if parsed_bundle is not None:
        for value in _extract_string_values(parsed_bundle):
            for pattern, label in _FORBIDDEN:
                for m in pattern.finditer(value):
                    _add_finding(label, m.group(), _snippet_for(m, value, label))

    # Check 2: wikilink allowlist check (skipped when allowed is None)
    if allowed is not None:
        if json_parse_error is not None:
            # IMPORTANT 2 fix: fail closed — report the parse error instead of
            # silently skipping the wikilink check.
            finding_str = (
                f"invalid bundle JSON ({json_parse_error}): "
                "wikilink allowlist check could not run"
            )
            _add_finding("invalid bundle JSON", json_parse_error, finding_str)
            return findings

        assert parsed_bundle is not None  # guaranteed if json_parse_error is None
        for value in _extract_string_values(parsed_bundle):
            # IMPORTANT 3: scan every string with a permissive wikilink regex
            # so non-wiki/ links (bare page names, shorthand paths) are caught.
            for raw_match in _PERMISSIVE_WIKILINK_RE.finditer(value):
                inner = raw_match.group(1)
                # Strip alias part (pipe separator)
                target = inner.split("|")[0].strip()
                resolved = resolve_target(target)
                if resolved is not None:
                    if resolved not in allowed:
                        finding_str = (
                            f"wikilink outside allowlist: {resolved} (from [[{target}]])"
                        )
                        _add_finding("wikilink outside allowlist", resolved, finding_str)
                else:
                    # Does not resolve → leaks page name
                    finding_str = (
                        f"unresolvable wikilink (leaks page name): [[{target}]]"
                    )
                    _add_finding("unresolvable wikilink", target, finding_str)

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
