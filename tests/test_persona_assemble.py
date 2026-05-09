"""Tests for the pure assemble_persona() function.

Three voice-block cases plus an edge case (no frontmatter).
"""
from __future__ import annotations
from living_vault.core.persona import assemble_persona


def _stylo() -> dict:
    return {
        "avg_sentence_length": 12.0,
        "sentence_length_stddev": 5.0,
        "question_rate": 0.1,
        "exclamation_rate": 0.0,
        "first_person_rate": 0.2,
        "second_person_rate": 0.05,
        "preferred_separator": "—",
        "list_density": 0.3,
        "code_density": 0.0,
        "wikilink_density": 1.5,
        "top_phrases": ["in der praxis", "siehe auch"],
        "register": "informal-de",
    }


def test_case_a_stylometric_plus_distilled():
    persona = assemble_persona(
        path="concepts/x.md",
        title="X",
        frontmatter={"created": "2026-04-01", "tags": ["alpha", "beta"]},
        body_excerpt="The opening paragraph...",
        voice_features=_stylo(),
        voice_distilled="Speaks in compact, declarative German...",
    )
    assert persona["path"] == "concepts/x.md"
    assert persona["title"] == "X"
    assert persona["era_marker"] == "2026-04-01"
    assert persona["themes"] == ["alpha", "beta"]
    assert persona["voice_features"] == _stylo()
    assert persona["voice_distilled"] == "Speaks in compact, declarative German..."
    assert persona["body_excerpt"].startswith("The opening")
    # legacy field "voice_sample" must NOT be present
    assert "voice_sample" not in persona


def test_case_b_stylometric_only_no_distilled():
    persona = assemble_persona(
        path="x.md",
        title="X",
        frontmatter={"created": "2026-04-01", "tags": ["alpha"]},
        body_excerpt="opening",
        voice_features=_stylo(),
        voice_distilled=None,
    )
    assert persona["voice_features"] == _stylo()
    assert persona["voice_distilled"] is None


def test_case_c_no_voice_features_at_all():
    """Old DB without Phase-9 schema — both columns missing."""
    persona = assemble_persona(
        path="x.md",
        title="X",
        frontmatter={"created": "2026-04-01", "tags": []},
        body_excerpt="opening",
        voice_features=None,
        voice_distilled=None,
    )
    assert persona["voice_features"] is None
    assert persona["voice_distilled"] is None
    # all other fields still present
    assert persona["body_excerpt"] == "opening"


def test_empty_frontmatter_yields_safe_defaults():
    persona = assemble_persona(
        path="x.md",
        title="X",
        frontmatter={},
        body_excerpt="opening",
        voice_features=_stylo(),
        voice_distilled=None,
    )
    assert persona["era_marker"] == ""
    assert persona["themes"] == []
    assert persona["frontmatter"] == {}
