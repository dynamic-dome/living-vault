# Séance RAG Evolution 01 — RAG-Summon / Summon by Question

**Datum:** 2026-07-04
**Projekt:** Living-Vault
**Status:** Spec v1, self-reviewed
**Sequenz:** 1 von 6

## Gesamtziel der Evolutionsserie

Séance soll von "Pages, die sprechen" zu einer RAG-gestuetzten
Gespraechsoberflaeche ueber den Vault wachsen, ohne die bestehenden
funktionierenden Pfade zu beschaedigen:

1. RAG-Summon / Summon by Question
2. Auto-Moderator
3. Evidence Veil
4. Semantic Neighbors
5. Persona Constellations
6. Belief Evolution

Jeder Punkt bekommt eine eigene Spec, einen Self-Review und eine kleine,
rueckwaertskompatible Implementierung. Bestehende Single-Page-Seance,
Roundtable-Modi, `consult_neighbor`, Session-Export, MCP-Server und
Public/Bundle-Privacy bleiben lauffaehig.

## Ziel dieses Slices

Der User kann in derselben Seance-UI eine Frage oder ein Thema eingeben:

> "Womit sollte ich dazu sprechen?"

Das System schlaegt 1-8 passende Pages als Personas vor. Der User kann die
Kandidaten sehen, einzelne auswaehlen oder abwaehlen und daraus wie bisher
eine Seance-Session starten.

RAG dient in diesem Slice nur der **Auswahl der Gespraechspartner**. Es wird
noch kein globaler RAG-Kontext in Antworten injiziert.

## Warum dieser Schnitt zuerst

Die Codebasis hat bereits:

- `living_vault.core.embeddings.search_semantic(con, query, k)`
- bestehende Seance-Session-Erzeugung via `summon_session(...)`
- Roundtable-Modi fuer 1-8 Personas
- eine Vanilla-JS UI mit Page-Auswahl

Der sicherste erste Schritt ist daher: Semantic Search findet Kandidaten,
aber die bestehende Persona-/Prompt-/Tool-Disziplin bleibt unveraendert.

## Out of Scope

- Kein Whole-Vault-RAG im Antwortloop.
- Kein neues LLM-Reranking.
- Keine Composite-/Multi-Page-Personas.
- Keine Aenderung an `consult_neighbor`-Allowlist.
- Keine Aenderung an MCP-Tool-Signaturen.
- Keine Public-Bundle-Live-RAG-Funktion.
- Keine neue Datenbanktabelle.
- Kein Frontend-Framework.

## UX-Design

Die linke Seitenleiste bekommt ueber der Page-Liste einen kompakten
RAG-Summon-Bereich:

- Eingabefeld: `ask the vault who should speak...`
- Button: `seek`
- Ergebnisliste mit Kandidaten:
  - Checkbox/Selection-State
  - relpath
  - Score als dezente Prozent-/Decimal-Anzeige
  - Grund: `semantic match`
- Aktion:
  - Bei 1 Kandidat: Doppelclick oder Auswahl + bestehendes Single-Summon
  - Bei 2-8 Kandidaten: bestehende Mode-Row und `summon the circle`

Die bestehende manuelle Page-Liste bleibt voll erhalten. RAG-Summon ist ein
zusaetzlicher Einstieg, kein Ersatz.

## API-Design

Neuer HTTP-Endpunkt in `apps/seance_ui/app.py`:

```python
class SummonCandidatesReq(BaseModel):
    query: str
    limit: int = 8

@app.post("/api/summon-candidates")
def summon_candidates(req: SummonCandidatesReq) -> dict:
    ...
```

Response:

```json
{
  "query": "agent memory",
  "candidates": [
    {
      "path": "concepts/agent-memory.md",
      "title": "agent-memory",
      "score": 0.72,
      "reason": "semantic match"
    }
  ]
}
```

Validation:

- `query.strip()` muss non-empty sein, sonst HTTP 400.
- `query` max. 1000 Zeichen, sonst HTTP 413.
- `limit` wird auf `1..8` geklemmt.
- Wenn keine Embeddings vorhanden sind oder kein passendes Modell im Index
  liegt, kommt `candidates: []`, kein 500.

## Backend-Design

Neues kleines transport-neutrales Modul:

`living_vault/apps/seance_ui/rag_summon.py`

Funktionen:

```python
MAX_RAG_SUMMON_QUERY_CHARS = 1000
MAX_RAG_SUMMON_CANDIDATES = 8

def suggest_personas(db_path: Path, query: str, *, limit: int = 8) -> dict:
    ...
```

Algorithmus:

1. Query trimmen und validieren.
2. DB oeffnen.
3. `search_semantic(con, query, k=limit)` ausfuehren.
4. Fuer Treffer Page-Metadaten aus `pages` lesen.
5. Treffer ohne Page-Row verwerfen.
6. Ergebnis in stabiler Reihenfolge nach Score desc liefern.

Defensive Fallbacks:

