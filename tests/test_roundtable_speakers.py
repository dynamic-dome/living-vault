"""Phase-10b: pick_speakers + mention parser + hash_color tests."""
from __future__ import annotations
import pytest
from living_vault.apps.seance_ui.roundtable import (
    pick_auto_speakers,
    pick_speakers,
    _parse_mentions,
    hash_color,
    PALETTE,
)
from living_vault.core import db as db_mod
from living_vault.core import embeddings as embeddings_mod
from living_vault.core.embeddings import NumpyBackend, index_embeddings
from living_vault.core.indexer import index_vault


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


def test_auto_mode_selects_semantic_session_match(vault_copy, db_path, monkeypatch):
    monkeypatch.setattr(embeddings_mod, "get_backend", lambda: NumpyBackend())
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    personas = [
        {"persona_path": "concepts/note-a.md", "color": "#aaa", "seat_idx": 0},
        {"persona_path": "concepts/note-b.md", "color": "#bbb", "seat_idx": 1},
    ]

    out = pick_auto_speakers(
        db_path=db_path,
        user_text="beta topics",
        personas=personas,
        turn_idx=0,
    )

    assert out[0]["persona_path"] == "concepts/note-b.md"


def test_auto_mode_caps_to_three_speakers(db_path, monkeypatch):
    db_mod.initialize(db_path)
    personas = [
        {"persona_path": "concepts/a.md", "color": "#aaa", "seat_idx": 0},
        {"persona_path": "concepts/b.md", "color": "#bbb", "seat_idx": 1},
        {"persona_path": "concepts/c.md", "color": "#ccc", "seat_idx": 2},
        {"persona_path": "concepts/d.md", "color": "#ddd", "seat_idx": 3},
    ]

    def fake_search_semantic(con, query, k):
        return [
            ("concepts/d.md", 0.9),
            ("concepts/c.md", 0.8),
            ("concepts/b.md", 0.7),
            ("concepts/a.md", 0.6),
        ]

    monkeypatch.setattr(
        "living_vault.apps.seance_ui.roundtable.search_semantic",
        fake_search_semantic,
    )

    out = pick_auto_speakers(
        db_path=db_path,
        user_text="anything",
        personas=personas,
        turn_idx=0,
    )

    assert [p["persona_path"] for p in out] == [
        "concepts/d.md",
        "concepts/c.md",
        "concepts/b.md",
    ]


def test_auto_mode_falls_back_to_roundrobin_without_hits(db_path, monkeypatch):
    db_mod.initialize(db_path)
    personas = _personas()
    monkeypatch.setattr(
        "living_vault.apps.seance_ui.roundtable.search_semantic",
        lambda con, query, k: [("concepts/outside.md", 0.9)],
    )

    out = pick_auto_speakers(
        db_path=db_path,
        user_text="no session match",
        personas=personas,
        turn_idx=1,
    )

    assert out == [personas[1]]


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
