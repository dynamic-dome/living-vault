# Iteration Log

## Iteration #1 — 2026-05-09 04:30

**Type:** feature
**Summary:** Phase 9 (Persona-Schicht 3 / Voice-Extraction) komplett implementiert mit subagent-driven TDD-Workflow
**Files changed:** living_vault/core/db.py, living_vault/core/llm.py (NEU), living_vault/core/voice/__init__.py (NEU), living_vault/core/voice/stylometric.py (NEU), living_vault/core/voice/distill.py (NEU), living_vault/core/persona.py (vollersatz), living_vault/cli.py, living_vault/apps/seance_ui/llm.py (zu shim), living_vault/apps/seance_ui/prompt.py (rewrite), living_vault/apps/seance_ui/app.py, living_vault/apps/seance_ui/static/index.html (CSS-hotfix), tests/test_db_migration.py (NEU), tests/test_core_llm.py (NEU), tests/test_persona_stylometric.py (NEU), tests/test_persona_distill.py (NEU), tests/test_persona_assemble.py (NEU), tests/test_extract_voice_cli.py (NEU), tests/test_real_wiki_guard_proof.py (NEU), tests/test_persona.py (rewrite), tests/test_seance_prompt.py (rewrite)
**Tests:** passed (118 passed, 0 failed, 0 deprecation warnings)
**Confidence:** 5/5
**Tags:** python, fastapi, sqlite, persona, voice-extraction, llm-tooling, schema-migration, tdd, subagent-driven, anthropic, multi-task

### Details

Master-Plan Phase 9 vollständig durchgezogen. Approach: brainstorming-Skill für Scope-Klärung (4 user-Entscheidungen: Pain-Anchor, Voice-Tiefe, Storage-Strategy, Replace-vs-Coexist), dann formaler Spec, dann writing-plans-Skill für 9-Task-Plan, dann subagent-driven-development für die Umsetzung — fresh subagent pro Task, two-stage review zwischen Tasks (spec compliance + code quality). Insgesamt 18 Commits in der Phase: 1 Spec + 1 Plan + 9 Implementation-Tasks + 7 Follow-up-Quality-Fixes (alle aus Code-Reviews) + 1 Final-Hardening (real_wiki_guard autouse) + 1 CSS-Hotfix für UI-Scroll-Bug.

Architektur: 4-Stufen-Pipeline (read_page → extract_stylometric → load_or_distill → assemble_persona). Stylometric ist deterministisch und immer da (12 Features pro Page); LLM-distilled Voice ist on-demand via separater CLI (`living-vault extract-voice`). DB-Schema-Erweiterung non-breaking via ALTER TABLE mit content-existence-probe. core/llm.py von apps/seance_ui hochgehoben (clean dep direction apps→core). lifespan handler ersetzt deprecated @app.on_event (Phase-8-Issue #1 closed).

Sichtprüfung mit echter Anthropic Haiku 4.5: 5 Pages distilliert, User-Verdikt "subtil aber spürbar" → Master-Plan-Row 9 ✅.

### Learnings

- **Subagent-driven-development mit fresh subagent + two-stage review skaliert sehr gut**: Bei 9 Tasks nur 7 Follow-up-Fixes nötig, alle minor. Das spec-vs-code-quality-review-Pattern fängt früh Drift ab. Kostenpunkt: ein Implementer + zwei Reviewer-Calls pro Task = 3x Subagent pro Plan-Task. Lohnt sich für Phasen >=5 Tasks.
- **User-Entscheidungen vor Approach-Vorschlägen einholen**: Initial habe ich drei Architektur-Approaches (A/B/C) vorgelegt und User antwortete "keine ahnung" — das war Signal dass die Wahl-Achsen für ihn Implementation-Details waren, keine echten User-Entscheidungen. Reduktion auf "Wann soll der LLM-distilled Pass laufen?" (User-spürbar, prägt Erfahrung) führte zu sofortiger klarer Entscheidung. Lesson: Architekturwahl muss am User-Erlebnis kalibriert sein, nicht an Code-Eleganz.
- **Self-review während des Spec-Schreibens fand bereits zwei Konsistenz-Lücken**: LLM-Modul-Migration (apps→core dependency direction) wurde erst beim Self-Review explizit gemacht; Cache-Strategy-Beschreibung war vorher widersprüchlich. Spec-Self-Review ist kein Theater-Schritt, er produziert echte Korrekturen.
- **`real_wiki_guard` als autouse zu deklarieren statt opt-in macht den Test-Isolation-Claim genuinely true**: Final-Reviewer fand dass die Phase-9-Checklist behauptete "verified by real_wiki_guard" obwohl kein Test die Fixture explizit anforderte. autouse-Fix + Proof-Test schliesst die Lücke.
- **Live-DB-Migration auto-läuft beim ersten initialize()-Call**: Wir mussten manuell `db.initialize(Path("~/wiki/.vault-engine.db"))` triggern damit die ALTER TABLE-Statements liefen. Bei nächstem produktivem Aufruf (z.B. seance-ui start) wäre die Migration sowieso passiert, aber für die Acceptance-Verification war der explizite Trigger nötig.

### Errors

(keine — alle Code-Quality-Findings wurden im normalen Cross-Review-Loop als Follow-ups adressiert, nicht als Bug-Fixes auf production-state)
