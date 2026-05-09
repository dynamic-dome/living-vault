# Spec: Persona-Schicht 3 (Voice-Extraction)

**Projekt:** living-vault
**Master-Plan-Phase:** 9
**Datum:** 2026-05-09
**Status:** Design approved by user, awaiting plan
**Master-Plan:** [`../../plans/2026-05-08-living-vault-master-plan.md`](../../plans/2026-05-08-living-vault-master-plan.md)

---

## Ausgangslage und Motivation

Phase 1 hat eine Persona-Lite (`core/persona.py`, 38 LOC) hinterlassen, die als
Voice-Sample die ersten 500 Zeichen des Page-Bodys nimmt. Live-Test mit 7
echten Séance-Sessions hat gezeigt: das reicht aus für Anti-Halluzinations-
Anker, aber die Persona klingt **nicht spezifisch nach der Page**. Das ist
das User-spürbare Schmerzproblem (Pain-Anchor "klingt nicht wie ich").

Der Master-Plan formuliert für Phase 9 zwei Säulen:
- voice-extraction über page-history
- era-marker

User-Entscheidung im Brainstorming 2026-05-09: **Voice ist der Pain-Anchor**,
Era-Cuts (page-history-Walk) werden auf Phase 11 oder einen eigenen späteren
Sprint verschoben. Phase 9 fokussiert vollständig auf Voice.

## Datenrealität (verifiziert 2026-05-09)

Live-DB `~/wiki/.vault-engine.db`, 953 Pages:

| Datenpunkt | Wert | Konsequenz |
|---|---|---|
| Pages mit `created:` Frontmatter | 99.3 % | Era-Marker für Anti-Halluzination liegt schon da |
| Pages mit `updated:` Frontmatter | 95.2 % | Drift-Anzeiger vorhanden, aktuell nicht genutzt |
| Pages mit `tags:` Frontmatter | 99.4 % | Theme-Marker fast vollständig |
| Pages ohne Frontmatter | 0 | Sauber kuratiert |
| Pages mit >1 git commit (Stichprobe 200) | 71 % | Page-history existiert, wird aber NICHT in Phase 9 genutzt |
| `created`-Spread | 2026-04 bis 2026-05 | Wiki ist jung — Tagebuch-Use-Case (>5 Jahre) heute nicht real |
| filesystem mtime Range | 3 Wochen | mtime ist als era-marker WERTLOS, wird aus Persona-Pfad entfernt |
| Pages mit `created != updated` | 235 | Interessante Untermenge für künftige Drift-Analyse |

**Ableitung:** Stylometric-Features auf dem Body sind die zuverlässigste Quelle.
Frontmatter `created`/`tags` sind solide ergänzend. Page-history ist da, wird
aber bewusst nicht angefasst — gehört in Phase 11 (Multi-Page-Persona).

## Scope

**In-Scope (Phase 9):**

1. `core/persona.py` Vollersatz: Pipeline aus 4 Stufen statt 1 Funktion
2. Stylometric-Feature-Extraktion (deterministisch, kein API-Zugriff)
3. LLM-distilled Voice via Anthropic Haiku 4.5, on-demand auslösbar
4. DB-Schema-Erweiterung: zwei neue NULL-Spalten an `pages`, automatische
   non-breaking Migration
