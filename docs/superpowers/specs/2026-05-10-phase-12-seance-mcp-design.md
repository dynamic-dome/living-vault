# Phase 12 — séance MCP-Tool + commit_insight (Design Spec)

**Datum:** 2026-05-10
**Phase im Master-Plan:** 12 (Phase 2)
**Vorgänger:** Phase 11 ✅ (synesthesia public subset, standalone subroute)
**Plan-Pendant:** [`../plans/2026-05-10-phase-12-seance-mcp.md`](../plans/2026-05-10-phase-12-seance-mcp.md)

## Ziel

séance — bisher nur über die FastAPI-Web-UI erreichbar — als **MCP-Tools**
exposen, damit Claude/andere Agents Personas direkt aus dem Tool-Layer
beschwören und Insights persistieren können, ohne den Umweg über den
Browser.

## Out-of-Scope (bewusst)

- **Kein Auth-Layer.** Lokal-only wie das séance-UI (127.0.0.1, single-user).
- **Keine Eigenentwicklung der Persona-/LLM-Loop.** Wir wiederverwenden
  `core.persona`, `core.llm`, `seance_ui.neighbors`, `seance_ui.roundtable`.
- **Kein Wiki-Schreibzugriff für Insights.** DB-Tabelle ist Source of Truth.
  Optionaler Wiki-Export ist Phase 12.x oder später.
- **Keine Schema-Änderung an bestehenden Tabellen.** Nur neue `insights`-Tabelle.
- **Keine UI-Änderung.** séance-UI bleibt byte-identisch.

## User-entschiedene Optionen (2026-05-10, AskUserQuestion vor Spec)

1. **MCP-Server-Ort:** Eigener Server `living_vault/mcp_servers/seance/server.py`
   — sauber getrennt vom `vault_engine`-Server, eigener Entry-Point `seance-mcp`.
2. **Insight-Persistenz:** Eigene DB-Tabelle `insights` in `.vault-engine.db`.
3. **Multi-Page:** Voll mit `page_paths: list[str]` direkt — kein Single-Path-Sonderfall
   im MCP-Interface. (Single-Page = `page_paths=[X]`.)
4. **Session-Scope:** Vollausbau in einer Session — `summon` + `say` + `commit_insight`
   + Multi-Page, analog Phase 11.

## Kernidee — wiederverwenden, nicht duplizieren

Die Roundtable-Mechanik aus `apps/seance_ui/app.py` (Mode-Coercion, Speaker-Pick,
LLM-Loop mit `consult_neighbor`-Tool, History-Cap, persona-skip-Edge-Cases)
existiert bereits und ist getestet. Der MCP-Server darf **keine Kopie** davon
sein.

**Refactor-Schritt vor MCP-Implementierung:** die transport-neutrale Orchestrierung
in ein neues Modul `apps/seance_ui/orchestrator.py` (Arbeitstitel) extrahieren.
Dieses Modul liefert pure Python-Datenstrukturen (dicts/Exceptions) — `app.py`
mappt sie auf HTTPException, der MCP-Server mappt sie auf MCP-Errors.

Konkret:

| Aktuell in `app.py` | Nach Refactor in `orchestrator.py` |
|---|---|
| `summon()` (FastAPI-Endpoint) | `summon_session(db_path, vault_root, page_paths, mode) -> SummonResult` |
| `say()` Single-Mode-Branch | `say_single(db_path, vault_root, session_id, text) -> SayResult` |
| `roundtable_say()` | `say_roundtable(db_path, vault_root, session_id, text) -> SayResult` |
| HTTP 400/404/410/413/502 | `SéanceError` mit `code` + `detail` |

`app.py` bleibt dünner Adapter. MCP-Tool-Funktionen sind ähnlich dünne Adapter
auf dieselbe Orchestrator-API.

**Entscheidung:** Refactor läuft IN Phase 12.2/12.3, nicht als separate Phase.
Bestehende `tests/test_seance_*` müssen weiterhin grün bleiben. Wenn ein Test
gegen `app.py` direkt geht, bleibt er unverändert; neue Orchestrator-Tests sind
zusätzlich.

## DB-Schema — neue Tabelle `insights`

