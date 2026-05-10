# Last Session — living-vault

*Datum: 2026-05-10*
*Agent: Claude Opus 4.7 (1M context)*
*Phasen: 12 + 13 + 14 + 13.x (Projekt-Abschluss)*

## Headline

**Living-Vault offiziell fertig. Phasen 12 + 13 + 14 in einer Session abgeschlossen,**
plus 13.x (`--follow` für Renames als Mini-Patch). 11 Commits, +20 Tests
(253 → 273 grün), 14 Phasen total über 3 Sessions (2026-05-08 → 2026-05-10).

## Was funktioniert jetzt

### Phase 12 — séance MCP-Tool

Neuer MCP-Server `seance-mcp` (Entry-Point in `pyproject.toml`) mit 5 Tools:
`summon`, `say`, `commit_insight`, `list_insights`, `list_sessions`. Architektur-
kern: in 12.2 wurde die transport-neutrale Logik aus `apps/seance_ui/app.py`
(~531 Zeilen) in `apps/seance_ui/orchestrator.py` (~270 Zeilen) extrahiert.
FastAPI-UI und MCP-Server greifen beide darauf zu — keine Code-Duplikation.
`SéanceError(code, detail)` mappt 1:1 auf HTTP-Status (400/404/410/413/502)
bzw. MCP-RuntimeError. Neue `insights`-Tabelle in `.vault-engine.db` mit
additive Migration (idempotent). `session_id` ist nullable, Standalone-Insights
ohne aktive Session erlaubt. 16k-char-Cap als Cost-Guard.

Subagent-driven-development für 12.2 Refactor — 1 Dispatch, 12/12 neue Tests
grün, alle 27 bestehenden UI-Tests unverändert grün. Subagent hat den
`monkeypatch.setattr(app_mod, "get_llm", ...)`-Fallstrick aus dem Briefing
korrekt gelöst (lazy `_app_mod.get_llm()`-Aufruf statt Direct-Import).

### Phase 13 — Version-History (in synesthesia-public Vault)

**Master-Plan-Korrektur:** Original-Plan sagte "Modal in living-portfolio".
User-Entscheidung 2026-05-10 verschob das in den Phase-11-synesthesia-public
Vault (`vault.dynamic-dome.com`) — konsistenterer Ort. Korrektur explizit
im Spec dokumentiert, nicht stillschweigend.

4-Layer-Stack: (1) `core/history.py` mit TTL-LRU-Cache 60s, walked von
vault_root nach oben bis zum nächsten `.git`-Verzeichnis, ASCII-Unit-
Separator (0x1F) im git-log-format, defensive Fallbacks (kein Git → leere
Liste statt Crash); (2) `vault-engine-mcp.page_history(path, limit=10)`
als MCP-Tool-Adapter; (3) `synesthesia-public-build` schreibt
`out-vault/history.json` (schema v1), `manifest.json` schema_version=2
mit `history_included: bool` (additive); (4) `vault-3d.html.j2` zeigt
Hover-driven History-Panel rechts unten (lazy fetch, max 10 Commits,
CSS-only). CLI: `living-vault history <path> --vault <root> [--limit N]`.

`include_history`-Default ist True — UI-Phase-11-Tests blieben durch
explizite Test-Updates auf `schema_version=2` und `history_included` in
required-keys grün. Der Phase-11-Determinismus-Test prüft `pages.json`
byte-identisch — neues `history.json` ist nicht im Vergleich, entkoppelt sauber.

### Phase 14 — Abschluss-Synthese

`~/wiki/wiki/synthesis/2026-05-10-living-vault-retro.md` mit current
thesis (3-Schichten-Modell mechanisch/semantisch/persona-haft + Privacy
als Architektur), 8 Supporting-Evidence-Punkte, 5 Counter-Evidence,
10 What-to-investigate-next-Items. `~/wiki/wiki/entities/living-vault.md`
neu angelegt mit `status: done`. Wiki-`log.md` + `index.md` aktualisiert.
Master-Plan-Phase 14 ✅, Aktuelle-Position-Block auf "Projekt offiziell
fertig". `docs/PHASE-14-CHECKLIST.md`. Wiki-Coverage-Gate beim Commit:
92.2% ≥ 85.0% pass.

### Phase 13.x — `--follow` für Renames (Mini-Erweiterung)

Eine Zeile in `core/history.py`: `--follow` als git-log-Argument. Effekt:
`page_history` zeigt jetzt die volle Geschichte einer Page auch über
`git mv`-Renames hinweg. Test mit Fixture-Repo (Commit → Edit → Rename →
Edit) verifiziert 4 Commits werden gefunden. Vorher: nur 2 (post-rename).

## Wichtigste Outputs

### Neue Files (8)

- `living_vault/core/insights.py` (Phase 12.1)
- `living_vault/core/history.py` (Phase 13.1)
- `living_vault/apps/seance_ui/orchestrator.py` (Phase 12.2)
- `living_vault/mcp_servers/seance/__init__.py` + `server.py` (Phase 12.3+12.4)
- `tests/test_insights.py` (+9 Tests)
- `tests/test_seance_orchestrator.py` (+12 Tests)
- `tests/test_seance_mcp.py` (+14 Tests)
- `tests/test_history.py` (+10 Tests in 13.1, +1 Test in 13.x)

