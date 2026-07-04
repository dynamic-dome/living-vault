"""Transport-neutral orchestration logic for the séance app.

Both the FastAPI HTTP adapter (app.py) and the upcoming MCP server
(mcp_servers/seance/server.py) share this module.

IMPORTANT: get_llm must NOT be imported directly here at module scope.
Instead, it is called via _app_mod.get_llm() so that monkeypatch on
app_mod.get_llm still works in tests.
"""
from __future__ import annotations
from pathlib import Path

from living_vault.core import db as db_mod
from living_vault.core.persona import build_persona
from living_vault.core.graph import neighbors as graph_neighbors
from living_vault.apps.seance_ui.prompt import build_system_prompt
from living_vault.apps.seance_ui import store
from living_vault.apps.seance_ui.neighbors import (
    CONSULT_NEIGHBOR_TOOL_DEF,
    make_consult_neighbor_handler,
)
from living_vault.apps.seance_ui.semantic_neighbors import semantic_neighbors_for_persona
from living_vault.apps.seance_ui.roundtable import (
    VALID_MODES,
    hash_color,
    pick_auto_speakers,
    pick_speakers,
    shared_history_for_persona,
)

# Lazy import: resolved at call time so monkeypatch on app_mod.get_llm works.
# Never do: from living_vault.apps.seance_ui.llm import get_llm
def _get_llm():
    from living_vault.apps.seance_ui import app as _app_mod
    return _app_mod.get_llm()


# Cost/DoS guards (Codex Security finding 2026-05-09).
_MAX_USER_TEXT_CHARS = 8_000        # per-message user text cap
_MAX_HISTORY_MESSAGES = 50          # last N messages replayed to LLM
_MAX_HISTORY_TOTAL_CHARS = 32_000   # total chars across replayed history


class SéanceError(Exception):
    """Transport-neutral error. Code maps 1:1 to existing HTTP status codes
    so app.py can keep its current API shape."""
    def __init__(self, code: int, detail):
        self.code = code   # 400/404/410/413/502
        self.detail = detail  # str OR dict (502 uses dict)
        super().__init__(detail)


