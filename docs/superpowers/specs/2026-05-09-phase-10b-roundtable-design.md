# Phase 10b — Multi-Persona-Roundtable

**Datum:** 2026-05-09
**Status:** approved (User: "spec schreiben")
**Phase:** Master-Plan Row 10b (Stufe 3 von 2 in der ursprünglichen Phase-10-Aufteilung — Stufe 2 = Phase 10a abgeschlossen am 2026-05-09)
**Vorgänger-Spec:** [`2026-05-09-phase-10a-consult-neighbor-design.md`](2026-05-09-phase-10a-consult-neighbor-design.md)
**Master-Plan:** [`../../plans/2026-05-08-living-vault-master-plan.md`](../../plans/2026-05-08-living-vault-master-plan.md)
**Brainstorming-Quelle:** [`~/wiki/wiki/todos/2026-05-09-living-vault-phase-10-neighbor-talk.md`](file:///C:/Users/domes/wiki/wiki/todos/2026-05-09-living-vault-phase-10-neighbor-talk.md)

---

## 1. Ziel

Der Séance-User kann eine **Gruppe von Wiki-Pages** summon (statt einer einzelnen) und mit ihnen als Roundtable interagieren. Drei Modi stehen zur Verfügung:

- **Round-Robin** — bei jeder User-Frage antwortet eine Persona, rotierend nach Sitzplatz
- **Moderator** — User adressiert mit `@persona-name` gezielt eine Persona; ohne Mention fällt das System auf Round-Robin zurück
- **Free-for-all** — alle Personas antworten zu jeder User-Frage, in Sitzplatz-Reihenfolge, jede sieht die Antworten der Vorredner als geteilte History

Sichtbares Verhalten in der UI:

```
User: Was haltet ihr von Phase 10?

│█ a2a-protokoll
│  Aus meiner Sicht ist Tool-Use ein
│  pragmatischer Trade-off zwischen
│  Komplexität und Reichweite ...

│█ self-evolving-mcp
│  Ich würde anders gewichten: das
│  Roundtable-Pattern hat seine eigene
│  Sprachoekonomie ...

│█ dream-team
│  Beide Vorredner unterschaetzen
│  die Migration ...
```

Phase 10b baut auf Phase 10a auf und wiederverwendet 80% der bestehenden Code-Pfade: dieselbe `respond_with_tools`-Loop pro Persona, dieselbe `consult_neighbor`-Allowlist-Disziplin, dieselbe Mini-Bubble-Renderung im UI. Neu ist die Modus-Logik im App-Layer und die Persona-Bubbles in der UI.

## 2. User-getroffene Entscheidungen (nicht neu verhandeln)

Aus dem Phase-10a-Brainstorming + Phase-10b-Brainstorming 2026-05-09:

1. **Stufe 3 baut alle drei Modi** (Round-Robin, Moderator, Free-for-all) — nicht nur einen.
2. **UI-Layout: sequentielle Bubbles mit Persona-Label & Color-Code.** Skaliert auf 1-8 Personas, mobile-tauglich.
3. **Mode-Toggle UX: Multi-Select Page-Liste + Modus-Dropdown.** 1 Page selektiert → Single-Mode automatisch; 2+ Pages → Modus-Dropdown erscheint.
4. **Cross-Persona-Consult erlaubt.** Im Roundtable kann jede Persona ihre eigenen Wiki-Nachbarn UND die anderen Roundtable-Teilnehmer consultieren. Allowlist pro Persona = `graph_neighbors(self) ∪ {andere Teilnehmer}`.
5. **Geteilte History.** Jede Persona sieht alles, was am Tisch gesagt wurde, in einem gemeinsamen Konversations-Stream. Wie ein echtes Gespräch, in dem alle einander zuhören.
6. **Sequenzielle Calls für Free-for-all** — nicht parallel. Persona-A → Persona-B → Persona-C, jede sieht die Antworten der Vorredner. Latenz ~3× Single-Turn, aber Personas können aufeinander reagieren.
7. **Hash-basierte deterministische Persona-Colors.** `color = palette[hash(persona_path) % len(palette)]`. Wiedererkennungswert über Sessions hinweg.
8. **Approach A — Symmetrische Architektur.** Roundtable ist ein Wrapper um N parallele Persona-States; wiederverwendet `make_consult_neighbor_handler`, `respond_with_tools`, `build_persona`, `build_system_prompt` aus Phase 10a unverändert.
9. **Cost-Caps mittel.** Max 8 Personas pro Roundtable; Cost-Disclaimer beim Summon nur in Free-for-all-Modus mit ≥3 Personas (Round-Robin und Moderator brauchen keinen, weil dort max 1 Persona pro Turn aktiv ist).
10. **Modus ist fix nach Summon.** Kein Mid-Session-Switch.

## 3. Architektur

```
┌──────────────────────────────────────────────────────────────────────┐
│ User picks N pages + mode in UI → POST /api/summon                   │
│   Body: {paths: [p1, p2, p3], mode: "freeforall"}                    │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
        ┌────────────────────────────────────┐
        │ apps/seance_ui/app.py:summon()      │
        │  • validate 1-8 paths               │
        │  • validate mode in 4-set            │
        │  • build_persona for each path      │
        │  • new_session(mode=mode,            │
        │      page_path=paths[0])             │
        │  • for each path: add_session_       │
        │      persona(session, path,          │
        │      color=hash_color(path),         │
        │      seat_idx=i)                      │
        └──────────────────────────┬─────────┘
                                   ▼
        ┌────────────────────────────────────┐
        │ POST /api/say (branches on mode)    │
        │                                     │
        │  if session.mode == 'single':      │
        │    → existing Phase-10a path        │
        │      (returns {reply, tool_events}) │
        │                                     │
        │  if session.mode in (roundrobin,   │
        │      moderator, freeforall):        │
        │    → roundtable_say()               │
        │      (returns {replies: [...],      │
        │       tool_events: [...]})          │
        └──────────────────────────┬─────────┘
                                   ▼
        ┌────────────────────────────────────┐
        │ apps/seance_ui/app.py:              │
        │   roundtable_say(req)               │
        │  • personas = get_session_personas  │
        │  • turn_idx = count_user_turns      │
        │  • speakers = pick_speakers(mode,   │
        │      user_text, personas, turn_idx) │
        │  • persist user_msg                 │
        │  • for each speaker:                │
        │      build per-speaker context      │
        │      respond_with_tools             │
        │      persist assistant_msg          │
        │      (with persona_path = speaker)  │
        │  • return shaped response           │
        └──────────────────────────┬─────────┘
                                   ▼
        ┌────────────────────────────────────┐
        │ apps/seance_ui/roundtable.py (NEW) │
        │  pick_speakers(mode, user_text,    │
        │                personas, turn_idx)  │
        │  • round-robin: rotates by turn-idx │
        │  • moderator: parses @-mention,     │
        │    falls back to round-robin        │
        │  • free-for-all: returns all        │
        │                                     │
        │  hash_color(persona_path) → hex     │
        │                                     │
        │  shared_history_for_persona(        │
        │    session_id, persona_path)        │
        │   → list[(role, text)] with         │
        │     "[other says]: ..." prefix on   │
        │     other personas' assistant rows  │
        └────────────────────────────────────┘
```

### 3.1 Komponenten

| Komponente | Pfad | Verantwortung | Status |
|---|---|---|---|
| `seance_sessions.mode` | `core/db.py` | Schema-Migration: `ALTER TABLE seance_sessions ADD COLUMN mode TEXT NOT NULL DEFAULT 'single'`. Werte: `single` / `roundrobin` / `moderator` / `freeforall`. Default sichert Backward-Compat. | erweitert |
| `seance_session_personas` Tabelle | `core/db.py` | M:N Mapping: `(session_id, persona_path, color, seat_idx)`. PK: `(session_id, persona_path)`. Index auf `session_id`. | NEU |
| `pick_speakers()` | `apps/seance_ui/roundtable.py` | Modus-Logik. Returnt geordnete Liste der Personas die diesen Turn antworten. | NEU |
| `_parse_mentions()` | `apps/seance_ui/roundtable.py` | Mention-Parser für Moderator-Modus: matched `@{stem}` case-insensitive, order-preserving, dedup. | NEU |
| `hash_color()` | `apps/seance_ui/roundtable.py` | `color = PALETTE[hash(persona_path) % len(PALETTE)]`. Deterministisch. PALETTE = 8 Cyberpunk-Farben (cyan, mint, lavender, peach, rose, gold, sage, sky). | NEU |
| `shared_history_for_persona()` | `apps/seance_ui/roundtable.py` | Baut die geteilte History für eine spezifische Persona auf. Eigene Antworten als `("assistant", text)`, fremde als `("user", f"[{stem} says]: {text}")`. | NEU |
| `roundtable_say()` | `apps/seance_ui/app.py` | Orchestriert die Sequenz: pick_speakers → for each → build_persona/system_prompt/handler/history → respond_with_tools → persist. | NEU |
| `say()` Branch | `apps/seance_ui/app.py` | Branch auf `session.mode`. `single` → existing path. Anderes → roundtable_say. | erweitert |
| `summon()` Endpoint | `apps/seance_ui/app.py` | Erweitert auf `paths: list[str], mode: str`. Validiert 1-8, validiert mode-set. Persistiert Personas mit hash_color + seat_idx. | erweitert |
| `add_session_persona()` | `apps/seance_ui/store.py` | INSERT in `seance_session_personas`. | NEU |
| `get_session_personas()` | `apps/seance_ui/store.py` | SELECT ordered by `seat_idx`. Returns `list[{path, color, seat_idx}]`. | NEU |
| `new_session()` | `apps/seance_ui/store.py` | Erweitert: `mode: str = "single"` keyword. INSERT inkl. mode-Spalte. | erweitert |
| `count_user_turns()` | `apps/seance_ui/store.py` | `SELECT COUNT(*) FROM seance_messages WHERE session_id=? AND role='user'`. Wird für `turn_idx` in pick_speakers verwendet. | NEU |
| `build_system_prompt()` | `apps/seance_ui/prompt.py` | Erweitert: neuer optionaler kw-arg `teammate_paths: list[str] | None = None`. Wenn gesetzt, fügt Mode-Block ein: "Du sitzt mit X, Y am Tisch — du kannst sie via consult_neighbor consultieren". | erweitert |
| UI Multi-Select + Mode-Dropdown | `apps/seance_ui/static/index.html` | Page-Picker mit Checkboxen, Modus-Dropdown wenn ≥2 selektiert, Cost-Disclaimer-Toast bei Free-for-all+≥3 Personas. | erweitert |
| UI Persona-Bubbles | `apps/seance_ui/static/index.html` | Bubbles mit `border-left: 3px solid {color}`, Persona-Label oben (stem), gerendert in seat_idx-Reihenfolge. | erweitert |

### 3.2 Reuse aus Phase 10a (unverändert)

- `core/llm.py:AnthropicLLM.respond_with_tools` — pro Persona unverändert aufgerufen
- `core/llm.py:FakeLLMWithTools` — wird für Roundtable-Tests N Mal mit eigenen Scripts instanziiert
- `apps/seance_ui/neighbors.py:make_consult_neighbor_handler` — Allowlist wird pro Persona erweitert um Teammates
- `apps/seance_ui/neighbors.py:CONSULT_NEIGHBOR_TOOL_DEF` — unverändert
- `apps/seance_ui/store.py:add_message`, `add_tool_event`, `get_history`, `get_session_detail` — unverändert (nutzt schon das `persona_path` Feld aus Phase 10a)
- `apps/seance_ui/prompt.py:_TEMPLATE` — bleibt; nur der `teammate_paths`-Pfad ergänzt einen weiteren Block

## 4. Datenfluss (Roundtable, Free-for-all-Modus mit 3 Personas)

### 4.1 Summon

```
POST /api/summon {paths: ["concepts/a.md", "concepts/b.md", "concepts/c.md"],
                  mode: "freeforall"}

→ validate len(paths) in 1..8                         → 400 if violated
→ validate mode in {single, roundrobin, moderator, freeforall}  → 400 if violated
→ validate each path exists in pages table             → 404 if any missing
→ if len(paths) == 1: mode is forced to "single"
→ session_id = store.new_session(page_path=paths[0], mode=mode)
→ for i, p in enumerate(paths):
    color = hash_color(p)
    store.add_session_persona(session_id, p, color, seat_idx=i)
→ return {session_id, personas: [{path, color, seat_idx}, ...], mode}
```

### 4.2 Free-for-all-Turn-Lebenszyklus

```
T+0   POST /api/say {session_id, text="Was haltet ihr von X?"}
      → store.add_message(role='user', persona_path=NULL, content=text)

T+1   personas = get_session_personas(session_id)
                  → [{A, color_A, 0}, {B, color_B, 1}, {C, color_C, 2}]
      turn_idx = count_user_turns(session_id) - 1   # 0-indexed
      speakers = pick_speakers(mode='freeforall', user_text=text,
                                personas=personas, turn_idx=0)
                  → [A, B, C]   (alle, in seat_idx-Reihenfolge)

T+2   For speaker A:
      neighbors_A = graph_neighbors(A.path)
      teammate_paths = [B.path, C.path]
      allowlist = set(neighbors_A) | set(teammate_paths)
      raw_handler = make_consult_neighbor_handler(
          vault_root=, db_path=, session_id=, persona_path=A.path,
          allowlist=allowlist)
      persona_data = build_persona(vault_root, db_path, A.path)
      system = build_system_prompt(persona_data,
          neighbor_titles=[Path(n).stem for n in neighbors_A],
          neighbor_paths=list(neighbors_A),
          teammate_paths=teammate_paths)
      history = shared_history_for_persona(session_id, A.path)
      reply_A = llm.respond_with_tools(system, history, tools, handler, max_iter=5)
      store.add_message(role='assistant', persona_path=A.path, content=reply_A)
      tool_events.extend(handler-captured events)

T+3   For speaker B:
      teammate_paths = [A.path, C.path]
      allowlist = set(graph_neighbors(B.path)) | {A.path, C.path}
      ... build_persona/system_prompt for B
      history = shared_history_for_persona(session_id, B.path)
        → contains [("user", "Was haltet ihr von X?"),
                    ("user", "[A says]: " + reply_A)]
        → because reply_A was just persisted with persona_path=A.path,
          shared_history_for_persona wraps it as labeled-user from B's view
      reply_B = llm.respond_with_tools(...)
      persist with persona_path=B.path

T+4   For speaker C: analog. History includes both A's and B's replies.

T+5   Return {
        replies: [
          {persona_path: A.path, text: reply_A, color: color_A, seat_idx: 0},
          {persona_path: B.path, text: reply_B, color: color_B, seat_idx: 1},
          {persona_path: C.path, text: reply_C, color: color_C, seat_idx: 2},
        ],
        tool_events: [...],   # all tool_events from all 3 personas, in order
      }
```

### 4.3 Round-Robin-Modus

Wie 4.2, aber `pick_speakers` returned nur `[personas[turn_idx % len(personas)]]`. D.h. **eine Persona pro User-Turn**, rotierend.

```
turn_idx=0 → speakers = [A]    → reply 1: A spricht
turn_idx=1 → speakers = [B]    → reply 2: B spricht (sieht User-Turn 0+1 + A's reply)
turn_idx=2 → speakers = [C]
turn_idx=3 → speakers = [A]    (wrap-around)
```

### 4.4 Moderator-Modus

```python
def pick_speakers(*, mode='moderator', user_text, personas, turn_idx):
    mentioned = _parse_mentions(user_text, personas)
    if mentioned:
        return mentioned
    return [personas[turn_idx % len(personas)]]   # round-robin fallback
```

`_parse_mentions` findet alle `@{stem}` Vorkommen in `user_text` und matched gegen `personas[*].path`'s stem (case-insensitive, order-preserving, dedup).

Beispiel:
- `@a2a-protokoll, was sagst du?` → `[A]` (wenn A.path stem `a2a-protokoll`)
- `@A und @B sollten einig sein` → `[A, B]` (Reihenfolge der ersten Mentions)
- `was meint ihr?` → `[personas[turn_idx % N]]` (Fallback)
- `@unknown-persona` → kein match → Fallback

### 4.5 Geteilte History — Rendering pro Persona

Anthropic-API kennt nur `user` und `assistant` Roles. Wir simulieren "third party persona" durch Umverpackung:

```python
def shared_history_for_persona(session_id, persona_path) -> list[tuple[str, str]]:
    """Return history from this persona's view.

    - user messages → ("user", text) unverändert
    - assistant messages with persona_path == this persona → ("assistant", text)
    - assistant messages with other persona_path → ("user", f"[{other_stem} says]: {text}")

    tool_use rows are filtered out (Phase-10a asymmetry preserved).
    """
    rows = SELECT role, content, persona_path FROM seance_messages
           WHERE session_id = ? AND role IN ('user', 'assistant')
           ORDER BY id
    out = []
    for row in rows:
        if row.role == 'user':
            out.append(('user', row.content))
        elif row.persona_path == persona_path:
            out.append(('assistant', row.content))
        else:
            other_stem = Path(row.persona_path).stem
            out.append(('user', f"[{other_stem} says]: {row.content}"))
    return out
```

Begründung: Anthropic-API erlaubt nur die zwei Roles. Indem wir fremde Persona-Antworten als labeled `user` umverpacken, kann Persona-A die Beiträge der Mitstreiter als externen Stimulus lesen. Die Phase-9-`_cap_history`-Logik bleibt unverändert, sie wirkt auf der umverpackten Liste.

### 4.6 Cost-Caps

| Cap | Wert | Verhalten bei Überschreitung |
|---|---|---|
| `MAX_PERSONAS_PER_ROUNDTABLE` | 8 | Summon-Endpoint rejected mit HTTP 413 |
| `_MAX_HISTORY_TOTAL_CHARS` | 32_000 | bleibt **global** geteilt; oldest history-rows werden gedropt (existierender `_cap_history` Mechanismus) |
| `MAX_CONSULT_CALLS_PER_TURN` | 10 | unverändert pro Persona pro User-Turn |
| `max_iterations` | 5 | unverändert pro Persona pro User-Turn |
| Free-for-all-Effective-Cost | N × Single-Turn | warning Toast in UI bei Summon mit ≥3 Personas + Free-for-all |

### 4.7 Persona-Color-Palette

```python
_PALETTE = [
    "#7adfd5",   # cyan
    "#a8e6cf",   # mint
    "#c9b3ff",   # lavender
    "#ffd3a5",   # peach
    "#fda4af",   # rose
    "#fde68a",   # gold
    "#bbf7d0",   # sage
    "#a5d8ff",   # sky
]

def hash_color(persona_path: str) -> str:
    """Deterministic color from path. Same path always gets same color."""
    h = sum(ord(c) for c in persona_path)   # cheap, deterministic, no hash-randomization
    return _PALETTE[h % len(_PALETTE)]
```

**Wichtig:** Python's built-in `hash()` ist hash-randomized seit 3.3. Wir nutzen `sum(ord(c))` als deterministischen, prozess-übergreifend stabilen Ersatz. Genug Varianz für 8-bin-modulo, billig zu berechnen.

## 5. Schema-Migration

```python
# core/db.py — nach Phase-10a-Block
_PHASE_10B_SEANCE_SESSIONS_COLUMNS = [
    ("mode", "TEXT NOT NULL DEFAULT 'single'"),
]

_PHASE_10B_NEW_TABLES = """
CREATE TABLE IF NOT EXISTS seance_session_personas (
    session_id   INTEGER NOT NULL REFERENCES seance_sessions(id),
    persona_path TEXT NOT NULL,
    color        TEXT NOT NULL,
    seat_idx     INTEGER NOT NULL,
    PRIMARY KEY (session_id, persona_path)
);
CREATE INDEX IF NOT EXISTS idx_ssp_session ON seance_session_personas(session_id);
"""

# In initialize() nach Phase-10a-Block:
con.executescript(_PHASE_10B_NEW_TABLES)
for col, sqltype in _PHASE_10B_SEANCE_SESSIONS_COLUMNS:
    if not _column_exists(con, "seance_sessions", col):
        con.execute(f"ALTER TABLE seance_sessions ADD COLUMN {col} {sqltype}")
```

Idempotenz: `CREATE TABLE IF NOT EXISTS` ist von Natur aus idempotent. `ALTER TABLE ADD COLUMN` ist durch `_column_exists` geschützt. Existing single-mode-Sessions behalten `mode='single'` durch DEFAULT.

## 6. Error-Handling-Tabelle

| Fehlerquelle | Verhalten | UI-Sicht |
|---|---|---|
| Summon mit 0 paths | HTTP 400 "at least one page required" | Toast |
| Summon mit > 8 paths | HTTP 413 "max 8 personas per roundtable" | Toast |
| Summon mit duplicate paths | dedup silently, return one entry | (transparent) |
| Summon mit unknown mode | HTTP 400 "unknown mode" | Toast |
| Summon mit nicht-existenter Page | HTTP 404 "page not found: X" | Toast |
| Moderator-Modus ohne `@`-Mention | Round-Robin-Fallback (eine Persona nach `turn_idx`) | UI rendert eine Bubble |
| Moderator-Modus mit `@unknown-name` | Treat as no-mention → round-robin fallback | UI rendert eine Bubble |
| Persona im Roundtable: build_persona returns None (page gone since summon) | Skip diese Persona, log entry in tool_events als `{tool_name: "persona_skipped", persona_path, error: "page gone"}`; andere antworten weiter | UI rendert N-1 Bubbles plus eine Error-Bubble |
| Anthropic-API-Fehler bei Persona K von N | Stop loop nach Persona K, persist die (K-1) bereits erfolgreichen Antworten, return 502 mit `{partial_replies: [...], error: ...}` | Frontend zeigt was kam + Fehler-Banner |
| Schema-Migration Konflikt | `_column_exists` + `IF NOT EXISTS` schützen gegen alle Re-Runs | (silent recovery) |
| Mid-Session Mode-Switch | Nicht erlaubt. Mode bleibt fix nach Summon. Kein PATCH-Endpoint. | n/a |

**Globale Disziplin:** Eine fehlerhafte Persona darf den Roundtable nicht killen. Wenn 3 Personas am Tisch und Persona-B's `build_persona` schlägt fehl, antworten A und C trotzdem.

## 7. Testing

### 7.1 Test-Verteilung

| Datei | Was wird getestet | Tests |
|---|---|---|
| `tests/test_db_migration.py` (erweitert) | `seance_sessions.mode` column added idempotent. `seance_session_personas` table created with PRIMARY KEY + index. Bestehende Sessions bekommen `mode='single'` als Default. Twice-call no-op. | 3 |
| `tests/test_roundtable_speakers.py` (NEU) | `pick_speakers` für alle 3 Modi: Round-Robin rotates by turn_idx (0→A, 1→B, 2→C, 3→A), Moderator with @-mention picks named personas, Moderator without mention falls back to round-robin, Free-for-all returns all in seat_idx order, Mention-parser case-insensitive, multiple mentions order-preserving + dedup, Unknown mention treated as no-mention. Plus `hash_color` determinism (same path → same color across calls). | 9 |
| `tests/test_seance_store.py` (erweitert) | New `add_session_persona(session_id, persona_path, color, seat_idx)`. Updated `new_session(mode=...)` accepts `mode` keyword and persists it. New `get_session_personas(session_id)` returns ordered by seat_idx. New `count_user_turns(session_id)` counts user-role messages. | 4 |
| `tests/test_roundtable_history.py` (NEU) | `shared_history_for_persona`: own assistant rows stay as ('assistant', ...), others get wrapped as ('user', '[stem says]: ...'). User rows pass through. tool_use rows filtered out. Empty history. Multiple speakers across multiple turns produce correct interleaved view per persona. | 5 |
| `tests/test_roundtable_app.py` (NEU) | End-to-end via FastAPI TestClient: Summon with mode='roundrobin' creates session_personas rows. Multi-page summon validates 1-8. `say()` branches on session.mode (single → existing path, roundtable → roundtable_say). Round-robin alternates A→B→C across 3 user-turns. Moderator @-mention picks the right persona. Free-for-all all 3 personas reply with FakeLLMWithTools, in seat_idx order. Cross-Persona consult: A can call consult_neighbor on B's path. Skip-broken-persona: build_persona returns None for one of three → other two reply, third gets persona_skipped tool_event. | 10 |
| `tests/test_seance_app.py` (erweitert) | Existing 'mode=single' tests still pass after the branch in say(). Summon without `paths` parameter or with single path behaves like Phase-10a single-mode. Backward-compat for legacy summon shape. | 3 |
| `tests/test_seance_prompt.py` (erweitert) | `build_system_prompt` accepts `teammate_paths` kw-arg. Mode-block "Du sitzt mit X, Y am Tisch" appears in prompt. Empty teammate_paths → no mode-block (single-persona behavior). | 3 |
| **Summe Phase 10b** | | **37** |

Plan-Schätzung war 34; mit detail-tightening Tests landen wir typischerweise höher (vgl. Phase 10a: Plan 27 → ist 38).

### 7.2 FakeLLMWithTools Iteration Pattern für Roundtable-Tests

```python
fake_a = FakeLLMWithTools([{"type": "text", "text": "I am A"}])
fake_b = FakeLLMWithTools([{"type": "text", "text": "I am B"}])
fake_c = FakeLLMWithTools([{"type": "text", "text": "I am C"}])

fakes_iter = iter([fake_a, fake_b, fake_c])
monkeypatch.setattr(app_mod, "get_llm", lambda: next(fakes_iter))
```

`get_llm()` wird in `roundtable_say()` pro Persona einmal aufgerufen. Jede Persona bekommt ihre eigene Fake-Instanz und kann mit eigenem Script ausgestattet werden — das ermöglicht später (Phase 12+) heterogene Modelle pro Persona.

### 7.3 Live-DB-Smoke

Nach Implementierung manuelle Sichtprüfung im Browser, drei Szenarien:

1. **Round-Robin:** Summon mit 3 Pages, mode='roundrobin'. 3 User-Fragen hintereinander. Erwartung: Personen rotieren A→B→C, jede sieht die Vorgänger.

2. **Moderator:** Summon mit 3 Pages, mode='moderator'. User schreibt erst "was meint ihr alle?" (round-robin-Fallback), dann "@a2a-protokoll, was meinst du?" (gezielt A). Erwartung: erste Frage löst nur eine Bubble aus, zweite Frage genau A.

3. **Free-for-all:** Summon mit 3 Pages, mode='freeforall'. Eine User-Frage. Erwartung: 3 Bubbles in seat_idx-Reihenfolge, B/C reagieren auf A's Antwort, alle haben unterschiedliche Color-Codes.

User-Sichtprüfungs-Verdikt wird im Master-Plan / Iteration-Log dokumentiert wie bei Phase 10a.

## 8. Acceptance-Kriterien

```
☐ Schema-Migration (mode + seance_session_personas) idempotent gegen Live-DB
☐ pick_speakers für alle 3 Modi mit allen 9 Tests grün
☐ FakeLLMWithTools-Iteration pattern works for N-persona scripts
☐ Round-Robin-Live-Smoke: 3 User-Fragen rotieren A→B→C
☐ Moderator-Live-Smoke: @-Mention funktioniert, Fallback auf round-robin
☐ Free-for-all-Live-Smoke: 3 Personas reagieren aufeinander, geteilte History
☐ Cost-Disclaimer beim Summon mit ≥3 Personas in Free-for-all
☐ Cross-Persona-Consult: Persona-A ruft consult_neighbor("persona-b.md")
☐ Geteilte History: Persona-B sieht "[A says]: ..." Prefix
☐ Persona-Bubbles in UI mit deterministischer Color, Persona-Label
☐ Skip-broken-persona: 1 von 3 fehlt, andere antworten weiter
☐ Existing Phase-10a single-mode tests bleiben alle grün
☐ User-Sichtprüfung positiv für alle 3 Modi
```

## 9. Was NICHT in Phase 10b

Bewusst ausgeschlossen, kommt in späterer Phase oder gar nicht:

- **Persona-Streaming** — alle Antworten kommen synchron in einer Response
- **WebSocket-Updates** — non-streaming
- **Mid-Session-Mode-Switch** — Modus ist fix nach Summon
- **N>8 Personas** — Hard-Cap
- **Dynamic teammate-add/remove** — Roundtable-Cast ist fix nach Summon
- **Persona-vs-Persona-Direct-Reply** — wird durch geteilte History implizit erreicht
- **Persona-eigene Modelle** (Persona-A nutzt Opus, Persona-B nutzt Haiku) — `get_llm()` wird pro Persona neu aufgerufen, was das später ermöglicht, aber Phase 10b nutzt überall denselben Default
- **Export-Polish für Roundtable** — der existing `_format_session_markdown` rendert tool_use als raw JSON; das ist Phase-11/12-Kandidat, nicht 10b

## 10. Aufwand-Schätzung

| Bereich | LOC | Files |
|---|---|---|
| `core/db.py` Schema-Migration + new table | ~25 | 1 erweitert |
| `apps/seance_ui/store.py` neue Funktionen (add_session_persona, get_session_personas, count_user_turns, new_session+mode) | ~60 | 1 erweitert |
| `apps/seance_ui/roundtable.py` (NEU) — pick_speakers + _parse_mentions + hash_color + shared_history_for_persona | ~150 | 1 neu |
| `apps/seance_ui/app.py` summon-Erweiterung + say()-Branch + roundtable_say() | ~150 | 1 erweitert |
| `apps/seance_ui/prompt.py` teammate_paths + mode-block | ~30 | 1 erweitert |
| `apps/seance_ui/static/index.html` Multi-Select + Dropdown + Persona-Bubbles + Color-Code | ~200 | 1 erweitert |
| Tests (37 neu, ~600 LOC) | ~600 | 5 erweitert, 2 neu |
| **Summe** | **~1215** | **6 erweitert, 2 neu** |

Phase-10a war ~570 LOC. Phase-10b ist ~2× größer wegen UI-Komplexität (Multi-Select + Color-Coded Bubbles) und der 3 Modus-Varianten.

## 11. Übergang zu Implementation

Nach User-Review dieser Spec → `superpowers:writing-plans` Skill → `docs/superpowers/plans/2026-05-09-phase-10b-roundtable.md` mit Task-Liste für `subagent-driven-development`.

Master-Plan-Tabelle ist bereits auf "Phase 10b 🟡 in Arbeit" gesetzt (Commit `f68cd70`).
