# Last Session — living-vault

*Datum: 2026-05-09*
*Agent: Claude Opus 4.7 (1M context)*
*Phase: 11 (Synesthesia public subset + standalone Embed)*

## Headline

**Master-Plan-Phase 11 komplett ✅ in einer Session,** 9 Commits, +14 Tests
(204 → 218 grün), Live-DB-Sichtprüfung positiv mit 953 Real-Pages und
10-Page-kuratierter Allowlist.

Phase 11 hat sich gegen Embed in CV/dome-dynamics entschieden und stattdessen
eine **Standalone-Subroute-Architektur** gebaut: `synesthesia-public-build`
produziert ein deploy-fertiges Bundle (`out-vault/`) für `vault.dynamic-dome.com`,
mit Allowlist-Layer als Laufzeit-Filter (kein DB-Schema-Eingriff).

## Was funktioniert jetzt

### Phase 11 — Public Vault (standalone)

**Allowlist-Layer (`core/privacy.py`):**
- `public_pages(con, allowlist=None)` liefert Union: `WHERE is_public=1 OR path IN (...)`. Backwards-kompatibel mit Default `allowlist=None`.
- `load_allowlist(path)` parst Plain-Text-Datei (eine relpath/Zeile, `#`-Kommentare, utf-8).
- `allowlist_skipped(con, allowlist)` liefert Pfade die im Allowlist stehen aber nicht in der DB existieren — fürs Build-Manifest.

**Public-Build CLI (`synesthesia-public-build`, neuer Entry-Point):**
- Standalone @click.command (NICHT subcommand des bestehenden `synesthesia` — Backwards-Compat).
- Produziert `out-vault/index.html` (3D-Vault, public-only) + `manifest.json` (Schema v1, 14 Felder) + `pages.json` (sortierte Page-Liste).
- Default `--embed-url=https://vault.dynamic-dome.com`, override via Flag.

**3D-Template-Brand-Header (`vault-3d.html.j2`):**
- Header-Block oben: `vault.dynamic-dome.com · N öffentliche Pages aus 953 · Stand YYYY-MM-DD`
- Footer-Block unten: `Build YYYY-MM-DDTHH:MM:SSZ · schema v1`
- CSS-only, system-font-stack, pointer-events:none (canvas bleibt orbit/zoom-fähig).
- Wrapped in `{% if embed_url %}` — Legacy-Renders ohne diese Vars sind byte-identisch zu Pre-Phase-11.

**Deploy-Skript + Doku:**
- `scripts/deploy-public-vault.ps1`: PowerShell-Wrapper, ruft `synesthesia-public-build.exe` mit sane defaults (`$HOME\wiki`, `$HOME\wiki\.vault-engine.db`, `docs/public-allowlist.txt`, `out-vault`). Optional `-DeployTarget`, `-OpenManifest`.
- `docs/DEPLOY-PUBLIC-VAULT.md`: Quick-Start, Allowlist-Workflow, drei Hosting-Pfade (Cloudflare Pages / Netlify / GitHub Pages), DNS, Troubleshooting.
- `docs/public-allowlist.txt`: 10 kuratierte Pages aus 3 Clustern (MCP/Agentic, Living-Vault-Meta, Mikromagnetik/3MA/NDT).

### Sichtprüfung 2026-05-09 (positiv)

- **Stage 1 (frontmatter-only build):** `public_total=0`, Pipeline läuft sauber. User-Verdikt: "sieht ok aus".
- **Stage 2 (allowlist-curated):** `public_total=10`, `edges_total=4` (3ma-ml→3ma-x8, barkhausenrauschen↔3ma-x8 doppelt, agentic-trends→agent-sdk). User-Verdikt: "okay, also geht".
- **Stage 3 (visual):** 3D-Vault rendert lokal mit 10 Knoten, 4 Edges, Header sichtbar. User-Verdikt: "nicht ganz keine edges aber wenige eben".
- **Stage 4 (privacy):** Edge-Filter hält — Pages außerhalb der Allowlist erscheinen weder als Knoten noch als Edge-Endpoints.

## Schema-Stand

**Keine Schema-Änderungen.** Allowlist ist Laufzeit-Filter, kein DB-Zustand.
Begründung: derselbe Vault kann verschiedene Public-Builds produzieren je nach
Allowlist-Wahl. Build-Reproducibility wird über das Manifest abgesichert
(byte-deterministischer index.html + pages.json modulo build_at).

## Wichtigste Code-Outputs

### Neue Files (10)

