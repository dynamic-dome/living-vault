# Phase 13 — Version-History (Design Spec)

**Datum:** 2026-05-10
**Phase im Master-Plan:** 13 (Phase 2)
**Vorgänger:** Phase 12 ✅ (séance MCP)
**Plan-Pendant:** [`../plans/2026-05-10-phase-13-version-history.md`](../plans/2026-05-10-phase-13-version-history.md)

## Ziel

Pro öffentlich-sichtbarer Vault-Page die letzten 10 Git-Commits anzeigen,
sodass Besucher des `vault.dynamic-dome.com` sehen können, wann und wie eine
Page über Zeit gewachsen ist. Die "living" Eigenschaft des Vaults wird damit
sichtbar — heute fühlt sich der Public Build wie ein statischer Snapshot an,
Phase 13 macht den zeitlichen Verlauf explizit.

## Master-Plan-Korrektur

Original-Eintrag: `Phase 13 = Version-History-Modal in living-portfolio`
(`docs/plans/2026-05-08-living-vault-master-plan.md` Zeile 51).

**Korrigiert nach AskUserQuestion 2026-05-10:** Phase 13 baut das Modal in
**synesthesia-public Vault** (`vault.dynamic-dome.com`), NICHT in
living-portfolio. Begründung: Phase 11 hat den Public-Vault als eigene Subroute
gebaut — er ist der konsistentere Ort für das History-Modal als die statische
CV-Site. living-portfolio behält nur Auto-Sync + /now + Freshness-Badges
(Phase 1).

Master-Plan-Update wird im Close-Commit (13.6) gemacht.

## User-entschiedene Optionen (2026-05-10, AskUserQuestion vor Spec)

1. **Display-Ort:** synesthesia-public Vault (`vault.dynamic-dome.com`) —
   Modal-UI im Phase-11-Standalone-Vault. Public-only.
2. **History-Tiefe:** Letzte 10 Commits, kompakt: Datum + Hash + Commit-Subject.
   Kein Diff, kein Snapshot.
3. **Caching:** Live via subprocess `git log` + LRU-Memo-Cache mit 60s TTL.
4. **Session-Scope:** Vollausbau — Engine + MCP-Tool + CLI + UI-Modal.

## Out-of-Scope (bewusst)

- **Kein Diff-Render im Modal.** Nur Commit-Liste mit Subject. Diff ist Phase 13.x.
- **Kein Snapshot pro Commit.** Wer Page X zum Zeitpunkt Y sehen will, geht
  manuell ins Wiki-Repo. Public-Vault zeigt nur "Wann hat sich was geändert".
- **Keine Cache-DB-Tabelle.** LRU-Memo-Cache reicht — bei Build-Zeit-Lookup
  ist die Page-Liste begrenzt (10 in der aktuellen Allowlist), bei Live-Lookup
  ist die TTL-Cache-Strategie billiger als Schema-Migration.
- **Kein Author-Display im Modal.** Wir extrahieren den Author intern (für
  Tests/MCP), zeigen ihn aber nicht öffentlich — der Vault ist Solo-Repo,
  Author ist trivial "domes".
- **Keine Page-Identity über Renames.** Wenn eine Page umbenannt wurde,
  zeigt `git log` die History ab dem neuen Namen. `--follow` als Phase-13.x.
- **Kein Wiki-Schreibzugriff.** Read-only.

## Architektur — neuer core/history.py-Layer

```
                  ┌────────────────────────────┐
                  │ core/history.py            │  ← NEU
                  │  page_history()            │
                  │  _git_log_for_path()       │
                  │  _lru_with_ttl()           │
                  └─────────┬──────────────────┘
                            │
              ┌─────────────┼──────────────────────┐
              ▼             ▼                      ▼
     ┌────────────┐  ┌─────────────────┐  ┌──────────────────────┐
     │ CLI:       │  │ vault-engine-   │  │ apps/synesthesia/    │
     │ living-    │  │  mcp.page_      │  │  render.py           │
     │  vault     │  │  history        │  │  public_build()      │
     │  history   │  │  (MCP tool)     │  │   → history.json     │
     └────────────┘  └─────────────────┘  └──────────┬───────────┘
                                                     │
                                                     ▼
                                          ┌──────────────────────┐
                                          │ vault-3d.html.j2     │
                                          │ History-Modal        │
                                          │  (lazy fetch)        │
                                          └──────────────────────┘
```

## `core/history.py` — Public-API

