"""Séance — FastAPI app, lock-free single-process.

Bind: 127.0.0.1 only. No auth (local-only).
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from living_vault.core import db as db_mod
from living_vault.core.persona import build_persona
from living_vault.core.graph import neighbors as graph_neighbors
from living_vault.apps.seance_ui.prompt import build_system_prompt
from living_vault.apps.seance_ui.llm import get_llm
from living_vault.apps.seance_ui import store
from living_vault.apps.seance_ui.neighbors import (
    CONSULT_NEIGHBOR_TOOL_DEF,
    make_consult_neighbor_handler,
)
from living_vault.apps.seance_ui.roundtable import (
    VALID_MODES,
    hash_color,
    pick_speakers,
    shared_history_for_persona,
)


def _vault_root() -> Path:
    p = os.environ.get("LIVING_VAULT_ROOT")
    if not p:
        raise RuntimeError("LIVING_VAULT_ROOT env var is not set")
    return Path(p)


def _db_path() -> Path:
    p = os.environ.get("LIVING_VAULT_DB")
    if p:
        return Path(p)
    return _vault_root().parent / ".vault-engine.db"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    db_mod.initialize(_db_path())
    yield


app = FastAPI(title="séance", lifespan=_lifespan)
STATIC_DIR = Path(__file__).parent / "static"

# Cost/DoS guards (Codex Security finding 2026-05-09).
# Local-only setup, but unbounded text + replayed history would still
# cause runaway Anthropic-API spend on a malformed client.
_MAX_USER_TEXT_CHARS = 8_000        # per-message user text cap
_MAX_HISTORY_MESSAGES = 50          # last N messages replayed to LLM
_MAX_HISTORY_TOTAL_CHARS = 32_000   # total chars across replayed history


class SummonReq(BaseModel):
    # Phase-1 single-path shape (backward-compat):
    path: str | None = None
    # Phase-10b multi-path shape:
    paths: list[str] | None = None
    mode: str = "single"


class SayReq(BaseModel):
    session_id: int
    text: str


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/pages")
def list_pages() -> list[dict]:
    con = db_mod.connect(_db_path())
    try:
        rows = con.execute(
            "SELECT path, title, mtime FROM pages ORDER BY mtime DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


@app.post("/api/summon")
def summon(req: SummonReq) -> dict:
    # Determine path list: legacy `path` or new `paths`
    if req.paths is not None:
        paths = list(req.paths)
    elif req.path is not None:
        paths = [req.path]
    else:
        raise HTTPException(status_code=400, detail="must provide 'path' or 'paths'")

    # Length check on raw input (so 9 duplicates correctly return 413 before dedup).
    if len(paths) == 0:
        raise HTTPException(status_code=400, detail="at least one page required")
    if len(paths) > 8:
        raise HTTPException(status_code=413, detail="max 8 personas per roundtable")

    # Dedup preserving order (Python 3.7+ dicts preserve insertion order).
    paths = list(dict.fromkeys(paths))

    # Validate mode + coerce based on path count.
    if req.mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"unknown mode: {req.mode}")
    if len(paths) == 1:
        # Single path always means single-mode session; ignore any roundtable
        # mode the caller might have requested (UX safeguard).
        mode = "single"
    elif req.mode == "single":
        # Multi-path with mode=single doesn't make sense; default to roundrobin.
        mode = "roundrobin"
    else:
        mode = req.mode

    # Validate each page AND keep the built persona dicts for response reuse.
    built_personas: list[dict] = []
    for p in paths:
        persona = build_persona(_vault_root(), _db_path(), p)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"page not found: {p}")
        built_personas.append(persona)

    # Create session — page_path is paths[0] for legacy compatibility with
    # the existing /api/say flow that reads page_path from seance_sessions.
    sid = store.new_session(_db_path(), page_path=paths[0], mode=mode)

    # Add personas + assemble response personas array in one pass.
    personas_out: list[dict] = []
    for i, p in enumerate(paths):
        color = hash_color(p)
        store.add_session_persona(_db_path(), sid, p, color=color, seat_idx=i)
        personas_out.append({"persona_path": p, "color": color, "seat_idx": i})

    return {
        "session_id": sid,
        "mode": mode,
        "personas": personas_out,
        # Backward-compat: legacy callers expect a `persona` field with the
        # first page's full persona dict. Reuse the validation-loop result.
        "persona": built_personas[0],
    }


def _cap_history(history: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Replay only the last N messages; further trim oldest if total chars exceed cap."""
    capped = history[-_MAX_HISTORY_MESSAGES:]
    total = sum(len(content) for _, content in capped)
    while total > _MAX_HISTORY_TOTAL_CHARS and len(capped) > 1:
        _, dropped = capped.pop(0)
        total -= len(dropped)
    return capped


