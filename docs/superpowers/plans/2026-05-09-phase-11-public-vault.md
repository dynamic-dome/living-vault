# Plan: Phase 11 — Public Vault

**Spec:** [`../specs/2026-05-09-phase-11-public-vault-design.md`](../specs/2026-05-09-phase-11-public-vault-design.md)
**Erwartete Dauer:** 6-7h reine Arbeit, ~1 Tag mit Reviews und Sichtprüfung
**Vorgehen:** Subagent-driven-development, Codex-Verifier nach jedem Task

---

## Task 11.1 — Allowlist-Layer

**Ziel:** `core/privacy.py` erweitert um Allowlist-Union, `apps/synesthesia/layout.py` erweitert um Allowlist-Parameter.

### Files

- `living_vault/core/privacy.py` (erweitern)
- `living_vault/apps/synesthesia/layout.py` (signature)
- `tests/test_privacy.py` (neue Tests)

### Spec-Punkte abdecken

§3 (Architektur Allowlist-Layer), §5 (Tests 1-3)

### Akzeptanzkriterien

- `public_pages(con, allowlist: list[str] | None = None) -> list[str]` liefert Union, sortiert.
- `load_allowlist(path: Path) -> list[str]` parst Datei, strippt `#`-Kommentare, strippt Leerzeilen, Whitespace.
- `allowlist_skipped(con, allowlist: list[str]) -> list[str]` liefert Pfade aus Allowlist, die nicht in `pages` stehen.
- `compute_layout(db_path, public_only=False, allowlist=None)` — wenn `allowlist` und `public_only` gesetzt sind, wird Union gefilttert.
- Tests: 5 neue Cases in `tests/test_privacy.py` (`test_public_pages_union_with_allowlist`, `test_load_allowlist_strips_comments_and_blanks`, `test_load_allowlist_handles_unicode_paths`, `test_allowlist_with_nonexistent_paths_skipped_silently`, `test_public_pages_no_duplicates_when_path_in_both_sources`).
- Bestehende Tests bleiben grün.

### Test-Runner-Hinweis (Pflicht)

`.venv/Scripts/python.exe -m pytest tests/test_privacy.py tests/test_layout.py -x`

### Subagent-Brief

```
Task 11.1 — Allowlist-Layer für Public-Vault.

Files: living_vault/core/privacy.py, living_vault/apps/synesthesia/layout.py,
       tests/test_privacy.py.

Spec: docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md (§3, §5).
Plan: docs/superpowers/plans/2026-05-09-phase-11-public-vault.md (Task 11.1).

Implementiere:
1. core/privacy.py: public_pages(con, allowlist=None), load_allowlist(path),
   allowlist_skipped(con, allowlist).
2. apps/synesthesia/layout.py: compute_layout(db_path, public_only=False,
   allowlist=None) — wenn beide gesetzt → Union via public_pages.
3. tests/test_privacy.py: 5 neue Test-Cases laut Plan.

Constraints:
- Allowlist-Format: Plain-Text, eine relpath pro Zeile, # = Kommentar, Leerzeilen ok.
- public_pages() ohne allowlist-Param: Verhalten exakt wie vorher (rückwärts-kompatibel).
- Sortierung der Rückgabe deterministisch (ORDER BY path bzw. sorted()).
- Keine API-Breaking-Change in compute_layout (allowlist=None Default).

Test-Runner: .venv/Scripts/python.exe -m pytest tests/test_privacy.py tests/test_layout.py -x
```

### Definition of Done

- 5+ neue Tests grün, alle alten Privacy/Layout-Tests grün.
- Subagent-Self-Review-Pass + Spec-Reviewer-Pass.

---

## Task 11.2 — Privacy-Regression-Verschärfung

**Ziel:** Privacy-Regression-Suite deckt Allowlist-Fall ab. Real-Wiki-Snapshot-Fixture bleibt klein und reproducible.

### Files

- `tests/test_privacy_regression.py` (erweitern)
- `tests/fixtures/` (eventuell minimal-Wiki-Snapshot, falls noch nicht da)

### Spec-Punkte

§5 (Tests 4)

### Akzeptanzkriterien

- `test_no_private_path_in_public_build_with_allowlist` — baut Vault, setzt Allowlist mit privater Page, prüft dass kein anderer privater Pfad im Build steht. Wichtig: zeigt dass Allowlist ein **expliziter Override** ist (User trägt explizit Verantwortung), aber Edge-Leakage nicht passiert.
- `test_no_private_path_in_public_build_when_allowlist_empty` — leere Allowlist → Verhalten = ohne Allowlist.
- `test_edge_between_public_and_private_page_not_rendered` — Edge nur zwischen public Pages.
- Bestehender `test_no_private_path_in_public_synesthesia_build` bleibt unverändert grün.

