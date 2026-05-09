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
    actually included in the payload the LLM sees."""
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

    # Build a body where the first 8000 chars are all 'A' and the next 100 are all 'Z'
    # — the 'Z' segment should NOT appear in the payload
    huge = ("A" * 8000) + ("Z" * 100) + ("A" * 8000)  # 16100 chars total
    distill_voice_via_llm(_page(body=huge), CapturingLLM())
    full_payload = captured["system"] + " " + " ".join(m for _, m in captured["history"])
    # Tight check: the 'Z' segment past the 8000-char cap must NOT be in payload
    assert "Z" * 100 not in full_payload
    # Sanity: the 'A' prefix that fits within the cap IS in payload
    assert "A" * 100 in full_payload


def test_default_prompt_is_present_and_nonempty():
    assert isinstance(DEFAULT_DISTILL_PROMPT, str)
    assert "voice" in DEFAULT_DISTILL_PROMPT.lower()
    assert "summary" in DEFAULT_DISTILL_PROMPT.lower() or "description" in DEFAULT_DISTILL_PROMPT.lower()


def test_distill_accepts_custom_system_prompt():
    """The system_prompt kwarg overrides DEFAULT_DISTILL_PROMPT when supplied."""
    captured = {}

    class CapturingLLM:
        def respond(self, system, history):
            captured["system"] = system
            captured["history"] = history
            return "ok"

    custom = "Pretend you are a haiku critic."
    distill_voice_via_llm(_page(), CapturingLLM(), system_prompt=custom)
    assert captured["system"] == custom
