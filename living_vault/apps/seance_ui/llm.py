"""Backwards-compat re-export shim.

The LLM abstraction now lives in `living_vault.core.llm`. This module
remains so Phase-1 imports (`from living_vault.apps.seance_ui.llm import ...`)
continue to work without changing call sites.
"""
from living_vault.core.llm import (  # noqa: F401  re-exported for back-compat
    LLM,
    FakeLLM,
    AnthropicLLM,
    get_llm,
    respond,
)

__all__ = ["LLM", "FakeLLM", "AnthropicLLM", "get_llm", "respond"]
