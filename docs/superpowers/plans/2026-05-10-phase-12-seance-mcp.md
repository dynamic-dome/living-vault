# Phase 12 — séance MCP-Tool + commit_insight (Implementation Plan)

**Datum:** 2026-05-10
**Spec:** [`../specs/2026-05-10-phase-12-seance-mcp-design.md`](../specs/2026-05-10-phase-12-seance-mcp-design.md)
**Vorgänger:** Phase 11 ✅
**Methodik:** Subagent-driven-development pro Sub-Task (wie Phase 10/11).

## Sub-Tasks

| # | Titel | Methode | Akzeptanz |
|---|---|---|---|
| 12.1 | Insights-Tabelle + `core/insights.py` | direkt | Migration idempotent, insert+list Tests grün |
| 12.2 | Orchestrator-Refactor `apps/seance_ui/orchestrator.py` | subagent | Bestehende Tests grün + neue Orchestrator-Tests grün |
| 12.3 | `mcp_servers/seance/server.py` (Skeleton + summon/say) | subagent | `_tool_*`-Tests grün, ENV-Var-Hardening |
| 12.4 | `commit_insight` + `list_insights` + `list_sessions` MCP-Tools | direkt | Vollständige Tool-Suite, Roundtrip-Test |
| 12.5 | pyproject.toml Entry-Point `seance-mcp` + Voll-Test-Lauf | direkt | `seance-mcp.exe` installiert, 230+ Tests grün |
| 12.6 | Codex-Verifier-Pass + Master-Plan-Update + Close-Commit | direkt | Phase-12-Status ✅, PHASE-12-CHECKLIST.md |

## 12.1 — Insights-Tabelle + core/insights.py

**Files:**
- `living_vault/core/db.py` — neue Tabelle `insights` in `SCHEMA` (Anhang an
  bestehendes `SCHEMA`-String, NICHT als separates Phase-12-Migration-Skript).
- `living_vault/core/insights.py` — NEU
- `tests/test_insights.py` — NEU

**Funktionen in `core/insights.py`:**
```python
def insert_insight(
    db_path: Path,
    *,
    page_path: str,
    persona_path: str,
    question: str,
    insight: str,
    session_id: int | None = None,
) -> int:
    """Returns insight_id. Validates session_id existence if not None."""

def list_insights(
    db_path: Path,
    *,
    page_path: str | None = None,
    persona_path: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Returns rows ordered by created_at DESC. Limit capped to 100."""

def get_insight(db_path: Path, insight_id: int) -> dict | None:
    """Single-row read for tests/debugging."""
```

**Tests (mind. 6):**
1. `insert_insight` legt Row an, `get_insight` findet sie
2. `session_id=None` ist erlaubt
3. `session_id` der nicht existiert → `ValueError`
4. `list_insights(page_path=X)` filtert korrekt
5. `list_insights(persona_path=Y)` filtert korrekt
6. `list_insights(limit=200)` → max 100 zurück (Cap)
7. Empty inputs (`question=""`) → `ValueError`
8. Migration ist idempotent: `db.initialize()` zweimal hintereinander → kein Fehler

**Test-Isolation:** `tmp_path / "test.db"` — NIEMALS gegen `~/wiki/.vault-engine.db`.

## 12.2 — Orchestrator-Refactor

**Files:**
- `living_vault/apps/seance_ui/orchestrator.py` — NEU (extrahiert Logik aus `app.py`)
- `living_vault/apps/seance_ui/app.py` — verschlankt zu HTTP-Adapter
- `tests/test_seance_orchestrator.py` — NEU

**Pflichtartefakte des Orchestrator-Moduls:**

```python
class SéanceError(Exception):
    """Transport-neutral error. Code maps 1:1 to existing HTTP status codes
    so app.py can keep its current API shape."""
    def __init__(self, code: int, detail: str | dict):
        self.code = code   # 400/404/410/413/502
        self.detail = detail
        super().__init__(detail)

def summon_session(
    db_path: Path,
    vault_root: Path,
    *,
    page_paths: list[str],
    mode: str = "single",
) -> dict:
    """Returns {session_id, mode, personas, persona}. Raises SéanceError."""

def say_single(
    db_path: Path,
    vault_root: Path,
    *,
    session_id: int,
    text: str,
) -> dict:
    """Returns {reply, tool_events}. Raises SéanceError."""

def say_roundtable(
    db_path: Path,
    vault_root: Path,
    *,
    session_id: int,
    text: str,
) -> dict:
    """Returns {replies, tool_events}. Raises SéanceError(502, ...) on partial failure."""

def say(
    db_path: Path,
    vault_root: Path,
    *,
    session_id: int,
    text: str,
) -> dict:
    """Dispatches to say_single or say_roundtable based on session.mode.
    This is the single entry point both transports should use."""
```

