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
    path: str


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
    persona = build_persona(_vault_root(), _db_path(), req.path)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"page not found: {req.path}")
    sid = store.new_session(_db_path(), page_path=req.path)
    return {"session_id": sid, "persona": persona}


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
