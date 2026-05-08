from living_vault.apps.seance_ui.prompt import build_system_prompt


def test_system_prompt_contains_anti_hallucination_clause():
    persona = {
        "path": "concepts/note-a.md",
        "title": "note-a",
        "era_marker": "2026-01-15",
        "themes": ["alpha", "example"],
        "voice_sample": "This is note A. Alpha topics.",
        "frontmatter": {"type": "concept"},
    }
    p = build_system_prompt(persona, neighbor_titles=["note-b", "syn-1"])
    assert "concepts/note-a.md" in p
    assert "2026-01-15" in p
    assert "do not invent" in p.lower() or "darfst nichts erfinden" in p.lower()
    assert "note-b" in p
    assert "Alpha topics" in p


def test_system_prompt_handles_empty_themes():
    persona = {
        "path": "x.md", "title": "x", "era_marker": "",
        "themes": [], "voice_sample": "", "frontmatter": {},
    }
    p = build_system_prompt(persona, neighbor_titles=[])
    assert "x.md" in p
