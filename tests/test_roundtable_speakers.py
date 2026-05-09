"""Phase-10b: pick_speakers + mention parser + hash_color tests."""
from __future__ import annotations
import pytest
from living_vault.apps.seance_ui.roundtable import (
    pick_speakers,
    _parse_mentions,
    hash_color,
    PALETTE,
)


def _personas() -> list[dict]:
    return [
        {"persona_path": "concepts/alpha.md", "color": "#aaa", "seat_idx": 0},
        {"persona_path": "concepts/beta.md", "color": "#bbb", "seat_idx": 1},
        {"persona_path": "concepts/gamma.md", "color": "#ccc", "seat_idx": 2},
    ]


def test_roundrobin_rotates_by_turn_idx():
    p = _personas()
    assert pick_speakers(mode="roundrobin", user_text="x", personas=p, turn_idx=0) == [p[0]]
    assert pick_speakers(mode="roundrobin", user_text="x", personas=p, turn_idx=1) == [p[1]]
    assert pick_speakers(mode="roundrobin", user_text="x", personas=p, turn_idx=2) == [p[2]]
    assert pick_speakers(mode="roundrobin", user_text="x", personas=p, turn_idx=3) == [p[0]]  # wrap


def test_freeforall_returns_all_in_seat_order():
    p = _personas()
    out = pick_speakers(mode="freeforall", user_text="x", personas=p, turn_idx=42)
    assert out == p  # turn_idx irrelevant for freeforall


def test_moderator_with_mention_picks_matched_persona():
    p = _personas()
    out = pick_speakers(mode="moderator", user_text="@alpha what?", personas=p, turn_idx=0)
    assert out == [p[0]]


def test_moderator_with_multiple_mentions_preserves_order():
    p = _personas()
    out = pick_speakers(mode="moderator", user_text="@gamma and @alpha", personas=p, turn_idx=0)
    # order: gamma first (mentioned first), then alpha
    assert out == [p[2], p[0]]


def test_moderator_without_mention_falls_back_to_roundrobin():
    p = _personas()
    out0 = pick_speakers(mode="moderator", user_text="was meint ihr?", personas=p, turn_idx=0)
    out1 = pick_speakers(mode="moderator", user_text="was meint ihr?", personas=p, turn_idx=1)
    assert out0 == [p[0]]
    assert out1 == [p[1]]


def test_moderator_with_unknown_mention_falls_back_to_roundrobin():
    p = _personas()
    out = pick_speakers(mode="moderator", user_text="@unknown_persona ", personas=p, turn_idx=0)
    assert out == [p[0]]  # fallback to round-robin


def test_parse_mentions_is_case_insensitive():
    p = _personas()
    out = _parse_mentions("@ALPHA tell me", p)
    assert out == [p[0]]


def test_parse_mentions_dedup():
    p = _personas()
    out = _parse_mentions("@alpha and @alpha again", p)
    assert out == [p[0]]


def test_parse_mentions_does_not_match_inside_email():
    """A `@stem` inside an email address (e.g. ping@alpha.com) must NOT match.
    The negative lookbehind in the regex guards against this false positive."""
    p = _personas()
    out = _parse_mentions("Send to ping@alpha.com please", p)
    assert out == []
    # but a standalone mention in the same string still works
    out2 = _parse_mentions("ping@alpha.com but also @alpha standalone", p)
    assert out2 == [p[0]]


def test_parse_mentions_works_after_punctuation():
    """A `@stem` after comma/space must still match (only word chars + dot
    are blocked by the lookbehind)."""
    p = _personas()
    out = _parse_mentions("Hey,@alpha what?", p)
    assert out == [p[0]]
    out2 = _parse_mentions("@alpha at start", p)
    assert out2 == [p[0]]


def test_hash_color_is_deterministic_and_in_palette():
    c1 = hash_color("concepts/alpha.md")
    c2 = hash_color("concepts/alpha.md")
    c3 = hash_color("concepts/beta.md")
    assert c1 == c2  # determinism
    assert c1 in PALETTE
    assert c3 in PALETTE
    # colors may or may not differ depending on path-bucket — both are fine
