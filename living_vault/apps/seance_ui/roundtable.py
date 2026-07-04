"""Phase-10b: roundtable orchestration helpers.

This module owns:
  - pick_speakers: mode-logic that returns which personas speak this turn.
  - _parse_mentions: @-mention parsing for moderator mode.
  - hash_color: deterministic persona color from path.
  - shared_history_for_persona: render the shared conversation from one
    persona's view, with [other says]: prefix on teammate replies.

It does NOT call the LLM, write to DB, or know about FastAPI. It's pure
functions over data structures (lists/dicts) so it can be tested cheaply.
"""
from __future__ import annotations
import re
from pathlib import Path

from living_vault.core import db as db_mod
from living_vault.core.embeddings import search_semantic


# 8-color palette tuned for the dark séance UI theme.
PALETTE: list[str] = [
    "#7adfd5",   # cyan
    "#a8e6cf",   # mint
    "#c9b3ff",   # lavender
    "#ffd3a5",   # peach
    "#fda4af",   # rose
    "#fde68a",   # gold
    "#bbf7d0",   # sage
    "#a5d8ff",   # sky
]


# All known session modes. Used by summon() to validate user input.
# Note: 'single' is in this set (it's a valid session mode), but pick_speakers
# only accepts the three roundtable modes — single-mode sessions never reach
# pick_speakers because say() branches on mode and routes single → existing
# Phase-10a path, not roundtable_say.
VALID_MODES = frozenset({"single", "roundrobin", "moderator", "freeforall", "auto"})
ROUNDTABLE_MODES = frozenset({"roundrobin", "moderator", "freeforall", "auto"})


def hash_color(persona_path: str) -> str:
    """Deterministic color from path. Same path always gets same color
    across processes (Python's built-in hash() is randomized by default
    since 3.3, so we use a stable cheap alternative).

    MIRROR: living_vault/apps/seance_ui/static/index.html `hashColorJs()`
    must use the same PALETTE order and the same sum-of-char-codes hash,
    otherwise historical session replays show different colors than live
    sessions. If you change PALETTE here, update both."""
    h = sum(ord(c) for c in persona_path)
    return PALETTE[h % len(PALETTE)]


def _parse_mentions(text: str, personas: list[dict]) -> list[dict]:
    """Find @{stem} mentions in text and return matching personas in order
    of first appearance. Case-insensitive. Each persona appears at most once
    in the result (the per-persona `break` below caps it after the first hit).

    The negative lookbehind `(?<![\\w.])` guards against false positives in
    email addresses (e.g. "ping@alpha.com" should NOT match the @alpha mention,
    because the `@` is preceded by `g` which is a word char). Standalone `@alpha`
    or punctuation-prefixed `, @alpha` still match correctly."""
    text_lower = text.lower()
    # Collect (position, persona) pairs, then sort by position so that
    # "@gamma and @alpha" returns [gamma, alpha].
    positions: list[tuple[int, dict]] = []
    for p in personas:
        stem = Path(p["persona_path"]).stem.lower()
        # left-side: prevent email-like matches (no word char or '.' before @)
        # right-side: word boundary so @alpha doesn't swallow @alphabet
        for m in re.finditer(rf"(?<![\w.])@{re.escape(stem)}\b", text_lower):
            positions.append((m.start(), p))
            break  # first hit per persona is enough — caps the dedup
    positions.sort(key=lambda t: t[0])
    return [p for _, p in positions]


def pick_speakers(
    *,
    mode: str,
    user_text: str,
    personas: list[dict],
    turn_idx: int,
) -> list[dict]:
    """Decide which personas speak this turn given the mode.

    Args:
      mode: one of 'roundrobin', 'moderator', 'freeforall'
            ('single' is handled outside this function — say() never
            calls into roundtable_say for single-mode sessions.)
      user_text: the latest user message (used by moderator mode).
      personas: ordered by seat_idx, ascending.
      turn_idx: 0-indexed count of user turns so far in this session.

    Returns: ordered list of personas that should speak this turn.
    """
    if not personas:
        return []

    if mode == "freeforall":
        return list(personas)

    if mode == "moderator":
        mentioned = _parse_mentions(user_text, personas)
        if mentioned:
            return mentioned
        # fall through to round-robin behavior on no-mention
        return [personas[turn_idx % len(personas)]]

    if mode == "roundrobin":
        return [personas[turn_idx % len(personas)]]

    raise ValueError(f"unknown mode: {mode}")


def pick_auto_speakers(
    *,
    db_path,
    user_text: str,
    personas: list[dict],
    turn_idx: int,
    max_speakers: int = 3,
) -> list[dict]:
    """Pick relevant already-summoned personas using semantic search.

    The search may return any page in the DB, but this function only admits
    paths already present in the current session's persona list.
    """
    if not personas:
        return []
    if not user_text.strip():
        return [personas[turn_idx % len(personas)]]

    by_path = {p["persona_path"]: p for p in personas}
    seats = {p["persona_path"]: p.get("seat_idx", i) for i, p in enumerate(personas)}
    k = max(16, len(personas) * 3)
    con = db_mod.connect(db_path)
    try:
        rows = search_semantic(con, user_text, k=k)
    finally:
        con.close()

    scored: list[tuple[float, int, dict]] = []
    seen: set[str] = set()
    for path, score in rows:
        if path not in by_path or path in seen or score <= 0:
            continue
        seen.add(path)
        scored.append((score, seats[path], by_path[path]))

    if not scored:
        return [personas[turn_idx % len(personas)]]

    scored.sort(key=lambda t: (-t[0], t[1]))
    cap = max(1, min(max_speakers, len(personas)))
    return [p for _, _, p in scored[:cap]]


def shared_history_for_persona(
    db_path,
    session_id: int,
    persona_path: str,
) -> list[tuple[str, str]]:
    """Build a persona-specific view of the shared roundtable history.

    Anthropic's API only knows 'user' and 'assistant' roles. We simulate
    'third party persona' by wrapping other personas' replies as labeled
    user-content (e.g. '[alpha says]: ...'), so persona-X can read what
    teammates said as if it were external user context.

    Filtering rules:
      - role == 'user' → ('user', text) unchanged
      - role == 'assistant' AND persona_path == this → ('assistant', text)
      - role == 'assistant' AND other persona → ('user', '[stem says]: text')
      - role == 'tool_use' → SKIPPED (Phase-10a asymmetry preserved)
    """
    from living_vault.core import db as db_mod
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT role, content, persona_path FROM seance_messages "
            "WHERE session_id = ? AND role IN ('user', 'assistant') "
            "ORDER BY id",
            (session_id,),
        ).fetchall()
        out: list[tuple[str, str]] = []
        for r in rows:
            if r["role"] == "user":
                out.append(("user", r["content"]))
                continue
            # role == 'assistant'
            if r["persona_path"] == persona_path:
                out.append(("assistant", r["content"]))
            else:
                other_stem = Path(r["persona_path"] or "").stem or "unknown"
                out.append(("user", f"[{other_stem} says]: {r['content']}"))
        return out
    finally:
        con.close()
