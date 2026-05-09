# Phase 13 — Version-History (Implementation Plan)

**Datum:** 2026-05-10
**Spec:** [`../specs/2026-05-10-phase-13-version-history.md`](../specs/2026-05-10-phase-13-version-history.md)
**Methodik:** Direkte Implementierung pro Sub-Task; Subagent nur falls Komplexität verlangt.

## Sub-Tasks

| # | Titel | Methode | Akzeptanz |
|---|---|---|---|
| 13.1 | `core/history.py` + TTL-LRU + Tests | direkt | Subprocess-Pfad mit Fixture-Repo, Cache-Hit verifiziert |
| 13.2 | `vault-engine-mcp.page_history` Tool | direkt | `_tool_page_history` Test grün |
| 13.3 | `public_build` schreibt `history.json` + `--no-history` Flag | direkt | history.json schema v1, manifest schema_version=2 |
| 13.4 | `vault-3d.html.j2` History-Modal hinter `include_history` | direkt | Render-Test mit/ohne Flag |
| 13.5 | `living-vault history` CLI + Voll-Test-Pass | direkt | 270+ Tests grün |
| 13.6 | Master-Plan-Korrektur + PHASE-13-CHECKLIST + Close | direkt | Phase-13 ✅ |

## 13.1 — core/history.py

**Files:**
- `living_vault/core/history.py` — NEU
- `tests/test_history.py` — NEU

**Implementierung:**

```python
# core/history.py
import subprocess, time
from pathlib import Path
from typing import Any

_DEFAULT_TTL_SECONDS = 60.0
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 100
_SUBPROCESS_TIMEOUT_SECONDS = 5.0

# (key) → (timestamp, value)
_CACHE: dict[tuple, tuple[float, list[dict]]] = {}

def _find_git_root(start: Path) -> Path | None:
    p = start.resolve()
    while True:
        if (p / ".git").exists():
            return p
        if p.parent == p:
            return None
        p = p.parent

def page_history(
    vault_root: Path,
    relpath: str,
    *,
    limit: int = _DEFAULT_LIMIT,
    ttl: float = _DEFAULT_TTL_SECONDS,
) -> list[dict]:
    if limit < 1:
        limit = 1
    if limit > _MAX_LIMIT:
        limit = _MAX_LIMIT
    key = (str(Path(vault_root).resolve()), relpath, limit)
    now = time.time()
    cached = _CACHE.get(key)
    if cached is not None and now - cached[0] < ttl:
        return cached[1]
    result = _git_log_for_path(Path(vault_root), relpath, limit)
    _CACHE[key] = (now, result)
    return result

def _git_log_for_path(vault_root: Path, relpath: str, limit: int) -> list[dict]:
    git_root = _find_git_root(vault_root)
    if git_root is None:
        return []
    # rel-to-git-root path
    abs_target = (vault_root / relpath).resolve()
    try:
        rel_to_repo = abs_target.relative_to(git_root)
    except ValueError:
        return []
    sep = "\x1f"
    fmt = sep.join(["%h", "%aI", "%an", "%s"])
    try:
        proc = subprocess.run(
            ["git", "-C", str(git_root), "log",
             "-n", str(limit), f"--format={fmt}",
             "--", str(rel_to_repo).replace("\\", "/")],
            capture_output=True, text=True, encoding="utf-8",
            timeout=_SUBPROCESS_TIMEOUT_SECONDS, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    rows: list[dict] = []
    for line in proc.stdout.splitlines():
        parts = line.split(sep)
        if len(parts) != 4:
            continue
        sha, date, author, subject = parts
        rows.append({
            "sha": sha, "date": date,
            "author": author, "subject": subject,
        })
    return rows

def clear_cache() -> None:
    """For tests."""
    _CACHE.clear()
```

**Tests (mind. 8):**
1. Fixture-Repo (tmp_path mit `git init`, `user.email/user.name` per local config,
   3 Commits auf gleicher Datei) → page_history liefert 3 Rows, neueste zuerst
