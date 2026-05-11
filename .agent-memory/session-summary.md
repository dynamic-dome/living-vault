# Last Session — living-vault

*Datum: 2026-05-11*
*Agent: Claude Opus 4.7 (1M context)*

## Headline

**Phase-13 Real-Run-Bugfix + Blueprint-PoC gegen kompetenz-wiki + Projekt-Doku-Konvention etabliert.**
4 Commits gepusht, 2 zusätzliche Speicherorte für die neue User-Konvention (CLAUDE.md + HOW-TO-USE.md in jedem Projekt-Root).

## Was Wurde Gemacht

- **Bugfix Phase 13:** `deploy-public-vault.ps1` `-Vault` Default `$HOME\wiki` → `$HOME\wiki\wiki` (Commit `4ca72c8`)
- **Blueprint-PoC:** kompetenz-wiki indexiert (193 Pages, 840 Edges), Allowlist generiert, Deploy ohne Code-Change durch
- **Wiki-Outputs:** `wiki/wiki/todos/2026-05-11-living-vault-kompetenz-wiki-publishing.md` (P3), `wiki/wiki/queries/2026-05-11-session-living-vault-blueprint-poc.md`, log.md + index.md aktualisiert
- **Wrap-Up Memory + Gitignore:** Commit `1591820` (out-vault-*/, Learnings L1+L2)
- **HOW-TO-USE.md** als 199-Zeilen-Index/Wegweiser (Commit `8fe90af`)
- **CLAUDE.md im Root** mit Vorrang-Verweis auf HOW-TO-USE.md (Commit `6095c25`)
- **Globale Konvention:** Block "Projekt-Eintrittspunkt" in `~/.claude/CLAUDE.md` eingetragen + Memory-Backup `user_project_entrypoint_convention.md`

## Open Items

- **193-Pages-3D-Modell im Browser inspizieren** — User hat technisches "Beweis reicht" gewählt und Sichtprüfung vertagt
- **kompetenz-wiki braucht mehr Git-Commits** damit History-Panel reicher wird (heute nur 1 Initial-Commit)
- **Variante B (TOML-Profile)** skizziert im Wiki-TODO, nicht implementiert
- **Audit existierender Projekte:** Andere Projekte (`dome-dynamics`, DCO, Plugins) wurden NICHT auf CLAUDE.md+HOW-TO-USE.md-Pflicht durchgegangen — passiert reaktiv in deren jeweiligen Sessions

## Next Steps

1. Bei nächster Session in einem fremden Projekt: gemäß neuer globaler Regel proaktiv prüfen ob CLAUDE.md + HOW-TO-USE.md im Root existieren, sonst Anlegen vorschlagen
2. Carry-Over aus 2026-05-10 (Wiki-Export von Insights, Variant-Templates, Belief-Evolution als eigener Master-Plan) bleibt unverändert offen
3. Falls kompetenz-wiki regelmäßig publiziert werden soll: Wiki-TODO `2026-05-11-living-vault-kompetenz-wiki-publishing.md` als Anker, Variante B (TOML-Profile) implementieren

## Statistics

- Commits: 4 (`4ca72c8` Phase-13-fix, `1591820` Wrap-up, `8fe90af` HOW-TO-USE, `6095c25` CLAUDE.md — alle gepusht)
- Tests: 273 grün (unverändert — keine Python-Code-Änderung)
- Neue Learnings: 3 (L1 deploy-bug, L2 generic-reader, L3 user-konvention)
- Neue Wiki-TODOs: 1 (P3)
- Neue Doku-Files: 2 (HOW-TO-USE.md, CLAUDE.md)
- Globale Regeln neu: 1 (Projekt-Eintrittspunkt-Block in `~/.claude/CLAUDE.md`)

## Active Warnings

- Phase-close-Tests fangen Config-Default-Bugs nicht (Lesson L1) — bei zukünftigen Phasen Real-Run-Sichtprüfung VOR `CLOSED` markieren
- Ab nächster Session: CLAUDE.md+HOW-TO-USE.md-Check in JEDEM Projekt (globale Regel)