### Wiki-Schreibwege (separates Repo `~/wiki/`)

- `wiki/synthesis/2026-05-10-living-vault-retro.md` (~250 Zeilen)
- `wiki/entities/living-vault.md` (neu, status: done)
- `wiki/log.md` Append + `index.md` Synthesis-Sektion erweitert

### Erweiterte Files (7)

- `living_vault/core/db.py` — `insights`-Tabelle in SCHEMA
- `living_vault/apps/seance_ui/app.py` — 531 → 195 Zeilen, jetzt HTTP-Adapter
- `living_vault/mcp_servers/vault_engine/server.py` — `page_history` Tool
- `living_vault/apps/synesthesia/render.py` — `include_history`-Param,
  `history.json`-Generation, `--no-history`-Flag, `manifest schema_version=2`
- `living_vault/apps/synesthesia/templates/vault-3d.html.j2` — Hover-driven
  History-Panel mit lazy fetch
- `living_vault/cli.py` — `living-vault history`-Subcommand
- `pyproject.toml` — Entry-Point `seance-mcp`

### Stats

- 11 Commits (Phase 12 ×5, Phase 13 ×7, Phase 14 ×2 + wiki, Phase 13.x ×1)
- 273 Tests grün (Phase 11 endete bei 218, +55 in dieser Session)
- 1 Subagent-Dispatch (Phase 12.2 Refactor — 0 Bugs)
- 0 Codex-Verifier-Pässe (User wählte "direkt schließen" für 12 + 13)

## Methodik die wirkte

1. **AskUserQuestion vor Spec-Schreiben** klärte für Phase 12 vier
   Architektur-Optionen (Server-Ort, Persistenz, Multi-Page, Scope)
   und für Phase 13 vier weitere (Display-Ort, History-Tiefe, Caching,
   Scope) VOR Code-Beginn. Drei Phase-Mid-Pivots verhindert. Phase 13
   inkl. Master-Plan-Korrektur (Modal-Ort von portfolio nach
   synesthesia-public verschoben).
2. **Refactor-vor-Adapter-Disziplin** in Phase 12.2: erst Orchestrator
   extrahieren, dann MCP-Server als dünnen Adapter draufsetzen. ~165
   Zeilen MCP-Server-Code statt ~400 mit Code-Duplikation.
3. **Subagent-Briefing mit explizitem Fallstrick-Hinweis** verhinderte
   den `monkeypatch`-Fehler im Phase-12.2-Refactor. Subagent musste
   `_app_mod.get_llm()` lazy aufrufen, nicht direkt importieren — wurde
   im Briefing genannt, korrekt umgesetzt.
4. **Defensive Fallbacks > Exceptions in Read-Wegen.** `core.history`
   wirft NIE: kein Git, kein Repo, kein File → leere Liste.
5. **Schema-Bump v1 → v2 sauber additive** in Phase 13.3 — `history_included: bool`
   default true, alte v1-Reader ignorieren das Feld. `test_public_build_manifest_has_required_fields`
   wurde explizit auf v2 geupdated, kein stilles Schema-Brechen.

## Drei kritische Momente

1. **Master-Plan-Korrektur in Phase 13 vor Spec-Beginn.** Original-Plan
   sagte "Version-History in living-portfolio". AskUserQuestion ergab,
   dass Phase 11 (synesthesia-public Vault) der konsistentere Display-Ort
   ist. Spec dokumentiert die Korrektur explizit als
   `## Master-Plan-Korrektur`-Block — nicht stilles Verschieben.
   Master-Plan-Eintrag wurde im Phase-13-Close mitgeupdatet.

2. **Orchestrator-Refactor-Strategie in Phase 12 als Architektur-
   Schlüsselentscheidung.** Spec erkannte: das séance-UI ist stark mit
   FastAPI verheiratet (HTTPException, Pydantic). Saubere Trennung VOR
   MCP-Implementation, sonst hätte 12.3 ~400 Zeilen duplizieren müssen.
   Subagent-Auftrag in 12.2 explizit "bestehende UI-Tests unverändert
   grün halten" als Pflicht. Resultat: 1 Dispatch, 0 Test-Modifikationen,
   12 neue Orchestrator-Tests grün.

3. **`--follow`-Mini-Erweiterung als Beispiel für saubere Carry-Over-
   Reihenfolge.** Phase 14 schloss das Projekt formal ab, aber die Retro
   listete 10 inkrementelle Items. Eines davon war `--follow` (trivial,
   ~30 Min). User entschied: jetzt mitnehmen. 1 Zeile Code + 1 Test —
   273. Test grün. Beispiel dass nicht jedes Carry-Over auf "später"
   geparkt werden muss; trivial-niedriges braucht keine eigene Phase.

## Patterns aktualisiert / NEU

