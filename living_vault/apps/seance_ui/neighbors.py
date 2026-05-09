"""Phase-10a: consult_neighbor tool-handler factory.

The factory `make_consult_neighbor_handler` returns a closure that the LLM-loop
calls with (tool_name, tool_args). The closure:
  1. Validates the tool args (Pydantic-like manual check, no new dep).
  2. Checks the requested neighbor_path is in the allowlist (graph-derived).
  3. Reads the page body via core.reader (with a hard 1500-char excerpt cap).
  4. Persists a tool-use event in seance_messages.
  5. Returns either a string (the excerpt) or a dict {is_error, content}.

The LLM-loop in core.llm.respond_with_tools handles both return shapes.
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable, Iterable

from living_vault.core.reader import read_page
from living_vault.apps.seance_ui import store


BODY_EXCERPT_CHARS = 1500
MAX_CONSULT_CALLS_PER_TURN = 10


CONSULT_NEIGHBOR_TOOL_DEF: dict = {
    "name": "consult_neighbor",
    "description": (
        "Read an excerpt of a neighbor wiki page that you (the persona) link to. "
        "Use this when you would like to consult what a neighbor knows before answering. "
        "You can call this multiple times in one turn but be selective."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "neighbor_path": {
                "type": "string",
                "description": "Relative path of the neighbor page (must be one of your own neighbors).",
            }
        },
        "required": ["neighbor_path"],
    },
}


def make_consult_neighbor_handler(
    *,
    vault_root: Path,
    db_path: Path,
    session_id: int,
    persona_path: str,
    allowlist: Iterable[str],
) -> Callable[[str, dict], str | dict]:
    """Build a handler closure bound to one séance turn.

    The closure mutates a private call-count cell to enforce MAX_CONSULT_CALLS_PER_TURN.
    """
    allow = set(allowlist)
    state = {"calls": 0}

    def handler(tool_name: str, tool_args: dict):
        # 1. arg validation
        if "neighbor_path" not in tool_args or not isinstance(tool_args["neighbor_path"], str):
            return {"is_error": True, "content": "missing required field: neighbor_path"}
        nbr = tool_args["neighbor_path"].strip()

        # 2. soft-cap budget
        if state["calls"] >= MAX_CONSULT_CALLS_PER_TURN:
            return {
                "is_error": True,
                "content": (
                    f"consultation budget exhausted "
                    f"({MAX_CONSULT_CALLS_PER_TURN}/turn) — please answer with what you have"
                ),
            }

        # 3. allowlist check
        if nbr not in allow:
            return {"is_error": True, "content": f"not a neighbor of {persona_path}"}

        # 4. fetch page body
        target = vault_root / nbr
        if not target.exists():
            store.add_tool_event(
                db_path, session_id,
                persona_path=persona_path,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result_summary={"error": "page no longer exists"},
            )
            return {"is_error": True, "content": "page no longer exists"}

        try:
            page = read_page(target, vault_root)
        except Exception as e:  # noqa: BLE001 — broad on purpose, surface as is_error
            store.add_tool_event(
                db_path, session_id,
                persona_path=persona_path,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result_summary={"error": f"could not read page: {type(e).__name__}"},
            )
            return {"is_error": True, "content": "could not read page"}

        excerpt = (page.body or "").strip()[:BODY_EXCERPT_CHARS]

        # 5. persist successful tool event + count
        state["calls"] += 1
        store.add_tool_event(
            db_path, session_id,
            persona_path=persona_path,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result_summary={
                "chars": len(excerpt),
                "title": page.title,
                "calls_used": state["calls"],
            },
        )
        return excerpt

    return handler
