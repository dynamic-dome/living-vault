# Séance-UI Deutsch + 3-Schritte-Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Séance-Chat-UI wird komplett deutsch beschriftet, in einen geführten 3-Schritte-Flow umgebaut (Seiten wählen → Modus → Start) und bekommt eine eingebaute Klickanleitung (Starthinweis + Hilfe-Overlay).

**Architecture:** Reiner Frontend-Umbau in der einzigen Datei `living_vault/apps/seance_ui/static/index.html` (Vanilla JS + CSS, kein Build-Step). Backend-API (`/api/pages`, `/api/summon`, `/api/summon-candidates`, `/api/constellations`, `/api/say`, `/api/sessions*`) bleibt byte-identisch unberührt. Visuelle Identität (Palette, Fonts, Animationen) bleibt erhalten.

**Tech Stack:** Vanilla JS, CSS Custom Properties, FastAPI-Static-Serving (unverändert). QA über lokalen uvicorn-Server + Playwright-Browser.

## Global Constraints

- Nur `living_vault/apps/seance_ui/static/index.html` wird geändert.
- Alle sichtbaren Strings deutsch (korrekte Umlaute, UTF-8); Code-Identifier bleiben englisch.
- Keine Änderung an Request-/Response-Shapes der API-Aufrufe.
- CSS-Variablen, Fonts, Keyframes (`flicker`, `rift`, `materialize`) unverändert lassen.
- Kein `alert()`; bestehendes `confirm()` für Kostenhinweis bleibt (übersetzt).
- Max. 8 Seiten pro Gespräch (bestehende Grenze, unverändert).
- Server-Startkommando für QA: `.venv/Scripts/python.exe -m uvicorn living_vault.apps.seance_ui.app:app --port 8000` mit `--host 127.0.0.1`.

---

### Task 1: Sidebar-Umbau — Schritt ①: ein Suchfeld, Liste mit Häkchen, Chips; Dropdown + Doppelklick entfernen

**Files:**
- Modify: `living_vault/apps/seance_ui/static/index.html` (HTML-Body Sidebar, zugehöriges CSS, JS-Funktionen `loadPages`, `renderPageDropdown` (löschen), `togglePageSelection`, `syncSelectionDom`, `updateSelectionControls`, `singleSummonOnDoubleClick` (löschen), `renderRagCandidates`, `renderConstellations`, RAG-Form-Handler)

**Interfaces:**
- Produces: `selectedPaths: Set<string>` (bleibt global), `filterPageList(term)` (client-seitiger Filter), `showFullList()` (Ergebnisse schließen, Liste zeigen), `renderChips()` (Chips-Zeile). Task 2 liest `selectedPaths.size`; Task 2 definiert `startConversation()`.
- Consumes: bestehende Endpoints `/api/pages`, `/api/summon-candidates`, `/api/constellations`.

**Schritte:**

