# Phase 9 — Acceptance Checklist

When all boxes are ticked, Phase 9 is done and the master-plan row turns ✅.
Status is set MANUALLY after verification — auto-ticking is not allowed.

## Engine + DB

- [x] DB-Migration: `voice_features` and `voice_distilled` columns exist on
      live `~/wiki/.vault-engine.db` (verified 2026-05-09 by Task 9 Step 1
      after triggering `db.initialize()`)
- [x] All 953 pre-existing pages preserved after migration; 953 embeddings
      preserved; is_public counts unchanged (verified 2026-05-09)
- [x] `core/llm.py` lifted from `apps/seance_ui/llm.py`; old import path
      still works via shim (verified `tests/test_core_llm.py` — 6 tests)
- [x] `LIVING_VAULT_FAKE_LLM` env var no longer truthy-string-traps
      ("0"/"false"/"no" correctly disable FakeLLM)

## Voice Pipeline

- [x] `extract_stylometric()` produces all 12 required fields (verified
      `tests/test_persona_stylometric.py` — 12 tests including pure-code-body
      regression)
- [x] `distill_voice_via_llm()` runs with FakeLLM, respects 8K body cap,
      accepts `system_prompt` override (verified
      `tests/test_persona_distill.py` — 5 tests)
- [x] `assemble_persona()` handles all three voice-block cases plus
      empty-frontmatter (verified `tests/test_persona_assemble.py` — 4 tests)
- [x] `build_persona()` end-to-end: caches `voice_features` in DB, reads
      `voice_distilled` when present, single-SELECT round-trip (verified
      `tests/test_persona.py` — 5 tests)
- [x] `prompt.py:build_voice_block()` falls back to Case C if `voice_features`
      dict is malformed (verified `tests/test_seance_prompt.py` — 7 tests)

## CLI

- [x] `living-vault extract-voice --help` lists all flags
      (`--vault`, `--db`, `--limit`, `--force`, `--yes`)
- [x] `extract-voice --limit N` caps page count (verified
      `tests/test_extract_voice_cli.py`)
- [x] `extract-voice` skips already-distilled pages without `--force`,
      replaces them with `--force` (verified)
- [x] `extract-voice` shows cost disclaimer; aborts deterministically on `n`
      with exit_code=1 + "Aborted" output (verified)
- [x] `extract-voice` against empty DB reports "Nothing to do." cleanly
      (verified)
- [x] `extract-voice` runs successfully against live DB with `--limit 3 --yes`
      (verified Task 9 Step 2 — 3/3 OK, 0 failed; FakeLLM echoes cleaned up)

## Séance Integration

- [x] `seance_ui/app.py` calls `build_persona` (not `build_persona_lite`) —
      both `summon()` and `say()` call sites switched
- [x] `seance_ui/app.py` uses `lifespan` context manager (not
      `@app.on_event("startup")`) — Issue #1 from Phase-8 gate closed
- [x] No `DeprecationWarning: on_event` in pytest run output
- [x] `apps/seance_ui/llm.py` is a re-export shim — no Phase-1 implementation
      code remaining

## Test Suite Health

- [x] `pytest -q` from repo root: all green (116 passed, 0 failed)
- [x] Total test count ≥ 96 — actual: **116** (Phase-1 had 74, Phase-9 added
      ~42 covering migration, llm-lift, stylometric, distill, assemble,
      persona, prompt-cases, extract-voice CLI)
- [x] No Phase-1 test regressed
- [x] No `~/wiki/` access from any test (verified by `real_wiki_guard`
      fixture, which monkeypatches `open()` to refuse paths under
      `~/wiki/`)
- [x] No real Anthropic calls from any test (verified — FakeLLM only via
      `LIVING_VAULT_FAKE_LLM=1` env var or direct injection)

## User Sichtprüfung (subjective — final master-plan criterion)

This is the only step the implementation cannot self-verify. The master-plan
defines Phase 9 success as **the user perceives the séance to "klingen mehr
nach der Page"** after `extract-voice` runs against real Anthropic.

- [ ] Run `living-vault extract-voice --limit 5 --yes` against live DB with
      real Anthropic key (NOT in `LIVING_VAULT_FAKE_LLM` mode) — costs ~$0.03
- [ ] Open Séance UI (`seance-ui` script or `uvicorn living_vault.apps.seance_ui.app:app --port 7777`),
      summon a page that was just distilled
- [ ] Compare to a page that was NOT distilled (only stylometric voice_features)
- [ ] User-Eindruck: "klingt mehr nach der Page" — if yes, Phase 9 ✅
      and master-plan row 9 turns ✅. If no, iterate the prompt template
      in `core/voice/distill.py:DEFAULT_DISTILL_PROMPT` or in
      `apps/seance_ui/prompt.py:_TEMPLATE`, then re-run.

## Commit Index

Phase-9 commits (most recent first):

```
64f842b living-vault | Phase-9: type-hint seance lifespan param, drop noise comments
0afcb16 living-vault | Phase-9: seance uses build_persona + lifespan handler
5f40550 living-vault | Phase-9: tighten extract-voice test assertions + zero-pages case
83d9655 living-vault | Phase-9: extract-voice cli with cost disclaimer
0f4702e living-vault | Phase-9: prompt fallback when voice_features dict is malformed
346fe3d living-vault | Phase-9: prompt template with three voice-block cases
6fef17f living-vault | Phase-9: persona orchestrator single-SELECT + clearer test name
c81ff70 living-vault | Phase-9: build_persona orchestrator replaces persona_lite
464aa82 living-vault | Phase-9: parameterize distill prompt + tighten truncation test
4f10351 living-vault | Phase-9: distill_voice_via_llm with FakeLLM tests
1a30c5c living-vault | Phase-9: stylometric early-return fix + single-source key set
1459792 living-vault | Phase-9: stylometric extractor + 11 tests
d193647 living-vault | Phase-9: fix LIVING_VAULT_FAKE_LLM truthy-string trap
4c7115b living-vault | Phase-9: lift llm abstraction to core, shim in seance_ui
19b62ae living-vault | Phase-9: clarify executescript commit semantics in db.initialize
709c8fd living-vault | Phase-9: db migration adds voice columns to pages
4aa0b92 living-vault | Phase-9: design spec for persona-schicht-3 (voice-extraction)
0749f2a living-vault | Phase-9: implementation plan with 9 tasks (TDD per Phase-1 conventions)
```

`git log --grep="Phase-9"` is the cross-session handoff index.
