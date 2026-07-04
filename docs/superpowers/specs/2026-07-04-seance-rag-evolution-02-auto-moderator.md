# Séance RAG Evolution 02 — Auto-Moderator

**Datum:** 2026-07-04
**Projekt:** Living-Vault
**Status:** Spec v1, self-reviewed
**Sequenz:** 2 von 6

## Ziel dieses Slices

Eine bestehende Multi-Persona-Seance kann im neuen Modus `auto` laufen. Der
User muss dann nicht mehr per `@mention` entscheiden, wer spricht. Pro Turn
waehlt der Auto-Moderator 1-3 bereits beschworene Personas aus, deren Page am
besten zur aktuellen User-Frage passt.

Wichtig: Auto-Moderator **summoned keine neuen Pages**. Er routet nur innerhalb
des bereits vom User bestaetigten Kreises.

## Warum dieser Schnitt jetzt

Slice 01 macht RAG zur Auswahlhilfe fuer den Kreis. Slice 02 macht RAG zur
Gespraechsleitung innerhalb dieses Kreises, ohne die Antwort-Prompts oder
`consult_neighbor` zu erweitern.

Damit bleibt die Trust-Boundary stabil:

- RAG findet Sprecher.
- Die Sprecher antworten weiterhin ueber bestehende Persona-Prompts.
- Es wird kein globaler RAG-Kontext in Antworten injiziert.

## Out of Scope

- Kein Zugriff auf Pages ausserhalb der Session-Personas.
- Kein neuer Retrieval-Context in `say()`.
- Kein LLM-basierter Moderator.
- Keine neuen DB-Tabellen.
- Kein Persistieren von Moderator-Gruenden in `seance_messages`.
- Keine Aenderung an `moderator` mit `@mention`.

## UX-Design

Die bestehende Circle-Auswahl bekommt eine weitere Option:

- `auto-moderator`

Nach dem Summon zeigt der Header:

```text
the circle — 3 spirits · auto
```

Wenn der User eine Frage stellt, antworten 1-3 passende Personas. In diesem
Slice muessen die Auswahlgruende noch nicht prominent gerendert werden; das
folgt in Slice 03 Evidence Veil.

## Backend-Design

Interner Mode-Wert:

```python
"auto"
```

Erweiterungen:

- `roundtable.VALID_MODES` enthaelt `auto`.
- `roundtable.ROUNDTABLE_MODES` enthaelt `auto`.
- Neue Funktion:

```python
def pick_auto_speakers(
    *,
    db_path: Path,
    user_text: str,
    personas: list[dict],
    turn_idx: int,
    max_speakers: int = 3,
) -> list[dict]:
    ...
```

Algorithmus:

1. Wenn keine Personas: `[]`.
2. Wenn Query leer: Round-robin-Fallback.
3. `search_semantic(con, user_text, k=max(16, len(personas) * 3))`.
4. Treffer nach Session-Persona-Pfaden filtern.
5. Bis zu 3 Personas nach Score desc auswaehlen.
6. Wenn keine Session-Persona in semantischen Treffern vorkommt: Round-robin.

Die Funktion ist bewusst deterministisch:

- Scores sortieren absteigend.
- Bei Score-Gleichstand entscheidet `seat_idx`.
- Output folgt der Score-Relevanz, nicht der Sitzreihenfolge.

## Orchestrator-Integration

In `say_roundtable(...)`:

```python
if mode == "auto":
    speakers = pick_auto_speakers(...)
else:
    speakers = pick_speakers(...)
```

Alles danach bleibt gleich:

- `build_persona`
- Nachbarn
- Teammates
- `consult_neighbor`-Allowlist
- History-Perspektive
- LLM-Caps
- Partial-Failure-Verhalten

## Privacy- und Safety-Grenzen

Der Auto-Moderator darf nur zwischen bereits bestaetigten Session-Personas
waehlen. Er darf keine neuen Pfade an Tools geben und keine fremden Pages lesen.

Bei fehlenden Embeddings oder leerer Trefferliste faellt er auf Round-robin
zurueck, statt zu crashen oder zufaellig zu waehlen.

## Rueckwaertskompatibilitaet

Unveraendert bleiben:

- `single`
- `roundrobin`
- `moderator`
- `freeforall`
- `@mention`-Semantik
- `seance-mcp` kann den neuen Mode nutzen, muss aber nicht angepasst werden,
  weil es `summon(... mode: str)` bereits generisch durchreicht.

## Test-Strategie

Neue Tests:

1. `tests/test_roundtable_speakers.py::test_auto_mode_selects_semantic_session_match`
2. `tests/test_roundtable_speakers.py::test_auto_mode_caps_to_three_speakers`
3. `tests/test_roundtable_speakers.py::test_auto_mode_falls_back_to_roundrobin_without_hits`
4. `tests/test_roundtable_app.py::test_roundtable_auto_mode_routes_to_semantic_speaker`
5. `tests/test_seance_app.py::test_summon_accepts_auto_mode`

Focused verification:

```powershell
.venv/Scripts/python.exe -m pytest -q `
  tests/test_roundtable_speakers.py `
  tests/test_roundtable_app.py::test_roundtable_auto_mode_routes_to_semantic_speaker `
  tests/test_seance_app.py::test_summon_accepts_auto_mode `
  tests/test_rag_summon.py
```

Regression verification should also rerun the Slice-01 focused/broad set.

## Acceptance Criteria

1. UI exposes `auto-moderator`.
2. Backend accepts `mode="auto"` for multi-persona summon.
3. Auto-mode chooses relevant existing session personas by semantic match.
4. Auto-mode caps replies at 3 speakers.
5. Auto-mode falls back to stable round-robin if embeddings/hits are absent.
6. Existing modes still pass their tests.
7. No answer-loop RAG context is added.

## Self-Review

### Placeholder Scan

No TBD/TODO placeholders remain. The mode name, algorithm, fallback and tests
are explicit.

### Internal Consistency

The design uses RAG only for speaker choice. This matches Slice 01's boundary:
RAG helps route the conversation but does not expand what a persona knows.

### Scope Check

The slice touches one pure helper area, one orchestrator branch and one UI
select option. It is small enough to implement without refactoring the answer
loop.

### Ambiguity Check

The user-facing option says `auto-moderator`, but the internal mode is `auto`.
This is explicit so URLs/API payloads stay short while UI copy remains legible.

### Regression Risk Review

The main risk is changing `pick_speakers` behavior for existing modes. This
spec avoids that by adding a separate auto function and keeping existing mode
branches untouched.

### Privacy Review

The moderator only filters among session personas. Semantic results outside
the session are ignored. No snippets, page bodies or external paths are exposed.
