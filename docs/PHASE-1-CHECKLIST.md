# Phase 1 — Acceptance Checklist

Wenn alle Boxen abgehakt sind, geht's zum Phase-1-Abschluss-Gate (Master-Plan-Phase 8).
Der Status pro Master-Plan-Phase wird *nur* gesetzt wenn die zugehörigen Items hier
manuell bestätigt wurden — automatisches Ankreuzen ist nicht erlaubt.

## Engine

- [x] vault-engine indexiert 953 reale Wiki-Pages in ≤ 600 Sekunden (Task 19, gemessen: ~103s)
- [x] sentence-transformers + sqlite-vec funktionieren auf Windows (Task 3 spike, exit=0)
- [x] Embedding-Backend mit numpy-Fallback existiert (Task 13)
- [x] Content-hash-skip-unchanged greift bei Re-Indexing (Task 10 test)
- [x] vault-engine-mcp antwortet auf alle 8 Phase-1-Tools (Task 17 + 18)

## Synesthesia

- [x] Lokales 3D-HTML wird gerendert mit ≥ 90 % der Pages (Task 25, 953/953 Knoten sichtbar)
- [x] 3 Visual-Varianten (galaxy / city / network) vorhanden, Importmap-Fix wirkt
- [x] Privacy-Regression-Test grün (Task 24)
- [x] **Optional**: synesthesia gegen real-wiki manuell verifiziert + visuell akzeptabel
      (User-Sichtprüfung 2026-05-08: drei Varianten als brauchbar bewertet,
      Phase-2-Backlog für Interaktion notiert; nochmal bestätigt 2026-05-09 im Phase-8-Gate-Review)

## Séance

- [x] Web-UI startet auf 127.0.0.1:7777 (Task 30 + 31)
- [x] Page-Picker links + Chat rechts (Task 30)
- [x] /api/summon erstellt Session + persona (Task 30 test)
- [x] /api/say nutzt FakeLLM in Tests, AnthropicLLM in Produktion (Task 28)
- [x] Anti-Halluzinations-Klausel im System-Prompt (Task 27)
- [x] Konversations-Persistenz in DB (Task 29)
- [x] Past-Sessions-Tab + Session-Wieder-Laden + Export-zu-Wiki (Bonus 2026-05-08)
- [x] User-Sicht: erfolgreicher Persona-Test mit echter Wiki-Page durchgeführt (2026-05-08, MCP-Top-10-Synthesis-Selbstreferenz)

## Living-Portfolio

- [x] portfolio-sync dry-run läuft gegen real wiki (Task 36, 0 public pages → 0 leaks)
- [x] portfolio-sync apply schreibt nur is_public=1 Pages (Task 33 test)
- [x] /now-Page-Generator (Task 34)
- [x] Freshness-Badges (Task 33 test)
- [x] Privacy-Regression-Test grün (Task 35)
- [x] Smoke-Test: Page temporär als public markiert → dry-run zeigt sie korrekt

## Cross-cutting

- [x] `pytest -q` aus Repo-Root durchgehend grün (zuletzt: 71+ tests)
- [x] Alle Commits folgen Konvention `living-vault | Phase-{N}: …`
- [x] Privacy-Default (private unless tagged) durchgehend implementiert
- [x] Spike-Outcome dokumentiert (`scripts/spike_outcome.txt`)
- [x] Bench-Outcome dokumentiert (`scripts/bench_outcome.txt`)
- [x] docs/RUN-MCP-SERVER.md erklärt Claude-Code-Integration
- [x] docs/TODO-PHASE-2-SYNESTHESIA.md (User-Wunschliste für Phase 2)
- [x] docs/VISION-DIARY-SEANCE.md (Tagebuch-Vision für Phase 3)

## Gate-Decision für Phase 2

Mit allen Boxen ✅ ist Phase 1 abgeschlossen. Nächster Schritt laut Master-Plan:
**Phase 8 — Phase-1-Abschluss-Gate**: User entscheidet ob Phase 2 sofort startet
oder pausiert wird, bis genug Erfahrung mit Phase-1-Stand gesammelt ist.

**Empfohlener Pause-vor-Phase-2:**
- Mindestens 2 Wochen aktiver Nutzung von Séance + Synesthesia + Portfolio-Sync
- Sammeln von Friction-Points (Tagebuch-Vision z.B. wartet auf das digitale Tagebuch)
- Dann Phase 2 spezifisch dort wo User-Schmerz die Priorisierung diktiert

Phase 2 in der Master-Plan-Tabelle bleibt unverändert ⏳ pending bis User explizit
entscheidet.