- [ ] **1.1** `<html lang="en">` → `<html lang="de">`. Brandmark-Untertitel: `commune with the pages of the vault` → `Sprich mit den Seiten deines Vaults`. Tabs: `spirits` → `Seiten`, `records` → `Verlauf`.
- [ ] **1.2** Block `#pagePicker` (HTML), zugehöriges CSS (`#pagePicker`, `#pagePickerRow`, `#pageSelect`, `#pageSummonSelected`) und JS (`renderPageDropdown`, `pageSelect.onchange`, `pageSummonSelected.onclick`, `addPageSelection`) ersatzlos löschen. `#selectionStatus` wird durch Chips-Zeile (1.4) ersetzt.
- [ ] **1.3** RAG-Bereich wird Schritt ①: Überschrift `<div class="stepLabel">① Seiten auswählen <span class="stepMeta">(1–8)</span></div>`. Suchfeld-Placeholder: `Suchen oder Thema eingeben…`. Buttons: `seek` → `KI fragen`, `circles` → `Gruppen`. Eingabe filtert per `input`-Event live die Seitenliste (`filterPageList`: case-insensitive Substring auf `p.path` + `p.title`). Ergebnis-Container bekommt Kopfzeile mit `← zurück zur vollen Liste` (klick → `showFullList()`).
- [ ] **1.4** Listeneinträge mit Häkchen-Optik: `.pageItem::before {content:"☐"}` / `.pageItem.selected::before {content:"☑"}` (mono, ecto-Farbe bei selected). Nur `onclick = togglePageSelection`; `ondblclick`-Handler überall löschen (`loadPages`, `renderRagCandidates`). Chips-Zeile `#chips` unter der Liste: pro Auswahl ein Chip `name ×`, × entfernt aus `selectedPaths` + `renderChips()` + `syncSelectionDom()`. Leerzustand: `Noch keine Seite ausgewählt`.
- [ ] **1.5** Deutsche Texte in Schritt-①-Logik: Toast `the circle holds at most 8 spirits` → `Maximal 8 Seiten pro Gespräch`; `speak a question first` → `Gib zuerst einen Suchbegriff ein`; Hint `listening through the vault…` → `Der Vault wird durchsucht…`; `no spirits surfaced` → `Keine passenden Seiten gefunden`; `drawing circles through the vault…` → `Gruppen werden zusammengestellt…`; `no circles formed` → `Keine Gruppen gefunden`; `the vault would not answer/draw circles: N` → `Suche fehlgeschlagen (HTTP N)` / `Gruppen-Suche fehlgeschlagen (HTTP N)`; Dropdown-Reste (`loading spirits…`, `no spirits indexed`, `choose a page…`) entfallen mit 1.2; List-Hint `the register stirs…` → `Seiten werden geladen…`; RAG-Meta `semantic match` → `inhaltlich passend`.
- [ ] **1.6** Commit: `feat(seance-ui): Schritt 1 — einheitliche Seitenauswahl mit Filter, Häkchen, Chips (deutsch)`

### Task 2: Sidebar-Umbau — Schritte ② + ③: Modus immer sichtbar mit Erklärtext, ein Start-Button

**Files:**
- Modify: `living_vault/apps/seance_ui/static/index.html` (Mode-Row-HTML/CSS, `updateModeRow`, `summonRoundtable`, `summon`, neuer `startConversation`)

**Interfaces:**
- Produces: `startConversation()` — verzweigt: `selectedPaths.size === 1` → bisheriger `summon(path)`-Pfad (POST `/api/summon` mit `{path}`), `>= 2` → bisheriger Roundtable-Pfad (`{paths, mode, semantic_neighbors}`). `updateStepTwo()` ersetzt `updateModeRow()`.
- Consumes: `selectedPaths`, `renderChips`, `syncSelectionDom` aus Task 1.

**Schritte:**

- [ ] **2.1** `#modeRow` wird `#stepTwo`, **immer sichtbar** (kein `.visible`-Toggle mehr). Aufbau: `<div class="stepLabel">② Gesprächsmodus</div>`, Modus-Select, darunter `#modeHint` (Ein-Satz-Erklärung), Checkbox `Verwandte Seiten als Wissen einbeziehen`. Bei `selectedPaths.size < 2`: Select disabled, `#modeHint` = `Einzelgespräch — wähle 2+ Seiten für eine Gesprächsrunde.`
- [ ] **2.2** Modus-Optionen + Erklärungen (Map `MODE_HINTS`): `roundrobin` → `Reihum` / `Jede Seite antwortet nacheinander in fester Reihenfolge.`; `moderator` → `Moderiert (@Name)` / `Nur die Seite antwortet, die du mit @Name ansprichst.`; `auto` → `Auto-Moderator` / `Die passendste Seite antwortet automatisch.`; `freeforall` → `Alle gleichzeitig` / `Alle Seiten antworten auf jede Frage (teuerste Variante).` `change`-Listener aktualisiert `#modeHint`.
- [ ] **2.3** Schritt ③: ein Button `<button id="startBtn">▶ Gespräch starten</button>` (Ecto-Stil des bisherigen `#summonBtn`), disabled bei 0 Auswahl. `startConversation()` implementieren; `summonRoundtable`-Mindest-2-Toast entfällt (Verzweigung übernimmt). Kosten-Confirm: `Alle gleichzeitig mit N Seiten: ca. N-fache Token-Kosten pro Frage. Fortfahren?` Fehler-Toast `the circle would not form: N` → `Gespräch konnte nicht gestartet werden (HTTP N)`; `the spirit would not answer: path` → `Seite konnte nicht geladen werden: path`.
- [ ] **2.4** Statuszeile nach Start: Einzel → `✦ Gespräch mit <b>name</b> · Ära <era>` (Fallback `unbekannt`); Runde → `✦ Gespräch mit N Seiten · <Modusname>` + optional ` · verwandte Seiten` bei aktivierter Checkbox.
- [ ] **2.5** Commit: `feat(seance-ui): Schritte 2+3 — Modus immer sichtbar mit Erklärtext, ein Start-Button`