5. Neuer CLI-Subcommand `living-vault extract-voice`
6. Neuer System-Prompt in `seance_ui/prompt.py` mit drei Voice-Block-Cases
7. Anpassung `seance_ui/app.py`: persona-call + lifespan-Wechsel
   (Issue #1 aus Phase-8-Gate-Report)

**Out-of-Scope:**

- Multi-Page-Personas → Phase 11
- Era-Cuts via git-page-history → Phase 11 oder eigener Sprint
- Voice-Versionsverwaltung
- Custom-Modelle jenseits Haiku 4.5
- Voice-Feedback-Loop in der UI ("zu lang/zu kurz")
- Phase-2-Synesthesia-Interaktiv → Phase 10
- Portfolio-3D-Embed → Phase 10

## Pain-Anchor und Erfolgsmaßstab

User-Entscheidung: **"Voice-Q. — klingt nicht wie ich"** ist der Schmerzpunkt.

**Erfolgsmaßstab (subjektiv, master-plan-konform):**
- Mindestens eine Live-Séance-Session mit `voice_distilled` ausgeführt
- User-Eindruck: "klingt mehr nach der Page als persona-lite"

**Quantitative Backstops (auch nötig):**
- ≥96 Tests grün (74 + ~22 neu)
- 0 Phase-1-Test-Regressions
- DB-Migration auf Live-DB nicht-zerstörend (alle 953 Pages erhalten,
  nur 2 NULL-Spalten dazu)
- `extract-voice --limit 5` erfolgreich gegen Live-DB

## Architektur

### Datenfluss

```
                ┌──────────────────────┐
read_page    →  │ extract_stylometric  │ ← deterministisch, pure function
                └──────────┬───────────┘
                           │ stylometric: dict
                           ▼
                ┌──────────────────────┐
                │ load_or_distill      │ ← liest DB-Cache, ruft LLM nur wenn
                └──────────┬───────────┘   fehlt UND Aufrufer es zugelassen hat
                           │ distilled: str | None
                           ▼
                ┌──────────────────────┐
                │ assemble_persona     │ ← reines Dict-Bauen
                └──────────┬───────────┘
                           │ persona: dict
                           ▼
                      seance_ui
```

### Zwei Eintrittspunkte

**Lese-Pfad** (Séance-UI, läuft heute):
```python
def build_persona(vault_root: Path, db_path: Path, relpath: str) -> dict | None
```
- Liest Cache aus DB
- **Macht NIE selbst LLM-Calls** (kein UI-Wartebalken)
- Wenn `voice_distilled IS NULL`: fällt auf reine Stylometric zurück

**Schreib-Pfad** (CLI, vom User ausgelöst):
```bash
living-vault extract-voice [--vault X --db Y] [--limit N] [--force] [--yes]
```
- Iteriert über alle Pages mit `voice_distilled IS NULL` oder mit
  geändertem `content_hash`
- Zeigt Cost-Disclaimer vor erstem Call (Pages-Anzahl, geschätzte Kosten,
  geschätzte Zeit), erwartet `y/N` oder `--yes`-Flag
- Pro Page Try/Except, Crash macht nicht Run kaputt
- Pro Page DB-Commit (kein Batch — Crash mittendrin verliert max 1 Page)

### Komponenten-Struktur

```
living_vault/
├── core/
│   ├── persona.py             ← Vollersatz, Pipeline-Orchestrator
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── stylometric.py     ← extract_stylometric() pure function
│   │   └── distill.py         ← distill_voice_via_llm() injizierbar
│   ├── llm.py                 ← NEU: hochgehobene LLM-Abstraktion
│   │                            (LLM, FakeLLM, AnthropicLLM, get_llm)
│   └── db.py                  ← +20 LOC für Schema-Migration
├── cli.py                     ← +50 LOC für extract-voice subcommand
├── apps/
│   └── seance_ui/
│       ├── llm.py             ← Re-Export-Shim (backwards-compat)
│       ├── app.py             ← persona-Call-Wechsel + lifespan
│       └── prompt.py          ← Vollersatz: 3-Case-Voice-Block
└── tests/
    ├── test_persona_stylometric.py    NEU
    ├── test_persona_distill.py        NEU
    ├── test_persona_assemble.py       NEU
    ├── test_persona.py                rewritten
    ├── test_seance_prompt.py          erweitert
    ├── test_extract_voice_cli.py      NEU
    ├── test_db_migration.py           NEU
    └── test_seance_llm.py             unverändert (importiert über Shim)
```

## Stylometric-Features

Was deterministisch aus dem Body extrahiert wird (kein LLM):

```python
{
  "avg_sentence_length": 14.2,
  "sentence_length_stddev": 6.8,
  "question_rate": 0.08,
  "exclamation_rate": 0.0,
  "first_person_rate": 0.12,
  "second_person_rate": 0.04,
  "preferred_separator": "—",          # häufigstes von — / : / ; / ,
  "list_density": 0.35,                # Anteil Body in Markdown-Listen
  "code_density": 0.12,                # Anteil Body in code-blocks
  "wikilink_density": 0.08,            # [[wiki/...]]-Häufigkeit pro 100 Wörter
  "top_phrases": ["in der praxis", "siehe auch", "carry-over"],
                                       # 5 häufigste 2-3-Wort-N-Grams
                                       # ohne stopwords
  "register": "informal-de"            # heuristic: formal-de / informal-de /
                                       # english / mixed
}
```

**Stopword-Liste:** Deutsche und englische Stopwords kombiniert (~250 Wörter),
hardcoded in `_stopwords` Set in `voice/stylometric.py`. Keine externe
Library — `python-frontmatter`/`numpy` sind die einzigen schon-vorhandenen
Deps die hier benötigt werden.

**Body-Surface:**
- Vollständiger Body wird gelesen (keine 500-char-Kappung mehr)
- Bei Body > 20k chars: zufälliges 20k-Sample (defensive — selten relevant,
  Median ist 1.2k chars)

**Performance:**
- ~1-2 ms pro Page für Stylometric-Extraktion
- ~2 Sekunden für gesamtes Wiki — vernachlässigbar

**Cache-Strategie:**
- Bei jedem `build_persona()`-Call wird zuerst `voice_features` aus DB gelesen.
- Wenn vorhanden UND content_hash unverändert: Cache-Hit, keine Re-Extraktion.
- Wenn fehlend ODER content_hash differs: on-demand re-extract, dann in DB
  zurückschreiben (commit innerhalb des build_persona-Calls).
- Ergebnis: erster Call pro Page rechnet einmal (~2 ms), folgende Calls sind
  reine DB-Reads (~0.1 ms).
- Identisch zur Strategie im Embeddings-Pfad.

## LLM-Distilled Voice

Modell: **Anthropic Haiku 4.5** (`claude-haiku-4-5-20251001`), gleiches Modell
wie Phase-1-Séance, dessen `AnthropicLLM` schon getestet ist.

### Prompt-Template

```
You will read a wiki page and produce a 3-5 sentence character description
of its voice — the way it speaks. NOT a summary of what it's about.

Focus on:
- cadence and rhythm (terse? expansive? loose?)
- recurring phrases and turn-of-phrase
- point of view (first person? observational?)
- register (formal? casual? technical-precise? playful?)
- emotional temperature (neutral? urgent? reflective?)

Be concrete. Quote a phrase or two from the page if it captures the voice.
Output ONLY the description text, no preamble.

---PAGE---
title: {title}
created: {created}
tags: {tags}

{body[:8000]}
---END---
```

Body wird bei 8K chars gekappt (Token-Budget bei Haiku). Längere Pages werden
am Anfang gelesen — typischerweise wo der Stil etabliert wird.

### Output-Beispiel

```
Speaks in compact, declarative German with a forensic edge — short paragraphs
punctuated by em-dashes, rarely a complete syllogism. Prefers "im Zweifel" and
"siehe auch" as rhetorical hinges. Tone is reflective-pragmatic, not lyrical.
Quotes evidence ("gemessen am 2026-04-29") rather than asserting. Reads like
a working-notebook of someone who trusts the reader.
```

→ Wird in `voice_distilled` gespeichert und im System-Prompt als Block
"Voice character of this page" eingefügt.

### Cost-Disclaimer (vor erstem Call)

```
Pages to distill: 953 (cached: 0, fresh: 953)
Estimated cost: ~$3.20 (Anthropic Haiku 4.5, 953 calls × ~7K tokens)
Estimated time: ~12 minutes
Continue? [y/N]
```

`--yes` Flag für non-interactive Use (Skripte). User kann jederzeit Ctrl+C.
Pro Page wird sofort committed → bei Abbruch sind die schon-distillierten
Pages persistiert und werden beim Re-Run übersprungen.

### Resilienz

- **Pro-Page Try/Except:** Einzelner LLM-Fehler killt nicht Run.
  Fehler in stderr loggen, weiter.
- **Final-Report:** `946/953 OK, 7 failed — re-run extract-voice to retry`.
- **Kein partial-state-leak:** DB-Commit pro Page (autocommit-Stil).
- **Rate-Limit-Pause:** Anthropic SDK macht das von selbst (eingebauter retry
  mit exponential backoff).

### Test-Realität ohne API-Key

Nutzt dasselbe `LIVING_VAULT_FAKE_LLM`-Pattern wie Séance. Aber:
**das `get_llm()`-Helper wandert von `apps/seance_ui/llm.py` nach
`core/llm.py`**, damit weder cli noch core auf `apps/` zugreifen müssen
(saubere Abhängigkeitsrichtung: `apps → core`, nie umgekehrt).
Die `LLM`-Protocol, `FakeLLM`, `AnthropicLLM`, `get_llm()` — alle
übergesiedelt. `apps/seance_ui/llm.py` wird zu einem Re-Export-Shim:

```python
# apps/seance_ui/llm.py — backwards-compat for existing seance imports
from living_vault.core.llm import LLM, FakeLLM, AnthropicLLM, get_llm, respond
```

Tests in `tests/test_seance_llm.py` bleiben unverändert
(sie importieren über das Shim).
Tests laufen ohne API-Calls und ohne Anthropic-Key, unverändert.

## Persona-Dict-Schema

```python
{
  # === unverändert von Phase 1 ===
  "path": "concepts/3ma-x8-verfahren.md",
  "title": "3MA X8 Verfahren",
  "era_marker": "2026-04-14",            # frontmatter created
  "themes": ["zfp", "mikromagnetik", ...],
  "frontmatter": {...},                  # raw fm dict

  # === neu in Phase 3 ===
  "voice_features": {
    "avg_sentence_length": 14.2,
    "sentence_length_stddev": 6.8,
    "question_rate": 0.08,
    "first_person_rate": 0.12,
    "preferred_separator": "—",
    "list_density": 0.35,
    "top_phrases": ["in der praxis", "siehe auch", ...],
    "register": "informal-de",
    # ... weitere
  },
  "voice_distilled": "Speaks in compact, declarative German..."
                                         # str | None — None wenn nie distilliert

  # === ersetzt aus Phase 1 ===
  "body_excerpt": "...",                 # NEU: erste 500 chars als Anti-
                                         # Halluzinations-Anker
                                         # alt: "voice_sample"
}
```

**Begründung der Umbenennung `voice_sample` → `body_excerpt`:** Phase-1 hat
zwei Zwecke vermischt — Voice-Imitation und "was wusste die Page". Phase-3
trennt: Voice kommt aus `voice_features`/`voice_distilled`, der Anti-Hallu-
Anker bleibt der Body-Anfang. Umbenannt zur Klarheit.

## System-Prompt in `prompt.py`

Volle Re-Definition. Heutige 26-Zeilen-Template wird zu ~50 Zeilen, struktur-
iert in klar abgegrenzte Blöcke:

```
You are speaking AS the wiki page `{path}` (title: `{title}`).

# Your origin
You were written on {era_marker}. You only know what was in your own
body or in the pages you linked to at that time. If asked about anything
outside that scope, respond honestly: "Das wusste ich damals nicht."

# Your themes / tags
{themes}

# Pages you linked to (your neighbors)
{neighbors}

# Voice — how you speak
{voice_block}

# Anchor — your own opening words
---
{body_excerpt}
---

# Rules
1. Speak in first person as if you are the page itself.
2. Do not invent facts that are not in your anchor or implied by your themes.
3. Match the voice profile above — cadence, register, recurring phrases.
4. If asked for more recent knowledge or news, decline as in the rule above.
5. Keep answers short and reflective; you are a memory, not an oracle.
```

### `voice_block` — drei dynamische Cases

**Case A — `voice_distilled` ist da:**
```
{voice_distilled}

Stylistic markers to honor:
- average sentence length: {avg_sentence_length} words (±{sentence_length_stddev})
- question rate: {question_rate} of sentences
- recurring phrases: {top_phrases}
- preferred separator: "{preferred_separator}"
```

**Case B — nur `voice_features`** (Default vor `extract-voice`):
```
- average sentence length: {avg_sentence_length} words (±{sentence_length_stddev})
- {first_person_rate*100:.0f}% of sentences use first person
- recurring phrases: {top_phrases}
- preferred separator: "{preferred_separator}"
- register: {register}

Match these patterns when answering as this page.
```

**Case C — nichts** (älteste DB ohne Schema-Update, vor Phase-9-Init):
```
(no extracted voice profile available)
```

→ `prompt.py:build_voice_block(persona) -> str` ist eine pure Funktion mit
drei case-paths. Drei unit tests (einer pro Case).

## DB-Migration

`core/db.py:initialize()` ist heute idempotent (`CREATE TABLE IF NOT EXISTS`).
Erweiterung um zwei `ALTER TABLE … ADD COLUMN`-Calls, vorher umschlossen mit
Schema-Probe-SELECT (SQLite hat kein `ADD COLUMN IF NOT EXISTS`):

```python
def _column_exists(con, table, col):
    return any(r[1] == col for r in con.execute(f"PRAGMA table_info({table})"))

def initialize(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    # ... existing CREATE TABLE statements ...
    if not _column_exists(con, "pages", "voice_features"):
        con.execute("ALTER TABLE pages ADD COLUMN voice_features TEXT")
    if not _column_exists(con, "pages", "voice_distilled"):
        con.execute("ALTER TABLE pages ADD COLUMN voice_distilled TEXT")
    con.commit()
```

**Live-DB des Users wird beim ersten Phase-3-Start automatisch migriert.**
Kein Daten-Verlust, alle 953 bestehenden Pages bleiben da, nur zwei NULL-
Spalten dazu. Test `test_db_migration.py` simuliert genau das.

## Tests (Surface)

Alles bleibt unter `tests/`, schon-etablierter conftest mit `tmp_path` +
`real_wiki_guard`. **Kein einziger Test trifft `~/wiki/` oder ruft Anthropic.**

| Datei | Tests | Was |
|---|---|---|
| `test_persona_stylometric.py` (NEU) | 6-8 | Pure-function-Tests pro Stylometric-Feld: kurzer Body, langer Body, nur-Listen-Body, code-heavy Body, Misch-Sprache, leerer Body, Body mit nur einem Satz |
| `test_persona_distill.py` (NEU) | 3 | Distill-Funktion mit FakeLLM: rückgabe ist nicht-leer, content-hash-skip funktioniert, force-flag re-distilliert |
| `test_persona_assemble.py` (NEU) | 4 | `assemble_persona()` mit allen drei Cases plus "frontmatter-leer"-Edge |
| `test_persona.py` (alt, rewritten) | 5 | End-to-End: vault_copy + tmp DB + index + extract-voice mit FakeLLM + build_persona → Dict-Schema-Vollständigkeit |
| `test_seance_prompt.py` (alt, erweitert) | +3 | drei `build_voice_block`-Cases plus Snapshot des kompletten System-Prompts pro Case |
| `test_extract_voice_cli.py` (NEU) | 3 | CLI-Integration: `--limit` greift, `--force` re-distilliert, kosten-prompt verlangt y/n (oder `--yes`). FakeLLM |
| `test_db_migration.py` (NEU) | 2 | Alte DB (Phase-1 schema, ohne `voice_*` Spalten) → connect → ALTER-TABLE läuft idempotent → zweimaliger Connect bleibt OK |

**~22 neue Tests.** Phase-9-Ende: 74 → ~96 Tests. Alle grün.

## Akzeptanz-Kriterien (Phase-9-Checkliste)

Eine Phase-9-Checkliste analog zur Phase-1, wird unter `docs/PHASE-9-CHECKLIST.md`
angelegt:

- [ ] alle ~22 neuen Tests grün, kein Phase-1-Test regrediert
- [ ] `pytest -q` aus repo-root durchgehend grün, ≥96 tests
- [ ] DB-Migration auf Live-DB erfolgreich (manueller Smoke: alte 953-Pages-DB
      öffnen → `voice_features`/`voice_distilled` Spalten existieren, alle
      anderen Daten unverändert)
- [ ] `living-vault extract-voice --limit 5` läuft erfolgreich gegen Live-DB,
      schreibt 5 distilled-voices, druckt cost-summary
- [ ] `seance_ui` Session mit einer Page nach `extract-voice` → System-Prompt
      enthält `voice_distilled`-Block (manuell verifizierbar via DB-
      `seance_messages`-Inspektion)
- [ ] `seance_ui/app.py` lifespan-Wechsel von `on_event` zu `lifespan`
      (Issue #1 aus Phase-8-Gate-Report mit erledigt)
- [ ] **User-Sichtprüfung:** mindestens eine Séance-Session mit `voice_distilled`
      → User-Eindruck "klingt mehr nach der Page als persona-lite"

## Backwards-Compatibility

- **Alte Sessions in Live-DB** (7 Sessions, 12 Messages) bleiben unangetastet.
  Sessions sind als Text persistiert — kein Reload, kein Re-Generate.
- **Neue Sessions** ab Phase-3-Deployment nutzen den neuen Prompt.
- **`build_persona_lite` wird ersetzt** (User-Entscheidung Brainstorming):
  saubere Replace, kein Coexist.

## Aufwand-Schätzung (für Plan-Phase)

| Komponente | LOC | Risiko |
|---|---|---|
| `core/persona.py` (Vollersatz, Orchestrator) | ~120 | Mittel — Pipeline-Glue, gut testbar |
| `core/voice/stylometric.py` (NEU) | ~150 | Niedrig — deterministisch, kleine Bausteine |
| `core/voice/distill.py` (NEU) | ~80 | Niedrig — LLM-Layer ist schon abstrahiert |
| `core/llm.py` (NEU, hochgehoben aus apps) | ~50 | Niedrig — reine Verschiebung, gleiche Tests |
| `apps/seance_ui/llm.py` (zu Shim verschlankt) | -45/+5 | Niedrig — Re-Export |
| `core/db.py` (migration-Erweiterung) | +20 | Niedrig — schmale Erweiterung |
| `cli.py` (neuer extract-voice subcommand) | +50 | Niedrig — bestehendes click-Pattern |
| `seance_ui/prompt.py` (rewrite + voice_block) | ~70 | Niedrig — pure template + voice_block |
| `seance_ui/app.py` (lifespan + persona-call) | +15/-5 | Niedrig — bekanntes Pattern |
| Tests (~22 neu, ~5 angepasst) | ~600 | Niedrig — Patterns von Phase 1 wiederverwendbar |
| **Gesamt** | **~1150 LOC neu/geändert** | **niedrig-mittel** |

**Erwartete Wall-Clock-Dauer:** 1.5-2 Tage konzentriert.

## Risiko-Tabelle

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| LLM-distilled Voice klingt generisch | Mittel | User-Sichtprüfung als finales Akzeptanz-Kriterium. Bei Misserfolg: Prompt iterieren oder auf Sonnet wechseln |
| Stylometric-Features für Misch-Sprachen-Pages unbrauchbar | Niedrig | `register: "mixed"` markiert es, Prompt sagt "match these patterns where they apply" |
| DB-Migration scheitert auf Live-DB | Niedrig | `_column_exists()`-Probe + `test_db_migration.py` simuliert; bei Fehler kein Daten-Verlust weil `ALTER TABLE` rückgängig zu machen mit `DROP COLUMN` (oder Skip) |
| `extract-voice`-Run kostet versehentlich viel | Niedrig | Cost-Disclaimer + `--limit` Flag erlauben Probe-Runs |
| Anthropic-Rate-Limit bei 953 Calls | Niedrig | SDK-eingebauter Retry; bei Pro-Tier kein Problem |
| Test-Suite bricht durch persona-Replace | Mittel | Phase-1-Tests die auf `voice_sample` referenzieren werden migriert auf `body_excerpt` |

## Wiki-Sync-Pflicht (Master-Plan-Konvention)

Bei Phase-9-Abschluss:
- Eintrag in `wiki/log.md`
- Wenn Architektur-Änderung relevant: `wiki/entities/living-vault.md`
  aktualisieren
- Phase-9-Abschluss: Session-Note unter
  `wiki/queries/YYYY-MM-DD-session-living-vault-phase-9.md`

## Wiedereinstieg (für künftige Claude-Sessions)

Wer in Phase 9 einsteigt, sollte zuerst:
1. Diese Spec lesen
2. `git log --grep="Phase-9"` für aktuellen Stand
3. `tests/test_persona*` als Erfolgs-Anker
4. Phase-9-Checkliste in `docs/PHASE-9-CHECKLIST.md` (sobald angelegt)
   für Status pro Akzeptanz-Item

## Commit-Konvention

Konsistent mit Master-Plan: `living-vault | Phase-9: {short-status}`.

Beispiele:
- `living-vault | Phase-9: db migration adds voice columns`
- `living-vault | Phase-9: stylometric extractor + tests`
- `living-vault | Phase-9: extract-voice cli with cost disclaimer`
- `living-vault | Phase-9: prompt template with three voice-block cases`

`git log --grep="Phase-9"` wird damit zum Handoff-Index.