(Pattern-Extractor übersprungen — `errors.json` + `patterns.json` in
`.agent-memory/` weiterhin leer. Phase 12+13+14 produzierten keine
echten Bugs. Die Retro-Synthese im Wiki ist der eigentliche Pattern-
Speicher dieser Session — 7 übertragbare Lessons in
[[wiki/synthesis/2026-05-10-living-vault-retro]].)

## Codex-Externer-Pass

User wählte "direkt schließen" sowohl für Phase 12 als auch Phase 13.
Phase 12+13 sind Test-grün, aber haben keinen externen Codex-Verifier-
Pass. Risiko in der Retro-Synthese als Counter-Evidence dokumentiert.
Mitigation: bei nächster Sichtprüfung gegen Real-Wiki explizit prüfen.

## Offene Punkte / Carry-Over

### User-Action (kein Code)

- **Real-Run-Sichtprüfung gegen `~/wiki`** — `./scripts/deploy-public-vault.ps1
  -OpenManifest`. Phase 12 + 13 sind unangetestet im Live-Vault.
  History-Panel mit echten Wikilinks prüfen.
- **DNS + Hosting-Setup für `vault.dynamic-dome.com`** — Cloudflare Pages /
  Netlify / GitHub Pages, alle drei in `docs/DEPLOY-PUBLIC-VAULT.md`
  beschrieben.

### Niedrig-hängend (nicht jetzt, aber leicht)

- **Wiki-Export von Insights** als `seance.export_insight(insight_id)` MCP-Tool
  oder `commit_insight --export`-Flag. ~2-3h Arbeit. **Voraussetzung:** mind. 1
  echte Insight in der DB (heute 0). Sinnvoll wenn die erste reale séance-
  Insight ansteht.
- **Variant-Templates galaxy/city/network mit History-Panel** — derzeit nur
  `vault-3d.html.j2` hat das Phase-13-Panel.
- **Allowlist organisch erweitern** mit Bridge-Pages für mehr Edge-Density.

### Mittelfristig

- **Belief-Evolution als 4. Konsument** der Engine — braucht 2-3 Monate
  reale séance-Daten, sonst zeigt das Tool nichts. Spec-Idee schon im
  Master-Plan parkiert (#27).
- **Phase-9 content_hash Cache-Invalidation** (Wiki-TODO existiert).
- **Performance-Test gegen 953-Page-Allowlist** für `core.history` —
  bei vollem Vault könnte 953 × ~50ms ≈ 48s entstehen.

### Niedrig

- Codex-LOW SQLite-IN-Limit in `privacy.py` (Phase-11-Carry-Over,
  bei Allowlist >999 relevant, in Praxis nie).
- Backslash-Escape-Bug in Wiki-Reader (`barkhausenrauschen\.md` als
  Edge-Pfad — kaputter Wikilink-Parser-Edge-Case).

### Cross-Project

- Dream-Team-Sprint aus
  `~/wiki/wiki/synthesis/2026-05-09-claude-codex-self-evolving-dream-team.md`
  (User-Wunsch: frische Session, aus living-vault raus).

## Wiedereinstieg

**Living-Vault ist offiziell fertig.** Master-Plan zeigt Phasen 0-14 ✅.
Es gibt keinen ⏳-Eintrag mehr. Wer in das Projekt wieder einsteigt,
arbeitet an Carry-Over-Items, nicht an einer neuen Phase.

Empfohlener Re-Entry-Pfad:

1. `cd ~/Desktop/Claude-Projekte/living-vault && git log --oneline | head -20`
2. `cat docs/plans/2026-05-08-living-vault-master-plan.md` (alle Phasen ✅)
3. `cat ~/wiki/wiki/synthesis/2026-05-10-living-vault-retro.md` für die
   übertragbaren Lessons + den vollen Carry-Over-Katalog.
4. Bei `commit_insight --export` (wenn 1. Insight da): kleine Spec, 1 Sub-Task,
   ~2-3h. Pattern aus Phase 12 wiederverwenden.
5. Bei Belief-Evolution: separater Master-Plan, nicht als Phase 15 von
   living-vault — eigenes Projekt.

## Stats (Projekt-gesamt)

| Metrik | Wert |
|---|---|
| Phasen abgeschlossen | 14 (alle ✅) |
| Sessions total | 3 (2026-05-08, 2026-05-09, 2026-05-10) |
| Phase-Commits | 53 |
| Tests | 273 grün (Start ~50, Ende 273) |
| Subagent-Dispatches | 10 (1 Bug — selbst gefunden + gefixt) |
| MCP-Server | 2 (vault-engine-mcp 9 Tools, seance-mcp 5 Tools) |
| Codex-Verifier-Passes | 1 (Phase 11.1, 1× LOW geparkt) |
| Master-Plan-Status | Projekt offiziell fertig 2026-05-10 |
| Erfolgreichster Moment dieser Session | Phase 12.2 Subagent-Refactor: 1 Dispatch, monkeypatch-Fallstrick im Briefing antizipiert + korrekt gelöst, 12 neue Tests grün, 27 bestehende unverändert grün — Beweis dass Spec-Disziplin Subagents zuverlässig macht |
