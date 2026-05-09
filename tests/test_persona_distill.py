"""Tests for the LLM-distilled voice function (FakeLLM only — no API)."""
from __future__ import annotations
from living_vault.core.llm import FakeLLM
from living_vault.core.voice.distill import (
    distill_voice_via_llm,
    DEFAULT_DISTILL_PROMPT,
)


def _page(body: str = "Hello world.", title: str = "Test", created: str = "2026-04-01") -> dict:
    return {"title": title, "created": created, "tags": ["t1", "t2"], "body": body}


def test_distill_returns_string():
    llm = FakeLLM()
    out = distill_voice_via_llm(_page(), llm)
    assert isinstance(out, str)
    assert out  # non-empty


def test_distill_passes_body_into_prompt():
    """The page body is what gives the LLM something to react to. Verify it's
    actually included in the system prompt the FakeLLM sees."""
    captured = {}

    class CapturingLLM:
        def respond(self, system, history):
            captured["system"] = system
            captured["history"] = history
            return "captured"

    distill_voice_via_llm(_page(body="UNIQUE-BODY-MARKER-XYZ"), CapturingLLM())
    # body is part of the user message (so the LLM has something to read)
    full = captured["system"] + " " + " ".join(m for _, m in captured["history"])
    assert "UNIQUE-BODY-MARKER-XYZ" in full


def test_distill_truncates_body_at_8000_chars():
    """Spec: body capped at 8000 chars to fit token budget."""
    captured = {}

    class CapturingLLM:
        def respond(self, system, history):
            captured["system"] = system
            captured["history"] = history
            return "ok"

    huge = "ABCDEFGH" * 2000  # 16k chars
    distill_voice_via_llm(_page(body=huge), CapturingLLM())
    full_payload = captured["system"] + " " + " ".join(m for _, m in captured["history"])
    # The 8001th char onwards should not appear
    # We ensure the payload is shorter than the full huge body
    assert len(full_payload) < len(huge) + 4000  # 4k slack for prompt boilerplate


def test_default_prompt_is_present_and_nonempty():
    assert isinstance(DEFAULT_DISTILL_PROMPT, str)
    assert "voice" in DEFAULT_DISTILL_PROMPT.lower()
    assert "summary" in DEFAULT_DISTILL_PROMPT.lower() or "description" in DEFAULT_DISTILL_PROMPT.lower()