```python
def page_history(
    vault_root: Path,
    relpath: str,
    *,
    limit: int = 10,
) -> list[dict]:
    """Return latest N commits affecting `relpath`.

    Each row: {sha: str (short), date: str (ISO), author: str, subject: str}.
    Newest first. Empty list if no history (e.g. uncommitted file or path
    outside the repo).

    Calls `git log --format=... -n LIMIT -- <relpath>` once via subprocess,
    then memoizes for TTL=60s using a (vault_root, relpath, limit) key.
    """
```

**Subprocess-Aufruf:**
```python
subprocess.run(
    ["git", "-C", str(vault_root), "log",
     f"-n", str(limit),
     "--format=%h%x1f%aI%x1f%an%x1f%s",
     "--", relpath],
    capture_output=True, text=True, encoding="utf-8", check=False,
)
```

`%x1f` ist ASCII-Unit-Separator (0x1F) — zuverlässiger Trennzeichen-Ersatz für
TAB/Pipe in Commit-Messages.

**Cache:** Eigener TTL-LRU-Wrapper (60s default), nicht `functools.lru_cache`,
weil das kein TTL hat. Implementierung: dict mit `(key) → (timestamp, value)`,
Eviction auf Access wenn `time.time() - timestamp > ttl`.

**Fehlerfälle:**
- `git`-binary fehlt → `RuntimeError` mit klarer Message
- `vault_root` ist kein Git-Repo → leere Liste, KEIN Fehler (defensiver Pfad
  für Tests mit temp-Vaults ohne Git)
- `relpath` existiert nicht im Repo → leere Liste
- `git log` schreibt auf stderr aber returncode != 0 → leere Liste, log warn
- subprocess-Timeout (5s) → leere Liste, log warn

## MCP-Tool im vault-engine-mcp

Erweitert `living_vault/mcp_servers/vault_engine/server.py`:

```python
@mcp.tool()
def page_history(path: str, limit: int = 10) -> list[dict]:
    """Latest N commits affecting the page (Phase 13)."""
    return _tool_page_history(path, limit)

def _tool_page_history(path: str, limit: int) -> list[dict]:
    return history_mod.page_history(_vault_root(), path, limit=limit)
```

Achtung: `_vault_root()` liefert `~/wiki/wiki/` (das tatsächliche Page-Verzeichnis),
aber das **Git-Repo** ist `~/wiki/`. Daher muss `core.history.page_history` einen
expliziten `repo_root`-Parameter ODER selber `_vault_root().parent` nehmen.
**Entscheidung:** `core.history` akzeptiert den Page-`vault_root`, walked davon
intern bis zum nächsten `.git`-Verzeichnis hoch. Sauberer Fallback und nicht
abhängig von Konventionen.

```python
def _find_git_root(start: Path) -> Path | None:
    p = start.resolve()
    while True:
        if (p / ".git").exists():
            return p
        if p.parent == p:
            return None
        p = p.parent
```

`relpath` muss dann relativ zum `git_root` umgerechnet werden, nicht relativ
zum `vault_root`. Das Modul macht beides.

## Erweiterung in synesthesia-public-build

`apps/synesthesia/render.py public_build()` erzeugt aktuell:
- `out-vault/index.html`
- `out-vault/manifest.json` (schema v1)
- `out-vault/pages.json`

Phase 13 ergänzt:
- `out-vault/history.json` mit Schema:
  ```json
  {
    "schema": 1,
    "built_at": "2026-05-10T12:34:56Z",
    "pages": {
      "concepts/foo.md": [
        {"sha": "abc1234", "date": "2026-05-09T...", "author": "domes", "subject": "..."},
        ...
      ],
      ...
    }
  }
  ```
- `manifest.json` schema_version v1 → v2 mit neuem Feld `history_included: bool`
  (default true wenn `history.json` existiert).

Manifest-Schema-Bump v1 → v2 ist additive — fehlende Felder = v1-Default.

CLI-Flag: `synesthesia-public-build --no-history` schaltet die History-Generation
ab (für Builds wo Git-History irrelevant ist oder das Repo nicht initialisiert).

## UI — vault-3d.html.j2 History-Modal

Neue UI-Elemente, alle in `{% if include_history %}`-Block (Legacy-Renders
byte-identisch):

1. **`history.json` lazy-load** beim ersten Klick auf einen Knoten (nicht beim
   Page-Load — sonst ist der Initial-Payload zu groß bei vielen Pages).
2. **History-Panel** unten in der vorhandenen Page-Vorschau-Card:
   ```
   ┌────────────────────────────────┐
   │ concepts/foo.md                │
   │ Last edit: 5 days ago          │
   ├────────────────────────────────┤
   │ History (last 10 commits)       │
   │ • 2026-05-09 abc1234 phase-11..│
   │ • 2026-05-07 def4567 cluster..│
   │ • ...                           │
   └────────────────────────────────┘
   ```
