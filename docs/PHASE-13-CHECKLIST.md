# Phase 13 — Version-History (CLOSED)

**Status:** ✅ CLOSED — 2026-05-10
**Tests:** 272/272 grün (vorher 253, +19)
**Spec:** [`superpowers/specs/2026-05-10-phase-13-version-history.md`](superpowers/specs/2026-05-10-phase-13-version-history.md)
**Plan:** [`superpowers/plans/2026-05-10-phase-13-version-history.md`](superpowers/plans/2026-05-10-phase-13-version-history.md)

## Sub-Tasks

| # | Titel | Status | Tests delta | Commit |
|---|---|---|---|---|
| 13.0 | Spec + Plan | ✅ | — | `63f7777` |
| 13.1 | `core/history.py` + TTL-LRU | ✅ | +10 | `2e2f814` |
| 13.2 | `vault-engine-mcp.page_history` Tool | ✅ | +2 | `4b5c947` |
| 13.3 | `public_build` schreibt `history.json` + manifest v2 | ✅ | +3 | `d3fcfab` |
| 13.4 | `vault-3d.html.j2` History-Panel | ✅ | +2 | `7e68ec0` |
| 13.5 | `living-vault history` CLI + Voll-Pass | ✅ | +2 | `(this file)` |
| 13.6 | Master-Plan-Korrektur + Close | ✅ | — | (this commit) |

## Akzeptanzkriterien (alle erfüllt)

- [x] `core.history.page_history(repo, "concepts/foo.md")` liefert 10-er Liste
      mit `{sha, date, author, subject}` für Test-Repo.
- [x] TTL-Cache funktioniert: 2× Aufruf mit gleichem Key macht subprocess nur 1×.
- [x] `vault-engine-mcp.page_history` MCP-Tool als Adapter funktioniert.
- [x] `synesthesia-public-build` schreibt `history.json` (default), `--no-history`
      schaltet ab.
- [x] `vault-3d.html.j2` mit `include_history=True` rendert History-Panel,
      ohne `include_history` byte-identisch.
- [x] CLI `living-vault history <path>` druckt tabellarische History.
- [x] Test-Suite-Total ≥ 270 grün (tatsächlich 272), keine Regression.
- [ ] Real-Run gegen `~/wiki` mit 10-Page-Allowlist (Sichtprüfung) — User-Action,
      offen.

## Architektur-Entscheidungen (User-bestätigt 2026-05-10)

1. **Display-Ort:** synesthesia-public Vault (`vault.dynamic-dome.com`), NICHT
   living-portfolio (Master-Plan-Korrektur).
2. **History-Tiefe:** Letzte 10 Commits, kompakt (sha + ISO-Datum + author + subject).
   Kein Diff, kein Snapshot.
3. **Caching:** Live `git log` via subprocess + TTL-LRU 60s. KEINE DB-Tabelle.
4. **Session-Scope:** Vollausbau (Engine + MCP + CLI + UI-Panel).

## Wichtigste Outputs

### Neue Files (3)

- `living_vault/core/history.py` — TTL-LRU + git-log-Wrapper, defensive Fallbacks
- `tests/test_history.py` (+10), Erweiterungen in `test_mcp_server.py` (+2),
  `test_synesthesia_render.py` (+5), `test_cli.py` (+2)

### Modifizierte Files (5)

- `living_vault/mcp_servers/vault_engine/server.py` — `page_history` MCP-Tool
- `living_vault/apps/synesthesia/render.py` — `include_history`-Param,
  `history.json`-Generation, `--no-history`-Flag, `manifest.schema_version=2`
- `living_vault/apps/synesthesia/templates/vault-3d.html.j2` — Hover-driven
  History-Panel, lazy-fetched aus `history.json`
- `living_vault/cli.py` — `living-vault history`-Subcommand
- `docs/plans/2026-05-08-living-vault-master-plan.md` — Phase-13-Eintrag
  korrigiert (von portfolio → synesthesia-public), Status auf ✅

## Wichtigste Lessons

1. **Master-Plan-Korrektur via AskUserQuestion erlaubt.** Original-Plan sagte
   "Version-History in living-portfolio" — die User-Entscheidung 2026-05-10
   verschob das nach synesthesia-public-Vault. Die Korrektur wurde im Spec
   explizit dokumentiert (`## Master-Plan-Korrektur`), nicht stillschweigend
   gemacht. Das ist der saubere Weg, wenn neue Phasen-Vorgänger den Kontext
   ändern (Phase 11 hatte synesthesia-public erst gebaut).
2. **Manifest-Schema-Bump v1 → v2 muss Tests anfassen.** `test_public_build_manifest_has_required_fields`
   prüfte `schema_version == 1` — das musste auf 2 + neue `history_included`-Key
   in der required-keys-Liste. Das war eine *erlaubte* Test-Änderung, weil
   das Schema sich tatsächlich geändert hat. Keine Regression.
3. **Defensive Fallbacks > Exceptions.** `page_history` wirft NIE — kein Git,
   kein Repo, kein File: alle liefern leere Liste. Build/MCP/CLI-Caller
   müssen nicht jede Fehlerquelle separat erkennen.
4. **Hover statt Click für History-Display.** Das aktuelle Template hatte
   keinen Click-Mechanismus, nur Raycaster-Hover. Spec-Original sah Click +
   Modal vor — Implementierung machte stattdessen Hover-Update auf bestehendes
   `#picked`-Layout. Pragmatischer und konsistent mit Page-Vorschau.
5. **TTL-LRU eigene Implementation > functools.lru_cache.** `functools.lru_cache`
   hat kein TTL — eigener kleiner Wrapper mit `dict[(key) → (timestamp, value)]`
   plus Eviction-on-Access ist besser als z.B. `cachetools` als neue Dependency.

## Stats

| Metrik | Wert |
|---|---|
| Phase abgeschlossen in Session | 1 (Phase 13) |
| Commits | 7 (Spec+Plan + 13.1 + 13.2 + 13.3 + 13.4 + 13.5 + Close) |
| Code-Files neu/geändert | 1 neu (core/history.py) + 4 modifiziert |
| Test-Files neu/geändert | 1 neu (test_history.py) + 3 erweitert |
| Tests | 272/272 grün (+19 seit Phase 12) |
| Subagent-Dispatches | 0 (alles direkt — kleine fokussierte Edits) |
| Codex-Verifier-Passes | 0 (User-Wahl wie Phase 12) |
| Master-Plan-Status | Phasen 0-13 ✅, Phase 14 ▶ NEXT (Abschluss-Synthese) |

## Carry-Over für spätere Phasen

- **Real-Run gegen `~/wiki`** für visuelle Sichtprüfung des History-Panels.
  User-Action: `./scripts/deploy-public-vault.ps1 -OpenManifest`.
- **`--follow` für Renames** im git-log-Aufruf (Phase 13.x).
- **Diff-Render im Panel** (Phase 13.x oder Phase 13+).
- **Author-Display im UI** — aktuell intern erfasst, aber nicht gerendert.
  Bei Multi-User-Wiki später nachziehen.
- **Performance-Test gegen 953-Page-Allowlist** — bei vollem Build ~50ms × 953
  ≈ 48s; aktuelle Allowlist ist 10 Pages, kein Issue. Cache hilft im Build
  nicht (jede Page nur 1x abgefragt).
- **Build-time-Optimization:** `git log --all` mit batch-output statt 953
  separater subprocess-Calls — Phase 13.x falls relevant.
