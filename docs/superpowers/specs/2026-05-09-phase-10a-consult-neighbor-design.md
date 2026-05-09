# Phase 10a — consult_neighbor (Pull-on-Demand-Tool)

**Datum:** 2026-05-09
**Status:** approved (User: "spec, spec, spec ;)")
**Phase:** Master-Plan Row 10 (Stufe 2 von 2 — Stufe 3 = Multi-Persona-Roundtable folgt als Phase 10b nach Sichtprüfung)
**Vorgänger-Spec:** [`2026-05-09-persona-schicht-3-design.md`](2026-05-09-persona-schicht-3-design.md)
**Master-Plan:** [`../../plans/2026-05-08-living-vault-master-plan.md`](../../plans/2026-05-08-living-vault-master-plan.md)
**Brainstorming-Quelle:** [`~/wiki/wiki/todos/2026-05-09-living-vault-phase-10-neighbor-talk.md`](file:///C:/Users/domes/wiki/wiki/todos/2026-05-09-living-vault-phase-10-neighbor-talk.md)

---

## 1. Ziel

Die Séance-Persona kann ihre **Nachbar-Pages aktiv konsultieren**, während sie auf eine User-Frage antwortet. Statt dass die Persona nur den statischen Neighbor-Titel-Block aus dem System-Prompt kennt, ruft sie über Anthropic-Tool-Use ein internes Tool `consult_neighbor(neighbor_path)` auf, fetcht den Body-Excerpt der Nachbar-Page, und integriert das Wissen in ihre Antwort.

Sichtbares Verhalten in der UI:

```
User: Wie hängt das mit a2a-Protokollen zusammen?

│  » consulted [[a2a-protokoll]] (1500 chars)
│  » consulted [[mcp-routing]] (1500 chars)

│█ self-evolving-mcp
│  Aus a2a-protokoll lese ich, dass Tool-Use ...
│  und mcp-routing zeigt weiter, dass ...
```

Phase 10a baut **nur Stufe 2** (Single-Persona + Pull-on-Demand). Phase 10b baut Stufe 3 (Multi-Persona-Roundtable) auf demselben `respond_with_tools`-Fundament.

## 2. User-getroffene Entscheidungen (nicht neu verhandeln)

Aus dem Brainstorming 2026-05-09:

1. **Tool-Calls werden persistiert als sichtbare Events.** Jeder `consult_neighbor`-Roundtrip wird als eigene Message in `seance_messages` gespeichert (role='tool_use'), erscheint in der UI als Mini-Bubble, ist im Session-Export sichtbar.
2. **Tool-Loop-Logik in der LLM-Klasse.** `core/llm.py` bekommt eine zweite Methode `respond_with_tools(system, history, tools, tool_handler, max_iterations) -> str` die den Multi-Turn-Loop intern führt. App-Layer ruft eine Methode auf.
3. **Cost-Caps mittel.** Soft-Cap 10 `consult_neighbor`-Calls pro User-Turn, Warnung in UI bei Annäherung an Limit. Kein Cost-Disclaimer beim Summon (Stufe 2 ist Single-Persona, billiger als extract-voice).
4. **Stufe 2 + 3 sequenziell**, nicht Big-Bang. Phase 10a (Stufe 2) durch Sichtprüfung, dann eigenes Spec/Plan-Cycle für Phase 10b.
5. **Mode-Toggle UI** (Multi-Select-Page-Liste + Modus-Dropdown) ist Phase-10b-Scope. Phase 10a ändert die UI nur minimal: Single-Page-Summon bleibt, Tool-Event-Mini-Bubbles kommen dazu.
6. **Inline-Notiz-UI für Tool-Calls** (Mini-Bubble mit `» consulted [[path]] (N chars)`).
7. **Schema-Erweiterung:** Neue nullable Spalte `persona_path` in `seance_messages`. Phase 10a setzt sie auf `session.page_path` für assistant + tool_use Messages, NULL für user. Phase 10b nutzt sie variabel (verschiedene Personas pro Session).

## 3. Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│ User-Turn (POST /api/say)                                        │
└──────────────────────────┬───────────────────────────────────────┘
                           ▼
        ┌────────────────────────────────────┐
        │ apps/seance_ui/app.py:say()         │
        │  • build system prompt (unchanged)  │
        │  • build neighbor allowlist (graph) │
        │  • call llm.respond_with_tools(...) │
        │  • collect tool_events from handler │
        │  • return {reply, tool_events}      │
        └──────────────────────────┬─────────┘
                                   ▼
        ┌────────────────────────────────────┐
        │ core/llm.py:AnthropicLLM           │
        │  .respond_with_tools(               │
        │    system, history,                 │
        │    tools=[consult_neighbor_def],    │
        │    tool_handler=callback,           │
        │    max_iterations=5)                │
        │                                     │
        │  Loop:                              │
        │    1. messages.create(tools=tools)  │
        │    2. if response.stop_reason ==    │
        │         "tool_use":                  │
        │         → call tool_handler(args)   │
        │         → append tool_result        │
        │         → continue                  │
        │       else: return final text       │
        │    3. on max_iterations: extra      │
        │       call without tools → final    │
        │       forced text                   │
        └──────────────────────────┬─────────┘
                                   ▼ (callback)
        ┌────────────────────────────────────┐
        │ apps/seance_ui/neighbors.py (NEW)  │
        │  consult_neighbor(                  │
        │    path: str,                       │
        │    allowlist: set[str],             │
        │    vault_root, db_path,             │
        │    session_id, persona_path)        │
        │   → check allowlist                 │
        │   → reader.read_page                │
        │   → store.add_tool_event(...)       │
        │   → return body_excerpt             │
        └────────────────────────────────────┘
```

### 3.1 Komponenten

| Komponente | Pfad | Verantwortung | Status |
|---|---|---|---|
| `LLM.respond_with_tools` | `core/llm.py` | Multi-Turn-Loop. Iteriert max_iterations Mal. Bei `tool_use` → `tool_handler` aufrufen, `tool_result` an History anhängen. Bei `end_turn` → finalen Text zurückgeben. | erweitert |
| `FakeLLMWithTools` | `core/llm.py` | Test-Variante. Nimmt ein `script: list[dict]` mit erwarteten Tool-Calls und finaler Text-Antwort. Determiniert Loop-Verhalten ohne API. | NEU |
| `consult_neighbor` | `apps/seance_ui/neighbors.py` | Tool-Handler-Callback. Validiert allowlist, fetcht Page-Body, persistiert Tool-Event, returned Excerpt. | NEU |
| `say()` Endpoint | `apps/seance_ui/app.py` | Orchestriert Tool-Use-Turn. Sammelt Tool-Events während des Loops, gibt sie in der Response mit zurück. | erweitert |
| `add_tool_event` | `apps/seance_ui/store.py` | Schreibt eine Message mit `role='tool_use'`, `persona_path` gesetzt, `content`=JSON-serialisiertes Tool-Result-Summary. | NEU |
| `get_history` | `apps/seance_ui/store.py` | Filtert Tool-Use-Messages aus dem LLM-Replay raus (gibt nur user + assistant final-text zurück). | erweitert |
| `get_session_detail` | `apps/seance_ui/store.py` | Liefert ALLE Messages inklusive Tool-Use für Export + UI. | unverändert (gibt schon alle) |
| Schema-Migration | `core/db.py` | `ALTER TABLE seance_messages ADD COLUMN persona_path TEXT` (idempotent). | erweitert |
| UI Mini-Bubbles | `apps/seance_ui/static/index.html` | Rendert Tool-Events als kompakte italic Bubbles vor der finalen Persona-Antwort. | erweitert |

### 3.2 Bewusste Asymmetrien

- **DB-Persistenz vs. LLM-Replay:** Tool-Use-Messages werden vollständig persistiert (für UI/Export), aber **nicht** ins History-Replay an Anthropic zurückgespielt. Begründung: doppelte Tool-Calls vermeiden, Token sparen. Persona "vergisst" zwischen Turns was sie consultiert hat — gewollt, weil der finale Antwort-Text die Information bereits enthält.
- **Soft-Cap als is_error, nicht Hard-Stop:** Ab dem 11. Tool-Call gibt der Handler `is_error=true, content="consultation budget exhausted"` zurück. Persona kann darauf reagieren ("ich habe genug gelesen, lass mich antworten") statt einen abrupten 5xx-Fehler zu provozieren.
- **`max_iterations`-Hard-Stop mit Forced-Final-Call:** Wenn die Loop nach 5 Iterations nicht zu `end_turn` kommt, macht `respond_with_tools` einen letzten `messages.create` ohne `tools=`. Anthropic kann dann nicht mehr Tool-Use produzieren und liefert garantiert Text. Verhindert Infinite-Loop ohne Antwort-Verlust.

## 4. Datenfluss (eine Turn-Lebensdauer)

### 4.1 Tool-Definition (Anthropic-API-Schema)

```json
{
  "name": "consult_neighbor",
  "description": "Read an excerpt of a neighbor wiki page that you (the persona) link to. Use this when you would like to consult what a neighbor knows before answering. You can call this multiple times in one turn but be selective.",
  "input_schema": {
    "type": "object",
    "properties": {
      "neighbor_path": {
        "type": "string",
        "description": "Relative path of the neighbor page (must be one of your own neighbors)"
      }
    },
    "required": ["neighbor_path"]
  }
}
```

### 4.2 Allowlist-Disziplin

Der Tool-Handler akzeptiert NUR `neighbor_path`-Werte, die im aktuellen `graph_neighbors(page_path)`-Set liegen. Sonst → `tool_result.is_error=true, content="not a neighbor of {page_path}"`. Verhindert Prompt-Injection (Persona kann nicht nach `/etc/passwd` fragen) und unkontrollierte Wiki-Spaziergänge.

### 4.3 Cost-Caps (User-Wahl: Mittel)

| Cap | Wert | Verhalten bei Überschreitung |
|---|---|---|
| `max_iterations` (Loop-Hard-Limit) | 5 | Letzter Call ohne `tools=` → forciert Text-Antwort |
| `MAX_CONSULT_CALLS_PER_TURN` (Soft-Budget) | 10 | Tool-Handler returned is_error mit Budget-Hinweis ab Call 11 |
| `BODY_EXCERPT_CHARS` | 1500 | Excerpt wird hart bei 1500 Chars abgeschnitten (Phase-9 nutzt 500 für initialen Anchor — hier mehr, weil consultation tieferes Lesen braucht) |
| Existierende Phase-9-Caps bleiben | — | `_MAX_USER_TEXT_CHARS=8000`, `_MAX_HISTORY_MESSAGES=50`, `_MAX_HISTORY_TOTAL_CHARS=32000` weiterhin aktiv |

UI-Warnung: Wenn in einem Turn bereits 7+ consult_neighbor-Calls gemacht wurden, zeigt die nächste Mini-Bubble einen orangefarbenen Hinweis "» nähere dich Budget (8/10)". Reine UI-Decoration, kein Backend-Cap-Wechsel.

### 4.4 Turn-Lebenszyklus

```
T+0   POST /api/say {session_id, text}
      → store.add_message(role='user', persona_path=NULL, content=text)

T+1   say() baut allowlist = graph_neighbors(page_path)
      → calls_made = 0 (ref-cell für tool_handler closure)
      → tool_events: list = []
      → ruft llm.respond_with_tools(system, history_filtered, tools, cb, 5)

T+2   AnthropicLLM Iteration 1:
      messages.create(...) → response.stop_reason='tool_use'
      response.content = [
        {type:'text', text:'Lass mich kurz nachschauen…'},
        {type:'tool_use', id:'tu_1', name:'consult_neighbor',
         input:{'neighbor_path':'concepts/a2a-protokoll.md'}}
      ]

T+3   tool_handler('consult_neighbor', {'neighbor_path':...}):
      → calls_made += 1
      → if calls_made > 10: return {is_error:true, content:'budget exhausted'}
      → check allowlist OK
      → reader.read_page(vault_root/'concepts/a2a-protokoll.md')
      → body_excerpt = body[:1500]
      → store.add_tool_event(session_id, persona_path,
           tool_name='consult_neighbor',
           tool_args={'neighbor_path':'concepts/a2a-protokoll.md'},
           tool_result_summary={'chars': len(body_excerpt),
                                 'title': 'A2A Protokoll'})
      → tool_events.append({...summary...})
      → return body_excerpt

T+4   AnthropicLLM Iteration 2:
      messages.create(history + assistant_with_tool_use + tool_result)
      → response.stop_reason='end_turn'
      → response.content = [{type:'text', text:'Aus a2a-protokoll lese ich…'}]
      → return final_text

T+5   say():
      → store.add_message(role='assistant', persona_path=session.page_path,
                          content=final_text)
      → return {reply: final_text, tool_events: tool_events}
```

### 4.5 History-Replay-Filter

```python
def get_history(db_path, session_id) -> list[tuple[str, str]]:
    # vor Phase 10a: alle Messages
    # ab Phase 10a: NUR user + assistant final-text
    rows = con.execute(
        "SELECT role, content FROM seance_messages "
        "WHERE session_id = ? AND role IN ('user', 'assistant') "
        "ORDER BY id",
        (session_id,)
    ).fetchall()
    return [(r['role'], r['content']) for r in rows]
```

`get_session_detail` (Export-Pfad) bleibt unverändert und liefert weiterhin alle Messages inklusive Tool-Use.

## 5. Schema-Migration

```sql
-- core/db.py:_ensure_schema() (idempotent, Phase-9-Pattern)
ALTER TABLE seance_messages ADD COLUMN persona_path TEXT;
```

Bestehende Rows haben NULL — bleibt kompatibel. Phase 10a setzt `persona_path` auf `session.page_path` für `role IN ('assistant', 'tool_use')`, NULL für `role='user'`.

Idempotenz wie in Phase 9: try/except auf den ALTER, bei "duplicate column" → ignoriert.

## 6. Error-Handling-Tabelle

| Fehlerquelle | Tool-Handler-Verhalten | UI-Sicht |
|---|---|---|
| `neighbor_path` nicht in allowlist | `is_error=true, content="not a neighbor of {page}"` | Mini-Bubble: `» refused: not a neighbor` |
| `neighbor_path` in graph aber Page-File gone | `is_error=true, content="page no longer exists"` | Mini-Bubble: `» consult failed: page gone` |
| `reader.read_page` wirft (kaputtes YAML, Permission) | `is_error=true, content="could not read page"` | Mini-Bubble: `» consult error` |
| Anthropic-API-Fehler im Loop (Rate-Limit, Network) | propagiert nach oben → HTTP 502 detail "llm_error" | Frontend zeigt Fehler-Banner |
| `max_iterations=5` ohne `end_turn` | Loop bricht ab, ein Forced-Final-Call ohne `tools=` | Antwort kommt mit Mini-Bubble `» (consultation budget exhausted)` |
| Soft-Cap 10 überschritten | weitere Calls bekommen `is_error` mit Budget-Hinweis | Mini-Bubble: `» consult budget reached` |
| LLM antwortet mit `tool_use` aber falsch geformter `input` (kein `neighbor_path`) | tool_handler validiert via Pydantic, `is_error="missing required field"` | Mini-Bubble: `» invalid tool call` |

Alle is_error-Fälle werden als Tool-Events persistiert (mit `tool_result_summary={'error': msg}`), Sessions bleiben reproduzierbar.

## 7. Testing

### 7.1 Test-Verteilung

| Datei | Was wird getestet | Tests |
|---|---|---|
| `tests/core/test_llm_tools.py` (NEU) | `respond_with_tools` Loop-Logik mit FakeLLMWithTools: kein Tool-Call → direkt Text. Ein Tool-Call → Loop läuft 2 Iterations. max_iterations Hard-Stop mit Forced-Final-Call. Soft-Cap budget exhaustion. is_error tool_result wird korrekt durchgereicht. Tool-Schema-Validation. Empty-script edge-case. | 8 |
| `tests/seance_ui/test_neighbors.py` (NEU) | `consult_neighbor`: allowlist-rejection, missing-page, reader-error, happy-path, body-excerpt-cap (1500 chars), tool_event in DB persistiert (mit tool_args, tool_result_summary), persona_path korrekt gesetzt. | 6 |
| `tests/seance_ui/test_say_with_tools.py` (NEU) | End-to-end via FastAPI TestClient: User-Turn → FakeLLMWithTools-Script simuliert Tool-Call → tool_events in Response, Messages in DB in richtiger Reihenfolge, UI-Response-Shape (`{reply, tool_events}`). Mehrere Tool-Calls in einem Turn. Soft-Cap end-to-end (Script forciert 11 Calls). | 5 |
| `tests/seance_ui/test_store.py` (erweitert) | `add_tool_event` schreibt korrekte Spalten. `get_history` filtert tool_use Messages aus dem LLM-Replay raus. `get_session_detail` liefert sie mit (Export-Reproduzierbarkeit). | 4 |
| `tests/core/test_db_migration.py` (erweitert) | `seance_messages.persona_path` wird via ALTER TABLE hinzugefügt, idempotent (zweimal aufrufen → kein Fehler). Bestehende Rows haben NULL nach Migration. | 2 |
| `tests/seance_ui/test_app.py` (erweitert) | Privacy-Regression bleibt grün nach Phase-10a-Code. Allowlist-Bypass-Versuch (Tool-Handler direkt mit fremdem Pfad) → is_error, niemals 500. | 2 |

**Summe: 27 neue Tests.** Total-Test-Count nach Phase 10a: ~145 (Phase 9 endete mit 118).

### 7.2 FakeLLMWithTools (Test-Strategie ohne API)

```python
class FakeLLMWithTools:
    """Deterministic tool-loop simulation for tests.

    script = [
      {'type': 'tool_use', 'name': 'consult_neighbor',
       'input': {'neighbor_path': 'concepts/x.md'}},
      {'type': 'tool_use', 'name': 'consult_neighbor',
       'input': {'neighbor_path': 'concepts/y.md'}},
      {'type': 'text', 'text': 'final answer'}
    ]
    """
    def __init__(self, script: list[dict]):
        self._script = list(script)
        self.tool_calls_made: list[dict] = []

    def respond(self, system, history):
        # Phase-9-compat: if script has only one text step, behave like FakeLLM
        if len(self._script) == 1 and self._script[0]['type'] == 'text':
            return self._script[0]['text']
        raise RuntimeError("FakeLLMWithTools requires respond_with_tools")

    def respond_with_tools(self, system, history, tools, tool_handler, max_iterations=5):
        for step in self._script:
            if step['type'] == 'tool_use':
                self.tool_calls_made.append(step)
                result = tool_handler(step['name'], step['input'])
                # tool_handler returns is_error dict or excerpt str — irrelevant for FakeLLM
                # in real Anthropic loop, this would feed back into next messages.create
            elif step['type'] == 'text':
                return step['text']
        return "(script exhausted)"
```

Damit sind alle Loop-Pfade testbar ohne API-Mock-Library. Der Test-Code definiert das Script, FakeLLMWithTools spielt es ab.

### 7.3 Live-DB-Smoke

Nach Implementierung: ein einziger echter Turn gegen `~/wiki/.vault-engine.db` mit echter Anthropic-API. Erwartung:

- Persona consultiert mind. einen Nachbarn (durch User-Frage gezielt provoziert: "Was sagt Nachbar X dazu?")
- Tool-Event ist in `seance_messages` mit `role='tool_use'` persistiert
- Antwort referenziert den Nachbarn inhaltlich (manuelle Sichtprüfung)

Phase-9-Ritual: Sichtprüfungs-Verdikt vom User wird im Master-Plan / Iteration-Log dokumentiert.

### 7.4 Privacy-Test-Erweiterung

Phase 10 darf die Phase-1-Privacy-Regression nicht brechen. `consult_neighbor` liest aus dem Wiki — das ist erlaubt, weil die Persona innerhalb der laufenden Séance-Session arbeitet, nicht in eine geteilte Ausgabe schreibt. Test absichert:

```python
def test_consult_neighbor_does_not_leak_to_portfolio_sync():
    # 1. start session on a private page
    # 2. tool_handler consults a private neighbor
    # 3. assert no public:true rows created in pages table
    # 4. assert portfolio-sync still sees only public:true (existing test still passes)
```

## 8. Acceptance-Kriterien

```
☐ Schema-Migration läuft idempotent gegen Live-DB (zweiter Lauf = no-op)
☐ FakeLLMWithTools-Variante funktioniert in allen 27 Tests
☐ Live-Smoke: User schreibt "Was sagt Nachbar X dazu?" → Persona ruft
   consult_neighbor → Antwort referenziert Inhalt aus X
☐ UI zeigt Mini-Bubbles "» consulted [[X]] (N chars)" vor finaler Antwort
☐ Soft-Cap 10 funktioniert: synthetischer Test forciert 11 Calls,
   11. Call wird is_error, Persona kann reagieren
☐ max_iterations=5 funktioniert: Test forciert Loop-Stuck → Forced-Final-Call
   liefert Text statt 500
☐ Allowlist hält: Test mit forciertem fremdem Pfad → is_error
☐ Privacy-Test bleibt grün: kein public-Leak nach Tool-Use-Turn
☐ Export einer Session enthält tool_use Messages mit Wikilink-Referenzen
☐ Performance: Single-Turn mit 2 Tool-Calls < 4 Sekunden lokal (gegen
   echte Anthropic-API, gegen lokale Wiki-DB)
☐ Existing Phase-1 + Phase-9 Tests bleiben alle grün (118 Tests)
☐ Code-Review bestanden (Verifier + optional Security)
☐ User-Sichtprüfung positiv ("Persona greift sinnvoll auf Nachbarn zu")
```

## 9. Was NICHT in Phase 10a

Bewusst ausgeschlossen, kommt in Phase 10b oder später:

- **Multi-Persona-Roundtable** — Phase 10b
- **Mode-Toggle UI** (Multi-Select Pages, Roundtable-Modus-Dropdown) — Phase 10b
- **Streaming der Antwort** — Phase 1 ist non-streaming, das bleibt
- **Tool-Use-Iterationen parallel** — sequenziell pro Turn ist robuster
- **Cache für consultierte Excerpts pro Session** — kommt wenn beobachtet wird, dass dieselbe Persona dieselbe Page in 3 Turns consultiert
- **Streaming der Mini-Bubbles während des Loops** — Frontend bekommt sie alle in einer Response. Wenn das schlechter UX ist als gedacht, kommt es in Phase 11
- **Cost-Disclaimer beim Summon** — Phase 10b führt das ein, weil Roundtable teurer ist

## 10. Aufwand-Schätzung

| Bereich | LOC | Files |
|---|---|---|
| `core/llm.py` Erweiterung (`respond_with_tools` + `FakeLLMWithTools`) | ~80 | 1 erweitert |
| `apps/seance_ui/neighbors.py` (NEU) | ~50 | 1 neu |
| `apps/seance_ui/app.py` say-Endpoint Anpassung | ~30 | 1 erweitert |
| `apps/seance_ui/store.py` (`add_tool_event`, `get_history`-Filter) | ~30 | 1 erweitert |
| `core/db.py` Schema-Migration | ~5 | 1 erweitert |
| `apps/seance_ui/static/index.html` Mini-Bubble-Rendering | ~50 | 1 erweitert |
| Tests (27 neu) | ~250 | 3 neu, 3 erweitert |
| **Summe** | **~495** | **5 erweitert, 4 neu** |

TODO-Schätzung war 250 LOC für Stufe 2. Mit Tests-Drauf landen wir bei ~495. Phase-9-Vergleich: ~9000 LOC inkl. Tests, Phase 10a wird ein kleinerer Sprint.

## 11. Übergang zu Implementation

Nach User-Review dieser Spec → `superpowers:writing-plans` Skill → `docs/superpowers/plans/2026-05-09-phase-10a-consult-neighbor.md` mit Task-Liste für `subagent-driven-development`.

Master-Plan-Tabelle ist bereits auf "Phase 10 = Nachbar-Gespräche, 🟡 in progress" gesetzt (commit pending).