- `BackendNotAvailable` oder leere Embedding-Tabelle -> leere Liste.
- Unerwartete DB-Fehler werden nicht geschluckt; sie sind echte App-Fehler.
- Der Endpoint mappt Validierungsfehler auf HTTP 400/413.

## Privacy- und Safety-Grenzen

Dieser Slice ist local-only wie die bestehende FastAPI-Seance-UI.

Nicht erlaubt:

- Live-RAG im Public-Bundle.
- Rohe absolute Pfade in der API-Response.
- Volltext-Excerpts in den Kandidaten.
- Modellgesteuerte Pfadwahl ohne User-Bestaetigung.

Erlaubt:

- Vault-relative Page-Pfade, weil `/api/pages` diese bereits lokal zeigt.
- Titel und Scores.
- User bestaetigt die vorgeschlagenen Kandidaten vor `summon_session`.

## Rueckwaertskompatibilitaet

Bestehende Pfade bleiben unveraendert:

- `GET /api/pages`
- `POST /api/summon` mit `path`
- `POST /api/summon` mit `paths` + `mode`
- `POST /api/say`
- Records/Export
- `seance-mcp`

Die neue UI-Komponente nutzt die vorhandene `selectedPaths`-Mechanik. Wenn
RAG-Summon fehlschlaegt, bleibt die manuelle Page-Auswahl nutzbar.

## Test-Strategie

Pflicht vor jedem Pytest-Run:

- `tests/conftest.py` bestaetigt tmp_path/Test-DB-Isolation.
- `DELETE FROM`-Vorkommen in Tests sind gegen Test-DBs abgesichert.

Neue Tests:

1. `tests/test_rag_summon.py::test_suggest_personas_returns_semantic_candidates`
2. `tests/test_rag_summon.py::test_suggest_personas_rejects_empty_query`
3. `tests/test_rag_summon.py::test_suggest_personas_caps_limit_to_eight`
4. `tests/test_rag_summon.py::test_suggest_personas_returns_empty_without_embeddings`
5. `tests/test_seance_app.py::test_summon_candidates_endpoint_returns_candidates`
6. `tests/test_seance_app.py::test_summon_candidates_endpoint_rejects_empty_query`

Focused verification command:

```powershell
.venv/Scripts/python.exe -m pytest -q `
  tests/test_rag_summon.py `
  tests/test_seance_app.py::test_summon_candidates_endpoint_returns_candidates `
  tests/test_seance_app.py::test_summon_candidates_endpoint_rejects_empty_query `
  tests/test_seance_app.py::test_summon_with_paths_and_mode_creates_session_personas `
  tests/test_roundtable_speakers.py
```

Optional UI smoke after implementation:

```powershell
$env:LIVING_VAULT_ROOT="C:/Users/domes/wiki/wiki"
$env:LIVING_VAULT_DB="C:/Users/domes/wiki/.vault-engine.db"
.venv/Scripts/python.exe -m living_vault.apps.seance_ui.app
```

Then open `http://127.0.0.1:7777`, search a topic, select candidates, summon
the circle, ask one short question.

## Acceptance Criteria

1. UI offers a RAG-Summon query field without removing manual page selection.
2. `/api/summon-candidates` returns up to 8 semantic candidates with path,
   title, score and reason.
3. Candidate selection feeds the existing `selectedPaths` and `summonRoundtable`
   flow.
4. Empty/oversized queries fail readably.
5. Missing embeddings produce an empty candidate list, not a crash.
6. Existing single and roundtable summon tests still pass.
7. No public/bundle path is changed.
8. No absolute local paths or full page bodies are returned by the new endpoint.

## Follow-up Specs

This slice intentionally leaves the conversation loop unchanged. The next
spec, **Auto-Moderator**, may reuse the same semantic search primitive to pick
speakers per turn, but only after this slice is stable.

## Self-Review

### Placeholder Scan

No TBD/TODO placeholders remain. Endpoint shape, module path, validation and
tests are named.

### Internal Consistency

The design consistently keeps RAG outside the answer loop. It does not conflict
with existing strict persona prompts because the selected Pages still enter
the normal `summon_session` path.

### Scope Check

The slice is small enough for one implementation pass: one helper module, one
HTTP endpoint, one UI addition, focused tests. It does not attempt Auto-Moderator
or Semantic Neighbors.

### Ambiguity Check

The main ambiguous point is how to behave when embeddings are stale or missing.
This spec chooses fail-soft `candidates: []`, because this is an optional UI
entry point and manual selection remains available.

### Regression Risk Review

The highest regression risk is accidentally altering existing `selectedPaths`
or summon behavior in `index.html`. Mitigation: reuse the Set and existing
mode row, add tests for backend contracts, and browser-smoke the manual path
after implementation.

### Privacy Review

This spec returns only local relpaths, titles, scores and reasons. It does not
return snippets, absolute filesystem paths, secrets, or unbounded RAG context.
It does not affect public bundle generation.
