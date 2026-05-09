"""LLM-distilled voice description for a single page.

The body is sent (truncated to 8000 chars) to the injected `LLM`. The LLM
returns a 3-5 sentence character description that is *not* a content
summary — it describes how the page speaks. This string is later persisted
in the `pages.voice_distilled` column and rendered into the séance system
prompt.

Security note (Codex Security finding 2026-05-09): Metadata fields
(`title`, `created`, `tags`) are sanitized before interpolation into the
prompt envelope. Without sanitization, a frontmatter value containing
newlines + `---END---` could break out of the page envelope and steer
the persisted voice description.
"""
from __future__ import annotations
import re

from living_vault.core.llm import LLM


_BODY_CAP_FOR_LLM = 8_000
_METADATA_FIELD_CAP = 200  # max chars per title/created/tag entry
_TAGS_TOTAL_CAP = 1_000    # max chars across all joined tags


# Strip control characters, newlines, carriage returns, and any literal
# envelope markers. The envelope markers come from the prompt itself, so
# they must never appear in user-controlled metadata.
_FORBIDDEN_PATTERN = re.compile(r"[\r\n\x00-\x1f\x7f]+|---PAGE---|---END---")


def _sanitize_metadata_value(value: object, *, cap: int = _METADATA_FIELD_CAP) -> str:
    """Replace newlines / control chars / envelope markers with spaces, truncate."""
    text = str(value or "")
    cleaned = _FORBIDDEN_PATTERN.sub(" ", text)
    cleaned = cleaned.strip()
    if len(cleaned) > cap:
        cleaned = cleaned[:cap]
    return cleaned


def _sanitize_tags(tags: object) -> list[str]:
    """Sanitize each tag, drop empties, cap total joined length."""
    if not isinstance(tags, list):
        return []
    cleaned: list[str] = []
    total_len = 0
    for raw_tag in tags:
        tag = _sanitize_metadata_value(raw_tag, cap=_METADATA_FIELD_CAP)
        if not tag:
            continue
        # +2 for ", " separator
        if total_len + len(tag) + 2 > _TAGS_TOTAL_CAP:
            break
        cleaned.append(tag)
        total_len += len(tag) + 2
    return cleaned


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
    title = _sanitize_metadata_value(page.get("title", ""))
    created = _sanitize_metadata_value(page.get("created", ""))
    tags = _sanitize_tags(page.get("tags", []))
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


def distill_voice_via_llm(page: dict, llm: LLM, *, system_prompt: str = DEFAULT_DISTILL_PROMPT) -> str:
    """Ask `llm` to describe the page's voice. Returns the LLM's text response.

    `page` is a dict with at least `title`, `created`, `tags`, `body` keys.
    `system_prompt` defaults to DEFAULT_DISTILL_PROMPT but can be overridden
    for experimentation or A/B testing.
    Metadata fields are sanitized to prevent prompt-envelope injection;
    body is capped at _BODY_CAP_FOR_LLM chars.
    Caller is responsible for handling exceptions (network, rate-limit, etc).
    """
    user_msg = _build_user_message(page)
    return llm.respond(
        system=system_prompt,
        history=[("user", user_msg)],
    )