@app.post("/api/say")
def say(req: SayReq) -> dict:
    if len(req.text) > _MAX_USER_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"text too long ({len(req.text)} chars, max {_MAX_USER_TEXT_CHARS})",
        )

    # Phase-10b: branch on session.mode. Single-mode keeps the existing path.
    mode = store.get_session_mode(_db_path(), req.session_id)
    if mode is None:
        raise HTTPException(status_code=404, detail="session not found")
    if mode != "single":
        return roundtable_say(req)

    history = store.get_history(_db_path(), req.session_id)
    con = db_mod.connect(_db_path())
    try:
        row = con.execute(
            "SELECT page_path FROM seance_sessions WHERE id = ?", (req.session_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="session not found")
        page_path = row["page_path"]
        nbs = graph_neighbors(con, page_path)
    finally:
        con.close()

    persona = build_persona(_vault_root(), _db_path(), page_path)
    if persona is None:
        raise HTTPException(status_code=410, detail="page gone since session start")
    system = build_system_prompt(
        persona,
        neighbor_titles=[Path(n).stem for n in nbs],
        neighbor_paths=list(nbs),
    )

    # Persist user turn first so it's in DB even if the LLM call fails.
    store.add_message(_db_path(), req.session_id, "user", req.text, persona_path=None)

    raw_handler = make_consult_neighbor_handler(
        vault_root=_vault_root(),
        db_path=_db_path(),
        session_id=req.session_id,
        persona_path=page_path,
        allowlist=set(nbs),
    )

    # tool_events are a thin response-shape projection of the rows persisted in
    # seance_messages by raw_handler. Response carries {chars} or {error}; the
    # full DB row also has {title, calls_used} for successes. If the LLM-loop
    # raises mid-call, already-captured events are lost from the response but
    # remain in the DB — acceptable for Phase 10a.
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

    history_for_llm = list(history) + [("user", req.text)]
    history_for_llm = _cap_history(history_for_llm)

    llm = get_llm()
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

    store.add_message(
        _db_path(), req.session_id, "assistant", reply, persona_path=page_path
    )
    return {"reply": reply, "tool_events": tool_events}


def roundtable_say(req: SayReq) -> dict:
    """Orchestrate a multi-persona turn for roundrobin/moderator/freeforall sessions."""
    personas = store.get_session_personas(_db_path(), req.session_id)
    if not personas:
        raise HTTPException(status_code=410, detail="session has no participants")

    mode = store.get_session_mode(_db_path(), req.session_id)
    turn_idx = store.count_user_turns(_db_path(), req.session_id)  # 0-indexed for THIS upcoming turn

    # Persist user turn first so it's in DB even if any LLM call fails.
    store.add_message(_db_path(), req.session_id, "user", req.text, persona_path=None)

    speakers = pick_speakers(
        mode=mode,
        user_text=req.text,
        personas=personas,
        turn_idx=turn_idx,
    )

    replies: list[dict] = []
    tool_events: list[dict] = []

    persona_paths = {p["persona_path"] for p in personas}

    for speaker in speakers:
        speaker_path = speaker["persona_path"]

        # Build the persona; if it's gone, log a persona_skipped event and continue.
        persona_data = build_persona(_vault_root(), _db_path(), speaker_path)
        if persona_data is None:
            tool_events.append({
                "tool_name": "persona_skipped",
                "tool_args": {"persona_path": speaker_path},
                "tool_result_summary": {"error": "page gone since summon"},
            })
            continue

        # Build the system prompt with neighbors AND teammates
        con = db_mod.connect(_db_path())
        try:
            nbs = graph_neighbors(con, speaker_path)
        finally:
            con.close()
        teammate_paths = [p for p in persona_paths if p != speaker_path]

        system = build_system_prompt(
            persona_data,
            neighbor_titles=[Path(n).stem for n in nbs],
            neighbor_paths=list(nbs),
            teammate_paths=teammate_paths,
        )

        # Allowlist: graph neighbors + teammates (cross-persona consult allowed)
        allowlist = set(nbs) | set(teammate_paths)
        raw_handler = make_consult_neighbor_handler(
            vault_root=_vault_root(),
            db_path=_db_path(),
            session_id=req.session_id,
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
        history_for_llm = shared_history_for_persona(_db_path(), req.session_id, speaker_path)
        history_for_llm = _cap_history(history_for_llm)

        llm = get_llm()
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

        store.add_message(
            _db_path(), req.session_id, "assistant", reply,
            persona_path=speaker_path,
        )
        replies.append({
            "persona_path": speaker_path,
            "text": reply,
            "color": speaker["color"],
            "seat_idx": speaker["seat_idx"],
        })
        tool_events.extend(speaker_tool_events)

    return {"replies": replies, "tool_events": tool_events}


@app.get("/api/sessions")
def list_sessions_endpoint() -> list[dict]:
    return store.list_sessions(_db_path())


@app.get("/api/sessions/{session_id}")
def get_session_endpoint(session_id: int) -> dict:
    detail = store.get_session_detail(_db_path(), session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return detail


def _slugify(s: str) -> str:
    import re
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "session"


def _export_dir() -> Path:
    """Where to write exports. Defaults to ~/wiki/wiki/queries/."""
    p = os.environ.get("LIVING_VAULT_EXPORT_DIR")
    if p:
        return Path(p)
    return Path.home() / "wiki" / "wiki" / "queries"


def _format_session_markdown(detail: dict) -> str:
    from datetime import datetime
    started = detail.get("started_at", "")
    date_part = started[:10] if started else datetime.now().strftime("%Y-%m-%d")
    page_path = detail["page_path"]
    fm = [
        "---",
        "type: seance-transcript",
        f"date: {date_part}",
        f"started_at: {started}",
        f"summoned_page: {page_path}",
        "tags: [seance, transcript]",
        "---",
        "",
        f"# Séance — {page_path}",
        "",
        f"Conversation with the wiki page `[[wiki/{page_path[:-3] if page_path.endswith('.md') else page_path}]]`.",
        "",
    ]
    for m in detail["messages"]:
        role = "**You**" if m["role"] == "user" else "**Page**"
        fm.append(f"{role}:")
        fm.append("")
        fm.append(m["content"])
        fm.append("")
    return "\n".join(fm)


@app.post("/api/sessions/{session_id}/export")
def export_session_endpoint(session_id: int) -> dict:
    detail = store.get_session_detail(_db_path(), session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    out_dir = _export_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    started = detail.get("started_at", "")
    date_part = started[:10] if started else "0000-00-00"
    page_slug = _slugify(detail["page_path"].replace(".md", ""))
    fname = f"{date_part}-seance-{page_slug}.md"
    out_path = out_dir / fname
    out_path.write_text(_format_session_markdown(detail), encoding="utf-8")
    return {"exported_to": str(out_path), "session_id": session_id}


def main() -> None:
    import uvicorn
    uvicorn.run("living_vault.apps.seance_ui.app:app", host="127.0.0.1", port=7777, reload=False)


if __name__ == "__main__":
    main()
