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


## Iteration #2 — 2026-05-09 12:00

**Type:** feature
**Summary:** Phase 10a (consult_neighbor / Pull-on-Demand-Tool) komplett implementiert mit subagent-driven TDD-Workflow inkl. Live-Sichtprüfungs-Hotfix
**Files changed:** living_vault/core/db.py, living_vault/core/llm.py (respond_with_tools + FakeLLMWithTools), living_vault/apps/seance_ui/neighbors.py (NEU), living_vault/apps/seance_ui/store.py (add_tool_event + history filter + persona_path), living_vault/apps/seance_ui/app.py (say wired through respond_with_tools), living_vault/apps/seance_ui/static/index.html (mini-bubbles), living_vault/apps/seance_ui/prompt.py (Hotfix: full neighbor paths in system prompt), tests/test_db_migration.py, tests/test_seance_store.py, tests/test_core_llm_tools.py (NEU), tests/test_seance_neighbors.py (NEU), tests/test_seance_say_with_tools.py (NEU), tests/test_seance_app.py, tests/test_seance_prompt.py
**Tests:** passed (156 passed, war 118 vor Phase 10a, +38)
**Confidence:** 5/5
**Tags:** python, fastapi, anthropic, tool-use, mcp-tooling, llm-loop, schema-migration, tdd, subagent-driven, live-smoke, hotfix, ui

### Details

Master-Plan-Row 10 in 10a (Stufe 2 = Pull-on-Demand) und 10b (Stufe 3 = Multi-Persona-Roundtable) aufgeteilt. Phase 10a komplett: 8 Tasks via subagent-driven-development mit fresh subagent + 2-stage-Review pro Task. 16 Commits gesamt (8 Implementation + 6 Quality-Tightening + 1 Hotfix + 1 Closing). Architektur: respond_with_tools-Loop in core/llm.py mit max_iterations=5 Forced-Final-Call-Fallback, consult_neighbor-Handler-Closure mit Allowlist (graph_neighbors) + Soft-Cap (10 Calls/Turn) + Arg-Validation. UI-Mini-Bubbles "» consulted [[X]] (N chars)" italic mit grünem Border. seance_messages.persona_path nullable Spalte (vorbereitend für Phase 10b).

Live-Sichtprüfung 1. Versuch: Persona riet "sources/mcp-oekosystem/index.md" als Nachbar-Pfad (ihren eigenen Pfad-Stamm) statt der echten "concepts/..." Pfade. Persona diagnostizierte den Bug sogar selbst im Output. Hotfix `90120ea`: System-Prompt zeigt jetzt vollständige Nachbar-Pfade als "title -> `relpath`" plus expliziten Block "Calling consult_neighbor" der die LLM instruiert, den EXAKTEN relpath aus der Liste zu übergeben. 2. Versuch: 5 Nachbarn erfolgreich consultiert, Antwort inhaltlich angereichert ("Siemens Hannover Messe", "irreversibel"-Pattern, "stille Revolution"). User-Verdikt: positiv ("nice!!").

### Learnings

- **System-Prompt MUSS Nachbar-Pfade als vollständige relpaths enthalten, nicht nur Title-Stems**: Die LLM kann sonst den Tool-Call-String nicht korrekt bilden und scheitert konsequent am Allowlist-Check. Der Hotfix ist die wichtigste Erkenntnis für künftige Tool-Use-Designs in diesem Projekt: was die LLM als Tool-Argument übergeben soll, MUSS sie verbatim in ihrem Kontext sehen, nicht nur als "title das du transformieren musst".
- **Persona-eigene Diagnose des Bugs ist ein Signal für gutes Design**: Statt einfach zu halluzinieren hat die Persona im Output reflektiert "vielleicht `wiki/` statt `sources/`?" — das spricht dafür dass der Anti-Hallucination-Block im System-Prompt funktioniert (sie ratet nicht silently, sondern macht ihre Unsicherheit explizit).
- **Subagent-driven-development hält auch bei 8 Tasks Phase-9-Effizienz**: Phase-10a war ähnliche Task-Größe wie Phase-9, gleicher Quality-Fix-Anteil (~75% der Tasks bekamen Quality-Fixes, alle minor). Pattern ist robust.
- **Test-Verschärfung in Quality-Reviews findet echte Bugs**: Bei Task 5 (wire say()) hat ein verschärfter Test (von `<=10` auf `==10`) einen unbeabsichtigten Cap-Konflikt aufgedeckt: `max_iterations=5` (LLM-Loop) cappt VOR `MAX_CONSULT_CALLS_PER_TURN=10` (Handler-Soft-Cap). Test musste in zwei separate Tests gesplittet werden, einer pro Cap. Bei laxerer Test-Assertion wäre der Konflikt nie aufgefallen.

