# Vision: Tagebuch-Séance — "Sprich mit der Person, die du warst"

User-Idee vom 2026-05-08, nach erstem Live-Test der Phase-1-Séance.
Status: nicht in Phase 1 oder Phase 2, eigener späterer Vision-Sprint.

## Die Idee

Wenn ein langjährig geführtes Tagebuch (Jahre, idealerweise Jahrzehnte)
in living-vault indiziert wird, kann man:

- **mit einer Person sprechen, die man vor 7 Jahren war** — Page = Tagebucheintrag,
  Persona = Stimme/Wissensstand des damaligen Selbst
- **eine Lebensphase summonen** — "Wer war ich im Sommer 2019?", multiple
  Einträge zu einer Persona zusammengefasst
- **Belief-Evolution** — "Wie hat sich meine Meinung zu X über 8 Jahre verändert?",
  technisch ein semantic-search über Years × belief-relevant terms
- **Jahres-Synthesen** — automatisch aus Year-X-Einträgen generiert, dann selbst
  summon-fähig als "die Gesamtstimme dieses Jahres"

## Warum das funktionieren würde (technisch)

Die Engine kann das schon weitgehend:
- Vault-Reader mit Frontmatter ✅ (Tagebuch-Frontmatter mit `date:` lässt
  sich als era-marker pro Eintrag nutzen)
- Embeddings + semantic-search ✅ (10 Jahre Tagebuch = vermutlich
  3000-15000 Pages, weit unter unseren Performance-Grenzen)
- Persona-System ✅ (lite reicht für simple Einträge, voll für
  reflexionsstarke)
- Konversations-Persistenz ✅ (Phase-1 Séance schreibt sie schon mit)

Was zusätzlich gebaut werden muss:
- **Multi-Page-Persona** (eine Persona aus mehreren Pages eines Zeitraums)
- **Era-Filter** (nur Pages aus Jahr X / Monat Y für die Persona)
- **Jahres-Synthese-Generator** (analog zu wiki/synthesis/-Pages, aber
  per Jahr automatisch)

## Drei harte Realitäts-Checks bevor das gebaut wird

### 1. Format-Frage
Aktuell hypothetisch — User hat noch kein digitales Langzeit-Tagebuch.
Falls eines entsteht: am einfachsten als markdown unter `~/wiki/wiki/diary/YYYY/YYYY-MM-DD.md`
mit Frontmatter `type: diary` und `date:`. Direkt vom bestehenden
Vault-Indexer mitgenommen. Keine separate Engine.

### 2. Persona-Lite reicht hier nicht
Tagebucheinträge sind oft kurz und fragmentiert. Phase-1-Lite
(erste-500-Zeichen-als-voice-sample) wäre zu schwach.
Die Schicht-3-Persona (voice-extraction über page-history,
era-marker-Vollausbau) muss vor Tagebuch-Séance gebaut sein.

→ Reihenfolge: Phase-1 abschliessen → Phase-2 Schicht-3-Persona →
Tagebuch-Séance als Anwendung darauf.

### 3. Privatsphäre — kritisch
Tagebuch ist das Privateste. Aktuelle Séance schickt jeden
Voice-Sample über die Anthropic-API. Bevor ein einziger Eintrag indiziert
wird, muss explizit entschieden sein:

- Anthropic-API (Status quo): Kein Training-Logging laut TOS, aber bewusste
  Entscheidung. Modell: Haiku 4.5 ist günstig, ein langer Tagebuch-Chat
  kostet wenige Cent.
- Lokales LLM (Ollama + Llama 3.x oder Mistral): voll lokal, kein
  Datenexfiltrations-Risiko. Aber: Setup-Aufwand, schwächere
  Persönlichkeitsfähigkeit, langsamere Antworten.
- Hybrid: Tagebuch lokal, Wiki über Cloud — getrennte Pfade in der
  Engine.

→ Vor Tagebuch-Indizierung: explizite User-Entscheidung welcher Modus,
und Implementation einer LLM-Provider-Wahl pro Vault-Root.

## Wo das hingehört

Vermutliche Reihenfolge:
1. Phase 1 abschliessen (Etappe 7 Living-Portfolio + Phase-1-Gate)
2. Phase 2: Persona-Schicht-3 (Voll-Voice-Extraction)
3. Phase 2: Multi-Page-Persona (Lebensphasen)
4. Phase 2 oder 3: LLM-Provider-Wahl (lokal/cloud)
5. Phase 3: Diary-Vision-Sprint (eigener Spec, baut auf 2-4 auf)

## Notiz an Future-Self / Future-Claude

Wenn diese Vision später aktiviert wird: **fang nicht an Code zu schreiben
ohne den User zu fragen "wo liegt das Tagebuch und welche LLM-Provider"**.
Beide Antworten sind aktuell offen. Der gesamte Sprint-Plan hängt daran.
