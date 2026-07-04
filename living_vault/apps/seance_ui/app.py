"""Séance — FastAPI app, lock-free single-process.

Bind: 127.0.0.1 only. No auth (local-only).

This module is a thin HTTP adapter. Transport-neutral orchestration logic
lives in orchestrator.py. Both the FastAPI transport (here) and the MCP
transport (mcp_servers/seance/server.py) share that orchestrator.
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from living_vault.core import db as db_mod
from living_vault.apps.seance_ui.llm import get_llm  # noqa: F401 — re-exported for monkeypatching
from living_vault.apps.seance_ui import store
from living_vault.apps.seance_ui import orchestrator
from living_vault.apps.seance_ui import rag_summon
from living_vault.apps.seance_ui import constellations
from living_vault.apps.seance_ui import belief_evolution

# Re-export the constants and _cap_history so existing tests that import them
# from this module continue to work after the orchestrator extraction.
from living_vault.apps.seance_ui.orchestrator import (
    _MAX_USER_TEXT_CHARS,
    _MAX_HISTORY_MESSAGES,
    _MAX_HISTORY_TOTAL_CHARS,
    _cap_history,
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


class SummonReq(BaseModel):
    # Phase-1 single-path shape (backward-compat):
    path: str | None = None
    # Phase-10b multi-path shape:
    paths: list[str] | None = None
    mode: str = "single"
    semantic_neighbors: bool = False


class SayReq(BaseModel):
    session_id: int
    text: str


class SummonCandidatesReq(BaseModel):
    query: str
    limit: int = rag_summon.MAX_RAG_SUMMON_CANDIDATES


class ConstellationsReq(BaseModel):
    query: str
    limit: int = constellations.MAX_CONSTELLATIONS
    size: int = 3


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


@app.post("/api/summon-candidates")
def summon_candidates(req: SummonCandidatesReq) -> dict:
    try:
        return rag_summon.suggest_personas(
            _db_path(),
            req.query,
            limit=req.limit,
        )
    except rag_summon.RAGSummonError as e:
        raise HTTPException(e.code, e.detail) from e


@app.post("/api/constellations")
def constellation_candidates(req: ConstellationsReq) -> dict:
    try:
        return constellations.suggest_constellations(
            _db_path(),
            req.query,
            limit=req.limit,
            size=req.size,
        )
    except rag_summon.RAGSummonError as e:
        raise HTTPException(e.code, e.detail) from e


@app.post("/api/summon")
def summon(req: SummonReq) -> dict:
    paths = req.paths if req.paths is not None else ([req.path] if req.path else None)
    if paths is None:
        raise HTTPException(400, "must provide 'path' or 'paths'")
    try:
        return orchestrator.summon_session(
            _db_path(),
            _vault_root(),
            page_paths=paths,
            mode=req.mode,
            semantic_neighbors=req.semantic_neighbors,
        )
    except orchestrator.SéanceError as e:
        raise HTTPException(e.code, e.detail) from e


@app.post("/api/say")
def say(req: SayReq) -> dict:
    try:
        return orchestrator.say(
            _db_path(), _vault_root(), session_id=req.session_id, text=req.text,
        )
    except orchestrator.SéanceError as e:
        raise HTTPException(e.code, e.detail) from e


@app.get("/api/sessions")
def list_sessions_endpoint() -> list[dict]:
    return store.list_sessions(_db_path())


@app.get("/api/sessions/{session_id}")
def get_session_endpoint(session_id: int) -> dict:
    detail = store.get_session_detail(_db_path(), session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return detail


@app.get("/api/sessions/{session_id}/belief-evolution")
def belief_evolution_endpoint(session_id: int) -> dict:
    trace = belief_evolution.summarize_belief_evolution(_db_path(), session_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return trace


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


def _format_session_markdown(detail: dict, mode: str | None = None) -> str:
    """Render a séance session as Markdown.

    Single-mode sessions (Phase-10a): keep the legacy '**You**:' / '**Page**:'
    labels for backward-compat with existing exports.

    Roundtable sessions (Phase-10b: roundrobin / moderator / freeforall):
    label each assistant turn with its persona-stem (e.g. '**note-a**:'),
    render tool-use rows as readable lines ('» consulted [[X]] (N chars)')
    instead of raw JSON, and add a `mode:` field to the frontmatter.
    """
    import json
    from datetime import datetime
    started = detail.get("started_at", "")
    date_part = started[:10] if started else datetime.now().strftime("%Y-%m-%d")
    page_path = detail["page_path"]
    is_roundtable = mode is not None and mode != "single"

    fm: list[str] = [
        "---",
        "type: seance-transcript",
        f"date: {date_part}",
        f"started_at: {started}",
        f"summoned_page: {page_path}",
    ]
    if is_roundtable:
        fm.append(f"mode: {mode}")
    fm += [
        "tags: [seance, transcript]",
        "---",
        "",
        f"# Séance — {page_path}",
        "",
        f"Conversation with the wiki page `[[wiki/{page_path[:-3] if page_path.endswith('.md') else page_path}]]`.",
        "",
    ]

    for m in detail["messages"]:
        role = m["role"]
        content = m["content"]

        if role == "user":
            fm.append("**You**:")
            fm.append("")
            fm.append(content)
            fm.append("")
            continue

        if role == "tool_use":
            # Render readably, not as raw JSON. Same format the UI uses
            # (» consulted [[path]] (N chars) | » NAME failed: ERROR).
            try:
                payload = json.loads(content)
            except (ValueError, TypeError):
                fm.append(f"_unreadable tool event: {content}_")
                fm.append("")
                continue
            summary = payload.get("tool_result_summary", {}) or {}
            tool_name = payload.get("tool_name", "?")
            args = payload.get("tool_args", {}) or {}
            if "error" in summary:
                fm.append(f"_» {tool_name} failed: {summary['error']}_")
            else:
                npath = args.get("neighbor_path", "?")
                chars = summary.get("chars", 0)
                fm.append(f"_» consulted [[{npath}]] ({chars} chars)_")
            fm.append("")
            continue

        # role == "assistant": single-mode → **Page**, roundtable → **<stem>**
        if is_roundtable:
            persona_path = m.get("persona_path") or page_path
            stem = Path(persona_path).stem
            label = f"**{stem}**"
        else:
            label = "**Page**"
        fm.append(f"{label}:")
        fm.append("")
        fm.append(content)
        fm.append("")

    return "\n".join(fm)


@app.post("/api/sessions/{session_id}/export")
def export_session_endpoint(session_id: int) -> dict:
    detail = store.get_session_detail(_db_path(), session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    # Phase-10b: pass session mode so the formatter can render roundtable
    # sessions with per-persona labels and a mode-frontmatter field.
    mode = store.get_session_mode(_db_path(), session_id)
    out_dir = _export_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    started = detail.get("started_at", "")
    date_part = started[:10] if started else "0000-00-00"
    page_slug = _slugify(detail["page_path"].replace(".md", ""))
    fname = f"{date_part}-seance-{page_slug}.md"
    out_path = out_dir / fname
    out_path.write_text(_format_session_markdown(detail, mode=mode), encoding="utf-8")
    return {"exported_to": str(out_path), "session_id": session_id}


def main() -> None:
    import uvicorn
    uvicorn.run("living_vault.apps.seance_ui.app:app", host="127.0.0.1", port=7777, reload=False)


if __name__ == "__main__":
    main()
