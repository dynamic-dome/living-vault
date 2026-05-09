"""Phase-9 system prompt with three voice_block cases.

Case A — voice_distilled present + voice_features
Case B — voice_features only (voice_distilled is None)
Case C — neither (both NULL, e.g. very old DB)
"""
from __future__ import annotations
from living_vault.apps.seance_ui.prompt import build_system_prompt, build_voice_block


def _stylo() -> dict:
    return {
        "avg_sentence_length": 14.0,
        "sentence_length_stddev": 6.0,
        "question_rate": 0.1,
        "exclamation_rate": 0.0,
        "first_person_rate": 0.15,
        "second_person_rate": 0.0,
        "preferred_separator": "—",
        "list_density": 0.2,
        "code_density": 0.0,
        "wikilink_density": 0.5,
        "top_phrases": ["in der praxis", "siehe auch"],
        "register": "informal-de",
    }


def _persona_full() -> dict:
    return {
        "path": "concepts/x.md",
        "title": "X",
        "era_marker": "2026-04-01",
        "themes": ["alpha", "example"],
        "frontmatter": {"type": "concept"},
        "body_excerpt": "Opening words of the page about X.",
        "voice_features": _stylo(),
        "voice_distilled": "Speaks in compact German with em-dashes; reflective tone.",
    }


def test_voice_block_case_a_distilled_plus_stylometric():
    block = build_voice_block(_persona_full())
    assert "Speaks in compact German" in block
    assert "14" in block  # avg_sentence_length
    assert "in der praxis" in block
    assert "—" in block


def test_voice_block_case_b_stylometric_only():
    p = _persona_full()
    p["voice_distilled"] = None
    block = build_voice_block(p)
    assert "Speaks in compact German" not in block
    assert "14" in block
    assert "in der praxis" in block
    assert "informal-de" in block


def test_voice_block_case_c_no_voice_data():
    p = _persona_full()
    p["voice_distilled"] = None
    p["voice_features"] = None
    block = build_voice_block(p)
    assert "no extracted voice profile" in block.lower()


def test_system_prompt_contains_anti_hallucination_clause():
    p = _persona_full()
    out = build_system_prompt(p, neighbor_titles=["note-b", "syn-1"])
    assert "concepts/x.md" in out
    assert "2026-04-01" in out
    assert "do not invent" in out.lower()
    assert "note-b" in out
    assert "Opening words" in out


def test_system_prompt_renders_voice_block_inline():
    p = _persona_full()
    out = build_system_prompt(p, neighbor_titles=[])
    # Voice character must be in the prompt body
    assert "Speaks in compact German" in out


def test_system_prompt_handles_empty_themes():
    p = {
        "path": "x.md",
        "title": "x",
        "era_marker": "",
        "themes": [],
        "frontmatter": {},
        "body_excerpt": "",
        "voice_features": None,
        "voice_distilled": None,
    }
    out = build_system_prompt(p, neighbor_titles=[])
    assert "x.md" in out
    assert "no extracted voice profile" in out.lower()


def test_voice_block_falls_back_when_features_missing_required_keys():
    """Defensive: a malformed voice_features dict (missing required keys)
    must NOT crash with KeyError — fall through to Case C."""
    p = _persona_full()
    p["voice_distilled"] = None
    # remove a required key
    p["voice_features"] = {k: v for k, v in p["voice_features"].items() if k != "avg_sentence_length"}
    block = build_voice_block(p)
    # falls through to Case C
    assert "no extracted voice profile" in block.lower()


# === Phase-10a-hotfix: neighbor_paths must be in the system prompt for tool-use ===


def test_system_prompt_includes_full_neighbor_paths_when_provided():
    """Phase-10a: when consult_neighbor is available, the LLM must see the
    EXACT relpaths of its neighbors — not just titles — so it can pass them
    verbatim to the tool. Without this, the LLM would have to guess paths
    and would call consult_neighbor with paths that fail the allowlist
    (e.g. its own path-stem instead of the neighbor's actual relpath)."""
    p = _persona_full()
    out = build_system_prompt(
        p,
        neighbor_titles=["a2a-protokoll", "mcp-gateway"],
        neighbor_paths=[
            "concepts/a2a-protokoll.md",
            "concepts/mcp-gateway.md",
        ],
    )
    # full paths must be in the prompt verbatim
    assert "concepts/a2a-protokoll.md" in out
    assert "concepts/mcp-gateway.md" in out
    # and the prompt must mention consult_neighbor so the LLM knows to use the paths
    assert "consult_neighbor" in out


def test_system_prompt_neighbor_paths_optional_for_phase1_compat():
    """Phase-1 callers that only pass neighbor_titles must still work
    (the parameter is optional)."""
    p = _persona_full()
    out = build_system_prompt(p, neighbor_titles=["note-b", "syn-1"])
    assert "note-b" in out
    # consult_neighbor mention is fine to omit when no paths are passed
    # (we don't strictly require its absence — the test just verifies the
    # legacy two-argument call shape still works without raising)


# === Phase-10b Task 5: teammate_paths for roundtable context ===


def test_system_prompt_includes_teammate_paths_when_provided():
    """Phase-10b: when in a roundtable, the persona must know who else is at
    the table so it can decide to consult them via consult_neighbor."""
    p = _persona_full()
    out = build_system_prompt(
        p,
        neighbor_titles=["x", "y"],
        neighbor_paths=["concepts/x.md", "concepts/y.md"],
        teammate_paths=["concepts/teammate-a.md", "concepts/teammate-b.md"],
    )
    assert "concepts/teammate-a.md" in out
    assert "concepts/teammate-b.md" in out
    # the prompt mentions the roundtable context
    assert "Tisch" in out or "teammates" in out.lower() or "roundtable" in out.lower()


def test_system_prompt_no_teammate_block_when_paths_empty():
    p = _persona_full()
    out = build_system_prompt(
        p,
        neighbor_titles=["x"],
        neighbor_paths=["concepts/x.md"],
        teammate_paths=[],
    )
    # empty list: no teammate-block content
    assert "Tisch" not in out and "teammates" not in out.lower() and "roundtable" not in out.lower()


def test_system_prompt_teammate_paths_optional_for_phase10a_compat():
    """Phase-10a callers that only pass neighbor_paths must still work."""
    p = _persona_full()
    out = build_system_prompt(
        p,
        neighbor_titles=["x"],
        neighbor_paths=["concepts/x.md"],
    )
    # no teammate context, no roundtable mention
    assert "concepts/x.md" in out
    assert "Tisch" not in out