- `living_vault/apps/synesthesia/templates/vault-3d.html.j2` (erweitert, +19 Zeilen Header)
- `tests/test_synesthesia_render.py` (+213 Zeilen, +6 Tests)
- `tests/test_privacy_regression.py` (+67 Zeilen, +3 Tests)
- `tests/test_privacy.py` (+46 Zeilen, +5 Tests)
- `scripts/deploy-public-vault.ps1` (NEU, 96 Zeilen)
- `docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md` (NEU, 240 Zeilen)
- `docs/superpowers/plans/2026-05-09-phase-11-public-vault.md` (NEU, 372 Zeilen)
- `docs/PHASE-11-CHECKLIST.md` (NEU, 120 Zeilen)
- `docs/DEPLOY-PUBLIC-VAULT.md` (NEU, 154 Zeilen)
- `docs/public-allowlist.txt` (NEU, 26 Zeilen, 10 kuratierte Pages)

### Erweiterte Files (5)

- `living_vault/core/privacy.py` (+50 Zeilen: 3 neue Funktionen)
- `living_vault/apps/synesthesia/layout.py` (+20 Zeilen: allowlist-Param + PCA-pad-Fix)
- `living_vault/apps/synesthesia/render.py` (+165 Zeilen: public_build + public_build_cli)
- `pyproject.toml` (+1 Zeile: synesthesia-public-build entry point)
- `docs/plans/2026-05-08-living-vault-master-plan.md` (Phase-11-Status auf ✅)

### Stats

- 16 Files geändert, +1580 / -13 Zeilen
- 9 Commits (e706907 spec+plan, 9d1af0d 11.1, 2b08242 + 0f77072 11.2, ed01a9e 11.3, fa1b638 11.4, def5a3b 11.5, 60e3150 11.6, b076678 close)
- 218 Tests grün (Phase 10b endete bei 204, +14)
- 1 Codex-Verifier-Pass nach Task 11.1 (1 LOW-Finding, geparkt als Carry-Over)

## Methodik die wirkte

1. **Subagent-driven-development pro Task** wie in Phase 10a/10b. Bei 6 Sub-Tasks
   nur 1 Bug aus der Subagent-Arbeit (PCA-Pad bei n<3) — der war ein
   Edge-Case-Vorsorge-Fix, keine Regression.
2. **Codex-Verifier nach Task 11.1** lieferte 1 LOW-Befund (SQLite-IN-Limit) —
   bewusst geparkt statt sofort gefixt, weil praxis-irrelevant für kuratierte
   Allowlists. Vermeidet Scope-Creep.
3. **Click-Variante-B (zwei Entry-Points statt @click.group)** war die richtige
   Backwards-Compat-Entscheidung. Im Plan explizit notiert, sodass kein
   Subagent versuchen konnte den bestehenden CLI in eine Group umzubauen.
4. **Brand-Header in `{% if embed_url %}`-Block** hält Legacy-Renders byte-identisch.
   Verifiziert durch unveränderten `test_render_writes_html`.

## Drei kritische Momente

1. **Embed-Ziel-Entscheidung mit dem User vor dem Spec-Schreiben.** Master-Plan
   sagte "synesthesia public subset + portfolio 3D-Embed", aber die Kontext-Lage
   widersprach: `cv.dynamic-dome.com` ist statisches CV mit `noindex,nofollow`
   (kein Slot für Living-Embed), `dynamic-dome.com` Phase-5 wurde gerade
   abgeschlossen ohne dort einen Vault-Slot vorzusehen. AskUserQuestion mit
   4 Embed-Optionen → User wählt "eigene Subroute". Das hat den ganzen Spec-Cut
   geprägt — ohne diese Entscheidung wäre Phase 11 mit falschem Embed-Ziel
   gestartet.

2. **PCA-IndexError in Test-Fixture.** Beim Schreiben der Privacy-Regression-Tests
   crashte `_pca_3d` mit `IndexError` auf `c[2]`, weil 2-Page-Allowlist nur
   2 SVD-Komponenten lieferte. Der Subagent fand und fixte das selbst (Zero-Pad
   bei <3 Spalten). Production-Vaults mit >>3 Pages waren nie betroffen — aber
   ohne den Test-Edge-Case wäre der Bug unentdeckt geblieben. Lesson: Tests
   mit minimalen Fixtures finden Bugs, die produktive Daten verstecken.

3. **Bridge-Pages-Erkenntnis bei Sichtprüfung.** Die initial-kuratierte
   10-Page-Allowlist produzierte nur 4 Edges, weil die meisten Wikilinks der
   10 Pages auf nicht-allowlisted Pages zeigten. User-Reaktion "nur 10 punkte
   die nicht verbunden sind". Diagnose ergab: 5 "Bridge-Pages" wären
   überproportional wertvoll für Edge-Density (`model-context-protocol`,
   `magnetische-hysterese`, `multi-agenten-systeme`, `agents-und-parallelisierung`,
   `feature-selektion-pipeline`). User entschied "Phase-11 erst schließen,
   Allowlist später erweitern" — saubere Scope-Disziplin statt Phase-11-Ende
   zu verzögern.

