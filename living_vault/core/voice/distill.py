"""LLM-distilled voice description for a single page.

The body is sent (truncated to 8000 chars) to the injected `LLM`. The LLM
returns a 3-5 sentence character description that is *not* a content
summary — it describes how the page speaks. This string is later persisted
in the `pages.voice_distilled` column and rendered into the séance system
prompt.
"""
from __future__ import annotations

from living_vault.core.llm import LLM


_BODY_CAP_FOR_LLM = 8_000


DEFAULT_DISTILL_PROMPT = """You will read a wiki page and produce a 3-5 sentence character description
of its voice — the way it speaks. NOT a summary of what it's about.

Focus on:
- cadence and rhythm (terse? expansive? loose?)
- recurring phrases and turn-of-phrase
- point of view (first person? observational?)
- register (formal? casual? technical-precise? playful?)
- emotional temperature (neutral? urgent? reflective?)

Be concrete. Quote a phrase or two from the page if it captures the voice.
Output ONLY the description text, no preamble.
"""


def _build_user_message(page: dict) -> str:
    title = page.get("title", "")
    created = page.get("created", "")
    tags = page.get("tags", []) or []
    body = page.get("body", "") or ""
    if len(body) > _BODY_CAP_FOR_LLM:
        body = body[:_BODY_CAP_FOR_LLM]
    return (
        f"---PAGE---\n"
        f"title: {title}\n"
        f"created: {created}\n"
        f"tags: {', '.join(tags)}\n\n"
        f"{body}\n"
        f"---END---\n"
    )


def distill_voice_via_llm(page: dict, llm: LLM) -> str:
    """Ask `llm` to describe the page's voice. Returns the LLM's text response.

    `page` is a dict with at least `title`, `created`, `tags`, `body` keys.
    Caller is responsible for handling exceptions (network, rate-limit, etc).
    """
    user_msg = _build_user_message(page)
    return llm.respond(
        system=DEFAULT_DISTILL_PROMPT,
        history=[("user", user_msg)],
    )
