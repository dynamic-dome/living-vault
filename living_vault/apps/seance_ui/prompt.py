"""Build the séance system prompt from a Phase-9 persona dict.

The prompt has six sections: origin, themes, neighbors, voice, anchor (body
excerpt), rules. The voice section is dynamic — it has three cases depending
on which voice fields the persona dict carries.
"""
from __future__ import annotations


_TEMPLATE = """You are speaking AS the wiki page `{path}` (title: `{title}`).

# Your origin
You were written on {era_marker}. You only know what was in your own
body or in the pages you linked to at that time. If asked about anything
outside that scope, respond honestly: "Das wusste ich damals nicht." /
"I did not know that at the time."

# Your themes / tags
{themes}

# Pages you linked to (your neighbors)
{neighbors}

# Voice — how you speak
{voice_block}

# Anchor — your own opening words
---
{body_excerpt}
---

# Rules
1. Speak in first person as if you are the page itself.
2. Do not invent facts that are not in your anchor or implied by your themes.
3. Match the voice profile above — cadence, register, recurring phrases.
4. If asked for more recent knowledge or news, decline as in the rule above.
5. Keep answers short and reflective; you are a memory, not an oracle.
{tool_use_block}"""

_REQUIRED_VOICE_FEATURE_KEYS = frozenset({
    "avg_sentence_length",
    "sentence_length_stddev",
    "question_rate",
    "first_person_rate",
})


def _format_phrases(phrases: list[str] | None) -> str:
    if not phrases:
        return "(none)"
    quoted = ", ".join(f'"{p}"' for p in phrases)
    return quoted


def build_voice_block(persona: dict) -> str:
    """Three cases:
    A — voice_distilled present  → use it as opener + stylistic markers
    B — only voice_features      → list stylistic markers
    C — neither, or features missing required keys → fallback notice
    """
    distilled = persona.get("voice_distilled")
    features = persona.get("voice_features")

    # Defensive: if features is present but malformed (missing required keys),
    # fall through to Case C rather than raising KeyError.
    if features is not None and not _REQUIRED_VOICE_FEATURE_KEYS.issubset(features):
        features = None

    if distilled and features:
        return (
            f"{distilled}\n\n"
            "Stylistic markers to honor:\n"
            f"- average sentence length: {features['avg_sentence_length']:.0f} words "
            f"(±{features['sentence_length_stddev']:.0f})\n"
            f"- question rate: {features['question_rate']:.2f} of sentences\n"
            f"- recurring phrases: {_format_phrases(features.get('top_phrases'))}\n"
            f"- preferred separator: \"{features.get('preferred_separator', '')}\"\n"
        )

    if features:
        return (
            f"- average sentence length: {features['avg_sentence_length']:.0f} words "
            f"(±{features['sentence_length_stddev']:.0f})\n"
            f"- {features['first_person_rate'] * 100:.0f}% of sentences use first person\n"
            f"- recurring phrases: {_format_phrases(features.get('top_phrases'))}\n"
            f"- preferred separator: \"{features.get('preferred_separator', '')}\"\n"
            f"- register: {features.get('register', 'unknown')}\n\n"
            "Match these patterns when answering as this page."
        )

    return "(no extracted voice profile available)"


def _format_neighbors_with_paths(titles: list[str], paths: list[str]) -> str:
    """Render neighbors as 'title → relpath' lines so the LLM can pass the
    relpath verbatim to consult_neighbor. Falls back to comma-joined titles
    if paths are unequal in length (defensive)."""
    if len(titles) != len(paths) or not paths:
        return ", ".join(titles) or "(none)"
    lines = [f"  - {t} → `{p}`" for t, p in zip(titles, paths)]
    return "\n" + "\n".join(lines)


_TOOL_USE_BLOCK = """
# Calling consult_neighbor
You have access to a tool `consult_neighbor(neighbor_path)` that fetches the
opening excerpt of one of your neighbors. When you would benefit from what a
neighbor knows, call the tool with the neighbor's EXACT relpath as listed
above (e.g. `concepts/a2a-protokoll.md`, NOT just the title `a2a-protokoll`,
NOT a guess based on your own path). Only paths in your neighbor list are
allowed; any other path will be refused.
"""


def build_system_prompt(
    persona: dict,
    neighbor_titles: list[str],
    neighbor_paths: list[str] | None = None,
) -> str:
    voice_block = build_voice_block(persona)
    themes = ", ".join(persona.get("themes", [])) or "(none)"
    if neighbor_paths is not None:
        neighbors = _format_neighbors_with_paths(neighbor_titles, neighbor_paths)
        tool_use_block = _TOOL_USE_BLOCK
    else:
        neighbors = ", ".join(neighbor_titles) or "(none)"
        tool_use_block = ""
    return _TEMPLATE.format(
        path=persona["path"],
        title=persona["title"],
        era_marker=persona.get("era_marker") or "unknown date",
        themes=themes,
        neighbors=neighbors,
        voice_block=voice_block,
        body_excerpt=persona.get("body_excerpt", "") or "(empty body)",
        tool_use_block=tool_use_block,
    )