3. **CSS-only.** Keine Animation, kein Modal-Overlay — einfach scrollbares
   `<ul>` in der bestehenden Card.

`include_history` ist neuer Jinja-Context-Param, default `False` für
Backwards-Compat. Phase-11-Tests, die kein `include_history` setzen, bleiben
byte-identisch.

## CLI

Neuer Subcommand am `living-vault`-Group:

```
living-vault history <path> [--limit N]
```

Druckt die History tabellarisch:

```
sha     date                author  subject
abc1234 2026-05-09T15:21:00 domes   living-vault | Phase-11 ✅ CLOSED
def4567 2026-05-07T11:08:33 domes   ...
```

## Test-Strategie

| Layer | Tests |
|---|---|
| `core/history.py` | git-Repo-Fixture (Init temp-Repo, 3 Commits auf Test-Page), page_history liefert 3 Rows neueste-zuerst, Limit funktioniert, leere Liste wenn Page nicht existiert, leere Liste wenn vault_root kein Git-Repo, TTL-Cache: 2x-Aufruf macht subprocess nur 1x |
| `mcp_servers/vault_engine/server.py` | `_tool_page_history`-Roundtrip mit Fixture-Repo |
| `apps/synesthesia/render.py` | `public_build(include_history=True)` schreibt `history.json` mit korrektem Schema, `--no-history`-Flag schreibt es nicht |
| `vault-3d.html.j2` | Render mit `include_history=True` enthält History-DOM, Render ohne enthält es nicht (byte-identisch zu Phase 11) |
| Bestehende Tests | Müssen alle grün bleiben (Phase-11-Render insbesondere — `{% if %}`-Default false) |

**Test-Isolation:** wie immer — `tmp_path` für Repo-Setup. Hard-Guard im
`conftest.py` schützt `~/wiki/`.

**Ziel:** 253 → 270+ Tests grün.

## Risiken

| Risiko | Maßnahme |
|---|---|
| Test-Isolation: subprocess git in tmp-Repo könnte System-git-config laden | Tests setzen `GIT_CONFIG_GLOBAL=/dev/null` Equivalent (`git -c init.defaultBranch=main` und expliziten `user.name`/`user.email` per `--local`) |
| Subprocess-Aufruf flaky auf Windows wegen PATH | Im Test eines `git --version`-Smoke-Test vorab. Wenn Git fehlt, `pytest.skip`. |
| Build-Zeit explodiert bei vielen Pages | LRU-Cache während Build hilft nicht (jede Page nur einmal abgefragt). Bei 10-Page-Allowlist: 10×~50ms = 0.5s, akzeptabel. Bei 953 Pages: 50s — derzeit nicht relevant. |
| `git log --follow` wäre besser für Renames, ist aber komplex | Phase 13.x. v1 macht ohne `--follow`. |
| Cache-Stale: User editiert + committed während dev-Server läuft | TTL=60s ist akzeptabel. Public-Build nutzt cache nicht (eigener Prozess). |
| Encoding-Probleme bei Umlauten in Commit-Subjects | `text=True, encoding="utf-8"` — Repo committet schon mit utf-8 |
| Schema v1 → v2 bricht alte manifest-Reader | Additiv: `history_included: bool` mit default true. v1-Reader ignoriert es. |

## Akzeptanzkriterien

1. `core.history.page_history(repo, "concepts/foo.md")` liefert 10-er Liste mit
   `{sha, date, author, subject}` für Test-Repo.
2. TTL-Cache funktioniert: 2× Aufruf mit gleichem Key macht subprocess nur 1×.
3. `vault-engine-mcp.page_history` MCP-Tool als Adapter funktioniert.
4. `synesthesia-public-build` schreibt `history.json` (default), `--no-history`
   schaltet ab.
5. `vault-3d.html.j2` mit `include_history=True` rendert History-Liste, ohne
   `include_history` byte-identisch zu Phase-11-Output.
6. CLI `living-vault history <path>` druckt tabellarische History.
7. Test-Suite-Total ≥ 270 grün, keine Regression.
8. Real-Run gegen `~/wiki` mit 10-Page-Allowlist baut history.json mit
   3+ Pages mit echter History (Sichtprüfung).

## Was NICHT verhandelt wird

- 4 User-entschiedene Optionen
- LRU-TTL-Cache statt DB-Tabelle
- 10 Commits Limit (anpassbar via API, aber Default fix)
- Manifest-Schema-Bump v1 → v2 additiv
