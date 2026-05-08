"""Séance — FastAPI app, lock-free single-process.

Bind: 127.0.0.1 only. No auth (local-only).
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from living_vault.core import db as db_mod
from living_vault.core.persona import build_persona_lite
from living_vault.core.graph import neighbors as graph_neighbors
from living_vault.apps.seance_ui.prompt import build_system_prompt
from living_vault.apps.seance_ui.llm import get_llm
from living_vault.apps.seance_ui import store


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


app = FastAPI(title="séance")
STATIC_DIR = Path(__file__).parent / "static"


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
    persona = build_persona_lite(_vault_root(), _db_path(), req.path)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"page not found: {req.path}")
    sid = store.new_session(_db_path(), page_path=req.path)
    return {"session_id": sid, "persona": persona}


@app.post("/api/say")
def say(req: SayReq) -> dict:
    history = store.get_history(_db_path(), req.session_id)
    # find the page for this session
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
    persona = build_persona_lite(_vault_root(), _db_path(), page_path)
    if persona is None:
        raise HTTPException(status_code=410, detail="page gone since session start")
    system = build_system_prompt(persona, neighbor_titles=[Path(n).stem for n in nbs])

    history.append(("user", req.text))
    llm = get_llm()
    reply = llm.respond(system=system, history=history)

    store.add_message(_db_path(), req.session_id, "user", req.text)
    store.add_message(_db_path(), req.session_id, "assistant", reply)
    return {"reply": reply}


def main() -> None:
    import uvicorn
    uvicorn.run("living_vault.apps.seance_ui.app:app", host="127.0.0.1", port=7777, reload=False)


if __name__ == "__main__":
    main()