### Errors

(keine echten Bugs in finaler Code-Base — der Sichtprüfungs-Hotfix war ein Spec-Mangel, kein Bug)


## Iteration #3 — 2026-05-09 16:00

**Type:** feature
**Summary:** Phase 10b (Multi-Persona-Roundtable mit 3 Modi) komplett implementiert + alle 3 Spec-Restschuld-Items abgeräumt
**Files changed:** living_vault/core/db.py (mode column + seance_session_personas table), living_vault/apps/seance_ui/store.py (mode + add/get_session_personas + count_user_turns + get_session_mode), living_vault/apps/seance_ui/roundtable.py (NEU: pick_speakers + _parse_mentions + hash_color + shared_history_for_persona), living_vault/apps/seance_ui/prompt.py (teammate_paths kw-arg + _TEAMMATE_BLOCK), living_vault/apps/seance_ui/app.py (summon multi-page + mode + roundtable_say orchestrator + 502/partial_replies + roundtable-aware export), living_vault/apps/seance_ui/static/index.html (multi-select + mode-dropdown + persona-bubbles + hashColorJs mirror), tests/test_db_migration.py, tests/test_seance_store.py, tests/test_roundtable_speakers.py (NEU), tests/test_roundtable_history.py (NEU), tests/test_seance_prompt.py, tests/test_seance_app.py, tests/test_roundtable_app.py (NEU)
**Tests:** passed (204 passed, war 156 vor Phase 10b, +48)
**Confidence:** 5/5
**Tags:** python, fastapi, anthropic, tool-use, multi-persona, roundtable, mode-dispatch, shared-history, ui-color-coding, deterministic-hash, schema-migration, tdd, subagent-driven, live-smoke, partial-failure-handling, export-rendering

### Details

Phase 10b komplett: 9 Plan-Tasks via subagent-driven-development + 3 Restschuld-Items. 21 Commits gesamt (9 Implementation + 7 Quality-Tightening + 1 Closing + 4 Restschuld). Approach A (Symmetrische Architektur): Roundtable als Wrapper um N parallele Persona-States, wiederverwendet 80% der Phase-10a-Code-Pfade. Drei Modi (round-robin / moderator / freeforall) via pick_speakers-Dispatch. 1-8 Personas pro Roundtable. Cross-Persona-Consult: Allowlist erweitert um Teammate-Paths. Geteilte History via labeled-user-Wrapping ("[stem says]: text") weil Anthropic-API nur user/assistant-Roles kennt. Hash-deterministische Persona-Colors aus 8-Cyberpunk-Palette (Python `sum(ord(c)) % 8`, JS `sum(charCodeAt) % 8` als Mirror).

Sichtprüfung 2026-05-09: alle 3 Modi positiv durchlaufen. User-Verdikt: "geil, geil. Es funktioniert alles, wie es es soll. Supertoll, supertoll."

Restschuld nach Final-Review:
- R1 (`db29921`): Prompt-Drift in _TEAMMATE_BLOCK ("Pfade in der Liste oben" → "die folgenden Pfade sind zusätzlich erlaubt")
- R2 (`067df2c`): 502/partial_replies bei mid-loop-API-Fehler (try/except um respond_with_tools-Call, HTTPException 502 mit detail.partial_replies + tool_events + failed_persona)
- R3 (`652fcc2`): Roundtable-aware Export (per-persona-stem-Labels statt **Page**, tool_use als readable Italic-Lines statt raw JSON, mode: in Frontmatter)

### Learnings

