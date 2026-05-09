# Living-Vault-Trio — Design-Doc

**Status:** Draft (User-Review Pending)
**Datum:** 2026-05-08
**Autor:** Claude Opus 4.7 + User-Brainstorming
**Master-Plan:** [`../../plans/2026-05-08-living-vault-master-plan.md`](../../plans/2026-05-08-living-vault-master-plan.md)
**Genese:** [`~/wiki/wiki/synthesis/2026-05-08-mcp-ideen-genese-notebooklm.md`](file:///C:/Users/domes/wiki/wiki/synthesis/2026-05-08-mcp-ideen-genese-notebooklm.md)

---

## 1. Was wir bauen — Ein-Satz-Beschreibung

Eine **vault-engine** als zentrale Lese-/Verstehens-Schicht über `~/wiki/`, plus drei Konsumenten, die diese Engine je auf eigene Weise nutzen: **Synesthesia** (3D-Stadt aus dem Vault), **Séance** (Wiki-Pages als Gesprächspartner) und **Living-Portfolio** (Wiki-Anteile als lebende Inhalte auf cv.dynamic-dome.com).

## 2. Warum — Strategischer Kontext

Der `~/wiki/`-Vault ist ein 953-Seiten-Second-Brain. Heute ist er ein passives Markdown-Verzeichnis: Lesen heißt Datei öffnen, Suchen heißt grep, Zusammenhänge heißt Wikilinks-folgen-im-Kopf. Das skaliert nicht weiter.

Die **vault-engine** wandelt das passive Verzeichnis in einen aktiven Service um — eine Schnittstelle, die *versteht* statt nur *liest*. Drei Konsumenten zeigen, was möglich wird, sobald der Vault diese Schicht hat:

- **#33 Synesthesia** macht Vault-Topologie räumlich erfahrbar (spatial memory ist nachweislich der stärkste Gedächtnis-Hebel)
- **#34 Séance** macht alte Vault-Pages zu Gesprächspartnern (Externalisierung als Reflexions-Werkzeug)
- **#35 Living-Portfolio** macht curated Vault-Anteile zu öffentlichen, lebenden Site-Inhalten (Differenzierung gegenüber statischen Portfolios)

Die drei sind nicht "drei Tools". Sie sind **drei Linsen auf dieselbe lebendige Vault-Schicht**.

## 3. Architektur — Option C (Monolith-Repo, interne Library, dünne MCP-Schicht für Engine)

```
living-vault/
├── core/                       # Pure Python-Library, keine I/O-Side-Effects außer DB
│   ├── reader.py               # Markdown-Lesen, Frontmatter-Parsing
│   ├── graph.py                # Wikilink-Graph, Backlinks, Traversal
│   ├── embeddings.py           # sentence-transformers + sqlite-vec
│   ├── persona.py              # Voice-Extraction für Séance
│   ├── decay.py                # Staleness-Detection, Last-Touched-Tracking
│   ├── privacy.py              # public/private-Filter, Frontmatter-Auswertung
│   └── db.py                   # SQLite-Schicht über ~/wiki/.vault-engine.db
│
├── mcp_servers/
│   └── vault_engine/           # FastMCP-Wrapper um core/ — externe API
│       └── server.py
│
├── apps/
│   ├── synesthesia/            # CLI: erzeugt Three.js-HTML aus core/-Daten
│   │   ├── render.py
│   │   └── templates/vault-3d.html
│   ├── seance_ui/              # FastAPI-App: Web-UI für Persona-Chats
│   │   ├── app.py
│   │   └── static/
│   └── portfolio_sync/         # CLI: Wiki → cv-dynamic-dome Site-Routes
│       └── sync.py
│
├── tests/
├── pyproject.toml
└── docs/
```

**Schlüsseleigenschaften:**
- Innen Library-Direkt-Calls (keine MCP-Latenz, einfaches Debugging, einfache Tests)
- Nach außen *eine* MCP-Schnittstelle (`vault-engine-mcp`) für Claude Code
- Konsumenten sind eigenständige CLIs/Apps, brauchen den MCP-Server nicht
- State **immer** in `~/wiki/.vault-engine.db` (eine Datei, leicht zu inspizieren/löschen/rebuilden)

## 4. Komponente: vault-engine-mcp (das Fundament)

### 4.1 Verantwortlichkeit
Eine zustandsbehaftete Schicht, die den `~/wiki/`-Vault liest, indexiert, semantisch versteht und Persona-Profile pro Page extrahiert. Aktualisiert sich bei Vault-Änderungen inkrementell.

### 4.2 Drei Schichten

**Schicht 1 — Mechanisch:**
- Markdown-Parsing inkl. Frontmatter (yaml)
- Wikilink-Graph (`[[wiki/...]]`-Detection, Backlinks, neighbors, paths)
- File-Mtime + Git-Log für Last-Touched
- Stale-Detection nach Schwellwerten

**Schicht 2 — Semantisch:**
- Embeddings via `sentence-transformers/all-MiniLM-L6-v2` (lokal, ~80MB, CPU-OK)
- Persistierung als sqlite-vec-Vektoren in `.vault-engine.db`
- API: `similar_pages(page_id, k=10)`, `cluster(topic, threshold)`, `semantic_search(query)`
- Initial-Indexing der 953 Pages: ~5min einmalig, danach inkrementell pro geänderter Page

**Schicht 3 — Persona:**
- Pro Page: extrahiert aus Frontmatter + Content + History eine Persona-Beschreibung
  - Erstelldatum als Stimm-Anker ("zur Zeit der Erstellung wusste ich…")
  - Tags + Cluster als Themen-Linse
  - Schreibstil-Sample (erste 500 Tokens)
- Persistiert als `personas`-Tabelle in `.vault-engine.db`
- API: `get_persona(page_id)`, `extract_voice(corpus_filter)`

### 4.3 MCP-Tools (extern via FastMCP)
```
read_page(path) -> Page
search_semantic(query, k=10) -> [Page]
neighbors(path, depth=1) -> [Page]
backlinks(path) -> [Page]
similar(path, k=10) -> [Page]
cluster_for(topic) -> [Page]
get_persona(path) -> Persona
stale_pages(within_days=N) -> [Page]
public_pages() -> [Page]   # filtered by frontmatter `public: true`
reindex(force=False) -> Status
```

### 4.4 Persistenz-Schema (SQLite)
```sql
pages       (path, title, mtime, created_at, frontmatter_json, content_hash)
links       (from_path, to_path, link_text)
embeddings  (path, vector, model_version)         -- via sqlite-vec
personas    (path, voice_sample, themes_json, era_marker, hash)
runs        (started_at, action, pages_affected)  -- audit
```

### 4.5 Refresh-Strategie
- File-Watcher (`watchdog`) auf `~/wiki/` — bei Page-Change: nur diese Page neu indexieren
- Embedding-Recomputation nur wenn `content_hash` sich geändert hat
- Persona-Re-Extract nur bei substantiellen Änderungen (>20% Content-Diff)

## 5. Komponente: synesthesia (#33)

### 5.1 Verantwortlichkeit
Erzeugt aus dem Vault-Graph eine begehbare 3D-Stadt — lokal als full-vault, optional als public-curated-subset für die Site.

### 5.2 Layout-Algorithmus
- Cluster (semantic + tag-basiert) → Bezirke
- Pages → Häuser (Höhe = Wikilink-Anzahl, Helligkeit = Frische, Farbe = Cluster)
- Synthesis-Pages → Wahrzeichen (größer, leuchtend)
- Decay-Pages → sichtbar verfallend (Texturen, Risse, Moos)
- Force-directed Layout (3D), gerendert mit Three.js

### 5.3 Two Render Targets
**Target A: Lokal Full-Vault**
- CLI-Aufruf: `synesthesia render --output ~/wiki-3d.html`
- Self-contained HTML mit eingebetteter Geometrie + JSON-Daten
- Keine Privacy-Filter — du siehst alles

**Target B: Public Curated Subset**
- CLI-Aufruf: `synesthesia render --public-only --output ./apps/portfolio_sync/build/vault-3d.html`
- Filtert via `core.privacy.public_pages()` — nur Pages mit `public: true`
- Wird von `portfolio_sync` als statische Datei in cv.dynamic-dome.com eingebettet

### 5.4 Privacy-Schutz (kritisch)
- `--public-only` ist **Default**. `--full-vault` muss explizit gesetzt sein.
- Tests verifizieren: kein public-Build enthält jemals Page-Pfade, die nicht via `public_pages()` zurückkommen.

## 6. Komponente: séance (#34)

### 6.1 Verantwortlichkeit
Macht beliebige Wiki-Pages zu Gesprächspartnern. Nutzt das `personas`-Profil aus der Engine plus aktuelles LLM für die Konversation.

### 6.2 Zwei Frontends parallel

**Frontend A — MCP-Tool (Phase 2):**
- Tool `seance.summon(page_path)` setzt Claude in Persona-Mode
- System-Prompt aus `core.persona.get_persona(path)` + Page-Content
- Konversation läuft in der Claude-Code-Session
- Tool `seance.commit_insight(page_path, what_i_learned)` schreibt Insight zurück (append-only, separater Frontmatter-Block)

**Frontend B — Web-UI (Phase 1):**
- FastAPI + Server-Sent-Events
- URL: `http://localhost:7777/seance`
- UI: Page-Picker links, Chat-Fenster rechts, "Era-Marker" zeigt *wann* die Page geschrieben wurde
- Konversationen in `.vault-engine.db` Tabelle `seance_sessions` persistiert
- Optional: Multi-Page-Séance — bis zu 3 Personas im Raum

### 6.3 Anti-Halluzinations-Disziplin
- Persona darf nur sagen was *in der Page steht* oder *direkt verlinkt ist*
- System-Prompt enthält explizite "Du weißt nichts, was nicht in dieser Page oder ihren neighbors steht"
- Wenn User nach Wissen fragt, das nicht im Persona-Scope ist: Persona muss "das wusste ich damals nicht" antworten

## 7. Komponente: living-portfolio (#35)

### 7.1 Verantwortlichkeit
Synct curated Wiki-Anteile in das `cv-dynamic-dome`-Projekt als lebende Site-Inhalte.

### 7.2 Phase 1 — MVP-Funktionen
- `portfolio_sync sync` — Findet alle Pages mit `public: true`, schreibt sie als markdown-Routes ins cv-dynamic-dome-Projekt
- `portfolio_sync now` — Generiert `/now`-Page aus letzter Session-Note + offenen Wiki-TODOs
- Freshness-Badge pro Page: "zuletzt überdacht: 3 Wochen" (aus Engine-mtime)

### 7.3 Phase 2 — Erweiterungen
- Version-History-Modal pro Page (zeigt git-Verlauf der Page)
- 3D-Vault-Embed (`vault-3d.html` aus Synesthesia public build)
- /denken-Page mit Belief-Evolution (für später, wenn #27 belief-evolution-mcp gebaut)

### 7.4 Privacy-Modell — Default Private
- Pages ohne `public: true` werden **nie** synct
- `portfolio_sync sync --dry-run` zeigt was passieren würde, vor dem realen Sync
- Pre-Sync-Hook: Liste der zu syncenden Pages wird in `.last-sync.json` geschrieben — User kann reviewen, dann manuell `portfolio_sync apply` aufrufen
- Audit-Log in `.vault-engine.db` Tabelle `sync_runs`

### 7.5 Markierungsstrategie für 953 Pages
Vorgehen für initiales Frontmatter-Pflegen:
1. Default: alles privat (kein `public:`-Frontmatter = privat)
2. Cluster-basierte Pre-Selektion: Synthesis-Pages und Topics-Pages zuerst reviewen
3. User markiert in Batch: `portfolio_sync mark --interactive` zeigt Page für Page mit Vorschau, User kann y/n entscheiden
4. Markierung schreibt `public: true` in Frontmatter

## 8. Phase 1 — MVP-Scope (10-14 Tage)

| Komponente | Phase 1 | Phase 2 |
|---|---|---|
| **vault-engine** | Schichten 1+2 (mech + sem) komplett | Schicht 3 (Persona) hinzu |
| **synesthesia** | Lokal full-vault HTML | Public curated subset |
| **séance** | Web-UI mit Voice aus Frontmatter+Content (ohne Persona-Layer-Vollausbau) | MCP-Tool, Multi-Page, commit_insight |
| **living-portfolio** | Auto-Sync + /now + Freshness-Badges | Version-History, 3D-Embed |

**Phase-1-Akzeptanzkriterien:**
- Engine indexiert 953 Pages in <10min initial
- `vault-engine-mcp` antwortet auf alle Phase-1-Tools in <500ms
- Synesthesia rendert lokales 3D-HTML mit ≥90% der Pages sichtbar
- Séance-UI startet, lädt Page, führt Conversation mit Anti-Halluzinations-Disziplin
- Portfolio-Sync mit `--dry-run` zeigt korrekte Page-Liste, sync-apply schreibt Site-Routes

## 9. Risiken und Gegenmaßnahmen

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|---|---|---|
| sentence-transformers Windows-Quirks | Mittel | Frühe Spike — Tag 1 prüfen, ob Modell auf Windows ohne Pain läuft |
| sqlite-vec Maturity (relativ neu) | Mittel | Fallback: numpy + cosine-sim in Memory bei <5k Pages |
| Privacy-Leak bei Public-Build | **Hoch** | Tests verifizieren explizit, dass kein nicht-public Page-Pfad im Build erscheint. Pre-commit-Check. |
| Persona-Halluzinationen in Séance | Hoch | Strict-Mode im System-Prompt + Eval-Suite mit "darf nicht wissen"-Tests |
| 953-Pages-Frontmatter-Markierung | Hoch (User-Aufwand) | Interactive-Mark-Tool macht den Marathon erträglich, kann pausiert werden |
| 3D-Layout für 953 Knoten unleserlich | Mittel | Initial: Top-300 nach Wikilink-Anzahl + Synthesis. Zoom-out zeigt Cluster-Aggregate, Zoom-in zeigt Pages. |
| Engine-Refresh blockiert Vault-Operationen | Niedrig | Refresh in Background-Thread, Read-Calls nutzen Stale-OK Snapshot |
| Scope-Creep zwischen Konsumenten | Hoch | Master-Plan + Phase-Gates verhindern Mischen von Phase-1- und Phase-2-Features |

## 10. Was wir explizit *nicht* bauen (YAGNI)

- Kein Push-Sync via File-Watcher zur Site (nur explizit aufgerufen)
- Kein Multi-User-Modus (Vault gehört einem User)
- Kein eigener Auth-Layer für Séance-UI (lokal-only, Bind an 127.0.0.1)
- Keine GraphQL-API (MCP reicht)
- Kein Cloud-Embedding-Provider
- Keine Voice-Synthesis für Séance (Text-Chat reicht)
- Kein Wiki-Edit-Mode in Séance/Synesthesia (Read-only — Schreiben nur via `commit_insight` und `mark`)

## 11. Offene Fragen für Phase-2-Entscheidung

Werden geparkt, jetzt nicht beantworten:
- Soll Séance-UI öffentlich auf cv.dynamic-dome.com ausgestellt werden? (eher nein — privates Reflexions-Tool)
- Wann sind Embeddings "veraltet" — alle 6 Monate Re-Embedding mit neuem Modell?
- Brauchen wir ein eigenes "Page-Identity"-Konzept, das Renames überlebt?
- Soll der 3D-Vault auch begehbar sein (FPS-Mode) oder reicht Orbit-Camera?

## 12. Spec-Self-Review (vom Autor)

**Placeholder-Scan:** Keine TBDs gefunden.
**Internal Consistency:** Architektur (Section 3) und Komponenten-Beschreibungen (4-7) sind stimmig. Phase-Tabelle (8) deckt sich mit Komponenten-Sections.
**Scope-Check:** Scope ist groß aber durch Phase 1/2-Trennung und MVP-Definition handhabbar. Master-Plan macht Multi-Session-Charakter explizit.
**Ambiguity-Check:**
- "Persona" — eindeutig definiert in 4.2 Schicht 3.
- "Living" — eindeutig definiert in 7.2/7.3.
- "Public" — eindeutig: `public: true` in Frontmatter, default fehlt = privat.

Bereit für User-Review.
