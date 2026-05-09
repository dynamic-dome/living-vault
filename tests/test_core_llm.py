"""LLM abstraction lives in core.llm (moved from apps.seance_ui.llm).
The seance_ui shim must continue to re-export the same symbols.
"""
from __future__ import annotations
import os

import pytest


def test_core_llm_exposes_protocol_and_fake():
    from living_vault.core.llm import LLM, FakeLLM, respond
    llm = FakeLLM()
    out = respond(llm, system="be a page", history=[("user", "hi")])
    assert isinstance(out, str)
    assert out  # non-empty


def test_core_llm_get_llm_returns_fake_when_env_set(monkeypatch):
    from living_vault.core.llm import get_llm, FakeLLM
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    llm = get_llm()
    assert isinstance(llm, FakeLLM)


def test_core_llm_anthropic_class_exists():
    """We import the class but we don't instantiate it (would need API key)."""
    from living_vault.core.llm import AnthropicLLM
    assert AnthropicLLM is not None
    assert hasattr(AnthropicLLM, "respond")


def test_seance_ui_llm_shim_reexports_everything():
    """Backwards-compat: existing imports through the shim still work."""
    from living_vault.apps.seance_ui.llm import LLM, FakeLLM, AnthropicLLM, get_llm, respond
    from living_vault.core.llm import (
        LLM as core_LLM,
        FakeLLM as core_FakeLLM,
        AnthropicLLM as core_AnthropicLLM,
        get_llm as core_get_llm,
        respond as core_respond,
    )
    # Re-exports must be the SAME objects, not copies
    assert FakeLLM is core_FakeLLM
    assert AnthropicLLM is core_AnthropicLLM
    assert get_llm is core_get_llm
    assert respond is core_respond
