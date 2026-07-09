# Séance-UI: Deutsch, ergonomisch, geführt — Design

**Datum:** 2026-07-09
**Status:** Vom User abgenommen (Ton: funktional mit Mystik-Flavor · Anleitung: Hilfe-Button + Starthinweis · Struktur: geführter 3-Schritte-Flow)

## Problem

Die Séance-UI (`living_vault/apps/seance_ui/static/index.html`, Single-File, 829 Zeilen) ist für den User nicht selbsterklärend:

1. Alle Beschriftungen englisch („seek", „summon", „seal record", „trace").
2. Alle Begriffe metaphorisch verschleiert (Seiten = „spirits", Gespräch starten = „summon the circle") — auch übersetzt unverständlich.
3. Verwirrender Ablauf: drei parallele Auswahlwege (RAG-Suche, Dropdown, Liste), Modus-Zeile erscheint erst ab 2 ausgewählten Seiten, Klick und Doppelklick tun Unterschiedliches, zwei verschiedene Start-Buttons.

## Scope

**Nur** `living_vault/apps/seance_ui/static/index.html`. Keine API-/Backend-Änderungen. Die visuelle Identität (Kerzenlicht-Palette, Gold, Cinzel/Garamond, Flicker/Rift-Animationen) bleibt vollständig erhalten. Alle sichtbaren Texte werden deutsch und funktional; Mystik bleibt als Flavor (Brandmark, Untertitel, Optik).

## 1. Sidebar: geführter 3-Schritte-Flow

- **Kopf:** „✦ séance" + Untertitel „Sprich mit den Seiten deines Vaults". Tabs: **Seiten** / **Verlauf**.
- **① Seiten auswählen (1–8):**
  - Ein einziges Suchfeld. Eingabe filtert die Seitenliste sofort client-seitig.
  - Zwei Buttons daneben: **„KI fragen"** (bisheriger RAG-Endpoint `/api/summon-candidates` — schlägt zu einem Thema passende Seiten vor) und **„Gruppen"** (bisheriger `/api/constellations` — fertige 3er-Kombinationen).
  - KI-/Gruppen-Ergebnisse erscheinen anstelle der Liste, mit Link „← zurück zur vollen Liste".
  - Das redundante Seiten-Dropdown (`#pagePicker`) entfällt ersatzlos.
  - Auswahl per **einfachem Klick** (Häkchen-Optik ☑/☐ in Liste und Ergebnissen). Der Doppelklick-Sonderweg (Legacy-Single-Summon) entfällt ersatzlos.
  - Chips-Zeile „Ausgewählt: [name ×] …" unter der Liste, jederzeit sichtbar, × entfernt.
- **② Gesprächsmodus:** immer sichtbar.
  - Bei 0–1 Seiten: Hinweistext „Einzelgespräch — wähle 2+ Seiten für eine Gesprächsrunde", Modus-Menü disabled.
  - Ab 2 Seiten aktiv: **Reihum · Moderiert (per @Name ansprechen) · Auto-Moderator · Alle gleichzeitig** — mit Ein-Satz-Erklärung unter dem Menü, die beim Wechseln mitwechselt.
  - Checkbox „Verwandte Seiten als Wissen einbeziehen" (semantic neighbors).
- **③ Ein Start-Button:** „▶ Gespräch starten". 1 Seite → Einzel-API (`{path}`), ≥2 → Roundtable-API (`{paths, mode, semantic_neighbors}`). Beide bisherigen API-Aufrufpfade bleiben funktional identisch.

## 2. Chatbereich

- Statuszeile: „Kein Gespräch aktiv — wähle links Seiten aus" → „✦ Gespräch mit N Seiten · <Modus>" bzw. „✦ Gespräch mit <name> · Ära <era>".
- Header-Buttons: **„Meinungsverlauf"** (belief-evolution/trace), **„Exportieren"** (export/seal), neu **„?"** (Hilfe).
- **Leerer Chat = Starthinweis-Karte:** „So funktioniert séance" mit den Schritten 1️⃣ links Seiten auswählen (per Suche oder Liste) → 2️⃣ „Gespräch starten" klicken → 3️⃣ unten Frage tippen, plus ein Satz Konzept („Jede Seite antwortet aus ihrer eigenen Sicht, gestützt auf ihren Inhalt und ihre Verlinkungen."). Verschwindet beim Gesprächsstart.
- Eingabe: Placeholder „Stell deine Frage…", Button „Senden".
- Alle Toasts/Fehlermeldungen deutsch und konkret (z. B. „Wähle zuerst mindestens eine Seite aus", „Maximal 8 Seiten pro Gespräch").
- Quellen-Details: „Verwendete Quellen" / „eigene Seite" / „nachgeschlagen" / „semantisches Archiv" / „Routing".
- Tool-Events: „» liest [[pfad]] (N Zeichen)", Budget-Warnung deutsch.
- Kosten-Confirm bei „Alle gleichzeitig" mit ≥3 Seiten: deutsch, weiterhin `confirm()`.
- Verlauf-Tab: Einträge wie bisher (Pfad, Datum, Nachrichtenzahl — „N Nachrichten"), Klick lädt Sitzung: Status „Verlauf · <pfad>".

## 3. Hilfe-Overlay

„?"-Button im Header öffnet ein Modal (gleiches Theme): die 3 Schritte ausführlicher, Unterschied Filtern vs. „KI fragen" vs. „Gruppen", die 4 Modi erklärt, wozu Meinungsverlauf/Exportieren dienen, Limit 8 Seiten, Verlauf-Tab. Schließen per ×, Esc oder Klick auf den Hintergrund. Kein `alert()`.

## 4. Fehlerbehandlung

Bestehende Muster (Toast bei nicht-ok-Response, try/finally-Button-Reenable) bleiben unverändert, nur Texte deutsch.

## 5. Qualitätssicherung

- pytest-Suite unverändert grün (keine Backend-Berührung; kein Test referenziert die Séance-index.html).
- **In-Browser-QA Pflicht** (visueller Code): Server lokal starten, Kernflows prüfen — filtern, KI fragen, Gruppen, auswählen/abwählen (Liste + Chips), Einzel- und Roundtable-Start, Frage senden, Hilfe-Overlay, Verlauf-Tab, Meinungsverlauf, Exportieren, Zustand „leerer Vault".
