# Phase 10b — Multi-Persona-Roundtable Acceptance Checklist

Per spec: [`docs/superpowers/specs/2026-05-09-phase-10b-roundtable-design.md`](superpowers/specs/2026-05-09-phase-10b-roundtable-design.md)
Per plan: [`docs/superpowers/plans/2026-05-09-phase-10b-roundtable.md`](superpowers/plans/2026-05-09-phase-10b-roundtable.md)

## Automated Acceptance

- [x] Schema-Migration is idempotent against the live DB — verified 2026-05-09:
  ```
  python -c "from living_vault.core import db; from pathlib import Path; db.initialize(Path.home() / 'wiki' / '.vault-engine.db')"
  ```
  Run twice — both succeed; `mode` column appears on `seance_sessions`, `seance_session_personas` table exists.
- [x] pick_speakers tests green: 11 tests in `test_roundtable_speakers.py` (9 plan + 2 quality-fix tests for email-bypass)
- [x] shared_history_for_persona tests green: 5 tests in `test_roundtable_history.py`
- [x] Roundtable end-to-end tests green: 10 tests in `test_roundtable_app.py`
- [x] Phase-10a single-mode tests still green: existing test_seance_app.py + test_seance_say_with_tools.py + test_seance_neighbors.py + test_core_llm_tools.py
- [x] Full suite: `.venv/Scripts/python.exe -m pytest tests/ -v` reports **200 passed, 0 failed** (was 156 at end of Phase 10a; +44 tests for Phase 10b)

## Test Count Evolution

| Phase | Tests added | Total |
|---|---|---|
| Phase 10a closed | — | 156 |
| Task 1: schema migration | +3 | 159 |
| Task 2: store extensions (incl. quality-fix get_session_mode test) | +5 | 164 |
| Task 3: roundtable.py speakers (incl. quality-fix email-guard tests) | +11 | 175 |
| Task 4: shared_history_for_persona | +5 | 180 |
| Task 5: build_system_prompt teammate_paths | +3 | 183 |
| Task 6: summon endpoint (incl. quality-fix coercion + empty-paths tests) | +7 | 190 |
| Task 7: roundtable_say + e2e | +10 | 200 |
| Task 8: UI (no automated tests) | 0 | 200 |
| Task 9: smoke (no automated tests) | 0 | 200 |
| **Phase 10b final** | **+44** | **200** |

(Plan estimated 37 new tests; we landed at 44 because quality reviews added detail-tightening tests in Tasks 2, 3, and 6.)

## Live-DB Smoke (manual, requires real Anthropic API key)

Three scenarios, all in browser at `http://127.0.0.1:7777`:

### Setup
```bash
$env:ANTHROPIC_API_KEY = "sk-ant-..."  # if not already set
$env:LIVING_VAULT_ROOT = "C:/Users/domes/wiki/wiki"
.venv/Scripts/python.exe -m living_vault.apps.seance_ui.app
```

### Scenario 1: Round-Robin (3 turns)
- [ ] Pick 3 pages with multi-select (single-click 3 different pages from list)
- [ ] Mode-Dropdown shows up; select "round-robin"
- [ ] Click "summon roundtable"
- [ ] Header shows "roundrobin session with 3 personas"
- [ ] Ask 3 questions in a row
- [ ] Verify: turn 1 → persona A answers; turn 2 → persona B; turn 3 → persona C
- [ ] Each bubble has a different color, label shows the persona name

### Scenario 2: Moderator (with @-mention)
- [ ] Pick 2 pages
- [ ] Mode-Dropdown: select "moderator (@-mention)"
- [ ] Summon
- [ ] Ask "@persona-x, was meinst du?" — only that persona answers
- [ ] Ask without @-mention — round-robin fallback (1 persona answers)

### Scenario 3: Free-for-all
- [ ] Pick 3 pages
- [ ] Mode-Dropdown: select "free-for-all"
- [ ] Click summon — confirm dialog appears: "Free-for-all with 3 personas: ~3× token cost per turn"
- [ ] Confirm, then ask one question
- [ ] All 3 personas reply, each with own color
- [ ] Verify: persona B and C reference what A said (shared history works via [stem says] wrapping)
- [ ] Optional: have one persona @-mention call consult_neighbor on a teammate (mini-bubble appears)

### Backward-Compat: Single-Mode (Phase-10a)
- [ ] Double-click a single page in the list — legacy single-summon path triggers
- [ ] Header shows the single page name + era marker (Phase-10a behavior)
- [ ] Ask a question — get exactly ONE reply (not a `replies` array)
- [ ] Phase-10a tests still pass (regression check)

## Performance

- [ ] 3-persona free-for-all turn end-to-end: subjectively ≤ 30s against real Anthropic API.

## Notes

- **Persona color determinism:** colors are computed via `hash_color` in Python (summon time) and mirrored in JS (`hashColorJs` for past-session replays). Same path → same color across sessions, machines, processes. PALETTE + hash algorithm MUST match between Python and JS — comment in `roundtable.py:hash_color` flags this.
- **`max_iterations=5` per persona:** each persona's tool-use loop is independently capped, so even in free-for-all-mode no single persona can burn unlimited tool calls.
- **Geteilte History via labeled-user wrap:** Anthropic API only knows user/assistant roles. Other personas' replies are surfaced to a speaker as `("user", "[stem says]: text")` so they're readable as external context.
- **Teammate vs Neighbor allowlist:** in roundtable mode, each speaker's `consult_neighbor` allowlist is `graph_neighbors ∪ teammate_paths`. Teammates can be consulted even if they aren't wiki-graph-neighbors. This matches the spec (§4 "Cross-Persona-Consult").

## Phase-10b Status: ✅ CODE-COMPLETE 2026-05-09 (awaiting Sichtprüfung)

All automated acceptance criteria met, schema migration verified idempotent against live DB. Live-Sichtprüfung steht aus (3 Scenarios + Backward-Compat-Check). 200 Tests grün. 17 Commits gesamt für Phase 10b (`a1a740c` → `93019e0` mit Task 9 noch offen).
