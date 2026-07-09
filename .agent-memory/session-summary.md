# Last Session

*Date: 2026-07-09 10:00*
*Agent: Claude Code*

## What Was Done
- Séance-UI komplett auf Deutsch + geführter 3-Schritte-Flow (Suchfeld mit Live-Filter, Häkchen-Liste, Chips, ein Start-Button; Dropdown + Doppelklick entfernt)
- Starthinweis-Karte im leeren Chat + Hilfe-Overlay („?") als eingebaute Klickanleitung
- QA-Feinschliff: stummer /api/say-Fehlerpfad sichtbar gemacht, Suchfeld volle Breite, Numerus-Fixes
- Embeddings: [embeddings]-Extra via uv installiert, Vault 1602 Seiten mit all-MiniLM-L6-v2 indexiert — „KI fragen"/„Gruppen" liefern jetzt Ergebnisse
- Launcher-Policy: Re-Index mit Embeddings bei Vault-Änderung (LastWriteTime), vor Serverstart (D2)
- End-to-End-QA im Browser inkl. echtem LLM-Chat (Carry-Over T-1 erledigt); alles gepusht (6a542f2…e382e6d)

## Open Items
- ~~T-2: 3D-Polish auf galaxy/city/network-Varianten~~ — **VERWORFEN (2026-07-09)**: Synesthesia/3D wird nicht veröffentlicht (vault.dynamic-dome.com löst nicht auf, kein out-vault-Build, kein Zuschauer). Polieren-vor-Publizieren-Antipattern. Falls je gewünscht: erst *ein* Test-Deploy anschauen, dann entscheiden — nicht alle 3 Varianten polieren.
- T-3: Launcher-Freshness-Check im Alltag beobachten (Re-Index-Dauer ok?) — passiv, kein aktiver Task
- Séance-Verlauf enthält leere QA-Testsessions (keine Lösch-Funktion in der UI) — Nice-to-have

## Next Steps
Schlussstrich gezogen (2026-07-09). Séance-UI-Arbeit fertig + gepusht. Keine aktiven Tasks mehr.
Optional bei Bedarf: Codex-Review der Session-Commits.

## Statistics
- Iterations: 3 | Errors: 2 | New Patterns: 0 (Guard: zu wenig Daten)

## Active Warnings
- .vault-engine.db ohne WAL: nie `living-vault index` parallel zum laufenden Séance-Server (D2)
