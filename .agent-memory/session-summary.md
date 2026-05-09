# Last Session — living-vault

*Datum: 2026-05-09*
*Agent: Claude Opus 4.7 (1M context)*
*Phasen: 10a (consult_neighbor) + 10b (Multi-Persona-Roundtable) inkl. Restschuld*

**Note:** Der Desktop-Handoff (`Desktop/.agent-memory/session-summary.md`) wurde
nach dieser Session von einem anderen Projekt (dome-dynamics) überschrieben.
Dieses lokale Summary ist die Quelle für living-vault-spezifischen State.

## Headline

**Master-Plan-Phasen 10a + 10b BEIDE komplett ✅ in einer Session,**
inkl. positiver User-Sichtprüfung für beide Phasen UND aller 3 Spec-Restschuld-
Items abgeräumt. 41 Commits, 25 Files, +7212/-52 Zeilen, Tests von 118 → 204
(+86 in einer Session).

## Was funktioniert jetzt

### Phase 10a — consult_neighbor (Pull-on-Demand-Tool)

Eine Single-Persona Séance kann jetzt mid-turn `consult_neighbor(neighbor_path)`
aufrufen — Anthropic-Tool-Use-Loop in `core/llm.py` (`respond_with_tools`),
Allowlist-disziplinierter Handler in `apps/seance_ui/neighbors.py`, UI-Mini-
Bubbles vor der finalen Antwort. Soft-Cap 10 Calls/Turn, max_iterations=5
Loop-Hard-Limit mit Forced-Final-Call-Fallback.

**Sichtprüfung positiv:** User-Verdikt "nice!!" nachdem Persona 5 Nachbarn
consultiert und Antwort inhaltlich anreichert ("Siemens Hannover Messe",
"irreversibel"-Pattern, etc.).

### Phase 10b — Multi-Persona-Roundtable (3 Modi)

Multi-Page-Summon mit Mode-Picker. Drei Modi:
- **roundrobin**: pro User-Turn rotiert genau eine Persona (A → B → C → A...)
- **moderator**: User schreibt `@persona-stem` → genau diese Persona antwortet,
  ohne Mention fällt es auf round-robin zurück
- **freeforall**: alle Personas antworten in seat_idx-Reihenfolge, jede sieht
  die Antworten der Vorredner via geteilter History (`[stem says]: text`-Wrapping)

Cross-Persona-Consult: Roundtable-Teilnehmer können sich gegenseitig via
`consult_neighbor` befragen (Allowlist erweitert um Teammates).
Hash-deterministische Persona-Colors (`sum(ord) % 8`) — Python und JS
mirroren sich.

**Sichtprüfung positiv:** User-Verdikt "geil, geil, supertoll" nach allen
3 Modi durchgespielt.

### Phase-10b Restschuld (alle 3 abgeräumt)

- **R1**: Prompt-Drift in `_TEAMMATE_BLOCK` (gefixt)
- **R2**: 502/partial_replies bei mid-loop-API-Fehler — try/except um den
  LLM-Call, HTTPException 502 mit `{partial_replies, tool_events,
  failed_persona, error}` (war Spec §6 vorgegeben, war im Plan vergessen)
- **R3**: Roundtable-aware Export — per-persona-stem-Labels statt `**Page**:`,
  tool_use als readable Italic-Lines `_» consulted [[X]] (N chars)_` statt
  raw JSON, `mode:` in Frontmatter

## Schema-Stand der Live-DB (`~/wiki/.vault-engine.db`)

Beide Phase-10-Migrationen idempotent gegen die Live-DB applied:
- `seance_messages.persona_path` (Phase 10a, nullable)
- `seance_sessions.mode` (Phase 10b, default `'single'`)
- `seance_session_personas` Tabelle (Phase 10b, M:N: session_id, persona_path,
  color, seat_idx, PK auf erste zwei)

Existierende seance-Sessions aus Phase-9-Sichtprüfung sind unangetastet,
bekommen `mode='single'` durch Default. 5 Phase-9-Voice-Distillations bleiben
in der DB. Die Phase-10a + 10b Sichtprüfungs-Sessions (mit echter Anthropic-
API) sind in der DB persistiert und können in der "past sessions"-UI
zurückgespielt werden — die Roundtable-aware Export-Funktion (R3) rendert
sie korrekt mit Persona-Labels.

## Wichtigste Code-Outputs

### Neue Files
- `living_vault/apps/seance_ui/neighbors.py` — consult_neighbor handler
- `living_vault/apps/seance_ui/roundtable.py` — pick_speakers, hash_color,
  shared_history_for_persona, _parse_mentions
