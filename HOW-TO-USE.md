# How to Use Living-Vault

Index/Wegweiser durch das Projekt — verlinkt auf die jeweils ausfuehrlichen `docs/`-Dateien statt sie zu duplizieren.

> Status: Living-Vault ist **fertig** (Master-Plan-Phasen 0-14 ✅, 2026-05-10).
> Diese Datei ist ein Lese-Einstieg, kein Tutorial.

---

## Was ist Living-Vault?

Eine Engine fuer Markdown-Vaults (z.B. Obsidian) **plus drei Konsumenten**, die denselben Vault aus verschiedenen Linsen sichtbar machen:

```
  ┌──────────────────────────────────┐
  │   Vault Engine (Indexer + DB)    │  ← liest Markdown, Wikilinks, Frontmatter
  └──────────────┬───────────────────┘
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
  ┌─────────┐ ┌────────┐ ┌──────────┐
  │ Synes-  │ │ Séance │ │ Portfolio│
  │ thesia  │ │ (Chat) │ │  Sync    │
  │  (3D)   │ │        │ │ (Public) │
  └─────────┘ └────────┘ └──────────┘
   mechanisch   persona-  semantisch
                 haft
```

**Three-Layer-These (aus der Retro-Synthese):** Eine Engine, drei Linsen — mechanisch (Graph), semantisch (Public-Subset), persona-haft (Pages koennen sprechen).

**Verifiziert generisch:** Living-Vault funktioniert gegen beliebige Obsidian-aehnliche Vaults, nicht nur gegen `~/wiki`. PoC am 2026-05-11 gegen `~/Desktop/kompetenz-wiki` mit 193 Pages, 840 Edges, **ohne Code-Aenderung**. Siehe [[wiki/todos/2026-05-11-living-vault-kompetenz-wiki-publishing]] im Obsidian-Wiki.

---

## Setup (einmalig)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[embeddings,dev]"
pytest -q   # 273 Tests sollten gruen sein
```

Drei CLI-Tools werden als Entry-Points installiert:
- `living-vault` — CLI (index, history, extract-voice)
- `living-vault-mcp` — Vault-Engine als MCP-Server (9 Tools)
- `seance-mcp` — Séance als MCP-Server (5 Tools)

---

## Die drei Konsumenten — was sie tun, wie sie laufen

### 1. Vault Engine — das Fundament

**Was:** Indexiert einen Markdown-Vault in eine SQLite-DB (`.vault-engine.db`). Erkennt Pages, Wikilinks `[[…]]`, Frontmatter-Felder (`tags`, `aliases`, `supports`, `depends_on`, `applies_to`), Backlinks. Optional: Embeddings.

**Wann nutzen:** Vor jedem Run der drei Konsumenten — sie alle lesen aus der DB.

**Wie:**
```powershell
living-vault index --vault "C:\Users\domes\wiki\wiki" --db "C:\Users\domes\wiki\.vault-engine.db" --no-embed
```

**Als MCP-Server (fuer Claude Code):** Siehe [`docs/RUN-MCP-SERVER.md`](docs/RUN-MCP-SERVER.md). Bietet 9 Tools (Search, Backlinks, Page-Read, History, etc.).

---

### 2. Synesthesia — die 3D-Darstellung

**Was:** Rendert einen Subset des Vaults als interaktiven 3D-Graph (WebGL, Hover-driven History-Panel, Cluster-Faerbung). **Privacy als Architektur:** nur Pages auf der Allowlist landen im Public-Build, der Rest existiert fuer den Renderer nicht.

**Wann nutzen:** Zum Veroeffentlichen eines Vault-Subsets unter eigener Domain.

**Wie (Public-Build gegen `~/wiki`):**
```powershell
./scripts/deploy-public-vault.ps1
```
Defaults sind in Phase-13-Fix kalibriert (`-Vault $HOME\wiki\wiki`, Allowlist unter `docs/public-allowlist.txt`, Output `out-vault/`).

**Wie (gegen anderen Vault, z.B. kompetenz-wiki):**
```powershell
./scripts/deploy-public-vault.ps1 `
    -Vault "C:\Users\domes\Desktop\kompetenz-wiki\wiki" `
    -Db "C:\Users\domes\Desktop\kompetenz-wiki\.vault-engine.db" `
    -Allowlist "C:\Users\domes\Desktop\kompetenz-wiki\public-allowlist.txt" `
    -OutDir ".\out-vault-kompetenz"