```sql
CREATE TABLE IF NOT EXISTS insights (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    page_path     TEXT NOT NULL,           -- Welche Page wurde befragt (paths[0] für Roundtable)
    persona_path  TEXT NOT NULL,           -- Welche Persona hat die Insight geliefert
    question      TEXT NOT NULL,           -- User-Frage die zur Insight führte
    insight       TEXT NOT NULL,           -- Die Insight selbst (LLM-Output oder User-curated)
    session_id    INTEGER,                 -- NULL erlaubt: standalone commit_insight ohne Session
    created_at    TEXT NOT NULL,           -- ISO-UTC
    FOREIGN KEY (session_id) REFERENCES seance_sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_insights_page    ON insights(page_path);
CREATE INDEX IF NOT EXISTS idx_insights_persona ON insights(persona_path);
CREATE INDEX IF NOT EXISTS idx_insights_session ON insights(session_id);
```

**Migration:** additive in `core/db.py` `initialize()`, gleiches Pattern wie
Phase-9/10a/10b. `IF NOT EXISTS` macht es idempotent.

**Begründung der Felder:**
- `page_path` separat von `persona_path`, weil bei Roundtable-Sessions die
  Insight von einer **bestimmten** Persona kommt (`persona_path`), aber die
  Session als Ganzes oft an einer "Lead-Page" hängt (`page_path = paths[0]`).
- `session_id` nullable, weil ein Agent auch ohne aktive Séance-Session direkt
  eine Insight committen darf (z.B. nach manueller Reflexion).
- Kein `tags`-Feld in v1. Wenn nötig, später additiv ergänzen.

## MCP-Tool-Signaturen

Alle Tools im neuen FastMCP-Server `mcp_servers/seance/server.py`.

### `seance.summon`

```python
@mcp.tool()
def summon(page_paths: list[str], mode: str = "single") -> dict:
    """Open a séance session with one or more personas.

    Args:
        page_paths: Vault-relative paths to summon as personas. 1-8 entries.
        mode: 'single' | 'roundrobin' | 'moderator' | 'freeforall'.
              Auto-coerced: 1 path → 'single'; multi + 'single' → 'roundrobin'.

    Returns: {session_id, mode, personas: [{persona_path, color, seat_idx}, ...]}
    """
```

Validation rules (1:1 aus `app.py.summon`):
- `len(page_paths) == 0` → MCP-Error "at least one page required"
- `len(page_paths) > 8` → MCP-Error "max 8 personas per roundtable"
- Dedup preserving order
- Jede Page muss `build_persona()` non-None liefern, sonst Error pro Page

### `seance.say`

```python
@mcp.tool()
def say(session_id: int, text: str) -> dict:
    """Send a user turn to an open session and receive replies.

    For single-mode: returns {reply: str, tool_events: list}.
    For roundtable: returns {replies: list[{persona_path, text, color, seat_idx}], tool_events}.
    """
```

History-Cap (`_MAX_USER_TEXT_CHARS = 8000`, `_MAX_HISTORY_MESSAGES = 50`,
`_MAX_HISTORY_TOTAL_CHARS = 32000`) wandert in `orchestrator.py` und gilt für
beide Transporte (UI + MCP).

### `seance.commit_insight`

```python
@mcp.tool()
def commit_insight(
    page_path: str,
    persona_path: str,
    question: str,
    insight: str,
    session_id: int | None = None,
) -> dict:
    """Persist an insight gained from a séance session.

    Returns: {insight_id: int, created_at: str}
    """
```

Validation:
- `page_path`, `persona_path`, `question`, `insight` non-empty stripped
- `session_id` if given must exist in `seance_sessions` — sonst MCP-Error 404-equiv
- `len(insight) > 16_000` → Error (Cost-Guard, gleiches Muster wie text-cap)

### `seance.list_insights`

```python
@mcp.tool()
def list_insights(
    page_path: str | None = None,
    persona_path: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Read recent insights, optionally filtered by page or persona."""
```

Returns rows ordered `created_at DESC`, `limit` capped to 100.

### `seance.list_sessions` (read-only Helper)

```python
@mcp.tool()
def list_sessions() -> list[dict]:
    """Recent séance sessions with message counts."""
```

Wraps existing `store.list_sessions`. Nice-to-have für Agents die einen
`session_id` für `say`/`commit_insight` brauchen ohne UI.

## Entry-Point + Konfiguration

`pyproject.toml [project.scripts]` neu:
```
seance-mcp = "living_vault.mcp_servers.seance.server:main"
```

ENV-Vars (gleiche wie vault-engine-mcp):
- `LIVING_VAULT_ROOT` (Pflicht)
- `LIVING_VAULT_DB` (optional, default `<root>/../.vault-engine.db`)