### Task 3: Chatbereich — deutsche Texte, Starthinweis-Karte, Verlauf-Tab

**Files:**
- Modify: `living_vault/apps/seance_ui/static/index.html` (Header, `#log`-Startzustand, Form, `loadSessions`, `loadSessionIntoChat`, `traceBeliefs`, `appendTraceBubble`, `exportSession`, `appendEvidenceVeil`, `appendToolEvent`, Say-Handler)

**Interfaces:**
- Produces: `#starterCard` (Kurzanleitung im leeren Log, wird bei Gesprächsstart/Session-Load entfernt via `clearStarterCard()`).
- Consumes: `startConversation()`-Statuszeile aus Task 2.

**Schritte:**

- [ ] **3.1** Header: Leerlauf-Status `the circle is empty — choose a spirit` → `Kein Gespräch aktiv — wähle links Seiten aus`. Buttons: `trace` → `Meinungsverlauf`, `seal record` → `Exportieren`. Busy-Texte: `tracing…` → `wird erstellt…`, `sealing…` → `wird exportiert…`.
- [ ] **3.2** Starthinweis-Karte im leeren `#log` (Theme-konform, gild-Rahmen): Titel `So funktioniert séance`, Schritte `1. Wähle links eine oder mehrere Seiten aus (per Suche, Liste oder „KI fragen").` / `2. Klicke auf „▶ Gespräch starten".` / `3. Stell unten deine Frage.` plus Konzeptsatz `Jede Seite antwortet aus ihrer eigenen Sicht — gestützt auf ihren Inhalt und ihre Verlinkungen.` `clearStarterCard()` in `startConversation()` und `loadSessionIntoChat()` aufrufen.
- [ ] **3.3** Eingabe: Placeholder `speak into the dark…` → `Stell deine Frage…`, Button `ask` → `Senden`. Antwort-Fallback `(no reply)` → `(keine Antwort)`.
- [ ] **3.4** Verlauf-Tab: Leerzustand `no séances recorded — summon a spirit to begin` → `Noch keine Gespräche gespeichert — starte links dein erstes.`; Meta `N msgs` → `N Nachrichten`; Fehler `the record would not open` → `Gespräch konnte nicht geladen werden`; Status beim Laden `record · path` → `Verlauf · path`; `(unreadable tool event)` → `(nicht lesbares Tool-Ereignis)`.
- [ ] **3.5** Meinungsverlauf: Fehler `the trace would not form` → `Meinungsverlauf konnte nicht erstellt werden`; Block-Titel `Belief Evolution` → `Meinungsverlauf`; `N participants · N user turns · mode` → `N Teilnehmer · N Fragen · <Modusname>`; `first:`/`latest:` → `zu Beginn:`/`zuletzt:`; `(none)` → `(keine Angabe)`. Export: Fehler `the seal would not hold` → `Export fehlgeschlagen`; Erfolg `sealed into: path` → `Exportiert nach: path`.
- [ ] **3.6** Quellen + Tool-Events: `sources used` → `Verwendete Quellen`; `own page:` → `eigene Seite:`; `consulted:`/`none` → `nachgeschlagen:`/`keine`; `semantic archive:`/`off` → `semantisches Archiv:`/`aus`; `routing:`/`unknown` → `Routing:`/`unbekannt`. Tool-Event `» the medium consults [[p]] (N chars)` → `» liest [[p]] (N Zeichen)`; `» tool failed: err` → `» tool fehlgeschlagen: err`; Budget-Suffix `— the veil thins (i/10)` → `— Lese-Budget fast erreicht (i/10)`.
- [ ] **3.7** Commit: `feat(seance-ui): Chatbereich deutsch + Starthinweis-Karte`

