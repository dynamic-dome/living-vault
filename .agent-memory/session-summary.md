# Last Session — living-vault

*Datum: 2026-05-11*
*Agent: Claude Opus 4.7 (1M context)*

## Headline

**Phase-13 Real-Run-Bugfix + Blueprint-PoC gegen kompetenz-wiki.**
Sichtprüfung von Phase 13 (offen aus 2026-05-10) deckte einen Vault-Default-Bug auf,
gefixt + gepusht. Anschließend bewiesen: Living-Vault funktioniert als generischer
Vault-Reader gegen kompetenz-wiki ohne Code-Änderung (193 Pages, 840 Edges).

## Was Wurde Gemacht

- Sichtprüfung von Phase 13 → Bug entdeckt: `-Vault` Default zeigte auf `$HOME\wiki` statt `$HOME\wiki\wiki`
- Bugfix in `scripts/deploy-public-vault.ps1` + Kommentar-Klarstellung in `docs/public-allowlist.txt`
- `.gitignore` erweitert um `out-vault/` + `bash.exe.stackdump`
- Commit `4ca72c8` + Push auf `origin/master`
- PoC Variante A gegen kompetenz-wiki: Index (193/193), Allowlist (alle 193), Deploy (840 Edges, 0 Errors), Server-Run
- Wiki-TODO geschrieben: `wiki/wiki/todos/2026-05-11-living-vault-kompetenz-wiki-publishing.md` (P3, Variante B als Skizze)

## Open Items

- **Sichtprüfung des 193-Pages-3D-Modells im Browser** wurde nicht durchgeführt (User hat technisches "geht prinzipiell" abgenommen und auf später vertagt)
- **kompetenz-wiki braucht mehr Git-Commits** damit History-Panel sinnvoll ist (heute nur 1 Initial-Commit pro Page)
- **Variante B (TOML-Profile)** noch nicht implementiert — im Wiki-TODO skizziert für später
- `out-vault-kompetenz/` Test-Artefakt liegt im Repo (jetzt aber durch `.gitignore` abgedeckt)

## Next Steps

1. Bei Wiederaufnahme: Wiki-TODO `2026-05-11-living-vault-kompetenz-wiki-publishing` als Anker, Variante B (TOML-Profile) implementieren wenn mehr als 1-2 Vaults publiziert werden
2. kompetenz-wiki regelmäßig committen lassen, damit Phase-13 History-Panel reicher wird
3. Andere Carry-Over aus 2026-05-10 (Wiki-Export von Insights, Variant-Templates, Belief-Evolution) bleiben unverändert offen

## Statistics

- Commits: 1 (`4ca72c8` Phase-13-fix, gepusht)
- Tests: 273 (unverändert — kein Code in `living_vault/`, nur Skript + Config)
- Iterations logged: 0 (manuell gearbeitet ohne iteration-logger)
- New Learnings: 2 (L1 deploy-bug, L2 generic-vault-reader)
- New Wiki-TODOs: 1 (P3)

## Active Warnings

- Phase-close-Tests fangen Config-Default-Bugs nicht (Lesson L1) — bei zukünftigen Phasen Real-Run-Sichtprüfung VOR `CLOSED` markieren
