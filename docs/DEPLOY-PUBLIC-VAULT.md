# Deploy: Public Vault → `vault.dynamic-dome.com`

Phase-11 produziert ein deploy-fertiges Verzeichnis (`out-vault/` per Default).
Diese Seite beschreibt, wie aus diesem Verzeichnis eine öffentlich erreichbare
Subroute wird.

## Quick Start

```powershell
# Aus dem Project-Root (Claude-Projekte/living-vault):
./scripts/deploy-public-vault.ps1
```

Erwartetes Output (Beispiel):

```
[deploy-public-vault] building C:\...\out-vault ...
wrote C:\...\out-vault/ (5 public, 1 skipped, edges=3)
[deploy-public-vault] build OK
  public_total           = 5
  via frontmatter        = 0
  via allowlist          = 5
  allowlist_skipped      = 1
  edges_total            = 3
  build_at               = 2026-05-09T13:42:00Z
```

Der Build allein triggert kein Deploy — er produziert nur das Bundle. Hosting
ist getrennt (siehe unten).

## Allowlist-Workflow

Phase 11 unterstützt zwei Quellen für "public":

1. **Frontmatter** — Wiki-Page hat `public: true` im YAML-Header.
2. **Allowlist** — Pfad steht in `docs/public-allowlist.txt`, eine relpath pro
   Zeile. `#` startet Kommentare, Leerzeilen erlaubt.

Stand 2026-05-09: 0 Pages mit `public: true` im Wiki. Phase-11-Builds laufen
also vorerst über die Allowlist-Quelle. Beispiel `docs/public-allowlist.txt`:

```
# Phase-11 Public-Vault Allowlist.
# Eine Wiki-relpath pro Zeile (relativ zu ~/wiki).

concepts/a2a-protokoll.md
concepts/mcp-gateway.md
sources/mcp-oekosystem/index.md
synthesis/2026-05-08-mcp-ideen-genese-notebooklm.md
```

Nach jeder Allowlist-Änderung: Skript erneut laufen lassen, dann deployen.

## Hosting-Optionen

Drei Static-Host-Pfade. Wähle je nach Account-Lage. `out-vault/` ist
self-contained (HTML + manifest.json + pages.json), keine Server-Logik nötig.

### A) Cloudflare Pages

```powershell
# Einmalig: wrangler installieren, account verbinden
npm install -g wrangler
wrangler login

# Build und deploy in einem Schwung:
./scripts/deploy-public-vault.ps1
wrangler pages deploy ./out-vault --project-name=vault-dome
```

DNS: in Cloudflare Pages → Custom Domain → `vault.dynamic-dome.com` hinzufügen.
Cloudflare verwaltet das CNAME selbst, wenn die Domain dort liegt.

### B) Netlify

```powershell
# Einmalig:
npm install -g netlify-cli
netlify login

# Build und deploy:
./scripts/deploy-public-vault.ps1
netlify deploy --dir=./out-vault --prod
```

DNS: in Netlify-UI → Domain settings → Custom domain → `vault.dynamic-dome.com`.

### C) GitHub Pages

Wenn `vault-dome` ein eigenes Git-Repo ist:

```powershell
# Build:
./scripts/deploy-public-vault.ps1 -DeployTarget "C:\Pfad\zum\vault-dome-repo"

# Im vault-dome-repo:
cd C:\Pfad\zum\vault-dome-repo
git add .
git commit -m "chore: rebuild public vault"
git push
```

Dann GitHub-Pages-Einstellung im Repo aktivieren (Branch `master` oder
`gh-pages`), Custom Domain `vault.dynamic-dome.com` hinterlegen.

## DNS

`vault.dynamic-dome.com` → CNAME auf den Static-Host:

| Host | Ziel |
|---|---|
| Cloudflare Pages | `vault-dome.pages.dev` (oder von CF gegeben) |
| Netlify | `<site-id>.netlify.app` |
| GitHub Pages | `<user>.github.io` |

DNS wird im Domain-Provider von `dynamic-dome.com` eingerichtet — das ist eine
einmalige User-Action, nicht in den Phase-11-Code-Pfad gewickelt.

## Updates

Nach jeder Wiki-Änderung, die public werden soll:

1. `~/wiki/.vault-engine.db` aktualisieren (`living-vault index --vault ~/wiki --db ~/wiki/.vault-engine.db`)
2. Gegebenenfalls `docs/public-allowlist.txt` anpassen
3. `./scripts/deploy-public-vault.ps1`
4. Hosting-Trigger laut gewähltem Pfad oben

`manifest.json` enthält `build_at` — der ist auf der Site sichtbar (Footer).
Damit erkennt der Besucher, ob die Subroute frisch ist.

## Troubleshooting

| Symptom | Ursache | Fix |
|---|---|---|
| `public_total = 0` | Allowlist leer/nicht gefunden UND keine Frontmatter-public-Pages | Allowlist befüllen ODER Frontmatter `public: true` setzen |
| `allowlist_skipped` nicht leer | Pfade in der Allowlist existieren nicht in `pages` | Tippfehler? `living-vault index ...` wieder laufen lassen? |
| HTML zeigt 0 Edges | Eine alleinstehende Public-Page hat keine Public-Nachbarn | Erwartetes Verhalten (Privacy: Edges nur zwischen Public-Pages) |
| HTML rendert nicht | Browser-Konsole — meist three.js CDN nicht erreichbar | Network/Adblocker prüfen, `unpkg.com` whitelisten |

## Out-of-Scope

Die folgenden Punkte sind **nicht** Teil von Phase 11 und brauchen separate
Phasen:

- DNS-Setup (User-Action, nicht Code)
- Auto-Sync-Hook (Wiki-Änderung → Build-Trigger) — Phase 13+
- Interaktive UI-Slider/Filter — Phase 12+
- Embed-Iframe in dome-dynamics oder cv.dynamic-dome.com — eigene Phase

## Referenzen

- Spec: [`superpowers/specs/2026-05-09-phase-11-public-vault-design.md`](superpowers/specs/2026-05-09-phase-11-public-vault-design.md)
- Plan: [`superpowers/plans/2026-05-09-phase-11-public-vault.md`](superpowers/plans/2026-05-09-phase-11-public-vault.md)
- Master-Plan: [`plans/2026-05-08-living-vault-master-plan.md`](plans/2026-05-08-living-vault-master-plan.md)