### Task 4: Hilfe-Overlay („?")

**Files:**
- Modify: `living_vault/apps/seance_ui/static/index.html` (Header-Button, Overlay-HTML/CSS, `openHelp`/`closeHelp` + Esc-Handler)

**Interfaces:**
- Produces: `#helpOverlay` (Modal), Button `#helpBtn` in `#headerActions`.

**Schritte:**

- [ ] **4.1** `#helpBtn` („?", gild-Rahmen wie Export-Button, immer enabled, `aria-label="Hilfe"`) als erstes Element in `#headerActions`.
- [ ] **4.2** Overlay: fixiertes, zentriertes Panel (ash-Hintergrund, gild-Rahmen, max-width 62ch, scrollbar bei Überlauf) über abdunkelndem Backdrop. Inhalt: Titel `Anleitung`; die 3 Schritte; Absatz `Seiten finden:` (Tippen filtert die Liste · „KI fragen" schlägt zu einem Thema passende Seiten vor · „Gruppen" liefert fertige 3er-Kombinationen); Absatz `Die vier Modi:` (die 4 Erklärsätze aus Task 2.2); Absatz `Während des Gesprächs:` („Meinungsverlauf" fasst zusammen, wie sich die Positionen der Seiten entwickelt haben · „Exportieren" speichert das Gespräch als Datei · Tab „Verlauf" öffnet frühere Gespräche); Hinweis `Maximal 8 Seiten pro Gespräch.`
- [ ] **4.3** Schließen: ×-Button oben rechts, Klick auf Backdrop, Esc (`keydown`-Listener nur bei offenem Overlay aktiv). Kein `alert()`.
- [ ] **4.4** Commit: `feat(seance-ui): Hilfe-Overlay mit Klickanleitung`

### Task 5: In-Browser-QA (Pflicht) + Regressionscheck

**Files:**
- Keine Änderungen erwartet; Fixes fließen ggf. als Follow-up-Commits ein.

**Schritte:**

- [ ] **5.1** pytest: `.venv/Scripts/python.exe -m pytest -q` → erwartet: alle grün (Backend unberührt).
- [ ] **5.2** Server: `.venv/Scripts/python.exe -m uvicorn living_vault.apps.seance_ui.app:app --host 127.0.0.1 --port 8000` (Port vorher frei prüfen), Browser auf `http://127.0.0.1:8000`.
- [ ] **5.3** QA-Checkliste im Browser: Starthinweis sichtbar · Liste lädt · Filter tippt-filtert · „KI fragen" liefert Ergebnisse + `← zurück zur vollen Liste` funktioniert · „Gruppen" wählt 3er-Set · Klick toggelt Häkchen + Chip · × am Chip entfernt · 9. Seite → Toast `Maximal 8 Seiten pro Gespräch` · Modus-Erklärtext wechselt · Einzelstart (1 Seite) funktioniert · Rundenstart (2+) funktioniert, Statuszeile korrekt · Frage senden → Antwort(en) erscheinen, Quellen-Details deutsch · Hilfe öffnet/schließt (×, Esc, Backdrop) · Verlauf-Tab lädt alte Session · Meinungsverlauf + Exportieren funktionieren · kein einziger englischer UI-String mehr sichtbar.
- [ ] **5.4** Screenshot des Endzustands für den User; gefundene Probleme fixen + committen.

## Self-Review

- Spec-Abdeckung: Abschnitt 1 → Tasks 1+2 · Abschnitt 2 → Task 3 · Abschnitt 3 → Task 4 · Abschnitt 4 → in Tasks 1–3 (Toast-Muster bleiben) · Abschnitt 5 → Task 5. ✓
- Keine Platzhalter; alle Strings ausformuliert. ✓
- Namen konsistent: `selectedPaths`, `startConversation`, `renderChips`, `filterPageList`, `showFullList`, `clearStarterCard`, `updateStepTwo`, `MODE_HINTS`. ✓
