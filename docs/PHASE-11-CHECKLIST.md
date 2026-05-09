# Phase 11 — Public Vault Acceptance Checklist

Per spec: [`docs/superpowers/specs/2026-05-09-phase-11-public-vault-design.md`](superpowers/specs/2026-05-09-phase-11-public-vault-design.md)
Per plan: [`docs/superpowers/plans/2026-05-09-phase-11-public-vault.md`](superpowers/plans/2026-05-09-phase-11-public-vault.md)
Deploy doc: [`DEPLOY-PUBLIC-VAULT.md`](DEPLOY-PUBLIC-VAULT.md)

## Automated Acceptance

- [x] Allowlist-Layer Tests green: 6 tests in `test_privacy.py` (1 original + 5 added in Task 11.1)
- [x] Layout-with-Allowlist Tests green: 4 tests in `test_layout.py` (unchanged signature, default `allowlist=None`)
- [x] Privacy-Regression Tests green: 5 tests in `test_privacy_regression.py` (2 original + 3 added in Task 11.2)
- [x] Public-Build CLI Tests green: 8 tests in `test_synesthesia_render.py` (2 original + 4 added in Task 11.3 + 2 added in Task 11.4)
- [x] PCA-pad fix verified for n_samples<3 (no IndexError on c[2])
- [x] `synesthesia-public-build` entry point installed and callable
- [x] Existing `synesthesia` CLI unchanged (backward-compatible)
- [x] Full suite: `.venv/Scripts/python.exe -m pytest tests/ -q` reports **216 passed, 0 failed** (was 204 at end of Phase 10b; +12 tests for Phase 11.1+11.2+11.3+11.4)

## Test Count Evolution

| Phase | Tests added | Total |
|---|---|---|
| Phase 10b closed | — | 204 |
| Task 11.1: allowlist-layer | +5 | 209 |
| Task 11.2: privacy-regression tightened | +3 | 212 |
| Task 11.3: public-build CLI | +4 | 216 |
| Task 11.4: brand header / embed-url propagation | +2 | 218 |
| **Phase 11 final** | **+14** | **218** |

(Plan estimated +12 tests; we landed at +14 because the determinism test got a privacy-canary assert and Task 11.4 added two header-presence tests instead of one.)

## Code-Architecture Decisions Confirmed

- **Allowlist is a runtime filter, not a DB column.** No schema migration. The same vault can produce different public builds depending on which allowlist file is passed.
- **`public_build_cli` is a standalone @click.command, NOT a subcommand of the legacy `synesthesia` CLI.** Two entry points coexist (`synesthesia` + `synesthesia-public-build`). Backward-compat for the existing CLI is the priority.
- **Brand block in `vault-3d.html.j2` is wrapped in `{% if embed_url %}`.** Legacy renders (without those template vars) stay byte-identical to pre-Phase-11 builds.
- **Determinism test relaxed:** `index.html` is compared modulo build-stamp lines (lines containing "Build " or "Stand "). `pages.json` remains byte-identical. `manifest.json` differs only in `build_at`.

## Live-DB Smoke (User-Sichtprüfung)

Two-stage flow: (1) build with empty allowlist to verify the pipeline works against the real DB; (2) build with curated allowlist to verify the privacy boundary holds.

### Setup

```powershell
# Aus dem Project-Root:
.venv\Scripts\pip install -e .  # einmal nach Phase-11 (registriert synesthesia-public-build)

# Sicherstellen, dass die DB aktuell ist:
.venv\Scripts\living-vault index --vault $HOME\wiki --db $HOME\wiki\.vault-engine.db
```

### Stage 1: Frontmatter-only build (sanity check) ✅

- [x] `.\scripts\deploy-public-vault.ps1`
- [x] Stdout zeigt `public_total = 0` (Stand 2026-05-09: keine Page mit `public: true`)
- [x] `out-vault\manifest.json` existiert, `public_via_frontmatter = 0`, `public_via_allowlist = 0`
- [x] `out-vault\index.html` existiert (rendert leeren Vault)

User-Verdikt: "sieht ok aus" — Pipeline läuft sauber gegen die Real-DB (953 Pages indexiert, vault_root korrekt).

### Stage 2: Allowlist-curated build ✅

- [x] `docs\public-allowlist.txt` mit 10 Wiki-Pfaden befüllt (3 Cluster: MCP/Agentic, Living-Vault-Meta, Mikromagnetik/3MA/NDT)
- [x] `.\scripts\deploy-public-vault.ps1 -OpenManifest`
- [x] Stdout zeigt `public_total = 10`, `edges_total > 0` (4 Edges: 3ma-ml→3ma-x8, barkhausenrauschen↔3ma-x8 doppelt, agentic-trends→agent-sdk)
- [x] `manifest.allowlist_skipped` leer (alle 10 Pfade existieren in der DB)

