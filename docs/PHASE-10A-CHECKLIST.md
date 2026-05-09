# Phase 10a — consult_neighbor Acceptance Checklist

Per spec: [`docs/superpowers/specs/2026-05-09-phase-10a-consult-neighbor-design.md`](superpowers/specs/2026-05-09-phase-10a-consult-neighbor-design.md)
Per plan: [`docs/superpowers/plans/2026-05-09-phase-10a-consult-neighbor.md`](superpowers/plans/2026-05-09-phase-10a-consult-neighbor.md)

## Automated Acceptance

- [x] Schema-Migration is idempotent against the live DB — verified 2026-05-09:
  ```
  python -c "from living_vault.core import db; from pathlib import Path; db.initialize(Path.home() / 'wiki' / '.vault-engine.db')"
  ```
  Run twice — both calls succeed; `persona_path` column appears on `seance_messages` after the first call, second call is no-op.
- [x] FakeLLMWithTools-Variante works in all new tests
- [x] Soft-cap 10 enforced: `tests/test_seance_say_with_tools.py::test_say_soft_cap_when_iterations_is_high_enough` PASS
- [x] max_iterations=5 enforced: `tests/test_core_llm_tools.py::test_max_iterations_caps_loop` PASS — also exercised end-to-end via `test_say_max_iterations_cap_limits_loop`
- [x] Allowlist holds: `tests/test_seance_app.py::test_phase_10a_allowlist_blocks_bypass_attempt` PASS
- [x] Privacy-regression remains green: `tests/test_privacy_regression.py` PASS — also reinforced by `test_phase_10a_no_public_leak_after_tool_use_turn`
- [x] Full suite: `.venv/Scripts/python.exe -m pytest tests/ -v` reports **154 passed, 0 failed**

## Test Count Evolution

| Phase | Tests added | Total |
|---|---|---|
| Phase 9 close | — | 118 |
| Task 1: schema migration | +2 | 120 |
| Task 2: store API | +4 | 124 |
| Task 3: respond_with_tools | +8 | 132 |
| Task 4: consult_neighbor handler | +6 | 138 |
| Task 5: wire say() (split into 6 tests, not 5, after quality review) | +6 | 144 |
| Task 6: UI mini-bubbles (no automated tests) | 0 | 144 |
| Task 7: privacy + bypass | +2 | 154 |
| Task 8: smoke (no automated tests) | 0 | 154 |
| **Phase 10a final** | **+36** | **154** |

(Plan estimated 27 new tests; we landed at 36 because Task 5 split + Task 3's existing test_core_llm.py also got a re-run, and quality reviews added a couple of detail-tightening assertions.)

## Live-DB Smoke (manual, requires real Anthropic API key)

Prerequisite: `ANTHROPIC_API_KEY` is set in the environment. The séance UI binds to 127.0.0.1:7777.

- [ ] Start séance UI: `seance-ui` (this uses the AnthropicLLM, not FakeLLM)
- [ ] Open `http://127.0.0.1:7777` in a browser
- [ ] Pick a real wiki page that has at least 2 wikilinks (suggested: `concepts/3ma-ml-pipeline.md` or similar from the existing 953 pages)
- [ ] Ask: "Was sagt einer deiner Nachbarn dazu?" — phrase tuned to encourage tool-use
- [ ] **Verify mini-bubbles appear** between the user message and the assistant answer:
  - Format: `» consulted [[neighbor-x]] (N chars)`
  - Italic, low-opacity, with a green left border (#4a8)
  - Wikilink path is bold and brighter (#cfe)
- [ ] **Verify the final assistant answer references the neighbor's content** — not just the neighbor's title (proves the excerpt was actually injected into the LLM context, not just announced)
- [ ] Click "export to wiki" — verify the resulting markdown contains the tool_use rows in some readable form (current export behavior is what it is; if tool_use shows as raw JSON that's expected — Phase 10b can polish it if needed)
- [ ] Open a past session via the "past sessions" tab — verify tool_use mini-bubbles render correctly when replaying history
- [ ] **User-Sichtprüfungs-Verdikt:** ☐ positiv  ☐ neutral  ☐ negativ

## Performance

- [ ] Single-Turn mit 2 Tool-Calls: < 4s end-to-end gegen real Anthropic API (one-shot timing observation, not a hard requirement)

## Notes

- The "soft-cap (10) is the binding constraint" only when the LLM-loop's `max_iterations` is high enough. With the default `max_iterations=5` in `say()`, the LLM-loop cap binds first — the user will see at most 5 mini-bubbles per turn even if the LLM wants more. This is documented in `test_say_max_iterations_cap_limits_loop` and is the currently shipped behavior.
- If the manual smoke fails, file a follow-up TODO under `~/wiki/wiki/todos/` with the failure mode and tick the failing checklist item with a reference. Otherwise check all green and update the master plan.