```

**Deploy auf eigene Domain:** Siehe [`docs/DEPLOY-PUBLIC-VAULT.md`](docs/DEPLOY-PUBLIC-VAULT.md) (Cloudflare Pages / Netlify / GitHub Pages).

**Output-Files im `out-vault/`:**
- `index.html` — der eigentliche 3D-Renderer
- `pages.json` — Nodes + Edges fuer den Graphen
- `history.json` — git-log pro Page (Phase 13)
- `manifest.json` — Build-Metadata (schema_version=2)

---

### 3. Séance — die "Pages, die sprechen"

**Was:** Ein Roundtable-Chat-UI (FastAPI + Vanilla JS), in dem bis zu 8 Pages "summoned" werden und im Gespraech antworten. Jede Page hat eine extrahierte **Stimme** (Stylometric + LLM-distilled, siehe Phase 9). Modus: User-Frage geht an alle Pages, Antworten kommen aus der Sicht der jeweiligen Page, gestuetzt auf deren Inhalt + Backlinks.

**Wann nutzen:** Wenn du mit deinem Vault "sprechen" willst — z.B. drei alte Notizen zum gleichen Thema gleichzeitig befragen.

**Wie (UI-Server):**
```powershell
uvicorn living_vault.apps.seance_ui.app:app --reload --port 8000
# dann http://localhost:8000
```

**Wie (als MCP-Tool fuer Claude Code):**
Konfiguration in `~/.claude.json` oder via `claude mcp add`. Bietet 5 Tools:
- `summon` — Personas (Pages) waehlen
- `say` — eine Frage an alle gleichzeitig
- `commit_insight` — Erkenntnis aus der Konversation persistieren
- `list_insights`, `list_sessions` — Historie

Voice-Extraction (Phase 9) ist **separat**:
```powershell
living-vault extract-voice --help
```

**Vision-Idee:** [`docs/VISION-DIARY-SEANCE.md`](docs/VISION-DIARY-SEANCE.md) — Tagebuch-Séance ("Sprich mit der Person, die du warst"). Eigener spaeterer Sprint.

---

### 4. Portfolio Sync — der semantische Konsument

**Was:** Synchronisiert ausgewaehlte Vault-Pages in ein Portfolio-Site-Repo (z.B. `dynamic-dome.com`), inkl. Freshness-Badges. Auto-Sync mit Last-Updated-Indikator.

**Wann nutzen:** Wenn ein bestehendes Portfolio-Repo Wiki-Pages als Quelle haben soll, ohne dass du sie zweimal pflegst.

**Wie:** `living_vault.apps.portfolio_sync` — Details in den Phase-1/-9-Checklisten unter `docs/`.

---

## Version History (Phase 13)

Jede Page im Public-Vault hat ein Hover-driven History-Panel rechts unten im 3D-Modell. Lazy-fetcht git log fuer die Page (max 10 Commits, `--follow` fuer Renames). CLI:

```powershell
living-vault history "concepts/agentic-ai.md" --vault "C:\Users\domes\wiki\wiki" --limit 10
```

Voraussetzungen: Vault ist ein git-Repo, `core/history.py` walked vom `vault_root` nach oben bis zum naechsten `.git`-Verzeichnis.

---

## Multi-Vault-Setup

Living-Vault ist **bereits ein generischer Vault-Reader** — alle CLI-Schnittstellen (`--vault`, `--db`, `--allowlist`, `--out-dir`) nehmen beliebige Pfade. Es braucht keine Code-Generalisierung, nur saubere Konventionen pro Vault:

1. Eigene `.vault-engine.db` neben dem Vault
2. Eigene `public-allowlist.txt` (Format: ein Relpath pro Zeile, **relativ zum Vault-Content-Root**, identisch mit `pages.path` in der DB)
3. Eigener `out-vault-<name>/`-Output

PoC-Belege siehe [[wiki/queries/2026-05-11-session-living-vault-blueprint-poc]] im Obsidian-Wiki.

**Geplanter sauberer Refactor** (Variante B, noch nicht implementiert): TOML-Profile unter `config/vaults/{name}.toml`, CLI `living-vault deploy --profile <name>`. Siehe Wiki-TODO `2026-05-11-living-vault-kompetenz-wiki-publishing.md`.

---

## Wo welche Dokumentation lebt

| Datei | Inhalt |
|---|---|
| `README.md` | Knapper Setup-Block (4 Zeilen) |
| `HOW-TO-USE.md` | Diese Datei — Index/Wegweiser |
| `docs/plans/2026-05-08-living-vault-master-plan.md` | Master-Plan (14 Phasen, alle ✅) |
| `docs/PHASE-N-CHECKLIST.md` (N=1,9-14) | Phasen-Abschlussberichte mit Acceptance-Criteria |
| `docs/DEPLOY-PUBLIC-VAULT.md` | Drei Deploy-Optionen (Cloudflare/Netlify/GitHub Pages) |
| `docs/RUN-MCP-SERVER.md` | Vault-Engine-MCP in Claude Code einbinden |
| `docs/VISION-DIARY-SEANCE.md` | Geparkte Vision (nicht implementiert) |
| `docs/superpowers/specs/` | Architektur-Specs pro Phase |
| `~/wiki/wiki/synthesis/2026-05-10-living-vault-retro.md` | Retro-Synthese mit uebertragbaren Lessons (im Obsidian-Wiki) |
| `~/wiki/wiki/entities/living-vault.md` | Wiki-Entity-Seite (im Obsidian-Wiki) |

---

## Wenn etwas nicht funktioniert

- **`history.json` ist leer im Live-Vault** → `vault_root\relpath` zeigt eine Ebene zu hoch. Siehe Phase-13-Fix-Commit `4ca72c8` und Learning L1.
- **Allowlist-Path nicht gefunden** → Pfade muessen **ohne** `wiki/`-Prefix sein, identisch mit `pages.path` in der DB. Quick-Check: `python -c "import sqlite3; print('\n'.join(r[0] for r in sqlite3.connect('.vault-engine.db').execute('SELECT path FROM pages LIMIT 5')))"`.
- **Séance-UI gibt 500** → Pruefen ob `.vault-engine.db` existiert und `personas`-Tabelle gefuellt ist (`living-vault extract-voice` muss vorher gelaufen sein).
- **MCP-Server haengt** → Encoding-Setup pruefen (Windows-spezifisch, siehe `mcp-server-windows-setup` Skill im globalen `~/.claude/`).

---

## Carry-Over (was noch offen ist)

Living-Vault ist als Tool fertig. Offene Items sind alle **inkrementell**, kein neuer Master-Plan-Phase-Slot:

- Variante B (TOML-Profile) — wenn jemand 2+ Vaults regelmaessig publiziert
- Variant-Templates `galaxy`/`city`/`network` mit History-Panel (heute nur `vault-3d.html.j2`)
- Wiki-Export von Insights (`commit_insight --export` Flag) — sobald 1. echte Insight da ist
- Belief-Evolution als 4. Konsument — eigener Master-Plan, nicht Phase 15

Vollstaendige Liste in der Retro-Synthese im Wiki.
