"""LLM abstraction. Real impl uses Anthropic; tests use FakeLLM.

Lives in `core` so both `apps/` modules and the top-level CLI can import it
without violating dependency direction (apps → core, never reverse).
The `apps/seance_ui/llm.py` module re-exports these symbols for backwards
compatibility with Phase-1 imports.
"""
from __future__ import annotations
import os
from typing import Callable, Protocol

ToolHandler = Callable[[str, dict], "str | dict"]


class LLM(Protocol):
    def respond(self, system: str, history: list[tuple[str, str]]) -> str: ...


class FakeLLM:
    """Used in tests to avoid real API calls."""
    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        last_user = next((m for r, m in reversed(history) if r == "user"), "")
        return f"[fake echo] system={system[:30]}... user={last_user}"


class FakeLLMWithTools:
    """Deterministic tool-loop simulation for tests.

    Construct with a script like:
        [
          {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "x.md"}},
          {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "y.md"}},
          {"type": "text", "text": "final answer"},
        ]

    Each tool_use step calls tool_handler(name, input). When a 'text' step is
    reached, that text is returned. The handler's return value is captured but
    not echoed back into the script (the script itself decides the next step).
    """

    def __init__(self, script: list[dict]):
        self._script = list(script)
        self.tool_calls_made: list[dict] = []

    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        # Phase-1 compat: when the script has exactly one text step, behave like FakeLLM.
        if len(self._script) == 1 and self._script[0].get("type") == "text":
            return self._script[0]["text"]
        return "[fake tools-aware llm — use respond_with_tools]"

    def respond_with_tools(
        self,
        system: str,
        history: list[tuple[str, str]],
        tools: list[dict],
        tool_handler: ToolHandler,
        max_iterations: int = 5,
    ) -> str:
        iters = 0
        for step in self._script:
            kind = step.get("type")
            if kind == "tool_use":
                if iters >= max_iterations:
                    return "(consultation budget exhausted — forced final)"
                iters += 1
                self.tool_calls_made.append(step)
                tool_handler(step["name"], step["input"])
            elif kind == "text":
                return step["text"]
        # script ran out without a text step
        return "(script exhausted)"


class AnthropicLLM:
    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        from anthropic import Anthropic
        self._client = Anthropic()
        self._model = model

    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        msgs = [{"role": role, "content": content} for role, content in history]
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

    def respond_with_tools(
        self,
        system: str,
        history: list[tuple[str, str]],
        tools: list[dict],
        tool_handler: ToolHandler,
        max_iterations: int = 5,
    ) -> str:
        """Multi-turn Anthropic loop. Calls tool_handler(name, input) on each tool_use
        block. Returns the final assistant text. On max_iterations exhaustion, makes one
        last call without `tools=` to force a text answer.

        tool_handler return value contract:
          - str → tool_result.content = the string
          - dict with {"is_error": True, "content": "..."} → tool_result.is_error=True
        """
        # Build the running message list as the API expects: list[{role, content}]
        # where content can be a list of blocks once we start adding tool_use/tool_result.
        messages: list[dict] = [{"role": role, "content": content} for role, content in history]

        for _ in range(max_iterations):
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                tools=tools,
                messages=messages,
            )
            stop = getattr(resp, "stop_reason", None)
            blocks = list(resp.content)

            if stop != "tool_use":
                # done — collect text
                return "".join(b.text for b in blocks if getattr(b, "type", None) == "text")

            # Append the assistant message verbatim (Anthropic requires the original blocks)
            messages.append({"role": "assistant", "content": [
                self._block_to_dict(b) for b in blocks
            ]})

            # Run each tool_use block, build tool_result blocks
            tool_result_blocks = []
            for b in blocks:
                if getattr(b, "type", None) != "tool_use":
                    continue
                handler_out = tool_handler(b.name, b.input)
                if isinstance(handler_out, dict) and handler_out.get("is_error"):
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "is_error": True,
                        "content": handler_out.get("content", "error"),
                    })
                else:
                    content_str = handler_out if isinstance(handler_out, str) else str(handler_out)
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": content_str,
                    })

            messages.append({"role": "user", "content": tool_result_blocks})

        # Forced-final-call: drop tools, force text
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    @staticmethod
    def _block_to_dict(b) -> dict:
        kind = getattr(b, "type", None)
        if kind == "text":
            return {"type": "text", "text": b.text}
        if kind == "tool_use":
            return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
        # fallback — shouldn't happen but keeps the loop robust
        return {"type": kind or "unknown"}


def respond(llm: LLM, system: str, history: list[tuple[str, str]]) -> str:
    return llm.respond(system=system, history=history)


def get_llm() -> LLM:
    flag = os.environ.get("LIVING_VAULT_FAKE_LLM", "").strip().lower()
    if flag and flag not in ("0", "false", "no"):
        return FakeLLM()
    return AnthropicLLM()