### Stage 3: Visual Sichtprüfung ✅

- [x] `out-vault\index.html` lokal im Browser geöffnet
- [x] 3D-Vault rendert: 10 Knoten, wenige Edges (erwartetes Verhalten: meiste Wikilinks der 10 Pages zeigen auf Pages außerhalb der Allowlist; mehr Edges → mehr Allowlist-Coverage)

User-Verdikt: "okay, also geht, aber sind halt nur 10 punkte die nicht verbunden sind :D" → "nicht ganz keine edges aber wenige eben"

### Stage 4: Privacy-Spot-Check ✅

- [x] Privacy-Filter hält: Edge-Filter zeigt nur Verbindungen wo BEIDE Endpoints in der Allowlist stehen — Pages außerhalb der Allowlist erscheinen weder als Knoten noch werden sie über Edges referenziert.
- [x] Vault-Total (953) wird im Header transparent angezeigt — Besucher sehen, dass nur ein kuratierter Subset gezeigt wird.

### User-Sichtprüfungs-Verdikt: ✅ POSITIV
("okay, also geht" + "nicht ganz keine edges aber wenige eben" — Pipeline funktioniert, Privacy-Filter hält, Build reproduzierbar gegen Live-DB.)

## Deploy-Status

Phase 11 endet **mit dem Build-Bundle**. Tatsächliches Hosting (Cloudflare Pages /
Netlify / GitHub Pages + DNS für `vault.dynamic-dome.com`) ist User-Action und
**nicht** Teil der Definition of Done dieser Phase.

Optional weiter über `-DeployTarget`:

- [ ] `./scripts/deploy-public-vault.ps1 -DeployTarget '<host-source-dir>'` kopiert `out-vault/` an gewünschten Host-Source.
- [ ] Hosting-spezifischer Trigger laut [`DEPLOY-PUBLIC-VAULT.md`](DEPLOY-PUBLIC-VAULT.md).
- [ ] DNS für `vault.dynamic-dome.com` gesetzt.

## Carry-Over (explizit für spätere Phasen)

- **Phase 12+ (Interaktive UI):** Slider, Filter, Custom-Coloring, Layout-Persistence aus [`TODO-PHASE-2-SYNESTHESIA.md`](TODO-PHASE-2-SYNESTHESIA.md) Big-Ticket-Backlog.
- **Phase 12+ (variant-Templates mit Header):** Aktuell nur `vault-3d.html.j2` hat Phase-11-Header. `galaxy/city/network` rendern korrekt aber ohne Brand-Block. Niedriges Tasks-Lift wenn gewünscht.
- **Phase 13+ (Auto-Sync-Hook):** Wiki-Änderung → automatischer Build-Trigger. Aktuell User-getrieben.
- **Codex-LOW-Befund 11.1 (SQLite IN-Clause-Limit):** `public_pages()` und `allowlist_skipped()` nutzen `IN ({placeholders})`. Bei sehr großer Allowlist (>~999 Einträge je nach SQLite-Compile-Flag) kann das stoßen. Praxis-Auswirkung: keine — Allowlists sind kuratiert (~5-50 Einträge). Falls jemals nötig: chunked Query oder Tabelle-mit-temp-allowlist.
- **Embed-Iframe in dome-dynamics oder cv.dynamic-dome.com:** Eigene Phase, nicht Phase 11.

## Phase-11 Status: ✅ CLOSED 2026-05-09

Automated acceptance complete (218/218 tests green). User-Sichtprüfung der
Live-DB-Smoke positiv verifiziert: Pipeline funktioniert end-to-end gegen
953 Real-Wiki-Pages, 10 kuratierte Public-Pages mit 4 Edges, Privacy-Filter
hält, Build reproduzierbar.

Allowlist-Pflege ist laufender Prozess (kein Phase-Scope) — User entscheidet
organisch welche Pages dazu kommen. Bridge-Pages für mehr Edge-Density
(`model-context-protocol`, `magnetische-hysterese`, `multi-agenten-systeme`,
`agents-und-parallelisierung`, `feature-selektion-pipeline`) sind als
optionaler nächster Schritt im Iteration-Log notiert.

Tatsächlicher Live-Deploy auf vault.dynamic-dome.com ist User-Action ohne
Phase-Scope — DNS, Hosting-Account und CDN bleiben getrennt vom Code-Pfad.

8 Commits gesamt für Phase 11 (e706907 spec+plan, 9d1af0d 11.1, 2b08242
+ 0f77072 11.2, ed01a9e 11.3, fa1b638 11.4, def5a3b 11.5, 60e3150 11.6).