2. Limit funktioniert (3 Commits da, limit=2 → 2 Rows)
3. Page existiert nicht → []
4. vault_root außerhalb eines Git-Repos → []
5. Pfad außerhalb des Repos (relpath traversiert nach oben) → []
6. TTL-Cache: 2× Aufruf — zweiter darf subprocess NICHT erneut spawnen.
   Verifiziert via `monkeypatch` von `subprocess.run` mit Counter.
7. `clear_cache()` setzt Cache zurück
8. `limit > 100` wird auf 100 gecappt

**Test-Isolation:**
- `pytest.importorskip("subprocess")` ist nicht nötig
- Fixture: `tmp_path / "repo"`, `git init`, `git -C ... config user.name/email`
- Fixture läuft NUR wenn `shutil.which("git")` existiert (sonst skip)
- Vor jedem Test `history_mod.clear_cache()` (autouse fixture)

## 13.2 — vault-engine-mcp.page_history

**Files:**
- `living_vault/mcp_servers/vault_engine/server.py` — Edit (Tool ergänzen)
- `tests/test_mcp_server.py` — Edit (1 neuer Test)

**Edit-Stellen:**

```python
# am Anfang
from living_vault.core import history as history_mod

# ---- tool implementations ----
def _tool_page_history(path: str, limit: int = 10) -> list[dict]:
    return history_mod.page_history(_vault_root(), path, limit=limit)

# ---- MCP tool registration ----
@mcp.tool()
def page_history(path: str, limit: int = 10) -> list[dict]:
    """Last N commits affecting the page (newest first)."""
    return _tool_page_history(path, limit)
```

**Test:** Fixture-Repo + 1 Commit → `_tool_page_history` liefert ≥1 Row.

## 13.3 — synesthesia-public-build mit history.json

**Files:**
- `living_vault/apps/synesthesia/render.py` — Edit
- `tests/test_synesthesia_render.py` — Edit (3 neue Tests)

**Implementierung in `public_build`:**

```python
def public_build(
    vault_root: Path, db_path: Path, allowlist_path: Path,
    out_dir: Path, *, embed_url: str = "...",
    include_history: bool = True,
) -> dict:
    # ... existing logic ...
    if include_history:
        history = {
            "schema": 1,
            "built_at": built_at,
            "pages": {
                p: history_mod.page_history(vault_root, p, limit=10)
                for p in public_paths
            },
        }
        (out_dir / "history.json").write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        manifest["schema_version"] = 2
        manifest["history_included"] = True
    else:
        manifest["history_included"] = False
    # ... write manifest ...
```

**CLI-Flag in `public_build_cli`:**
```python
@click.option("--no-history", is_flag=True,
              help="Skip generating history.json")
def public_build_cli(..., no_history: bool):
    public_build(..., include_history=not no_history)
```

**Tests:**
- Default-Aufruf: `history.json` wird geschrieben, schema=1, pages-dict hat
  entries für die 2 Test-Pages, manifest schema_version=2
- `include_history=False`: keine `history.json`, manifest schema_version=2
  + `history_included: false`
- Existierende Determinism-Tests bleiben grün (history_included field is
  the only new manifest field; built_at exclusion fence unchanged)

**Achtung Phase-11-Tests:** `test_render_writes_html` etc. dürfen NICHT brechen.
`include_history` default-true, aber Phase-11-Tests setzen vault_root nicht
auf einen Git-Repo — d.h. `page_history` liefert dort `[]` und `history.json`
ist `{"pages": {"x.md": [], "y.md": []}}`. Falls ein Test asserts auf "Files
in out-dir" macht, müsste er ergänzt werden. **Erst Tests durchlesen, dann
entscheiden ob default false sicherer ist.**

**Entscheidung nach Test-Lese:** Wenn Phase-11-Tests die exakte Datei-Liste
asserten → `include_history` default **False** lassen, CLI default True.

## 13.4 — vault-3d.html.j2 History-Modal

**Files:**
- `living_vault/apps/synesthesia/templates/vault-3d.html.j2` — Edit
- `living_vault/apps/synesthesia/render.py` — `include_history` als Jinja-Context
- `tests/test_synesthesia_render.py` — Edit (2 neue Tests)

**Template-Edit (am Ende der bestehenden Page-Card):**