Windows-stdout-Hardening am Modul-Anfang (UTF-8 reconfigure), wie in
`vault_engine/server.py`.

## Architektur-Diagramm

```
                ┌─────────────────────────────────┐
                │ apps/seance_ui/app.py (FastAPI) │
                └──────────────┬──────────────────┘
                               │
                               ▼
              ┌────────────────────────────────────┐
              │ apps/seance_ui/orchestrator.py     │  ← NEU
              │  - summon_session()                │
              │  - say_single()                    │
              │  - say_roundtable()                │
              │  - SéanceError                     │
              └────────┬──────────────┬────────────┘
                       │              │
            ┌──────────▼──┐      ┌────▼─────────────────┐
            │ store.py    │      │ core.persona / .llm  │
            │ neighbors   │      │ neighbors handler    │
            │ roundtable  │      │ roundtable speakers  │
            └─────────────┘      └──────────────────────┘
                       ▲
                       │
                ┌──────┴──────────────────────────────┐
                │ mcp_servers/seance/server.py        │  ← NEU
                │  summon / say / commit_insight /    │
                │  list_insights / list_sessions      │
                └──────────────────────────────────────┘
                                ▲
                                │
                ┌───────────────┴──────────────┐
                │ core/insights.py             │  ← NEU
                │  insert_insight()            │
                │  list_insights()             │
                └──────────────────────────────┘
```

## Test-Strategie

| Layer | Tests |
|---|---|
| `core/insights.py` | Insert + read-back, NULL-session_id-Pfad, list_insights mit Filter, Limit-Cap |
| `core/db.py` | Migration ist idempotent (initialize() zweimal aufrufen ändert nichts) |
| `apps/seance_ui/orchestrator.py` | summon_session 1-Path/Multi-Path/Mode-Coercion, say_single Reply-Roundtrip mit FakeLLM, say_roundtable Speaker-Pick + persona_skipped, History-Cap |
| `mcp_servers/seance/server.py` | Tools über `_tool_*`-Helper getestet (gleiches Muster wie `vault_engine/server.py`) |
| Bestehende `tests/test_seance_*` | Müssen weiterhin grün bleiben — Refactor darf API von `app.py` nicht brechen |

**Ziel:** 218 → 230+ Tests grün.

## Risiken

| Risiko | Maßnahme |
|---|---|
| Refactor bricht UI-Tests | Schritt-für-Schritt: erst Orchestrator extrahieren, beide Test-Suites grün, DANN MCP-Tools draufsetzen |
| LLM-Halluzination beim Roundtable über MCP | Gleiche Strict-Mode-Prompts wie UI — nichts ändert sich am System-Prompt |
| Insights-Tabelle wächst unbegrenzt | Phase 12 ignoriert das. `list_insights` hat Default-Limit 20; Pruning ist Phase 12.x oder Wiki-Export |
| Concurrent Writes (UI + MCP gleichzeitig) | SQLite-Default-Locking reicht; nur kurze Transaktionen, keine langen Reads |
| Codex-LOW SQLite-IN-Limit (Phase-11-Carry-Over) | Nicht in Phase 12 relevant — keine IN-Klauseln in `insights`-Pfaden |

## Akzeptanzkriterien

1. `seance-mcp` startet als MCP-Server, antwortet auf `tools/list` mit den 5 Tools.
2. `seance.summon(page_paths=[X])` öffnet Session, `seance.say(session_id, text)`
   liefert eine Reply (FakeLLM in Tests).
3. `seance.summon(page_paths=[A,B], mode="roundrobin")` öffnet Multi-Persona-Session,
   `say` liefert `replies: list`.
4. `seance.commit_insight(...)` legt Row an, `seance.list_insights(page_path=X)`
   findet sie wieder.
5. `tests/test_seance_*` sind weiterhin grün, Test-Suite-Total ≥ 230.
6. UI bleibt funktionsfähig (kein Regression-Test bricht).
7. Codex-Verifier läuft über Phase-12-Diff, Befunde dokumentiert.

## Was NICHT verhandelt wird

- 4 User-entschiedene Optionen (Server-Ort, DB-Tabelle, Multi-Page, Vollausbau)
- Refactor des séance-UI-Codes ist Pflicht (sonst Code-Duplikation)
- DB-Schema oben — Felder geändert nur per neuer Spec-Revision
