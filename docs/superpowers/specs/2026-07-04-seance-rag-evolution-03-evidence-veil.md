# Séance RAG Evolution 03 — Evidence Veil

**Datum:** 2026-07-04
**Projekt:** Living-Vault
**Status:** Spec v1, self-reviewed
**Sequenz:** 3 von 6

## Ziel dieses Slices

Séance-Antworten sollen eine sichtbare, einklappbare Belegspur bekommen:

> Welche Persona/Page sprach hier, welche Quellen wurden konsultiert, und
> welcher Routing-Modus hat sie aufgerufen?

Das bleibt atmosphaerisch in der Seance-UI, aber epistemisch klarer: der User
sieht bei einer Antwort nicht nur Text, sondern auch den "Veil" darunter.

## Schnitt

Dieser Slice baut **kein neues Retrieval**. Er macht nur sichtbar, was im
bestehenden Antwortpfad bereits passiert:

- eigene Persona-Page
- konsultierte Nachbarn/Teammates ueber `consult_neighbor`
- Routing-Modus (`single`, `roundrobin`, `moderator`, `auto`, `freeforall`)

Semantic-Summon-Kandidaten und Auto-Moderator-Auswahl bleiben getrennt. Der
Evidence Veil darf nicht anfangen, fremde Pages nachzuladen.

## Out of Scope

- Keine Persistenz neuer Evidence-Daten in `seance_messages`.
- Keine neue DB-Tabelle.
- Kein Whole-Vault-RAG.
- Kein Zitierzwang fuer jede einzelne Aussage.
- Kein Exportformat-Umbau.
- Keine Aenderung am LLM-Prompt.
- Keine Aenderung an `consult_neighbor`-Allowlist.

## API-Design

Single-Mode `/api/say` erhaelt additiv:

```json
{
  "reply": "...",
  "tool_events": [],
  "evidence": {
    "persona_path": "concepts/note-a.md",
    "mode": "single",
    "own_page": "concepts/note-a.md",
    "consulted_paths": [],
    "routing": "single persona"
  }
}
```

Roundtable-Replies erhalten je Reply additiv:

```json
{
  "persona_path": "concepts/note-b.md",
  "text": "...",
  "color": "#...",
  "seat_idx": 1,
  "evidence": {
    "persona_path": "concepts/note-b.md",
    "mode": "auto",
    "own_page": "concepts/note-b.md",
    "consulted_paths": ["concepts/note-a.md"],
    "routing": "auto-moderator selected this persona from the current circle"
  }
}
```

Compatibility:

- Existing clients can ignore `evidence`.
- Existing response fields are unchanged.
- Tool events remain in `tool_events` as before.

## Backend-Design

Add a small helper in `orchestrator.py`:

```python
def _build_evidence(...):
    ...
```

Rules:

- `own_page` is always the responding `persona_path`.
- `consulted_paths` is derived only from successful `consult_neighbor`
  `tool_events`.
- `consulted_paths` is deduped preserving order.
- No page body, excerpts, absolute filesystem path or secrets are included.
- `routing` is a short human-readable string derived from mode.

## UI-Design

Under each assistant/persona bubble:

```text
sources used
own page: concepts/note-b.md
consulted: concepts/note-a.md
routing: auto-moderator selected this persona from the current circle
```

Implementation:

- Use native `<details>` / `<summary>` for the foldout.
- Keep it visually subdued: mono font, small size, no extra card-in-card.
- Existing separate tool-event bubbles remain visible.

## Test-Strategie

New tests:

1. Single-mode reply includes `evidence` with `own_page`.
2. Roundtable reply includes `evidence` per reply.
3. Consulted paths appear in evidence after successful `consult_neighbor`.
4. Evidence payload does not include `body`, `excerpt`, or absolute local paths.
5. Existing old response-shape tests still pass.

Focused verification:

```powershell
.venv/Scripts/python.exe -m pytest -q `
  tests/test_seance_app.py::test_summon_creates_session_and_responds `
  tests/test_roundtable_app.py::test_roundtable_reply_includes_evidence `
  tests/test_roundtable_app.py::test_cross_persona_consult_is_allowed `
  tests/test_seance_say_with_tools.py
```

## Acceptance Criteria

1. `/api/say` single-mode response includes add-on `evidence`.
2. Roundtable replies include add-on `evidence`.
3. UI renders an expandable `sources used` section under replies when evidence
   is present.
4. Evidence contains no bodies/excerpts/absolute local paths.
5. Existing tool-event display still works.
6. Existing modes and tests remain green.

## Self-Review

### Placeholder Scan

No TBD/TODO placeholders remain. Response shape, helper rules and UI behavior
are explicit.

### Internal Consistency

The spec makes existing context visible but does not expand retrieval. This
keeps it aligned with Slice 01 and 02: RAG routes, but answer knowledge remains
bounded by existing Persona/Neighbor rules.

### Scope Check

This is a small additive slice: one helper, response payload additions, UI
rendering and tests. No schema or prompt changes.

### Ambiguity Check

Evidence is live-only in this slice. Reopened sessions still show persisted
tool-event rows, but not reconstructed evidence foldouts. That is intentional
to avoid a transcript/export migration in this slice.

### Regression Risk Review

The highest risk is breaking existing clients that expect only `reply` or
`replies`. The implementation uses additive fields only, so old callers can
ignore them.

### Privacy Review

Evidence includes only relpaths and mode labels. It does not include full page
content, snippets, absolute local filesystem paths or hidden private graph
edges beyond paths already visible in the local Seance session.
