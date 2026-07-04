# Séance RAG Evolution 04 — Semantic Neighbors

**Datum:** 2026-07-04
**Projekt:** Living-Vault
**Status:** Spec v1, self-reviewed
**Sequenz:** 4 von 6

## Ziel dieses Slices

Eine Seance-Session kann optional semantisch nahe Pages als zusaetzliche
konsultierbare Archivquellen freischalten.

Bisher darf eine Persona via `consult_neighbor` nur:

- eigene Wikilink-Nachbarn konsultieren
- Roundtable-Teammates konsultieren

Mit `semantic_neighbors=true` darf sie zusaetzlich wenige semantisch aehnliche
Pages konsultieren. Diese Pages werden im Prompt klar als **Archivnaehe, nicht
als damaliges Eigenwissen** markiert.

## Grundsatz

Semantic Neighbors sind **opt-in**. Bestehende Sessions bleiben strict.

## Out of Scope

- Kein globales RAG-Context-Pack.
- Kein automatisches Lesen der semantischen Nachbarn ohne Tool-Call.
- Kein LLM-Reranking.
- Keine Public-Bundle-Funktion.
- Keine Composite-Personas.
- Keine Aenderung am Tool-Namen `consult_neighbor`.

## API-/Session-Design

Additive Spalte:

```sql
ALTER TABLE seance_sessions ADD COLUMN semantic_neighbors INTEGER NOT NULL DEFAULT 0
```

Additive Request-Felder:

```python
class SummonReq(BaseModel):
    path: str | None = None
    paths: list[str] | None = None
    mode: str = "single"
    semantic_neighbors: bool = False
```

`summon_session(...)` erhaelt ebenfalls `semantic_neighbors: bool = False`.

Response:

```json
{
  "session_id": 1,
  "mode": "auto",
  "semantic_neighbors": true,
  "personas": [...]
}
```

## Backend-Design

Neue Hilfsfunktion:

```python
def semantic_neighbors_for_persona(
    db_path: Path,
    persona_path: str,
    *,
    exclude: Iterable[str] = (),
    limit: int = 3,
) -> list[str]:
    ...
```

Algorithmus:

1. `similar(con, persona_path, k=limit + len(exclude) + 4)`
2. eigene Page und `exclude` entfernen
3. Score `<= 0` ignorieren
4. nur existierende Page-Paths zurueckgeben
5. Limit 3

Fallback:

- fehlende Embeddings -> `[]`
- keine Treffer -> `[]`

## Prompt-Design

`build_system_prompt(...)` bekommt optional `semantic_neighbor_paths`.

Neuer Block:

```text
# Semantically nearby archive pages
These pages are not pages you linked to at the time. Treat them as external
archive context you may consult, not as facts you originally knew.
  - `concepts/x.md`
```

Tool-Hinweis wird angepasst:

- Wenn semantic paths vorhanden sind, darf `consult_neighbor` exakte relpaths
  aus Neighbor-, Teammate- oder Semantic-Archive-Listen verwenden.
- Ohne semantic paths bleibt der alte Prompt faktisch unveraendert.

## Orchestrator-Design

In `say_single` und `say_roundtable`:

- `semantic_enabled = store.get_session_semantic_neighbors(...)`
- Wenn true:
  - semantic paths berechnen
  - prompt bekommt semantic paths
  - allowlist wird erweitert um semantic paths
- Wenn false:
  - bestehender Pfad bleibt unveraendert

Evidence Veil:

- `semantic_paths` werden im `evidence`-Payload als `semantic_paths` gezeigt.

## UI-Design

In der Circle-Mode-Row:

- Checkbox: `semantic archive`

Wenn aktiv, sendet `summonRoundtable()`:

```js
{paths, mode, semantic_neighbors: true}
```

Header:

```text
the circle — 3 spirits · auto · semantic archive
```

## Privacy- und Safety-Grenzen

- Opt-in only.
- Max 3 semantic paths pro Persona.
- Keine Snippets im Prompt, nur relpaths.
- Erst ein expliziter Tool-Call liest den Body-Excerpt.
- Semantic paths werden nur local-live verwendet, nicht im public bundle.
- Bestehende Allowlist-Blockade bleibt: nur vorberechnete relpaths sind erlaubt.

## Test-Strategie

Neue Tests:

1. Migration erzeugt `semantic_neighbors` default 0.
2. Summon kann `semantic_neighbors=true` persistieren.
3. `semantic_neighbors_for_persona` liefert semantisch nahe Pages ohne self.
4. Prompt rendert semantic archive block getrennt von linked neighbors.
5. Ohne Opt-in bleibt ein semantic-only Page-Consult blockiert.
6. Mit Opt-in darf ein semantic-only Page-Consult gelingen.
7. Evidence enthaelt `semantic_paths`.

## Acceptance Criteria

1. Existing sessions default to `semantic_neighbors=false`.
2. UI exposes an opt-in checkbox for semantic archive consultation.
3. Prompt clearly separates linked neighbors from semantic archive pages.
4. Tool allowlist includes semantic paths only when the session opted in.
5. Evidence Veil shows semantic paths when enabled.
6. Existing strict modes and tests remain green.

## Self-Review

### Placeholder Scan

No TBD/TODO placeholders remain. Schema, request field, prompt behavior and
tests are explicit.

### Internal Consistency

The feature does not inject RAG context automatically. It only adds bounded,
clearly labeled consultable paths after explicit session opt-in.

### Scope Check

The slice is larger than 01-03 because it adds a DB column and prompt option,
but it remains bounded: no new tool, no new table, no export changes.

### Ambiguity Check

The UI label `semantic archive` maps to backend `semantic_neighbors`. This is
explicit. The term "neighbor" is kept in code to match existing tool language.

### Regression Risk Review

Risk is accidentally broadening all sessions. Mitigation: DB default 0,
request default false, tests for blocked semantic-only consult without opt-in.

### Privacy Review

Only relpaths are added to prompts. Body excerpts are still fetched solely via
the capped, allowlisted `consult_neighbor` handler.
