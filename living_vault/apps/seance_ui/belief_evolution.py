"""Read-only perspective trace for séance sessions."""
from __future__ import annotations

from pathlib import Path

from living_vault.apps.seance_ui import store


MAX_TRACE_EVENTS = 24
MAX_STANCE_CHARS = 220


def _compact(text: str, *, max_chars: int = MAX_STANCE_CHARS) -> str:
    one_line = " ".join((text or "").split())
    if len(one_line) <= max_chars:
        return one_line
    return one_line[: max_chars - 1].rstrip() + "…"


def summarize_belief_evolution(db_path: Path, session_id: int) -> dict | None:
    """Summarize visible stance movement from persisted transcript messages."""
    detail = store.get_session_detail(db_path, session_id)
    if detail is None:
        return None

    mode = store.get_session_mode(db_path, session_id) or "single"
    session_personas = store.get_session_personas(db_path, session_id)
    participants = [p["persona_path"] for p in session_personas] or [detail["page_path"]]

    turn = 0
    timeline: list[dict] = []
    arcs: dict[str, dict] = {}

    for message in detail["messages"]:
        role = message["role"]
        if role == "user":
            turn += 1
            timeline.append({
                "turn": turn,
                "role": "user",
                "text": _compact(message["content"]),
            })
            continue
        if role != "assistant":
            continue

        persona_path = message.get("persona_path") or detail["page_path"]
        stance = _compact(message["content"])
        arc = arcs.setdefault(
            persona_path,
            {
                "persona_path": persona_path,
                "response_count": 0,
                "first_stance": stance,
                "latest_stance": stance,
                "changed": False,
            },
        )
        arc["response_count"] += 1
        arc["latest_stance"] = stance
        arc["changed"] = arc["first_stance"] != stance
        timeline.append({
            "turn": turn,
            "role": "assistant",
            "persona_path": persona_path,
            "stance": stance,
        })

    return {
        "session_id": session_id,
        "page_path": detail["page_path"],
        "mode": mode,
        "participants": participants,
        "turn_count": turn,
        "timeline": timeline[-MAX_TRACE_EVENTS:],
        "persona_arcs": list(arcs.values()),
    }