- `tests/test_core_llm_tools.py`, `test_seance_neighbors.py`,
  `test_seance_say_with_tools.py`, `test_roundtable_speakers.py`,
  `test_roundtable_history.py`, `test_roundtable_app.py`

### Erweiterte Files
- `core/db.py` — 2 Schema-Migrationen
- `core/llm.py` — `respond_with_tools` + `FakeLLMWithTools`
- `apps/seance_ui/store.py` — 6 neue Funktionen
- `apps/seance_ui/app.py` — `summon` multi-page, `say` mode-branch,
  `roundtable_say` Orchestrator, 502/partial_replies, roundtable-aware Export
- `apps/seance_ui/prompt.py` — `neighbor_paths` (10a-hotfix) + `teammate_paths`
- `apps/seance_ui/static/index.html` — Mini-Bubbles + Multi-Select +
  Mode-Dropdown + Persona-Bubbles + `hashColorJs`

### Documentation
- `docs/superpowers/specs/2026-05-09-phase-10a-consult-neighbor-design.md`
- `docs/superpowers/plans/2026-05-09-phase-10a-consult-neighbor.md`
- `docs/superpowers/specs/2026-05-09-phase-10b-roundtable-design.md`
- `docs/superpowers/plans/2026-05-09-phase-10b-roundtable.md`
- `docs/PHASE-10A-CHECKLIST.md`, `docs/PHASE-10B-CHECKLIST.md`
- `docs/plans/2026-05-08-living-vault-master-plan.md` — Phase-Tabelle aktualisiert

## Methodik die wirkte

1. **Subagent-driven-development** mit fresh subagent + 2-stage-Review hält
   Phase-9-Effizienz auch bei 10a+10b. ~75% der Tasks bekamen Quality-Fixes,
   alle minor.
2. **Spec-Mängel via Sichtprüfung gefunden**: Phase 10a's "consult_neighbor
   scheitert weil LLM Pfade rät" war kein Bug, sondern ein Spec-Mangel.
   Code-Review hätte das nie gefunden. Sichtprüfungen sind ein qualitativ
   anderer Reviewer.
3. **Test-Verschärfung in Quality-Reviews findet echte Bugs**: `==N` statt
   `<=N` deckte einen Cap-Konflikt zwischen `max_iterations=5` (LLM-Loop) und
   `MAX_CONSULT_CALLS_PER_TURN=10` (Handler-Soft-Cap) auf.

Vollständige Iterations-Log mit allen Learnings: `.agent-memory/iterations/iteration-log.md`
(Iterations #2 + #3 dokumentieren diese Session).

## Codex-Review (vorgeschlagen, ausstehend)

Phase 10a + 10b zusammen = substantieller Diff (25 Files, +7212 Zeilen).
Lohnt:
- **Verifier**: Default. Plan/Spec gegen Diff prüfen.
- **Security**: Tool-Use-Loop mit Allowlist + neue HTTP-Endpoints + Path-
  Traversal-Vektoren (im Test geprüft, aber Codex schaut unabhängig).
- **Quality-Fixer**: Optional, niedriger Mehrwert (14 Quality-Tightening-
  Commits in der Session decken das schon ab).

## Offene Punkte / Carry-Over

### Hoch
- **Phase 11 = Synesthesia public subset + portfolio 3D-Embed** (originär
  geplant als Phase 10, durch User-Pick verschoben). Public-Curated-Subset
  auf cv.dynamic-dome.com mit Privacy-Regression-Tests. Großer Schritt.

### Mittel (Cross-Project, User-Wunsch für FRISCHE Session)
- **Dream-Team-Sprint** aus
  `~/wiki/wiki/synthesis/2026-05-09-claude-codex-self-evolving-dream-team.md`.
  User hat explizit gesagt: in einer frischen Session mit großem Context-Fenster.
  Cross-Repo, raus aus living-vault.

### Niedrig
- Phase-9 content_hash Cache-Invalidation (Wiki-TODO existiert)
- Codex-Security LOW + INFO Findings (Wiki-TODO existiert)

## Wiedereinstieg

1. `cd ~/Desktop/Claude-Projekte/living-vault && git log --oneline | head -45`
2. `cat docs/plans/2026-05-08-living-vault-master-plan.md` (10a + 10b ✅)
3. `cat docs/PHASE-10A-CHECKLIST.md` && `docs/PHASE-10B-CHECKLIST.md`
4. `cat .agent-memory/iterations/iteration-log.md` (Iter #2 + #3 für Details)
5. Wenn Dream-Team: `~/wiki/wiki/synthesis/2026-05-09-claude-codex-self-evolving-dream-team.md`
6. Wenn Phase 11: brainstorming-Skill mit `~/wiki/wiki/todos/2026-05-09-living-vault-phase-10-neighbor-talk.md`-Pattern als Template
