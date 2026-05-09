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
"""


def _format_phrases(phrases: list[str] | None) -> str:
    if not phrases:
        return "(none)"
    quoted = ", ".join(f'"{p}"' for p in phrases)
    return quoted


def build_voice_block(persona: dict) -> str:
    """Three cases:
    A — voice_distilled present  → use it as opener + stylistic markers
    B — only voice_features      → list stylistic markers
    C — neither                  → fallback notice
    """
    distilled = persona.get("voice_distilled")
    features = persona.get("voice_features")

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


def build_system_prompt(persona: dict, neighbor_titles: list[str]) -> str:
    voice_block = build_voice_block(persona)
    themes = ", ".join(persona.get("themes", [])) or "(none)"
    neighbors = ", ".join(neighbor_titles) or "(none)"
    return _TEMPLATE.format(
        path=persona["path"],
        title=persona["title"],
        era_marker=persona.get("era_marker") or "unknown date",
        themes=themes,
        neighbors=neighbors,
        voice_block=voice_block,
        body_excerpt=persona.get("body_excerpt", "") or "(empty body)",
    )