def _cap_history(history: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Replay only the last N messages; further trim oldest if total chars exceed cap."""
    capped = history[-_MAX_HISTORY_MESSAGES:]
    total = sum(len(content) for _, content in capped)
    while total > _MAX_HISTORY_TOTAL_CHARS and len(capped) > 1:
        _, dropped = capped.pop(0)
        total -= len(dropped)
    return capped


def _routing_label(mode: str) -> str:
    if mode == "auto":
        return "auto-moderator selected this persona from the current circle"
    if mode == "moderator":
        return "moderator mode selected this persona"
    if mode == "roundrobin":
        return "round-robin turn order selected this persona"
    if mode == "freeforall":
        return "free-for-all invited every persona in the circle"
    return "single persona"


def _build_evidence(
    *,
    persona_path: str,
    mode: str,
    tool_events: list[dict],
    semantic_paths: list[str] | None = None,
) -> dict:
    consulted_paths: list[str] = []
    seen: set[str] = set()
    for event in tool_events:
        if event.get("tool_name") != "consult_neighbor":
            continue
        summary = event.get("tool_result_summary") or {}
        if "error" in summary:
            continue
        args = event.get("tool_args") or {}
        path = args.get("neighbor_path")
        if isinstance(path, str) and path not in seen:
            consulted_paths.append(path)
            seen.add(path)
    return {
        "persona_path": persona_path,
        "mode": mode,
        "own_page": persona_path,
        "consulted_paths": consulted_paths,
        "semantic_paths": semantic_paths or [],
        "routing": _routing_label(mode),
    }


def summon_session(
    db_path: Path,
    vault_root: Path,
    *,
    page_paths: list[str],
    mode: str = "single",
    semantic_neighbors: bool = False,
) -> dict:
    """Create a new séance session for the given pages.

    Returns {session_id, mode, personas, persona}.
    Raises SéanceError on validation/lookup failures.
    """
    # Length check on raw input (so 9 duplicates correctly return 413 before dedup).
    if len(page_paths) == 0:
        raise SéanceError(400, "at least one page required")
    if len(page_paths) > 8:
        raise SéanceError(413, "max 8 personas per roundtable")

    # Dedup preserving order (Python 3.7+ dicts preserve insertion order).
    paths = list(dict.fromkeys(page_paths))

    # Validate mode + coerce based on path count.
    if mode not in VALID_MODES:
        raise SéanceError(400, f"unknown mode: {mode}")
    if len(paths) == 1:
        # Single path always means single-mode session; ignore any roundtable
        # mode the caller might have requested (UX safeguard).
        effective_mode = "single"
    elif mode == "single":
        # Multi-path with mode=single doesn't make sense; default to roundrobin.
        effective_mode = "roundrobin"
    else:
        effective_mode = mode

    # Validate each page AND keep the built persona dicts for response reuse.
    built_personas: list[dict] = []
    for p in paths:
        persona = build_persona(vault_root, db_path, p)
        if persona is None:
            raise SéanceError(404, f"page not found: {p}")
        built_personas.append(persona)

    # Create session — page_path is paths[0] for legacy compatibility with
    # the existing /api/say flow that reads page_path from seance_sessions.
    sid = store.new_session(
        db_path,
        page_path=paths[0],
        mode=effective_mode,
        semantic_neighbors=semantic_neighbors,
    )

    # Add personas + assemble response personas array in one pass.
    personas_out: list[dict] = []
    for i, p in enumerate(paths):
        color = hash_color(p)
        store.add_session_persona(db_path, sid, p, color=color, seat_idx=i)
        personas_out.append({"persona_path": p, "color": color, "seat_idx": i})

    return {
        "session_id": sid,
        "mode": effective_mode,
        "semantic_neighbors": semantic_neighbors,
        "personas": personas_out,
        # Backward-compat: legacy callers expect a `persona` field with the
        # first page's full persona dict. Reuse the validation-loop result.
        "persona": built_personas[0],
    }


def say_single(
    db_path: Path,
    vault_root: Path,
    *,
    session_id: int,
    text: str,
) -> dict:
    """Run a single-mode séance turn.

    Returns {reply, tool_events}. Raises SéanceError.
    """
    history = store.get_history(db_path, session_id)
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT page_path FROM seance_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise SéanceError(404, "session not found")
        page_path = row["page_path"]
        nbs = graph_neighbors(con, page_path)
    finally:
        con.close()

    persona = build_persona(vault_root, db_path, page_path)
    if persona is None:
        raise SéanceError(410, "page gone since session start")
    semantic_enabled = store.get_session_semantic_neighbors(db_path, session_id)
    semantic_paths = []
    if semantic_enabled:
        semantic_paths = semantic_neighbors_for_persona(
            db_path,
            page_path,
            exclude=nbs,
        )
    system = build_system_prompt(
        persona,
        neighbor_titles=[Path(n).stem for n in nbs],
        neighbor_paths=list(nbs),
        semantic_neighbor_paths=semantic_paths,
    )

    # Persist user turn first so it's in DB even if the LLM call fails.
    store.add_message(db_path, session_id, "user", text, persona_path=None)

    raw_handler = make_consult_neighbor_handler(
        vault_root=vault_root,
        db_path=db_path,
        session_id=session_id,
        persona_path=page_path,
        allowlist=set(nbs) | set(semantic_paths),
    )

    tool_events: list[dict] = []

    def handler_with_capture(name: str, args: dict):
        result = raw_handler(name, args)
        if isinstance(result, dict) and result.get("is_error"):
            tool_events.append({
                "tool_name": name,
                "tool_args": args,
                "tool_result_summary": {"error": result["content"]},
            })
        else:
            tool_events.append({
                "tool_name": name,
                "tool_args": args,
                "tool_result_summary": {"chars": len(result) if isinstance(result, str) else 0},
            })
        return result

    history_for_llm = list(history) + [("user", text)]
    history_for_llm = _cap_history(history_for_llm)

    llm = _get_llm()
    if hasattr(llm, "respond_with_tools"):
        reply = llm.respond_with_tools(
            system=system,
            history=history_for_llm,
            tools=[CONSULT_NEIGHBOR_TOOL_DEF],
            tool_handler=handler_with_capture,
            max_iterations=5,
        )
    else:
        reply = llm.respond(system=system, history=history_for_llm)

    store.add_message(db_path, session_id, "assistant", reply, persona_path=page_path)
    return {
        "reply": reply,
        "tool_events": tool_events,
        "evidence": _build_evidence(
            persona_path=page_path,
            mode="single",
            tool_events=tool_events,
            semantic_paths=semantic_paths,
        ),
    }


def say_roundtable(
    db_path: Path,
    vault_root: Path,
    *,
    session_id: int,
    text: str,
) -> dict:
    """Orchestrate a multi-persona turn for roundrobin/moderator/freeforall sessions.

    Returns {replies, tool_events}.
    Raises SéanceError(502, dict) on partial failure (per spec §6).

    Edge case: if all speakers' build_persona returns None (every page gone since
    summon), the response is {replies: [], tool_events: [...persona_skipped...]}
    with no error — partial-failure is acceptable, no participant means no answers.
    """
    personas = store.get_session_personas(db_path, session_id)
    if not personas:
        raise SéanceError(410, "session has no participants")

    # re-fetch mode for self-containedness.
    mode = store.get_session_mode(db_path, session_id)
    semantic_enabled = store.get_session_semantic_neighbors(db_path, session_id)
    turn_idx = store.count_user_turns(db_path, session_id)  # 0-indexed for THIS upcoming turn

    # Persist user turn first so it's in DB even if any LLM call fails.
    store.add_message(db_path, session_id, "user", text, persona_path=None)

    if mode == "auto":
        speakers = pick_auto_speakers(
            db_path=db_path,
            user_text=text,
            personas=personas,
            turn_idx=turn_idx,
        )
    else:
        speakers = pick_speakers(
            mode=mode,
            user_text=text,
            personas=personas,
            turn_idx=turn_idx,
        )

    replies: list[dict] = []
    tool_events: list[dict] = []

    # Use a list (not a set) so teammate_paths order is deterministic.
    persona_paths_ordered = [p["persona_path"] for p in personas]

    for speaker in speakers:
        speaker_path = speaker["persona_path"]

        # Build the persona; if it's gone, log a persona_skipped event and continue.
        persona_data = build_persona(vault_root, db_path, speaker_path)
        if persona_data is None:
            tool_events.append({
                "tool_name": "persona_skipped",
                "tool_args": {"persona_path": speaker_path},
                "tool_result_summary": {"error": "page gone since summon"},
            })
            continue

        # Build the system prompt with neighbors AND teammates
        con = db_mod.connect(db_path)
        try:
            nbs = graph_neighbors(con, speaker_path)
        finally:
            con.close()
        teammate_paths = [p for p in persona_paths_ordered if p != speaker_path]
        semantic_paths = []
        if semantic_enabled:
            semantic_paths = semantic_neighbors_for_persona(
                db_path,
                speaker_path,
                exclude=set(nbs) | set(teammate_paths),
            )

        system = build_system_prompt(
            persona_data,
            neighbor_titles=[Path(n).stem for n in nbs],
            neighbor_paths=list(nbs),
            teammate_paths=teammate_paths,
            semantic_neighbor_paths=semantic_paths,
        )

        # Allowlist: graph neighbors + teammates + opt-in semantic archive pages.
        allowlist = set(nbs) | set(teammate_paths) | set(semantic_paths)
        raw_handler = make_consult_neighbor_handler(
            vault_root=vault_root,
            db_path=db_path,
            session_id=session_id,
            persona_path=speaker_path,
            allowlist=allowlist,
        )

        speaker_tool_events: list[dict] = []

        def handler_with_capture(name: str, args: dict, _events=speaker_tool_events, _h=raw_handler):
            result = _h(name, args)
            if isinstance(result, dict) and result.get("is_error"):
                _events.append({
                    "tool_name": name,
                    "tool_args": args,
                    "tool_result_summary": {"error": result["content"]},
                })
            else:
                _events.append({
                    "tool_name": name,
                    "tool_args": args,
                    "tool_result_summary": {"chars": len(result) if isinstance(result, str) else 0},
                })
            return result

        # Build per-speaker history (shared but persona-perspective rendering)
        history_for_llm = shared_history_for_persona(db_path, session_id, speaker_path)
        history_for_llm = _cap_history(history_for_llm)

        llm = _get_llm()
        try:
            if hasattr(llm, "respond_with_tools"):
                reply = llm.respond_with_tools(
                    system=system,
                    history=history_for_llm,
                    tools=[CONSULT_NEIGHBOR_TOOL_DEF],
                    tool_handler=handler_with_capture,
                    max_iterations=5,
                )
            else:
                reply = llm.respond(system=system, history=history_for_llm)
        except Exception as e:  # noqa: BLE001 — surface any LLM-loop failure as 502
            tool_events.extend(speaker_tool_events)
            raise SéanceError(
                502,
                {
                    "error": f"{type(e).__name__}: {e}",
                    "failed_persona": speaker_path,
                    "partial_replies": replies,
                    "tool_events": tool_events,
                },
            )

        store.add_message(
            db_path, session_id, "assistant", reply,
            persona_path=speaker_path,
        )
        replies.append({
            "persona_path": speaker_path,
            "text": reply,
            "color": speaker["color"],
            "seat_idx": speaker["seat_idx"],
            "evidence": _build_evidence(
                persona_path=speaker_path,
                mode=mode,
                tool_events=speaker_tool_events,
                semantic_paths=semantic_paths,
            ),
        })
        tool_events.extend(speaker_tool_events)

    return {"replies": replies, "tool_events": tool_events}


def say(
    db_path: Path,
    vault_root: Path,
    *,
    session_id: int,
    text: str,
) -> dict:
    """Dispatch a user message to the appropriate handler based on session mode.

    This is the single entry point both transports should use.
    Raises SéanceError(413) if text is too long.
    Raises SéanceError(404) if session not found.
    """
    if len(text) > _MAX_USER_TEXT_CHARS:
        raise SéanceError(
            413,
            f"text too long ({len(text)} chars, max {_MAX_USER_TEXT_CHARS})",
        )

    mode = store.get_session_mode(db_path, session_id)
    if mode is None:
        raise SéanceError(404, "session not found")

    if mode == "single":
        return say_single(db_path, vault_root, session_id=session_id, text=text)
    else:
        return say_roundtable(db_path, vault_root, session_id=session_id, text=text)