```jinja
{% if include_history %}
<div id="history-panel" class="history">
  <h4>History (last 10 commits)</h4>
  <ul id="history-list"></ul>
</div>
<script>
  // history.json lazy-loaded on first node click
  let _historyData = null;
  async function showHistoryFor(pagePath) {
    if (_historyData === null) {
      try {
        const r = await fetch('history.json');
        _historyData = (await r.json()).pages || {};
      } catch (e) { _historyData = {}; }
    }
    const list = document.getElementById('history-list');
    list.innerHTML = '';
    for (const c of (_historyData[pagePath] || [])) {
      const li = document.createElement('li');
      const dateShort = c.date.slice(0, 10);
      li.textContent = `${dateShort}  ${c.sha}  ${c.subject}`;
      list.appendChild(li);
    }
  }
  // Wire it up to the existing node-click handler.
  document.addEventListener('vault-node-clicked', (e) => {
    showHistoryFor(e.detail.path);
  });
</script>
<style>
.history { margin-top: 1em; font-family: monospace; font-size: 0.85em; }
.history h4 { margin: 0.5em 0; }
.history ul { list-style: none; padding-left: 0; max-height: 12em; overflow-y: auto; }
.history li { padding: 0.2em 0; border-bottom: 1px dotted #444; }
</style>
{% endif %}
```

**Wichtig:** Das aktuelle Template hat KEIN `vault-node-clicked`-Event. Die
exakte Click-Wiring-Stelle muss beim Lesen des aktuellen Templates ermittelt
werden — möglicherweise kommt der Hook in den bestehenden Three.js-onClick-
Handler. **Dieser Sub-Task fängt mit Lesen des Templates an.**

**Tests:**
- `public_build(include_history=True)` → HTML enthält "History (last 10 commits)"
- `public_build(include_history=False)` → HTML enthält NICHT "History"
  (byte-identisch zu Phase-11-Render)

## 13.5 — CLI + Voll-Test

**Files:**
- `living_vault/cli.py` — Edit (history-Subcommand)
- `tests/test_cli.py` — Edit (1 neuer Test)

**CLI:**
```python
@cli.command("history")
@click.argument("path")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--limit", default=10, type=int)
def history_cmd(path: str, vault: str, limit: int) -> None:
    """Show git history of a vault page."""
    rows = history_mod.page_history(Path(vault), path, limit=limit)
    if not rows:
        click.echo("(no history found)")
        return
    click.echo(f"{'sha':<10} {'date':<25} {'author':<15} subject")
    for r in rows:
        click.echo(f"{r['sha']:<10} {r['date']:<25} {r['author']:<15} {r['subject']}")
```

**Voll-Test:** `pytest -q` → ≥270 grün.

## 13.6 — Master-Plan + Close

1. **Master-Plan-Edit:** Phase-13-Zeile von "in living-portfolio" auf
   "in synesthesia-public Vault" korrigieren, Status auf ✅.
2. **PHASE-13-CHECKLIST.md** mit allen Sub-Task-Stages.
3. **Aktuelle-Position-Absatz** im Master-Plan aktualisieren.
4. **Close-Commit:** `living-vault | Phase-13 ✅ CLOSED — version-history shipped`.

## Commit-Konvention

- `living-vault | Phase-13: spec + plan (version-history)`
- `living-vault | Phase-13.1: core/history.py + TTL-LRU + tests`
- `living-vault | Phase-13.2: vault-engine-mcp.page_history tool`
- `living-vault | Phase-13.3: public-build writes history.json`
- `living-vault | Phase-13.4: vault-3d template History-Modal`
- `living-vault | Phase-13.5: living-vault history CLI + full pass`
- `living-vault | Phase-13.6: master-plan corrected + checklist`
- `living-vault | Phase-13 ✅ CLOSED`

## Out-of-Scope für Phase 13

- Diff-Render im Modal (Phase 13.x)
- `--follow` für Renames (Phase 13.x)
- Snapshot pro Commit (out — zu groß)
- DB-Cache-Tabelle für History (out — TTL-LRU reicht)
- Author-Display im Public-UI (intern ja, public nein)
- History für CV-Site / portfolio-sync (out — wir haben den Modal-Ort
  bewusst auf vault.dynamic-dome.com gemoved)