### Subagent-Brief

```
Task 11.2 — Privacy-Regression-Verschärfung für Phase 11.

Files: tests/test_privacy_regression.py.

Spec: docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md (§5 Risiko-Tabelle, Tests 4-6).

Implementiere 3 neue Privacy-Regression-Test-Cases:
1. test_no_private_path_in_public_build_with_allowlist
2. test_no_private_path_in_public_build_when_allowlist_empty
3. test_edge_between_public_and_private_page_not_rendered

Constraints:
- Nutzt vault_copy + db_path Fixtures (bestehend).
- Keine eigene Allowlist-Datei in tmp_path schreiben — Allowlist als list[str] direkt
  in compute_layout reichen (Task 11.1 macht load_allowlist, hier nutzen wir die liste).
- Edge-Test: vault_copy hat note-a (private) → note-b (public). Mit Allowlist=[note-a]
  wird note-a public → Edge sollte erscheinen. Ohne Allowlist → kein Edge im public build.

Test-Runner: .venv/Scripts/python.exe -m pytest tests/test_privacy_regression.py -x
```

### Definition of Done

- 3 neue Tests grün, alter Test grün.

---

## Task 11.3 — Public-Build CLI

**Ziel:** `synesthesia public-build` Subcommand. Producktiv-Surface.

### Files

- `living_vault/apps/synesthesia/render.py` (Refactor zu `click.group()`, neuer Subcommand)
- `tests/test_synesthesia_render.py` (erweitern)

### Spec-Punkte

§6 (Output-Schema), §7 (CLI-Surface)

### Akzeptanzkriterien

- `synesthesia public-build --vault X --db Y --allowlist Z --out OUT [--variant V] [--embed-url U]` läuft.
- Bestehender `synesthesia` (Top-Level-Aufruf ohne Subcommand) bleibt funktional **als Alias** auf den alten low-level-CLI — Pflicht: `pyproject.toml [project.scripts] synesthesia = "living_vault.apps.synesthesia.render:cli"` darf nicht brechen.
- Lösung: `cli` wird `@click.group(invoke_without_command=True)`, mit Default-Verhalten = bisheriger Render-CLI wenn keine Subcommand-Args (oder über `synesthesia legacy ...` als Subcommand). Wenn das nicht sauber geht: `cli` bleibt single-command, `public-build` wird ein **eigenständiges** click-Command, registriert als zweiter Entry-Point in pyproject.toml: `synesthesia-public-build = "living_vault.apps.synesthesia.render:public_build_cli"`.
- Empfohlen wegen Klarheit: **Variante B** (zweiter Entry-Point, kein click.group). Spec referenziert `synesthesia public-build` aber das ist semantisch — Implementierung kann gerne `synesthesia-public-build` heißen.
- Output-Verzeichnis enthält:
  - `index.html` (3D, public-only mit Allowlist)
  - `manifest.json` (Schema laut §6)
  - `pages.json` (`{"pages": [{"path": "...", "title": "...", "cluster": "..."}, ...]}`)
- Tests: 4 neue Cases (`test_public_build_writes_three_files`, `test_public_build_manifest_has_required_fields`, `test_public_build_skips_nonexistent_allowlist_paths`, `test_public_build_is_deterministic_modulo_build_at`).

### Subagent-Brief

```
Task 11.3 — Public-Build CLI für Phase 11.

Files: living_vault/apps/synesthesia/render.py,
       tests/test_synesthesia_render.py,
       pyproject.toml (Entry-Point ergänzen).

Spec: docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md (§6, §7).
Plan: docs/superpowers/plans/2026-05-09-phase-11-public-vault.md (Task 11.3).

Implementiere:
1. Neue Funktion `public_build(vault_root, db, allowlist, out, variant, embed_url)`
   in render.py — produziert out/index.html, out/manifest.json, out/pages.json.
2. Neuer Click-Command `public_build_cli` als separates @click.command, NICHT als Subcommand
   des bestehenden cli (wegen Backwards-Compat, siehe Plan-Note).
3. pyproject.toml: zweiter Entry-Point `synesthesia-public-build = "living_vault.apps.synesthesia.render:public_build_cli"`.
4. tests/test_synesthesia_render.py: 4 neue Tests laut Plan.

Constraints:
- Bestehender `synesthesia` Entry-Point + bestehende `cli` muss unverändert funktionieren
  (nicht brechen). Bestehende Tests test_render_writes_html / test_render_public_only_excludes_private
  müssen grün bleiben.
- manifest.json: build_at ist UTC ISO8601 ("YYYY-MM-DDTHH:MM:SSZ"). schema_version=1.
- Determinismus-Test: zwei Builds nacheinander, byte-vergleich von index.html und pages.json
  (manifest.json darf wegen build_at differieren).
- Allowlist-Path optional. Wenn fehlt: nur is_public=1-Filter.

Test-Runner: .venv/Scripts/python.exe -m pytest tests/test_synesthesia_render.py -x
```

