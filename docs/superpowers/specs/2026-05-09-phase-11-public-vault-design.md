# Phase 11 — Public Vault (Synesthesia public subset + standalone Embed)

**Datum:** 2026-05-09
**Status:** approved (User: "passt so")
**Phase:** Master-Plan Row 11 (originär `Phase 10` der trio-design, durch User-Pick-Phase-10a/10b verschoben)
**Master-Plan:** [`../../plans/2026-05-08-living-vault-master-plan.md`](../../plans/2026-05-08-living-vault-master-plan.md)
**Backlog-Quelle:** [`../../TODO-PHASE-2-SYNESTHESIA.md`](../../TODO-PHASE-2-SYNESTHESIA.md)
**Trio-Design (Section #33):** [`2026-05-08-living-vault-trio-design.md`](2026-05-08-living-vault-trio-design.md)

---

## 1. Ziel

Eine **privacy-disziplinierte, kuratierte Teilmenge** des Vault wird als statisches HTML-Bundle gerendert und auf einer eigenen Subroute (`vault.dynamic-dome.com`) gehostet. Default-private bleibt die Default-Privacy-Posture des Engines: **es zeigt sich nur, was explizit freigegeben ist**.

Sichtbares Endergebnis:

```
vault.dynamic-dome.com
  ↓
  ┌─ Header: "vault.dynamic-dome.com — n öffentliche Pages aus 953 (Stand: 2026-MM-DD)"
  ├─ 3D-Vault (variant=galaxy oder default), nur public Subset
  ├─ Edges nur zwischen public Pages (privacy-leak-free)
  └─ Footer: build-stamp + manifest-link
```

Phase 11 erweitert die bestehende Synesthesia-Pipeline (Phase 4) um ein Allowlist-Layer und einen `public-build`-Subcommand, der ein deploy-fertiges Verzeichnis produziert. Phase 11 baut **kein** Embed in `cv.dynamic-dome.com` und **kein** Iframe in `dome-dynamics` — das ist eine separate Phase.

## 2. User-getroffene Entscheidungen (nicht neu verhandeln)

Aus der Phase-11-Klärung 2026-05-09:

1. **Embed-Ziel: eigene Subroute** `vault.dynamic-dome.com` — kein Eingriff in CV-Site oder dome-dynamics-Portfolio.
2. **Public-Subset-Quelle: Frontmatter `public: true` ODER Allowlist-Datei** — Union aus beiden Quellen. Maximale Flexibilität bei kontrolliertem Code-Pfad.
3. **Allowlist-Format:** Plain-Text-Datei (`docs/public-allowlist.txt`), eine relpath pro Zeile, `#`-Kommentare und Leerzeilen erlaubt.
4. **Allowlist-Disziplin:** Nicht-existierende Pfade in der Allowlist sind kein Fehler (silent skip), werden aber im Build-Manifest als "skipped" geloggt.
5. **Privacy-Default behält Vorrang.** Kein Page wird public, wenn nicht eines der beiden Kriterien explizit erfüllt ist.
6. **Phase 11 enthält keine Interaktiv-UI** (Slider, Filter, Custom-Coloring aus `TODO-PHASE-2-SYNESTHESIA.md` Big-Ticket-Backlog) — das ist Phase 11+ oder später.
7. **DNS/Hosting ist User-Action.** Phase 11 produziert ein deploy-fertiges Verzeichnis, das User per Static-Hosting (Cloudflare Pages, Netlify, GitHub Pages, Plain-S3) ausliefert.
8. **Spec/Plan-Cycle wie Phase 10a/10b.** Subagent-driven-development, Codex-Verifier nach jedem Task, Codex-Security wegen Privacy-Boundary.

## 3. Architektur

```
┌──────────────────────────────────────────────────────────────────────┐
│ docs/public-allowlist.txt                                            │
│   # einer pro Zeile, # = Kommentar                                   │
│   concepts/a2a-protokoll.md                                          │
│   sources/mcp-oekosystem/index.md                                    │
│   ...                                                                │
└──────────────────────────┬───────────────────────────────────────────┘
                           ▼
        ┌────────────────────────────────────────┐
        │ core/privacy.py                         │
        │  • public_pages(con, allowlist=None)    │
        │    SELECT path FROM pages                │
        │    WHERE is_public = 1                   │
        │       OR path IN (?, ?, ?, ...)          │
        │    ORDER BY path                         │
        │  • load_allowlist(path) -> list[str]    │
        │    parse, strip comments+blank, return  │
        │  • allowlist_skipped(con, allowlist)    │
        │    [paths in allowlist not in pages]    │
        └──────────────────────────┬─────────────┘
                                   ▼
        ┌────────────────────────────────────────┐
        │ apps/synesthesia/layout.py              │
        │  compute_layout(db, public_only,        │
        │                  allowlist=None)         │
        │   ↓ delegiert an public_pages()         │
        └──────────────────────────┬─────────────┘
                                   ▼
        ┌────────────────────────────────────────┐
        │ apps/synesthesia/render.py              │
        │  cli (low-level) bleibt: --public-only  │
        │  + neuer Sub: public-build              │
        │    --vault, --db, --allowlist, --out    │
        │  produziert Verzeichnis:                │
        │    out/index.html                       │
        │    out/manifest.json                    │
        │    out/pages.json                       │
        └────────────────────────────────────────┘
                                   ▼
        ┌────────────────────────────────────────┐
        │ scripts/deploy-public-vault.ps1         │
        │ (oder docs/DEPLOY-PUBLIC-VAULT.md)       │
        │  rsync/cp ./out → static-host           │
        └────────────────────────────────────────┘
```

## 4. Schema-Änderungen

**Keine.** `pages.is_public` und der Frontmatter-Layer aus Phase 1 reichen aus. Allowlist ist ein **runtime-Filter**, kein DB-Zustand. Begründung: Allowlist ist ein Build-Artefakt (welcher Build zeigt was), nicht ein Page-Zustand (was ist Page X).

Das hat den Nebeneffekt: derselbe `is_public=0`-Page kann in Build-A drin sein (in Allowlist), in Build-B nicht (Allowlist-Diff). Das ist gewollt — Build-Reproducibility wird über das Manifest abgesichert (siehe §6).

## 5. Privacy-Regression-Disziplin

Privacy ist die **kritische Boundary** der Phase 11. Drei Risiko-Klassen:

| Risiko | Gegenmaßnahme |
|---|---|
| Frontmatter-Drift (Page wird versehentlich `public: true`) | Bestehender `test_no_private_path_in_public_synesthesia_build` deckt das ab. Erweitern um Allowlist-Path. |
| Allowlist-Drift (User trägt versehentlich private Page ein) | **Diese ist der Punkt:** Allowlist ist explizit User-kuratiert, kein Drift-Schutz. Per Design ist Allowlist ein "Override-public" und der User trägt die Verantwortung. Kein automatisches Veto. |
| Edge-Leakage (private→public-Edge sichtbar als Halbedge) | Bestehende `compute_layout`-Logik filtert Edges nur zwischen Pages-im-Filter — also gilt: ist Page X allowed, Page Y nicht, dann Edge X→Y wird **nicht** gerendert. Test bestätigt das. |
| Body-Leakage (private body excerpt im public html) | Synesthesia-Template rendert nur `path`, `title`, `cluster`, `mtime`, `degree` und Koordinaten. Kein Body. Bestätigt durch Code-Inspektion (`render.py:render_html`). |
| Allowlist mit Tippfehler (Pfad existiert nicht) | Silent skip, aber im Manifest-`skipped`-Array geloggt → User sieht das im Acceptance-Lauf. |

**Test-Erweiterungen Phase 11:**

1. `test_public_pages_union_with_allowlist` — public_pages liefert public ∪ allowlist
2. `test_load_allowlist_strips_comments_and_blanks` — Format-Tolerance
3. `test_allowlist_with_nonexistent_paths_skipped_silently` — kein Crash, in skipped-Liste
4. `test_no_private_path_in_public_build_with_allowlist` — Privacy-Regression-Variante mit Allowlist-Override
5. `test_public_build_manifest_has_all_required_fields` — Manifest-Schema-Stabilität
6. `test_public_build_is_deterministic` — gleicher Vault + gleiche Allowlist + gleiche DB → byte-identisches HTML (außer mtime/build_at)

## 6. Public-Build-Output-Schema

`synesthesia public-build` produziert ein Verzeichnis:

```
out/
├── index.html        # 3D-Vault, public subset only
├── manifest.json     # Build-Metadaten (siehe unten)
├── pages.json        # Liste der gebauten Pages (paths only)
└── (zukünftig:       # Phase 11+ Big-Ticket-Backlog
    ├── slider.html   #   Interaktive Variante
    ├── ...)
```

**`manifest.json`-Schema:**

```json
{
  "schema_version": 1,
  "build_at": "2026-05-09T12:34:56Z",
  "vault_root": "C:\\Users\\domes\\wiki",
  "vault_total_pages": 953,
  "public_via_frontmatter": 0,
  "public_via_allowlist": 7,
  "public_total": 7,
  "allowlist_path": "docs/public-allowlist.txt",
  "allowlist_skipped": [
    "concepts/typo-page-doesnt-exist.md"
  ],
  "edges_total": 12,
  "variant": "default",
  "embed_url": "https://vault.dynamic-dome.com",
  "build_tool": "living_vault.apps.synesthesia public-build",
  "engine_version": "0.1.0"
}
```

`embed_url` ist informativ (zur User-Doku, nicht funktional verlinkt). Die HTML-Datei selbst ist absolute-link-frei und auf jeder Subroute deploy-bar.

## 7. CLI-Surface

Bestehend (bleibt):

```
synesthesia --db <path> --output <html> [--public-only] [--variant default|galaxy|city|network]
```

Neu (additiv):

```
synesthesia public-build \
  --vault <vault-root> \
  --db <path-to-db> \
  --allowlist <path/to/allowlist.txt> \
  --out <out-dir> \
  [--variant default|galaxy|city|network] \
  [--embed-url https://vault.dynamic-dome.com]
```

Verhalten:

- Erstellt `out-dir` falls nicht da, **überschreibt** `index.html`/`manifest.json`/`pages.json` falls da.
- Idempotent gegen denselben Input (siehe Determinismus-Test).
- Exit 0 wenn Build success (auch bei skipped-allowlist-Pfaden), Exit 2 bei DB-fehlt/Vault-fehlt/Allowlist-Path-fehlt.
- Schreibt 1-Zeilen-Summary auf stderr: `wrote out/ (n public, k skipped, edges=e)`.

## 8. Sub-Phasen-Schnitt

Wie im User-Vorgespräch festgelegt:

| # | Aufgabe | Files | Tests | LOC-Schätzung |
|---|---------|-------|-------|---------------|
| 11.1 | Allowlist-Layer | `core/privacy.py`, `apps/synesthesia/layout.py` (signature ext.) | `test_privacy.py` (+5 Tests) | ~80 |
| 11.2 | Privacy-Regression-Verschärfung | `tests/test_privacy_regression.py` (+3 Tests), Real-Wiki-Snapshot-Fixture | (pure tests) | ~60 |
| 11.3 | Public-Build CLI | `apps/synesthesia/render.py` (neuer Subcommand) | `test_synesthesia_render.py` (+4 Tests) | ~100 |
| 11.4 | Cluster-Header über 3D | `apps/synesthesia/templates/*.j2` (Header-Block) | UI-Snapshot-Test (string-match) | ~50 |
| 11.5 | Deploy-Skript + Doku | `scripts/deploy-public-vault.ps1`, `docs/DEPLOY-PUBLIC-VAULT.md` | (none, Doku) | ~80 |
| 11.6 | Acceptance-Checklist | `docs/PHASE-11-CHECKLIST.md` | (none) | ~50 |

**Reihenfolge ist linear** — 11.2 hängt von 11.1 ab (Allowlist-API), 11.3 von 11.1+11.2, 11.4 baut auf 11.3 auf. 11.5+11.6 parallel zu 11.4 möglich.

## 9. Risiken und Gegenmaßnahmen

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| User vergisst Allowlist-Datei vor erstem Build | Hoch | `--allowlist` ist optional; ohne Allowlist wird nur Frontmatter-public gefiltert (was aktuell 0 Pages = leerer Vault). Manifest macht das sichtbar. |
| Allowlist-Tippfehler führt zu silent miss | Mittel | `manifest.allowlist_skipped` zeigt jeden Skip. Acceptance-Checkliste verlangt Sichtprüfung. |
| Layout instabil bei sehr kleiner Page-Zahl (n=1, n=2) | Mittel | `_pca_3d` schon defensive (n=1 → origin). Test für n=1, n=2, n=3 expliziert. |
| Build-Determinismus-Drift | Niedrig | `test_public_build_is_deterministic` direkt im Acceptance-Set. Manifest enthält build_at als einzige zeitabhängige Variable. |
| Subroute-Hosting-Setup fehlt User | Niedrig | DEPLOY-PUBLIC-VAULT.md gibt drei konkrete Hosting-Pfade (Cloudflare Pages, Netlify, GH-Pages). |
| Phase 11 wird zur UI-Überarbeitung gepulled (Slider/Filter aus Backlog) | Hoch | **Spec-Disziplin: Phase 11 enthält keine Interaktiv-UI.** Big-Ticket-Backlog explizit als Phase 12+ verschoben. |

## 10. Definition of Done

Phase 11 ist erledigt, wenn:

1. `synesthesia public-build` läuft auf der Real-DB unter `~/wiki/.vault-engine.db` und produziert `out/` Verzeichnis.
2. Privacy-Regression-Tests grün (alle alten + alle neuen aus §5).
3. `docs/PHASE-11-CHECKLIST.md` mit User-Sichtprüfung abgehakt:
   - User hat Allowlist mit 3-7 Pages befüllt
   - User hat Build laufen lassen
   - User hat `out/index.html` lokal im Browser geöffnet
   - User hat manifest.json gelesen, skipped-Liste verifiziert
4. Master-Plan-Tabelle: Phase 11 ⏳ → ✅, Commit `living-vault | Phase-11 ✅ CLOSED — Sichtpruefung positiv YYYY-MM-DD`.
5. Deploy-Skript existiert; tatsächlicher Live-Deploy auf `vault.dynamic-dome.com` ist **nicht Teil** der Definition of Done — der ist User-Action nach Phase-11-Close.

## 11. Out-of-Scope (explizit verschoben)

- Interaktive UI (Slider/Filter/Custom-Coloring) → Phase 12+
- Hybrid-Variant (galaxy + network mix) → Phase 12+
- Layout-Persistence (Drag-and-drop von Knoten, lokales State-File) → Phase 12+
- DNS-Setup `vault.dynamic-dome.com` → User-Action, nicht Code
- Embed-Iframe in `cv.dynamic-dome.com` oder `dynamic-dome.com` → eigene Phase, nicht Phase 11
- Auto-Sync-Hook (Wiki-Änderung → Build-Trigger) → Phase 13+ Operating-System-Schicht

## 12. Referenzen

- Phase 4 (synesthesia Phase 1, lokal-only): `apps/synesthesia/render.py`, `apps/synesthesia/layout.py`
- Privacy-Layer Phase 1: `core/privacy.py`
- Privacy-Regression-Test Phase 7: `tests/test_privacy_regression.py`
- Backlog (Phase 11+): `docs/TODO-PHASE-2-SYNESTHESIA.md`
- Trio-Design Section #33 (Hosting): `docs/superpowers/specs/2026-05-08-living-vault-trio-design.md`
- Master-Plan: `docs/plans/2026-05-08-living-vault-master-plan.md`
