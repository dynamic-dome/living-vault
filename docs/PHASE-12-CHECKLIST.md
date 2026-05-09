# Phase 12 — séance MCP-Tool + commit_insight (CLOSED)

**Status:** ✅ CLOSED — 2026-05-10
**Tests:** 253/253 grün (vorher 218, +35)
**Spec:** [`superpowers/specs/2026-05-10-phase-12-seance-mcp-design.md`](superpowers/specs/2026-05-10-phase-12-seance-mcp-design.md)
**Plan:** [`superpowers/plans/2026-05-10-phase-12-seance-mcp.md`](superpowers/plans/2026-05-10-phase-12-seance-mcp.md)

## Sub-Tasks

| # | Titel | Status | Tests delta | Commit |
|---|---|---|---|---|
| 12.0 | Spec + Plan | ✅ | — | `283eb1e` |
| 12.1 | Insights-Tabelle + `core/insights.py` | ✅ | +9 | `66748ce` |
| 12.2 | Orchestrator-Refactor `apps/seance_ui/orchestrator.py` | ✅ | +12 | `09f34ae` |
| 12.3+12.4 | seance-MCP-Server (5 Tools) + entry point | ✅ | +14 | `334f00d` |
| 12.5 | Voll-Test-Pass | ✅ | — | (in 12.3) |
| 12.6 | Master-Plan ✅ + Close | ✅ | — | (this commit) |

## Akzeptanzkriterien (alle erfüllt)

- [x] `seance-mcp` startet als MCP-Server mit 5 Tools (`summon`, `say`, `commit_insight`, `list_insights`, `list_sessions`).
- [x] `seance.summon(page_paths=[X])` öffnet Single-Mode-Session, `seance.say` liefert Reply (mit FakeLLM in Tests).
- [x] `seance.summon(page_paths=[A,B], mode="roundrobin")` öffnet Roundtable-Session.
- [x] `seance.commit_insight(...)` legt Row an, `seance.list_insights(page_path=X)` findet sie wieder.
- [x] `tests/test_seance_*` + `tests/test_roundtable_*` weiterhin grün, Suite-Total ≥ 230 (tatsächlich 253).
- [x] FastAPI-UI bleibt funktionsfähig (kein Regression-Test bricht).
- [x] Codex-Verifier-Pass: User wählte `Keiner — direkt schließen`.

## Architektur-Entscheidungen (User-bestätigt 2026-05-10)

1. **Eigener MCP-Server** unter `living_vault/mcp_servers/seance/server.py` (NICHT als Tools im `vault_engine`-Server).
2. **Eigene DB-Tabelle** `insights` (NICHT Wiki-Page pro Insight, NICHT Frontmatter-Append).
3. **Multi-Page voll** mit `page_paths: list[str]` (kein Single-Path-Sonderfall).
4. **Vollausbau** in einer Session (alle 5 Tools statt Spec-Only).

## Wichtigste Outputs

### Neue Files (5)

- `living_vault/core/insights.py` — DB-CRUD für Insights (insert + get + list mit Filter)
- `living_vault/apps/seance_ui/orchestrator.py` — transport-neutrale Logik (~270 Zeilen, extrahiert aus app.py)
- `living_vault/mcp_servers/seance/__init__.py` — leer
- `living_vault/mcp_servers/seance/server.py` — FastMCP-Server, 5 Tools, ~165 Zeilen
- `tests/test_insights.py` (+9), `tests/test_seance_orchestrator.py` (+12), `tests/test_seance_mcp.py` (+14)

### Modifizierte Files (3)

- `living_vault/core/db.py` — `insights`-Tabelle in SCHEMA, additive Migration
- `living_vault/apps/seance_ui/app.py` — verschlankt von ~531 auf ~195 Zeilen (HTTP-Adapter)
- `pyproject.toml` — Entry-Point `seance-mcp = "living_vault.mcp_servers.seance.server:main"`
- `docs/plans/2026-05-08-living-vault-master-plan.md` — Phase-12-Status auf ✅

## Wichtigste Lessons

1. **Refactor zuerst, MCP-Layer danach.** Orchestrator-Extraktion (12.2) wurde bewusst VOR dem MCP-Server (12.3) gemacht. So konnte der Subagent in 12.2 sich voll auf "bestehende Tests grün halten" konzentrieren, und der MCP-Code in 12.3 wurde reiner Adapter-Code (~165 Zeilen).
2. **Monkeypatch-Fallstrick erkannt.** Der Subagent musste `get_llm()` lazy via `_app_mod.get_llm()` aufrufen, NICHT direkt importieren — sonst hätte `monkeypatch.setattr(app_mod, "get_llm", ...)` in den Roundtable-Tests den Orchestrator nicht erreicht. Subagent-Briefing hat den Fallstrick explizit benannt → korrekt umgesetzt.
3. **AskUserQuestion vor Spec.** 4 Optionen vorab geklärt (Server-Ort, Persistenz, Multi-Page, Scope) — Spec wurde linear, ohne Mid-Phase-Pivots wie sie in Phase 11 beim Embed-Ziel auftraten.
4. **Pattern aus Phase 11 wiederholt:** Subagent-driven für den nicht-trivialen Refactor (12.2), direkte Implementierung für mechanische Layers (12.1, 12.3, 12.4).

## Stats

| Metrik | Wert |
|---|---|
| Phase abgeschlossen in Session | 1 (Phase 12) |
| Commits | 5 (Spec+Plan + 12.1 + 12.2 + 12.3-4 + Close) |
| Code-Files neu/geändert | 4 neu + 3 modifiziert |
| Tests | 253/253 grün (+35 seit Phase 11) |
| Subagent-Dispatches | 1 (für 12.2 Refactor) |
| Codex-Verifier-Passes | 0 (User wählte "direkt schließen") |
| Master-Plan-Status | Phasen 0-12 ✅, Phase 13 ▶ NEXT |

## Carry-Over für spätere Phasen

- **Wiki-Export von Insights** als optionales `commit_insight --export`-Flag — Phase 12.x oder beim Bedarf.
- **Insights-Tags/Kategorien** via additive Migration falls nötig.
- **Volltext-/Semantic-Search über Insights** als zukünftiges Tool.
- **Bulk-Import** alter Sessions in `insights` — manuell falls nötig.
