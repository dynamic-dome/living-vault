"""seance-mcp — FastMCP server exposing séance orchestration + insights.

Configuration via env vars:
  LIVING_VAULT_ROOT  - absolute path to the vault root (e.g. C:\\Users\\domes\\wiki\\wiki)
  LIVING_VAULT_DB    - absolute path to the SQLite db (default: <root>/../.vault-engine.db)

Tools exposed (Phase 12):
  summon, say, commit_insight, list_insights, list_sessions
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

# Windows MCP encoding hardening (per project memory reference).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastmcp import FastMCP

from living_vault.apps.seance_ui import orchestrator, store
from living_vault.core import insights as insights_mod


mcp = FastMCP("seance")


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


# Insight cap mirrors the LLM-output guard in orchestrator (text cap is for
# user input; insight is the persisted reflection — same order of magnitude).
_MAX_INSIGHT_CHARS = 16_000


# ---- tool implementations as plain functions (testable without stdio) ----

def _wrap_seance_error(fn, *args, **kwargs):
    """Translate orchestrator.SéanceError into MCP-visible RuntimeError."""
    try:
        return fn(*args, **kwargs)
    except orchestrator.SéanceError as e:
        raise RuntimeError(f"séance error [{e.code}]: {e.detail}") from e


def _tool_summon(page_paths: list[str], mode: str = "single") -> dict:
    return _wrap_seance_error(
        orchestrator.summon_session,
        _db_path(), _vault_root(),
        page_paths=page_paths, mode=mode,
    )


def _tool_say(session_id: int, text: str) -> dict:
    return _wrap_seance_error(
        orchestrator.say,
        _db_path(), _vault_root(),
        session_id=session_id, text=text,
    )


def _tool_commit_insight(
    page_path: str,
    persona_path: str,
    question: str,
    insight: str,
    session_id: int | None = None,
) -> dict:
    if len(insight) > _MAX_INSIGHT_CHARS:
        raise RuntimeError(
            f"séance error [413]: insight too long "
            f"({len(insight)} chars, max {_MAX_INSIGHT_CHARS})"
        )
    try:
        iid = insights_mod.insert_insight(
            _db_path(),
            page_path=page_path,
            persona_path=persona_path,
            question=question,
            insight=insight,
            session_id=session_id,
        )
    except ValueError as e:
        # Empty fields → 400; unknown session_id → 404.
        msg = str(e)
        code = 404 if "does not exist" in msg else 400
        raise RuntimeError(f"séance error [{code}]: {msg}") from e
    row = insights_mod.get_insight(_db_path(), iid)
    return {"insight_id": iid, "created_at": row["created_at"]}


def _tool_list_insights(
    page_path: str | None = None,
    persona_path: str | None = None,
    limit: int = 20,
) -> list[dict]:
    return insights_mod.list_insights(
        _db_path(),
        page_path=page_path,
        persona_path=persona_path,
        limit=limit,
    )


def _tool_list_sessions() -> list[dict]:
    return store.list_sessions(_db_path())


# ---- MCP tool registration ----

@mcp.tool()
def summon(page_paths: list[str], mode: str = "single") -> dict:
    """Open a séance session with one or more personas (1..8).

    mode: 'single' | 'roundrobin' | 'moderator' | 'freeforall'.
    Auto-coerces: 1 path → 'single'; multi + 'single' → 'roundrobin'.
    Returns: {session_id, mode, personas, persona}.
    """
    return _tool_summon(page_paths, mode)


@mcp.tool()
def say(session_id: int, text: str) -> dict:
    """Send a user turn to a session and receive replies.

    Single-mode: {reply, tool_events}.
    Roundtable: {replies, tool_events}.
    """
    return _tool_say(session_id, text)


@mcp.tool()
def commit_insight(
    page_path: str,
    persona_path: str,
    question: str,
    insight: str,
    session_id: int | None = None,
) -> dict:
    """Persist an insight gained from a séance turn.

    Returns: {insight_id, created_at}.
    session_id is optional (standalone insights allowed).
    """
    return _tool_commit_insight(
        page_path, persona_path, question, insight, session_id
    )


@mcp.tool()
def list_insights(
    page_path: str | None = None,
    persona_path: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Recent insights, ordered newest-first. Optional filters."""
    return _tool_list_insights(page_path, persona_path, limit)


@mcp.tool()
def list_sessions() -> list[dict]:
    """Recent séance sessions with message counts."""
    return _tool_list_sessions()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