### Definition of Done

- Neue CLI funktional, bestehende nicht gebrochen.
- 4 neue Tests grün, alle alten render-Tests grün.

---

## Task 11.4 — Cluster-Header über 3D

**Ziel:** Standalone-HTML hat Identitäts-Header. Subroute-Branding.

### Files

- `living_vault/apps/synesthesia/templates/vault-3d.html.j2` (Header-Block)
- ggf. `templates/galaxy.html.j2`, `city.html.j2`, `network.html.j2` (optional, nur wenn niedrigaufwändig)
- `tests/test_synesthesia_render.py` (string-match-Test)

### Spec-Punkte

§1 (Sichtbares Endergebnis), §6 (Output-Schema)

### Akzeptanzkriterien

- Template-Header zeigt: "vault.dynamic-dome.com — N öffentliche Pages aus 953 (Stand: YYYY-MM-DD)" oder ähnlich.
- Daten kommen aus dem `public_build`-Aufruf (über zusätzliche Template-Variablen).
- Footer zeigt Build-Stamp und Schema-Version.
- Header/Footer sind **CSS-only**, kein zusätzliches JS, lesbar auch ohne Three.js.
- Test: Build → HTML enthält "vault.dynamic-dome.com" (per default, oder via `--embed-url`-Override) und Page-Count.

### Subagent-Brief

```
Task 11.4 — Cluster-Header für Public-Vault Templates.

Files: living_vault/apps/synesthesia/templates/vault-3d.html.j2,
       tests/test_synesthesia_render.py.

Spec: docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md (§1).
Plan: docs/superpowers/plans/2026-05-09-phase-11-public-vault.md (Task 11.4).

Implementiere:
1. Header-DIV im Template (vor dem 3D-Canvas) mit:
   - Branding-Zeile "vault.dynamic-dome.com" (oder embed_url Override)
   - Subline "{count} öffentliche Pages aus {total} (Stand: {build_date})"
2. Footer mit "Build {build_at}, schema v{schema_version}"
3. CSS für Header/Footer im Template (dezent, dark, JetBrains-Mono — passt zur dome-dynamics-Ästhetik
   aber Standalone, KEINE externe Font-Abhängigkeit, system-font-stack).
4. Template bekommt zusätzliche Variablen: embed_url, public_count, vault_total_pages,
   build_date, build_at, schema_version. Diese werden in render_html() bzw. public_build()
   befüllt.
5. Test: test_public_build_html_has_branding_header (string-match auf "vault.dynamic-dome.com"
   und auf Page-Count).

Constraints:
- Variant-Templates galaxy/city/network NICHT touchen (Out-of-Scope, separater Lift).
  Header nur in default-Template (vault-3d.html.j2).
- public-build forciert variant=default für Phase 11. Variant-Override mit Header
  → späterer Phase-11+ Subtask.
- Kein neuer JS, keine Web-Fonts (Google-Fonts oder ähnlich).

Test-Runner: .venv/Scripts/python.exe -m pytest tests/test_synesthesia_render.py -x
```

### Definition of Done

- Header in vault-3d.html.j2 sichtbar.
- 1 neuer Test grün.

---

## Task 11.5 — Deploy-Skript + Doku

**Ziel:** User kann Public-Build mit einem Befehl auf Static-Host deployen.

### Files

- `scripts/deploy-public-vault.ps1` (PowerShell, Windows-Native)
- `docs/DEPLOY-PUBLIC-VAULT.md` (Hosting-Pfade)

### Spec-Punkte

§7 (Out-Verzeichnis), §11 (DNS user-action)

### Akzeptanzkriterien

- `deploy-public-vault.ps1` macht: 1) `synesthesia-public-build` aufrufen, 2) `out/` mit Build-Output befüllen, 3) optional rsync/cp nach Ziel-Verzeichnis (über env-Var oder Param).
- DEPLOY-PUBLIC-VAULT.md erklärt 3 Hosting-Pfade: Cloudflare Pages, Netlify, GitHub Pages.
- Skript prüft .venv-Existenz und nutzt `.venv/Scripts/python.exe`.

### Subagent-Brief

