"""Phase-10a: respond_with_tools loop tests using the deterministic FakeLLMWithTools."""
from __future__ import annotations
import pytest
from living_vault.core.llm import FakeLLMWithTools


def _noop_handler(name: str, args: dict) -> str:
    return f"result for {name}({args})"


def test_text_only_script_returns_text_immediately():
    llm = FakeLLMWithTools([{"type": "text", "text": "hi"}])
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=5
    )
    assert out == "hi"


def test_one_tool_use_then_text():
    llm = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "x.md"}},
        {"type": "text", "text": "final"},
    ])
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=5
    )
    assert out == "final"
    assert llm.tool_calls_made == [
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "x.md"}}
    ]


def test_multiple_tool_uses_in_a_turn():
    llm = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "x.md"}},
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "y.md"}},
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "z.md"}},
        {"type": "text", "text": "synthesis"},
    ])
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=5
    )
    assert out == "synthesis"
    assert len(llm.tool_calls_made) == 3


def test_handler_receives_name_and_args():
    seen: list[tuple[str, dict]] = []

    def cb(name: str, args: dict) -> str:
        seen.append((name, args))
        return "ok"

    llm = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "a.md"}},
        {"type": "text", "text": "done"},
    ])
    llm.respond_with_tools(system="s", history=[], tools=[], tool_handler=cb, max_iterations=5)
    assert seen == [("consult_neighbor", {"neighbor_path": "a.md"})]


def test_max_iterations_caps_loop():
    """If the script keeps emitting tool_use beyond max_iterations, the helper
    must terminate at exactly max_iterations calls and return the budget-
    exhausted fallback string (distinct from script-exhausted)."""
    script = [{"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": f"p{i}.md"}}
              for i in range(10)]  # ten tool_use steps, no terminating text
    llm = FakeLLMWithTools(script)
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=3
    )
    # exactly 3 calls fire (cap honored, not approximate), and the fallback
    # string is the budget-exhausted one, not the script-exhausted one.
    assert len(llm.tool_calls_made) == 3
    assert out == "(consultation budget exhausted — forced final)"


def test_handler_is_error_passes_through():
    received: list[str] = []

    def cb(name: str, args: dict):
        received.append("called")
        return {"is_error": True, "content": "not a neighbor"}

    llm = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "bad.md"}},
        {"type": "text", "text": "ok despite error"},
    ])
    out = llm.respond_with_tools(system="s", history=[], tools=[], tool_handler=cb, max_iterations=5)
    assert out == "ok despite error"
    assert received == ["called"]


def test_empty_script_returns_fallback_string():
    llm = FakeLLMWithTools([])
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=5
    )
    assert isinstance(out, str)


def test_legacy_respond_still_works_for_text_only_script():
    llm = FakeLLMWithTools([{"type": "text", "text": "echo"}])
    # Phase-1 callers use respond(); FakeLLMWithTools must not break that
    out = llm.respond(system="s", history=[("user", "hi")])
    assert out == "echo"
