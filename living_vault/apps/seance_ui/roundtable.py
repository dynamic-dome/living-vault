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
VALID_MODES = frozenset({"single", "roundrobin", "moderator", "freeforall"})
ROUNDTABLE_MODES = frozenset({"roundrobin", "moderator", "freeforall"})


def hash_color(persona_path: str) -> str:
    """Deterministic color from path. Same path always gets same color
    across processes (Python's built-in hash() is randomized by default
    since 3.3, so we use a stable cheap alternative)."""
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
