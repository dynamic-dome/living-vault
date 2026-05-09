"""LLM abstraction. Real impl uses Anthropic; tests use FakeLLM.

Lives in `core` so both `apps/` modules and the top-level CLI can import it
without violating dependency direction (apps → core, never reverse).
The `apps/seance_ui/llm.py` module re-exports these symbols for backwards
compatibility with Phase-1 imports.
"""
from __future__ import annotations
import os
from typing import Protocol


class LLM(Protocol):
    def respond(self, system: str, history: list[tuple[str, str]]) -> str: ...


class FakeLLM:
    """Used in tests to avoid real API calls."""
    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        last_user = next((m for r, m in reversed(history) if r == "user"), "")
        return f"[fake echo] system={system[:30]}... user={last_user}"


class AnthropicLLM:
    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        from anthropic import Anthropic
        self._client = Anthropic()
        self._model = model

    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        msgs = [
            {"role": role, "content": content}
            for role, content in history
        ]
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=system,
            messages=msgs,
        )
        parts = []
        for blk in resp.content:
            if getattr(blk, "type", None) == "text":
                parts.append(blk.text)
        return "".join(parts)


def respond(llm: LLM, system: str, history: list[tuple[str, str]]) -> str:
    return llm.respond(system=system, history=history)


def get_llm() -> LLM:
    flag = os.environ.get("LIVING_VAULT_FAKE_LLM", "").strip().lower()
    if flag and flag not in ("0", "false", "no"):
        return FakeLLM()
    return AnthropicLLM()
