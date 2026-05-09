# Master-Plan: Living-Vault-Trio

**Projekt-Shortname:** `living-vault`
**Datum:** 2026-05-08
**Erwartete Dauer:** 2-4 Wochen (10-14 Tage Phase 1, danach optional Phase 2)
**Design-Doc:** [`../superpowers/specs/2026-05-08-living-vault-trio-design.md`](../superpowers/specs/2026-05-08-living-vault-trio-design.md)
**Genese-Bericht:** [`~/wiki/wiki/synthesis/2026-05-08-mcp-ideen-genese-notebooklm.md`](file:///C:/Users/domes/wiki/wiki/synthesis/2026-05-08-mcp-ideen-genese-notebooklm.md)

---

## Ausgangsdiagnose (Evidenz-basiert)

**Vault-IST-Stand (gemessen 2026-05-08):**
- 953 Markdown-Pages unter `~/wiki/wiki/`
- 13 Top-Level-Cluster (concepts, dashboards, entities, lint, meta, patterns, queries, raw, sources, synthesis, todos, topics, _raw)
- Aggressiv verlinkt via `[[wiki/...]]`-Wikilinks
- Aktuell **kein** maschineller Verständnis-Layer — Lesen heißt Datei öffnen, Suchen heißt grep

**Bestehende verwandte Komponenten:**
- `Desktop/.agent-memory/` (Pattern-Catalog, Iteration-Log) — separat von Wiki
- `~/.claude/projects/.../memory/` (Claude-Code-Memory) — separat von Wiki
- `cv-dynamic-dome` Site (cv.dynamic-dome.com) — heute statisches Portfolio
- Diverse MCP-Server in Stack (notebooklm, wiki-MCP read/write) — keine semantische Schicht

**Beobachtete Pain-Points:**
- Wiki-Decay: Cv-Faktencheck 2026-05-08 hat 4 kritische/mittlere Befunde durch stille Veraltung gefunden
- Cross-Cluster-Synthese ist heute manuell (User schreibt Synthesen selbst)
- Site cv.dynamic-dome.com ist Snapshot, nicht Living
- Reflexions-Tools fehlen — Wiki ist lesbar, aber nicht "ansprechbar"

**Strategischer Hebel:** Eine Engine, drei Linsen. Phase-1-Wert ist sofort spürbar (lokales 3D, Web-Séance, Auto-Sync). Phase-2-Wert ist dauerhaft (Persona-Tiefe, Public-Showcase, Version-History).

## Phasen-Tabelle

| Phase | Ziel | Output | Status |
|---|---|---|---|
| 0 | Setup, Skeleton, Engine-Spike | Repo-Struktur unter `Claude-Projekte/living-vault/`, sentence-transformers-Spike auf Windows verifiziert | ✅ |
| 1 | core/-Library Schicht 1 (Mechanisch) | reader.py, graph.py, decay.py, privacy.py, db.py + Tests | ✅ |
| 2 | core/-Library Schicht 2 (Semantisch) | embeddings.py mit sqlite-vec, Initial-Indexing-Lauf der 953 Pages | ✅ |
| 3 | vault-engine-mcp Phase-1-API | mcp_servers/vault_engine/server.py, alle Phase-1-Tools getestet | ✅ |
| 4 | synesthesia Phase 1 (lokal) | apps/synesthesia/render.py + Three.js-Template, lokales 3D-HTML | ✅ |
| 5 | séance UI Phase 1 | apps/seance_ui/ FastAPI mit Persona-Lite + session-export | ✅ |
| 6 | living-portfolio MVP | apps/portfolio_sync/sync.py + /now + Freshness-Badges, dry-run + apply | ✅ |
| 7 | Phase-1-Integration & Polish | End-to-End-Test, Privacy-Test-Suite, Doku, Acceptance-Checklist | ✅ |
| 8 | **Phase-1-Abschluss-Gate** | User-Review aller drei Linsen, Entscheidung: Phase 2 starten oder pausieren | ✅ |
| 9 | (Phase 2) core/persona.py — Schicht 3 Persona-Vollausbau | persona.py, voice-extraction, era-marker | ✅ |
| 10 | (Phase 2) synesthesia public subset + portfolio 3D-Embed | --public-only Modus, Privacy-Tests, Site-Embed | ⏳ |
| 11 | (Phase 2) séance MCP-Tool + commit_insight | seance.summon, seance.commit_insight, Multi-Page-Modus | ⏳ |
| 12 | (Phase 2) Version-History-Modal in living-portfolio | Git-Backed Page-History-API, Modal-UI | ⏳ |
| 13 | Abschluss-Synthese | wiki/synthesis-Page mit current thesis, lessons learned, what to investigate next | ⏳ |

**Status-Symbole:** ✅ done | 🟡 in progress | ⏳ pending | ❌ blocked

## Bereits getroffene Entscheidungen (nicht neu verhandeln)

1. **Architektur-Stil:** Option C (Monolith-Repo, interne Library, *eine* MCP-Schicht für Engine, Konsumenten als CLI/Apps)
2. **Engine-Tiefe:** 3 Schichten — Mechanisch + Semantisch + Persona (Schichten 1+2 in Phase 1, Schicht 3 in Phase 2)
3. **Embedding-Stack:** Lokal, sentence-transformers `all-MiniLM-L6-v2`, sqlite-vec
4. **State-Storage:** SQLite einzeln in `~/wiki/.vault-engine.db`
5. **Privacy-Default:** Default private, opt-in via `public: true` Frontmatter
6. **Sprint-Modus:** Abgestuft — Phase 1 MVP zuerst, Phase 2 nach Review-Gate
7. **Repo-Pfad:** `Claude-Projekte/living-vault/`
8. **#33 Hosting:** Phase 1 lokal-only, Phase 2 public-curated-subset auf cv.dynamic-dome.com
9. **#34 Frontends:** Phase 1 Web-UI, Phase 2 zusätzlich MCP-Tool
10. **#35 Living-Definition:** Phase 1 Auto-Sync + /now + Freshness, Phase 2 Version-History + 3D-Embed

## Commit-Message-Konvention

```
living-vault | Phase-{N}: {knapper-status}
```

Beispiele:
- `living-vault | Phase-0: repo skeleton, sentence-transformers spike works on Windows`
- `living-vault | Phase-1: core.reader + core.graph passing tests`
- `living-vault | Phase-3: vault-engine-mcp answers all phase-1 tools <500ms`

`git log --grep="living-vault"` wird damit zum Handoff-Index für jeden frischen Claude.

## Offene Fragen für spätere Phasen

Bewusst geparkt, nicht jetzt entscheiden:
- Soll Séance-UI öffentlich auf cv.dynamic-dome.com ausgestellt werden?
- Wann werden Embeddings als "veraltet" eingestuft (Modell-Update-Strategie)?
- Brauchen wir ein "Page-Identity"-Konzept, das Renames überlebt?
- Soll der 3D-Vault begehbar sein (FPS-Mode) oder reicht Orbit-Camera?
- Synergie zu künftigen Ideen #11 synthesis-summoner und #26 time-machine: gleicher Engine-Service?
- Belief-Evolution (#27) als 4. Konsument der Engine — sinnvoll oder eigenes Projekt?

## Risiken und Gegenmaßnahmen

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| sentence-transformers Windows-Quirks | Mittel | **Phase 0 Spike** — Tag 1 prüfen, sonst Fallback auf numpy+cosine |
| Privacy-Leak in Public-Build (Phase 2) | **Hoch** | Pflicht-Test-Suite vor jedem Site-Sync, Default `--public-only` |
| Persona-Halluzinationen in Séance | Hoch | Strict-Mode-Prompt + Eval-Suite mit "darf nicht wissen"-Tests |
| 953-Page-Markierung als User-Marathon | Hoch | Interactive-Mark-Tool, pausierbar, Cluster-Pre-Selektion |
| 3D-Layout für 953 Knoten chaotisch | Mittel | Hierarchisch: Cluster-Aggregate → Pages bei Zoom-In |
| Scope-Creep zwischen Konsumenten | Hoch | Phase-Gate strikt: Phase-2-Features bleiben gesperrt bis Phase 1 abgenommen |

## Wiki-Sync-Pflicht

Bei substantiellem Phase-Abschluss:
- Eintrag in `wiki/log.md`
- Bei Architektur-Änderung: `wiki/entities/living-vault.md` aktualisieren oder erstellen
- Phase-1-Abschluss-Gate: Session-Note unter `wiki/queries/YYYY-MM-DD-session-living-vault-phase-1.md`
- Projekt-Abschluss: Synthese unter `wiki/synthesis/YYYY-MM-DD-living-vault-retro.md`

## Erwartete Phasen-Dauer (Solo, fokussiert)

| Phase | Dauer (Tage) |
|---|---|
| 0 (Setup + Spike) | 1 |
| 1 (Schicht 1) | 1.5 |
| 2 (Schicht 2) | 2 |
| 3 (MCP-Server) | 1 |
| 4 (Synesthesia) | 2 |
| 5 (Séance UI) | 2.5 |
| 6 (Portfolio) | 2 |
| 7 (Polish) | 1 |
| **Phase-1-Total** | **~13 Tage** |
| 8 (Gate) | 0.5 |
| 9-12 (Phase 2) | ~10-14 |
| 13 (Retro) | 0.5 |
| **Gesamt-Total** | **~24-28 Tage** |

## Wiedereinstieg-Hinweise (für künftige Claude-Sessions)

Wer in dieses Projekt einsteigt, sollte zuerst:
1. Diesen Master-Plan lesen — Phasen-Tabelle gibt aktuelle Position
2. `git log --grep="living-vault"` für Phase-Verlauf
3. `docs/superpowers/specs/2026-05-08-living-vault-trio-design.md` für Architektur-Detail
4. `~/wiki/wiki/synthesis/2026-05-08-mcp-ideen-genese-notebooklm.md` für Hintergrund (warum diese drei Tools)
5. Status-Symbole in Phasen-Tabelle ernst nehmen — wer ⏳ überspringt, bricht das Fundament

Aktuelle Position: **Phase 8 + 9 ✅ abgeschlossen am 2026-05-09**, Phase 10 ⏳ pending (User wählt: Synesthesia-Interaktiv ODER Nachbar-Gespräche, beide als Wiki-TODOs unter `~/wiki/wiki/todos/2026-05-09-living-vault-phase-10-*` notiert). Phase-9-Sichtprüfung positiv ("subtil aber spürbar"), 118 Tests grün, 5 Pages mit echter Anthropic-Distillation in Live-DB.
