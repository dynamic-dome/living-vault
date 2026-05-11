# CLAUDE.md — living-vault

## Erste Pflichtlektuere

**Lies zuerst [`HOW-TO-USE.md`](HOW-TO-USE.md).** Diese Datei ist der Index/Wegweiser durch das Projekt — was Living-Vault ist, welche drei Konsumenten (Vault Engine, Synesthesia/3D, Séance/Chat, Portfolio Sync) existieren, wie man sie startet, wo welche Dokumentation lebt, und was Troubleshooting-typische Fallstricke sind.

Alle weiteren Hinweise hier sind **Ergaenzungen** zu HOW-TO-USE.md, kein Ersatz.

## Status

Living-Vault ist als Tool **fertig** (Master-Plan-Phasen 0-14 ✅, 2026-05-10).
Offene Items sind alle inkrementell — kein neuer Master-Plan-Phase-Slot offen.
Vollstaendige Carry-Over-Liste in der Retro-Synthese im Wiki:
`~/wiki/wiki/synthesis/2026-05-10-living-vault-retro.md`.

## Verfassungsregeln (Vorrang)

`C:\Users\domes\Desktop\SESSION-WORKFLOW.md` ist Vorrang vor dieser Datei.
Globale Regeln in `~/.claude/CLAUDE.md` (Test-DB-Isolation, Codex-Review-Stufen,
TODO-Persistierung etc.) gelten ebenfalls.

## Projekt-spezifische Konventionen

- **Tests:** `.venv/Scripts/python.exe -m pytest -q` (system-`python` ist 3.14 ohne Deps — siehe Memory-Pin).
- **Allowlist-Pfade:** relativ zum **Vault-Content-Root** (`~/wiki/wiki`, nicht `~/wiki`), identisch mit `pages.path` in `.vault-engine.db`. Bei Pfad-Bugs in Skripten/Configs: Phase-13-Fix-Commit `4ca72c8` als Referenz.
- **Multi-Vault:** Living-Vault ist bereits generisch (PoC 2026-05-11 gegen kompetenz-wiki belegt). CLI-Schnittstellen (`--vault`/`--db`/`--allowlist`/`--out-dir`) akzeptieren beliebige Pfade. Refactor zu TOML-Profilen erst wenn 2+ Vaults regelmaessig publiziert werden (siehe Wiki-TODO `2026-05-11-living-vault-kompetenz-wiki-publishing.md`).
- **Phase-close-Tests fangen Config-Default-Bugs nicht** — bei zukuenftigen Aenderungen an User-aufrufbaren Skripten **Real-Run-Sichtpruefung gegen Production-Konvention** Teil des Close-Kriteriums machen (Learning L1 aus 2026-05-11).

## Wiedereinstieg

Standardpfad fuer Folge-Sessions:
1. `cat .agent-memory/session-summary.md` (aktueller Stand)
2. `cat HOW-TO-USE.md` (Komponentenuebersicht)
3. `git log --oneline -10`
4. Bei Arbeit an Carry-Over-Items: erst Wiki-TODO oder Retro-Synthese lesen, dann anfangen.