**Constants** (`_MAX_USER_TEXT_CHARS`, `_MAX_HISTORY_MESSAGES`, `_MAX_HISTORY_TOTAL_CHARS`)
und Helper `_cap_history()` wandern aus `app.py` nach `orchestrator.py`.

**`app.py`-Änderungen:**
- `SummonReq`/`SayReq` Pydantic-Modelle bleiben in `app.py` (HTTP-spezifisch)
- Endpoint-Bodies werden zu kurzen Adaptern:
  ```python
  @app.post("/api/summon")
  def summon(req: SummonReq) -> dict:
      paths = req.paths if req.paths is not None else ([req.path] if req.path else None)
      if paths is None:
          raise HTTPException(400, "must provide 'path' or 'paths'")
      try:
          return orchestrator.summon_session(
              _db_path(), _vault_root(), page_paths=paths, mode=req.mode,
          )
      except orchestrator.SéanceError as e:
          raise HTTPException(e.code, e.detail) from e
  ```

**Akzeptanz:**
- `tests/test_seance_app.py` (oder wie immer die UI-Tests heißen) → unverändert grün
- `tests/test_seance_orchestrator.py` → ≥ 8 neue Tests grün
- KEIN Test wird gelöscht oder verändert in dieser Sub-Task. Nur ergänzen.

**Subagent-Briefing:**
> Du bekommst Spec + diesen Plan. Dein Job: orchestrator.py extrahieren, app.py
> als Adapter umschreiben. **Pflicht:** alle bestehenden tests/test_seance_*.py
> bleiben grün ohne Änderung. Du darfst `_cap_history`, Roundtable-Loop,
> Mode-Coercion 1:1 verschieben — nicht neu erfinden. Bei Konflikten zwischen
> "schöner refactoren" und "bestehende Tests grün halten" gewinnt immer
> "bestehende Tests grün halten".

## 12.3 — MCP-Server-Skeleton + summon/say

**Files:**
- `living_vault/mcp_servers/seance/__init__.py` — leer
- `living_vault/mcp_servers/seance/server.py` — NEU
- `tests/test_seance_mcp.py` — NEU

**Server-Aufbau (Pattern wie `vault_engine/server.py`):**

```python
from __future__ import annotations
import os, sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastmcp import FastMCP
from living_vault.core import db as db_mod
from living_vault.apps.seance_ui import orchestrator, store
from living_vault.core import insights as insights_mod

mcp = FastMCP("seance")

def _vault_root() -> Path: ...
def _db_path() -> Path: ...

def _tool_summon(page_paths, mode): ...
def _tool_say(session_id, text): ...
# (commit_insight + list_* in 12.4)

@mcp.tool()
def summon(page_paths: list[str], mode: str = "single") -> dict:
    ...
```

**Error-Mapping:**
`SéanceError` aus dem Orchestrator wird in MCP-Errors umgewandelt — FastMCP
wirft normale `Exception`s als Tool-Errors zurück. Deshalb:

```python
def _tool_summon(page_paths, mode):
    try:
        return orchestrator.summon_session(
            _db_path(), _vault_root(), page_paths=page_paths, mode=mode
        )
    except orchestrator.SéanceError as e:
        raise RuntimeError(f"séance error [{e.code}]: {e.detail}") from e
```

**Tests:** über `_tool_*`-Helper, nicht über stdio. Mind. 4:
1. `_tool_summon(["x.md"])` mit fixturierter Page → returns valid dict
2. `_tool_summon([])` → RuntimeError mit "[400]"
3. `_tool_say(session_id, "hi")` mit FakeLLM → returns reply
4. `_tool_say(invalid_id, "...")` → RuntimeError mit "[404]"

**Subagent-Briefing:**
> Skeleton + summon/say MCP-Tools bauen. Wichtige Pflicht: dies ist ein dünner
> Adapter, KEIN Re-Implement. summon/say rufen orchestrator.* auf, fangen
> SéanceError, und werfen RuntimeError. Tests laufen via _tool_summon/_tool_say
> direkt — nicht via stdio. ENV-Var-Setup analog vault_engine.

## 12.4 — commit_insight + list_insights + list_sessions

**Tools im selben `mcp_servers/seance/server.py`:**

```python
def _tool_commit_insight(page_path, persona_path, question, insight, session_id):
    page_path = page_path.strip()
    persona_path = persona_path.strip()
    question = question.strip()
    insight = insight.strip()
    if not (page_path and persona_path and question and insight):
        raise RuntimeError("séance error [400]: page_path, persona_path, question, insight must be non-empty")
    if len(insight) > 16_000:
        raise RuntimeError(f"séance error [413]: insight too long ({len(insight)} chars, max 16000)")
    insight_id = insights_mod.insert_insight(
        _db_path(),
        page_path=page_path,
        persona_path=persona_path,
        question=question,
        insight=insight,
        session_id=session_id,
    )
    # Read back created_at for the response
    row = insights_mod.get_insight(_db_path(), insight_id)
    return {"insight_id": insight_id, "created_at": row["created_at"]}

def _tool_list_insights(page_path, persona_path, limit):
    return insights_mod.list_insights(
        _db_path(),
        page_path=page_path, persona_path=persona_path, limit=limit,
    )

def _tool_list_sessions():
    return store.list_sessions(_db_path())
```