```
Task 11.5 — Deploy-Skript + Doku für Phase 11.

Files: scripts/deploy-public-vault.ps1, docs/DEPLOY-PUBLIC-VAULT.md.

Spec: docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md (§11).
Plan: docs/superpowers/plans/2026-05-09-phase-11-public-vault.md (Task 11.5).

Implementiere:
1. scripts/deploy-public-vault.ps1:
   - Parameter: -OutDir (default ./out-vault), -Vault (default ~/wiki),
     -Db (default ~/wiki/.vault-engine.db), -Allowlist (default docs/public-allowlist.txt),
     -EmbedUrl (default https://vault.dynamic-dome.com)
   - Schritte: .venv-Check → public-build aufrufen → manifest.json anzeigen → "deploy
     manuell oder via -DeployTarget pfad" Hinweis
   - PowerShell-syntax (laut globaler CLAUDE.md: PowerShell, kein /dev/null)
2. docs/DEPLOY-PUBLIC-VAULT.md:
   - Section "Quick start" mit deploy-public-vault.ps1
   - Section "Hosting options" mit 3 Pfaden:
     a) Cloudflare Pages — wrangler pages deploy ./out-vault --project-name=vault-dome
     b) Netlify — netlify deploy --dir=./out-vault --prod
     c) GitHub Pages — gh-pages-action mit Out als Source
   - Section "DNS" — vault.dynamic-dome.com → CNAME auf Static-Host
   - Section "Allowlist-Workflow" — wie User die Allowlist befüllt und neu deployt

Constraints:
- Skript darf nur lokale Aktionen — kein Push auf Remote ohne explizite User-Action.
- Doku-Sprache: Deutsch (User-Präferenz aus globaler CLAUDE.md).
- Skript-Comments: Englisch.

Tests: keine (Skript + Doku-Task).
```

### Definition of Done

- Skript läuft trocken (`-WhatIf`-äquivalent oder explizit Dry-Run).
- Doku verlinkt aus Master-Plan.

---

## Task 11.6 — Acceptance-Checklist

**Ziel:** Phase-11 abgenommen.

### Files

- `docs/PHASE-11-CHECKLIST.md`

### Spec-Punkte

§10 (Definition of Done)

### Akzeptanzkriterien

- Checklist-Format identisch zu PHASE-10A/PHASE-10B-CHECKLIST.md (Codebase-Konsistenz).
- Sechs User-Sichtprüfungs-Punkte:
  1. ☐ Allowlist mit 3-7 Wiki-Pfaden befüllt
  2. ☐ `deploy-public-vault.ps1` lief ohne Fehler
  3. ☐ `out/manifest.json` öffnen, `public_total > 0`, `allowlist_skipped` plausibel
  4. ☐ `out/index.html` lokal im Browser geöffnet, 3D-Vault rendert
  5. ☐ Header zeigt korrekte Subroute + Page-Count
  6. ☐ Privacy-Test (Spot-Check): keine private Page im HTML-Source per Strg+F gefunden
- Tests-Status-Block: `.venv/Scripts/python.exe -m pytest tests/ -x` Output anhängen.
- Carry-Over-Section: Hinweis auf Big-Ticket-Backlog (Phase 12+).

### Subagent-Brief

```
Task 11.6 — Acceptance-Checklist.

Files: docs/PHASE-11-CHECKLIST.md.

Spec: docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md (§10).

Schreibe Checklist im Stil von PHASE-10A-CHECKLIST.md / PHASE-10B-CHECKLIST.md
(Files lesen, Format spiegeln). 6 User-Sichtprüfungs-Items laut Plan-Akzeptanzkriterien.
Acceptance-Block mit pytest-Output. Carry-Over-Section.
```

### Definition of Done

- Checklist existiert.
- User hat alle 6 Items abgehakt (in einer eigenen Sichtprüfungs-Phase NACH Task 11.5).

---

## Übergreifende Constraints (alle Tasks)

1. **Test-Runner Pflicht:** `.venv/Scripts/python.exe -m pytest …`. Nie bare pytest, nie system python (Memory: `project_test_runner_uses_venv.md`).
2. **Codex-Verifier nach jedem Task** (CLAUDE.md-Regel "Codex Review (abgestuft)").
3. **Codex-Security** zusätzlich nach Task 11.3 (Privacy-Boundary erweitert).
4. **Commit-Message-Konvention:** `living-vault | Phase-11.X: <knapper-status>`.
5. **Sprache:** Code/Identifier Englisch, User-Kommunikation Deutsch.
6. **Master-Plan-Status-Update** nach Task 11.6: ⏳ → ✅, plus separater Doku-Commit.
7. **Real-Wiki bleibt unangetastet** außer durch User-Befüllung von `docs/public-allowlist.txt`. Tests nutzen Fixtures.

## Übergreifender Acceptance-Pass

Nach Task 11.6, vor Master-Plan-Update:

```
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short
```

Erwartung: 204 + (5+3+4+1) = 217+ Tests grün.