## Patterns aktualisiert / NEU

(Pattern-Extractor übersprungen: errors.json + patterns.json beide leer, kein
Evidenz-Base. Phase 11 produzierte 7 high-quality Learnings als Iteration-Log-
Einträge, aber keine echten Bugs.)

## Codex-Externer-Pass (User-Plan)

User hat NICHT angekündigt einen externen Codex-Pass über den Phase-11-Diff
laufen zu lassen ("ne, passt so" auf Codex-Security-Anfrage). Der Codex-Verifier-
Pass nach Task 11.1 ist die einzige unabhängige Sicht — Befund war 1 LOW
(SQLite-IN-Limit), als Carry-Over geparkt.

## Offene Punkte / Carry-Over

### Hoch (Phase 12, sofort relevant)

- **Phase 12 = séance MCP-Tool + commit_insight** ist `▶ NEXT` im Master-Plan.
  Pflichtartefakte:
  - `seance.summon` als MCP-Tool exposen (aktuell nur via FastAPI-UI)
  - `seance.commit_insight` für Persona-Insight-Persistence
  - Multi-Page-Modus auch via MCP-Tool
- **Allowlist erweitern um Bridge-Pages** für mehr Edge-Density im Public-Build
  (organischer Prozess, kein Phase-Scope).

### Mittel

- **DNS + Hosting-Setup für `vault.dynamic-dome.com`** — User-Action, nicht Code
  (Cloudflare Pages / Netlify / GitHub Pages, alle drei in DEPLOY-PUBLIC-VAULT.md
  beschrieben).
- **Phase 13 = Version-History-Modal in living-portfolio**.

### Niedrig

- **Phase-9 content_hash Cache-Invalidation** (Wiki-TODO existiert).
- **Codex-LOW SQLite-IN-Limit** (in `public_pages` und `allowlist_skipped`) —
  bei Allowlist >999 Einträgen relevant, in Praxis irrelevant.
- **Variant-Templates galaxy/city/network mit Header** — aktuell nur
  `vault-3d.html.j2` hat Phase-11-Header. Niedriger Lift.
- **Backslash-Escape-Bug in Wiki-Reader** (`barkhausenrauschen\.md` als Edge-Pfad
  beobachtet — kaputter Wikilink-Parsing-Edge-Case, kein Phase-11-Blocker).

### Cross-Project

- **Dream-Team-Sprint** aus `~/wiki/wiki/synthesis/2026-05-09-claude-codex-self-evolving-dream-team.md`
  (User-Wunsch: frische Session mit großem Context, aus living-vault raus).

## Wiedereinstieg

1. `cd ~/Desktop/Claude-Projekte/living-vault && git log --oneline | head -15`
2. `cat docs/plans/2026-05-08-living-vault-master-plan.md` (Phase 11 ✅, Phase 12 ▶ NEXT)
3. `cat docs/PHASE-11-CHECKLIST.md` (alle Stages abgehakt, ✅ CLOSED)
4. `cat .agent-memory/iterations/iteration-log.md` (Iter #4 für Phase-11-Details)
5. Wenn Phase 12: `cat docs/superpowers/specs/2026-05-08-living-vault-trio-design.md` (Section
   #34 Frontends — MCP-Tool-Anforderungen). Brainstorming-Skill für Scope-Klärung,
   dann normaler Spec/Plan-Cycle.
6. Wenn Allowlist erweitern: `docs/public-allowlist.txt` editieren, dann
   `./scripts/deploy-public-vault.ps1 -OpenManifest`.

## Stats

| Metrik | Wert |
|---|---|
| Phase abgeschlossen in Session | 1 (Phase 11) |
| Commits | 9 (Spec+Plan + 6 Sub-Tasks + Close) |
| Code-Files geändert/neu | 11 (5 erweitert + 6 neu) |
| Doc-Files geändert/neu | 5 (1 Master-Plan-Update + 4 neu) |
| Tests | 218/218 grün (+14 seit Phase 10b) |
| Codex-Verifier-Passes | 1 (1 LOW-Finding, geparkt) |
| Subagent-Dispatches | 4 (3 Implementer + 1 Verifier) |
| Master-Plan-Status | Phasen 0-11 ✅, Phase 12 ▶ NEXT |
| Erfolgreichster Moment | Subagent-11.2 fand und fixte selbständig den PCA-IndexError-Edge-Case bei n<3 — Test-Driven Bug-Discovery in Aktion |