**Tests (mind. 4):**
1. `_tool_commit_insight(...)` legt Insight an, `_tool_list_insights(page_path=X)` findet sie
2. Empty `insight` → RuntimeError [400]
3. `len(insight) > 16000` → RuntimeError [413]
4. `_tool_commit_insight(session_id=invalid)` → ValueError aus insights_mod
5. `_tool_list_sessions()` returns dict-list (kann leer sein)

## 12.5 — Entry-Point + Voll-Test

**Files:**
- `pyproject.toml` — eine Zeile in `[project.scripts]`:
  ```
  seance-mcp = "living_vault.mcp_servers.seance.server:main"
  ```
- pip install -e . — neu installieren damit Entry-Point greift
- `pytest -q` über die ganze Suite

**Akzeptanz:**
- Test-Suite-Total ≥ 230 (vorher 218, +12+ erwartet)
- `seance-mcp.exe --help` funktioniert oder Server startet zumindest
  (FastMCP startet stdio-loop, manuelles Test ist optional)
- Keine Regression in bestehenden 218 Tests

## 12.6 — Verifier + Close

1. **Codex-Verifier** über den Phase-12-Diff (Default-Verifier-Rolle, "Wurden die
   angekündigten Änderungen korrekt umgesetzt?"). Optional auch Security falls User
   das wünscht.
2. **`docs/PHASE-12-CHECKLIST.md`** schreiben mit allen Sub-Task-Stages abgehakt.
3. **Master-Plan-Update**: Phase-12-Zeile auf ✅, Aktuelle-Position-Absatz aktualisieren.
4. **Close-Commit**: `living-vault | Phase-12 ✅ CLOSED — séance MCP shipped`.
5. **Wrap-up** in folgender Session.

## Commit-Konvention

Ein Commit pro Sub-Task:
- `living-vault | Phase-12: spec + plan (séance MCP)`
- `living-vault | Phase-12.1: insights table + core/insights.py`
- `living-vault | Phase-12.2: orchestrator extracted from seance_ui/app.py`
- `living-vault | Phase-12.3: seance MCP server skeleton + summon/say`
- `living-vault | Phase-12.4: commit_insight + list_insights tools`
- `living-vault | Phase-12.5: seance-mcp entry point + full test pass`
- `living-vault | Phase-12.6: PHASE-12-CHECKLIST + master-plan ✅`
- `living-vault | Phase-12 ✅ CLOSED`

## Risiken & Mitigationen

| Risiko | Mitigation |
|---|---|
| Orchestrator-Refactor bricht UI-Tests subtil | Sub-Task-Reihenfolge: erst 12.2 (Refactor + UI-Tests grün halten) → DANN 12.3 draufsetzen. KEINE parallele Arbeit an beiden. |
| Subagent versucht consult_neighbor neu zu bauen | Plan + Spec verbieten das explizit. Im Subagent-Briefing nochmal hervorgehoben. |
| `insights`-Tabellen-Migration kollidiert mit laufendem séance-UI | Tests benutzen tmp_path-DB. Production-DB wird nur bei Vault-Restart neu migriert; additive `IF NOT EXISTS` ist no-op. |
| FastMCP-Tool-Errors landen anders als erwartet beim Client | `_tool_*`-Tests umgehen das, validieren reine Python-Fehler. stdio-Loop wird in einer manuellen Spot-Check-Session getestet (optional). |

## Out-of-Scope für Phase 12

- Wiki-Export von Insights (`commit_insight --export` als Markdown-Page) → Phase 12.x oder Phase 13+
- Insights-Tags/Kategorien → spätere additive Migration
- Insights-Suche (volltext / semantisch) → späteres Tool
- Bulk-Insight-Import aus alten Sessions → manuell falls nötig
- séance-MCP-Auth → bleibt local-only

## Wiedereinstieg-Hinweise

Wer Phase 12 mid-stream übernimmt:
1. `docs/superpowers/plans/2026-05-10-phase-12-seance-mcp.md` (this file) → Tabelle oben
2. Status der Sub-Tasks: `git log --grep="Phase-12"`
3. Bei Refactor-Konflikt im Orchestrator: bestehende `tests/test_seance_*` sind die Source of Truth
4. ENV-Vars für lokales Test: `LIVING_VAULT_ROOT=$HOME/wiki/wiki`,
   `LIVING_VAULT_DB=$HOME/wiki/.vault-engine.db`