- **Approach A (Symmetric Wrapper) ist die richtige Wahl bei feature-Erweiterungen die einen bestehenden Code-Pfad multiplexen**: Statt eine zweite Endpoint-/LLM-Klasse zu bauen war Phase 10b ein dünner Wrapper um die Phase-10a-Tool-Loop, der pro Persona einmal durchläuft. Wiederverwendung von make_consult_neighbor_handler, respond_with_tools, FakeLLMWithTools, store-Funktionen war bei jedem Schritt unverändert.
- **Geteilte History via labeled-user-Wrapping ist eine elegante Anthropic-API-Workaround**: Anthropic kennt nur user/assistant-Roles. Andere Personas' Antworten als `("user", "[stem says]: text")` zu rendern lässt den LLM-Call die Beiträge der Mitstreiter als "externer Stimulus" lesen, ohne API-Fight. Test 5 in test_roundtable_history.py beweist die korrekte Verschachtelung über mehrere Turns.
- **Hash-deterministische Colors brauchen einen MIRROR-Comment auf BEIDEN Seiten**: Python und JS hashen jeweils `sum(char_codes) % len(PALETTE)`. Wenn nur eine Seite geändert wird, divergieren live-Sessions und historische Replays in der Farbgebung. Quality-Reviewer hat gefordert dass `hash_color` in roundtable.py einen `MIRROR: living_vault/apps/seance_ui/static/index.html hashColorJs()` Block bekommt, JS hat einen Mirror-Comment in die andere Richtung. Cross-language-Code-Symmetrie ist nur durch explicite Comments verifierbar.
- **Closure-Trap bei Multi-Iteration-Schleifen**: Ohne `_events=speaker_tool_events, _h=raw_handler` als Default-Args würden alle Closure-Captures in der Speaker-Loop auf die LAST-Iteration-Bindings zeigen (Python late-binding). Default-Arg-Early-Binding ist die idiomatische Lösung — hat der Quality-Reviewer für Task 7 explizit verifiziert.
- **TOCTOU im double-build_persona-Pattern**: Task 6 hatte ursprünglich `build_persona(paths[0])` zweimal (einmal zur Validation, einmal für die `persona`-Response-Field). Wenn die Page zwischen den Calls verschwindet → silent omission der `persona`-Key in der Response. Capturing-Loop in `built_personas` schließt das Fenster. Quality-Reviewer hat das früh genug gefangen.
- **Empty-Set-Iteration ist nicht-deterministisch**: `persona_paths = {p["persona_path"] for p in personas}` produziert Set-Iteration in nicht-deterministischer Reihenfolge → System-Prompt drifted zwischen Runs. Fix: list comprehension `persona_paths_ordered = [p["persona_path"] for p in personas]` (Python 3.7+ insertion order). Wichtig wenn der Prompt jemals snapshot-getestet werden soll.

### Errors

(keine echten Bugs in finaler Code-Base — alle Quality-Items im Cross-Review-Loop als Tightening-Commits adressiert)


## Iteration #4 — 2026-05-09 18:30

**Type:** feature
**Summary:** Phase 11 (synesthesia public subset) komplett implementiert mit Allowlist-Layer, Public-Build-CLI, 3D-Brand-Header, Deploy-Skript und positiver User-Sichtprüfung gegen 953-Page-Real-DB
**Files changed:** living_vault/core/privacy.py (allowlist API: public_pages mit Union, load_allowlist, allowlist_skipped), living_vault/apps/synesthesia/layout.py (compute_layout +allowlist Param + PCA-Pad-Fix für n<3), living_vault/apps/synesthesia/render.py (public_build + public_build_cli @click.command, render_html +**extra_ctx), living_vault/apps/synesthesia/templates/vault-3d.html.j2 (Brand-Header + Footer in {% if embed_url %}-Block), pyproject.toml (synesthesia-public-build entry point), tests/test_privacy.py (+5 Tests), tests/test_privacy_regression.py (+3 Tests), tests/test_synesthesia_render.py (+6 Tests), scripts/deploy-public-vault.ps1 (NEU), docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md (NEU), docs/superpowers/plans/2026-05-09-phase-11-public-vault.md (NEU), docs/PHASE-11-CHECKLIST.md (NEU), docs/DEPLOY-PUBLIC-VAULT.md (NEU), docs/public-allowlist.txt (NEU mit 10 kuratierten Pages), docs/plans/2026-05-08-living-vault-master-plan.md (Phase-11-Status)
**Tests:** passed (218 passed, war 204 vor Phase 11, +14)
**Confidence:** 5/5
**Tags:** python, fastapi, click, jinja2, pca, sqlite, privacy-boundary, allowlist, manifest-schema, deterministic-build, deploy-pipeline, schema-stability, tdd, subagent-driven, live-smoke, codex-verifier

### Details

Master-Plan-Phase-11 vollständig durchgezogen. 6 Sub-Tasks via subagent-driven-development mit fresh subagent + Codex-Verifier-Default nach jedem Task. 9 Commits gesamt (1 Spec+Plan + 1 Allowlist-Layer + 1 PCA-Pad-Fix + 1 Privacy-Regression + 1 Public-Build-CLI + 1 Brand-Header + 1 Deploy-Skript + 1 Acceptance-Checklist + 1 Final-Close). Architektur: Allowlist als runtime-Filter (kein DB-Schema-Eingriff), `public_pages(con, allowlist=None)` liefert Union via SQL `WHERE is_public=1 OR path IN (...)`, `compute_layout` rückwärts-kompatibel mit Default `allowlist=None`. Neue Click-Command `public_build_cli` als standalone @click.command (NICHT subcommand) zur Backwards-Compat des bestehenden `synesthesia`-Entry-Points. Manifest-Schema v1 mit 14 Feldern (build_at als einzige zeitabhängige Variable). Determinismus-Test relaxed: index.html modulo build-stamp-lines (Build/Stand), pages.json byte-identisch.

Codex-Verifier-Pass nach Task 11.1 lieferte 1 LOW-Finding (SQLite IN-Clause-Parameter-Limit ~999) — als Phase-11-Carry-Over geparkt, in der Praxis irrelevant für kuratierte Allowlists.

User-Sichtprüfung 2026-05-09 in 4 Stages durchlaufen: (1) frontmatter-only build → public_total=0 plausibel; (2) allowlist-curated build mit 10 Pages → public_total=10, edges_total=4 (drei Cluster: MCP/Agentic, Living-Vault-Meta, Mikromagnetik); (3) 3D-Vault-Render mit 10 Knoten + 4 Edges sichtbar; (4) Privacy-Filter hält. User-Verdikt: "okay, also geht" → Master-Plan-Row 11 ✅.

### Learnings

- **Privacy-Boundaries müssen über die Test-Suite explizit verteidigt werden, nicht nur im Code-Pfad**: Phase 11 hat 6 dedizierte Privacy-Tests (5 union-Logik + 3 regression + edge-isolation). Der bestehende `test_no_private_path_in_public_synesthesia_build` aus Phase 7 wurde nicht angefasst, sondern die neue Allowlist-Variante daneben gestellt. Layered defense gegen privacy drift.
- **`render_html` mit `**extra_ctx` durchreichen ist eine elegante Backwards-Compat-Lösung für Template-Variablen**: Statt die Funktion-Signature mit 6 neuen Optional-Args aufzublähen, akzeptiert sie `**extra_ctx` und reicht alles ans Jinja2-Template weiter. Templates die die Vars nicht referenzieren ignorieren sie. Legacy-Renders bleiben byte-identisch (verifiziert durch bestehenden render-Test).
- **Click-Subcommand-vs-standalone-Entscheidung muss früh stehen**: Click hat zwei mutually exclusive Patterns: `@click.group()` mit Subcommands oder `@click.command()` standalone. Sobald ein @click.command als Entry-Point registriert ist, kann es nicht mehr ohne Breaking-Change in eine Group umgewandelt werden. Phase-11 hat das durch zwei separate Entry-Points (`synesthesia` + `synesthesia-public-build`) gelöst, beide als standalone @click.command. Das war im Plan als explizite "Variante B" notiert.
- **PCA-SVD-Component-Count = `min(n_samples, n_features)` ist eine subtile Falle bei kleinen Test-Fixtures**: Beim Schreiben der Privacy-Regression-Tests (vault_copy mit 2 allowlisted Pages) crashte `_pca_3d` mit `IndexError` auf `c[2]`, weil SVD nur 2 Komponenten lieferte. Production-Vaults mit >>3 Pages waren nie betroffen — Fix war minimal (Zero-Padding bei <3 Spalten), aber der Bug wäre ohne Test-Edge-Case nie aufgefallen. Lesson: Tests mit minimalen Fixtures finden Bugs, die produktive Daten verstecken.
- **Brand-Header in `{% if embed_url %}` halten Legacy-Renders byte-identisch**: Phase 11 fügt Header/Footer-CSS+HTML zum Default-Template, aber ohne dass `embed_url` (oder die anderen vars) gesetzt sind, rendert das Template wie vorher. Bestehender `synesthesia` low-level CLI ist unangetastet. Das ist die richtige Strategie wenn ein Template multiple Use-Cases bedienen muss (low-level dev vs deploy-bundle).
- **Determinismus-Tests müssen Time-Variables explizit ausnehmen, nicht naiv byte-vergleichen**: Erste Implementierung von `test_public_build_is_deterministic` schlug fehl, weil das Template `{{ build_at }}` und `{{ build_date }}` rendert. Lösung: `_strip_buildstamp(text)` filtert Zeilen mit "Build " oder "Stand " bevor verglichen wird. Manifest darf `build_at` differieren, alle anderen Felder müssen identisch sein. Test wurde explizit "modulo_build_at" benannt.
- **Bridge-Pages haben überproportional viel Edge-Wert in einem Subset-Render**: Erste 10-Page-Allowlist produzierte nur 4 Edges, weil die meisten Wikilinks der 10 Pages auf nicht-allowlisted Pages zeigten (`model-context-protocol`, `magnetische-hysterese` etc.). Lesson: Beim Kuratieren von Public-Subsets erst Bridge-Pages identifizieren (Pages die mehrfach von der Subset-Auswahl verlinkt werden), nicht nur Themen-Cluster picken.

### Errors

(keine echten Bugs in finaler Code-Base — der PCA-Pad-Fix war eine Edge-Case-Vorsorge ohne production-Auswirkung, der Codex-Verifier-LOW-Befund SQLite-IN-Limit ist theoretisch ohne praktischen Trigger, alle Quality-Items im Cross-Review-Loop adressiert)
