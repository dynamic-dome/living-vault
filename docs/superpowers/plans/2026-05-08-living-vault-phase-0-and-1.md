# Living-Vault Phase 0 + Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `vault-engine-mcp` foundation (mechanical + semantic layers) and three thin Phase-1 consumers — Synesthesia (local 3D), Séance (Web-UI), Living-Portfolio (auto-sync + /now + freshness) — all reading from a single SQLite-backed vault state.

**Architecture:** Monolith repo `living-vault/` with `core/` Python library (pure, testable), one MCP server `vault-engine-mcp` wrapping `core/`, and three independent app folders that import `core/` directly (no MCP latency between core and apps). State persisted in `~/wiki/.vault-engine.db`.

**Tech Stack:** Python 3.11+, FastMCP, FastAPI, sentence-transformers (with numpy+cosine fallback), sqlite-vec (with BLOB-column fallback), Three.js (CDN-loaded in HTML template), pytest, watchdog (file events), python-frontmatter, click (CLIs).

**Master-Plan:** [`../../plans/2026-05-08-living-vault-master-plan.md`](../../plans/2026-05-08-living-vault-master-plan.md)
**Design-Doc:** [`../specs/2026-05-08-living-vault-trio-design.md`](../specs/2026-05-08-living-vault-trio-design.md)

**Conventions:**
- All paths absolute or relative to repo root `C:\Users\domes\desktop\Claude-Projekte\living-vault\`
- Repo root for shell commands: assume `cd` already at repo root unless stated
- Commit messages follow master-plan convention: `living-vault | Phase-{N}: {status}`
- Wiki path: `C:\Users\domes\wiki\wiki\` (the actual markdown corpus)
- DB path: `C:\Users\domes\wiki\.vault-engine.db` (one level above the wiki/wiki/ subdir)
- Python import path: install repo as editable (`pip install -e .`) — all imports use `from living_vault.core.X import Y`

---

## Phase 0 — Setup, Skeleton, Spike (Tasks 1-7)

### Task 1: Repo skeleton and pyproject

**Files:**
- Create: `pyproject.toml`
- Create: `living_vault/__init__.py`
- Create: `living_vault/core/__init__.py`
- Create: `living_vault/mcp_servers/__init__.py`
- Create: `living_vault/mcp_servers/vault_engine/__init__.py`
- Create: `living_vault/apps/__init__.py`
- Create: `living_vault/apps/synesthesia/__init__.py`
- Create: `living_vault/apps/seance_ui/__init__.py`
- Create: `living_vault/apps/portfolio_sync/__init__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "living-vault"
version = "0.1.0"
description = "Vault engine + 3 consumers (synesthesia, seance, living-portfolio)"
requires-python = ">=3.11"
dependencies = [
  "python-frontmatter>=1.0",
  "click>=8.1",
  "fastmcp>=0.4",
  "fastapi>=0.110",
  "uvicorn>=0.27",
  "watchdog>=4.0",
  "numpy>=1.26",
  "anthropic>=0.34",
  "jinja2>=3.1",
]

[project.optional-dependencies]
embeddings = [
  "sentence-transformers>=2.7",
  "sqlite-vec>=0.1.1",
]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
]

[project.scripts]
living-vault-mcp = "living_vault.mcp_servers.vault_engine.server:main"
synesthesia = "living_vault.apps.synesthesia.render:cli"
portfolio-sync = "living_vault.apps.portfolio_sync.sync:cli"

[tool.setuptools.packages.find]
include = ["living_vault*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
venv/
build/
dist/
.vault-engine.db
.vault-engine.db-journal
.vault-engine.db-wal
.vault-engine.db-shm
*.log
.DS_Store
node_modules/
```

- [ ] **Step 3: Write `README.md`**

```markdown
# living-vault

Vault engine + 3 consumers: Synesthesia (3D), Séance (chat), Living-Portfolio (site).

See `docs/plans/2026-05-08-living-vault-master-plan.md` and `docs/superpowers/specs/2026-05-08-living-vault-trio-design.md`.

## Setup

    python -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[embeddings,dev]"
    pytest -q
```

- [ ] **Step 4: Create empty `__init__.py` files**

All `__init__.py` files listed in **Files** above contain a single line:
```python
"""living_vault package."""
```

- [ ] **Step 5: Commit**

```powershell
cd C:\Users\domes\desktop\Claude-Projekte\living-vault
git init
git add .
git commit -m "living-vault | Phase-0: repo skeleton and pyproject"
```

---

### Task 2: Virtualenv + editable install

**Files:** None (environment setup only)

- [ ] **Step 1: Create venv and install**

```powershell
cd C:\Users\domes\desktop\Claude-Projekte\living-vault
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Expected output: `Successfully installed living-vault-0.1.0 ...`

- [ ] **Step 2: Verify**

```powershell
pytest --collect-only
```

Expected: `collected 0 items` (no tests yet, but no import errors).

- [ ] **Step 3: No commit** (venv is gitignored, no source change)

---

### Task 3: sentence-transformers + sqlite-vec spike

**Files:**
- Create: `scripts/spike_embeddings.py`

This task determines whether we install the `embeddings` extras or fall back. Run before all later embedding tasks.

- [ ] **Step 1: Write spike script**

Create `scripts/spike_embeddings.py`:
```python
"""Spike: verify sentence-transformers + sqlite-vec on Windows.

Exit codes:
  0 - both libraries work; use them
  1 - sentence-transformers fails; fall back to numpy+cosine
  2 - sqlite-vec fails; embeddings work but BLOB-column fallback needed
  3 - both fail; numpy+cosine + BLOB column
"""
from __future__ import annotations
import sys
import sqlite3
import tempfile
from pathlib import Path


def try_sentence_transformers() -> bool:
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer("all-MiniLM-L6-v2")
        v = m.encode(["hello world"], normalize_embeddings=True)
        ok = v.shape == (1, 384)
        print(f"[st] OK shape={v.shape}")
        return ok
    except Exception as e:
        print(f"[st] FAIL {type(e).__name__}: {e}")
        return False


def try_sqlite_vec() -> bool:
    try:
        import sqlite_vec
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.db"
            con = sqlite3.connect(str(p))
            con.enable_load_extension(True)
            sqlite_vec.load(con)
            con.execute("CREATE VIRTUAL TABLE v USING vec0(embedding float[384])")
            con.close()
        print("[vec] OK")
        return True
    except Exception as e:
        print(f"[vec] FAIL {type(e).__name__}: {e}")
        return False


def main() -> int:
    st_ok = try_sentence_transformers()
    vec_ok = try_sqlite_vec()
    if st_ok and vec_ok:
        return 0
    if not st_ok and vec_ok:
        return 1
    if st_ok and not vec_ok:
        return 2
    return 3


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Install embeddings extras and run spike**

```powershell
pip install -e ".[embeddings]"
python scripts/spike_embeddings.py
echo "exit=$LASTEXITCODE"
```

Expected outputs (one of):
- `[st] OK shape=(1, 384)` + `[vec] OK` + `exit=0` — happy path
- `[st] FAIL ...` + `[vec] OK` + `exit=1` — fallback branch A
- `[st] OK ...` + `[vec] FAIL ...` + `exit=2` — fallback branch B
- both FAIL + `exit=3` — fallback branch C

- [ ] **Step 3: Record outcome**

Create `scripts/spike_outcome.txt` with one line:
```
exit=<N>  # one of 0,1,2,3
```

This file is checked by Task 13 to decide which embedding implementation to wire up.

- [ ] **Step 4: Commit**

```powershell
git add scripts/spike_embeddings.py scripts/spike_outcome.txt
git commit -m "living-vault | Phase-0: embeddings spike completed (exit=<N>)"
```

---

### Task 4: Test fixture — minimal fake vault

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/fixtures/vault/concepts/note-a.md`
- Create: `tests/fixtures/vault/concepts/note-b.md`
- Create: `tests/fixtures/vault/synthesis/syn-1.md`

A controlled fixture vault is the heart of every test. It contains exactly 3 pages with known content, frontmatter, and wikilinks. **Critical: tests must NEVER touch the real `~/wiki/`.**

- [ ] **Step 1: Write fixture page A**

`tests/fixtures/vault/concepts/note-a.md`:
```markdown
---
type: concept
status: active
created: 2026-01-15
updated: 2026-04-01
tags: [example, alpha]
public: false
---

# Note A

This is note A. It links to [[wiki/concepts/note-b]] and [[wiki/synthesis/syn-1]].

A discusses alpha topics.
```

- [ ] **Step 2: Write fixture page B**

`tests/fixtures/vault/concepts/note-b.md`:
```markdown
---
type: concept
status: active
created: 2026-02-20
updated: 2026-02-20
tags: [example, beta]
public: true
---

# Note B

This is note B. It mentions [[wiki/concepts/note-a]] (backlink).

B discusses beta topics.
```

- [ ] **Step 3: Write fixture page C (synthesis, no public flag = private)**

`tests/fixtures/vault/synthesis/syn-1.md`:
```markdown
---
type: synthesis
status: active
created: 2026-03-10
updated: 2026-04-30
tags: [example, synthesis]
---

# Synthesis 1

A synthesis tying together [[wiki/concepts/note-a]] and [[wiki/concepts/note-b]].
```

- [ ] **Step 4: Write `tests/conftest.py`**

```python
"""Shared pytest fixtures.

ABSOLUTE RULE: tests must never touch ~/wiki/ or the real .vault-engine.db.
Every fixture below uses tmp_path or the static fixtures/vault/ tree.
"""
from __future__ import annotations
import shutil
import sqlite3
from pathlib import Path
import pytest

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"


@pytest.fixture
def fixture_vault_root() -> Path:
    """The static, read-only fixture vault. Tests must not write into it."""
    assert FIXTURE_VAULT.exists(), f"missing fixture vault at {FIXTURE_VAULT}"
    return FIXTURE_VAULT


@pytest.fixture
def vault_copy(tmp_path: Path, fixture_vault_root: Path) -> Path:
    """A writable copy of the fixture vault under tmp_path."""
    dst = tmp_path / "vault"
    shutil.copytree(fixture_vault_root, dst)
    return dst


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A fresh sqlite db file path under tmp_path."""
    return tmp_path / ".vault-engine.db"


@pytest.fixture
def real_wiki_guard(monkeypatch):
    """Hard guard: any attempt to open ~/wiki paths raises."""
    real_root = (Path.home() / "wiki").resolve()
    real_open = open

    def guarded_open(file, *a, **k):
        try:
            p = Path(file).resolve()
        except Exception:
            return real_open(file, *a, **k)
        if str(p).startswith(str(real_root)):
            raise RuntimeError(f"REFUSING to touch real wiki path: {p}")
        return real_open(file, *a, **k)

    monkeypatch.setattr("builtins.open", guarded_open)
```

- [ ] **Step 5: Verify fixtures load**

```powershell
pytest --collect-only
```

Expected: `collected 0 items` (still no tests yet, but no errors).

- [ ] **Step 6: Commit**

```powershell
git add tests/
git commit -m "living-vault | Phase-0: test fixtures + real-wiki guard"
```

---

### Task 5: DB schema constants

**Files:**
- Create: `living_vault/core/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:
```python
"""Tests for core.db — schema initialization."""
from pathlib import Path
import sqlite3
import pytest

from living_vault.core import db as db_mod


def test_initialize_creates_all_tables(db_path: Path):
    db_mod.initialize(db_path)
    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    con.close()
    names = {r[0] for r in rows}
    assert "pages" in names
    assert "links" in names
    assert "personas" in names
    assert "runs" in names


def test_initialize_is_idempotent(db_path: Path):
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call must not raise
    assert db_path.exists()


def test_connect_returns_open_connection(db_path: Path):
    db_mod.initialize(db_path)
    con = db_mod.connect(db_path)
    assert con.execute("SELECT 1").fetchone() == (1,)
    con.close()
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest tests/test_db.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` on `living_vault.core.db`.

- [ ] **Step 3: Write minimal implementation**

`living_vault/core/db.py`:
```python
"""SQLite schema for the vault engine.

Storage: one file at ~/wiki/.vault-engine.db (default) or any explicit Path.
Embedding storage strategy is decided in core.embeddings based on spike outcome.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    path           TEXT PRIMARY KEY,
    title          TEXT,
    mtime          REAL,
    created_at     TEXT,
    updated_at     TEXT,
    frontmatter    TEXT,
    content_hash   TEXT,
    is_public      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_pages_public ON pages(is_public);
CREATE INDEX IF NOT EXISTS idx_pages_mtime  ON pages(mtime);

CREATE TABLE IF NOT EXISTS links (
    from_path  TEXT NOT NULL,
    to_path    TEXT NOT NULL,
    link_text  TEXT,
    PRIMARY KEY (from_path, to_path, link_text)
);
CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_path);

CREATE TABLE IF NOT EXISTS personas (
    path           TEXT PRIMARY KEY,
    voice_sample   TEXT,
    themes         TEXT,
    era_marker     TEXT,
    hash           TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    action        TEXT NOT NULL,
    pages_seen    INTEGER DEFAULT 0,
    pages_updated INTEGER DEFAULT 0,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS embeddings_blob (
    path     TEXT PRIMARY KEY,
    model    TEXT NOT NULL,
    dim      INTEGER NOT NULL,
    vector   BLOB NOT NULL
);
"""


def initialize(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
pytest tests/test_db.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/db.py tests/test_db.py
git commit -m "living-vault | Phase-0: core.db schema + tests"
```

---

### Task 6: Frontmatter + content hash reader

**Files:**
- Create: `living_vault/core/reader.py`
- Create: `tests/test_reader.py`

- [ ] **Step 1: Write the failing test**

`tests/test_reader.py`:
```python
from pathlib import Path
from living_vault.core.reader import read_page, content_hash


def test_read_page_parses_frontmatter(fixture_vault_root: Path):
    p = read_page(fixture_vault_root / "concepts" / "note-a.md", fixture_vault_root)
    assert p.title == "note-a"
    assert p.frontmatter["type"] == "concept"
    assert p.frontmatter["public"] is False
    assert "alpha" in p.frontmatter["tags"]
    assert "[[wiki/concepts/note-b]]" in p.body


def test_read_page_relative_path(fixture_vault_root: Path):
    p = read_page(fixture_vault_root / "concepts" / "note-b.md", fixture_vault_root)
    assert p.relpath == "concepts/note-b.md"


def test_read_page_public_flag(fixture_vault_root: Path):
    p_priv = read_page(fixture_vault_root / "concepts" / "note-a.md", fixture_vault_root)
    p_pub = read_page(fixture_vault_root / "concepts" / "note-b.md", fixture_vault_root)
    p_unset = read_page(fixture_vault_root / "synthesis" / "syn-1.md", fixture_vault_root)
    assert p_priv.is_public is False
    assert p_pub.is_public is True
    assert p_unset.is_public is False  # missing key defaults to private


def test_content_hash_stable():
    h1 = content_hash("hello world")
    h2 = content_hash("hello world")
    assert h1 == h2
    assert h1 != content_hash("hello world ")
    assert len(h1) == 64  # sha256 hex
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest tests/test_reader.py -v
```

Expected: `ModuleNotFoundError: living_vault.core.reader`.

- [ ] **Step 3: Write minimal implementation**

`living_vault/core/reader.py`:
```python
"""Read markdown pages from a vault root with frontmatter parsing."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import frontmatter


@dataclass
class Page:
    relpath: str            # forward-slash, relative to vault_root, e.g. "concepts/note-a.md"
    title: str              # filename stem
    body: str               # markdown body (without frontmatter)
    frontmatter: dict[str, Any] = field(default_factory=dict)
    mtime: float = 0.0
    is_public: bool = False
    content_hash_value: str = ""


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_page(file_path: Path, vault_root: Path) -> Page:
    file_path = file_path.resolve()
    vault_root = vault_root.resolve()
    rel = file_path.relative_to(vault_root).as_posix()
    raw = file_path.read_text(encoding="utf-8")
    fm = frontmatter.loads(raw)
    body = fm.content
    md = dict(fm.metadata)
    is_public = bool(md.get("public", False))
    return Page(
        relpath=rel,
        title=file_path.stem,
        body=body,
        frontmatter=md,
        mtime=file_path.stat().st_mtime,
        is_public=is_public,
        content_hash_value=content_hash(raw),
    )
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
pytest tests/test_reader.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/reader.py tests/test_reader.py
git commit -m "living-vault | Phase-0: core.reader with frontmatter + content hash"
```

---

### Task 7: Vault walker — iterate all pages

**Files:**
- Modify: `living_vault/core/reader.py` (add `walk_vault`)
- Modify: `tests/test_reader.py` (add walker tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_reader.py`:
```python
from living_vault.core.reader import walk_vault


def test_walk_vault_finds_all_md_files(fixture_vault_root):
    pages = list(walk_vault(fixture_vault_root))
    relpaths = sorted(p.relpath for p in pages)
    assert relpaths == [
        "concepts/note-a.md",
        "concepts/note-b.md",
        "synthesis/syn-1.md",
    ]


def test_walk_vault_skips_hidden(tmp_path, fixture_vault_root):
    import shutil
    dst = tmp_path / "vault"
    shutil.copytree(fixture_vault_root, dst)
    (dst / ".hidden.md").write_text("---\n---\nhidden\n", encoding="utf-8")
    (dst / ".obsidian").mkdir()
    (dst / ".obsidian" / "config.md").write_text("---\n---\nx\n", encoding="utf-8")
    pages = list(walk_vault(dst))
    paths = {p.relpath for p in pages}
    assert ".hidden.md" not in paths
    assert all(not pp.startswith(".obsidian/") for pp in paths)
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest tests/test_reader.py::test_walk_vault_finds_all_md_files -v
```

Expected: `ImportError: cannot import name 'walk_vault'`.

- [ ] **Step 3: Add walker to `living_vault/core/reader.py`**

Append to the file:
```python
from collections.abc import Iterator


def walk_vault(vault_root: Path) -> Iterator[Page]:
    """Yield Page for every .md file under vault_root, skipping dotted dirs/files."""
    vault_root = vault_root.resolve()
    for path in vault_root.rglob("*.md"):
        rel = path.relative_to(vault_root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        yield read_page(path, vault_root)
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_reader.py -v
```

Expected: 6 passed (4 prior + 2 new).

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/reader.py tests/test_reader.py
git commit -m "living-vault | Phase-0: walk_vault iterator"
```

---

## Phase 1 — Schicht 1 (Mechanical) — Tasks 8-12

### Task 8: Wikilink extraction

**Files:**
- Create: `living_vault/core/graph.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Write the failing test**

`tests/test_graph.py`:
```python
from living_vault.core.graph import extract_wikilinks


def test_extract_wikilinks_single():
    body = "see [[wiki/concepts/foo]] and [[wiki/concepts/bar]]."
    links = extract_wikilinks(body)
    assert ("wiki/concepts/foo", None) in links
    assert ("wiki/concepts/bar", None) in links


def test_extract_wikilinks_with_alias():
    body = "see [[wiki/synthesis/abc|the synthesis]]"
    links = extract_wikilinks(body)
    assert ("wiki/synthesis/abc", "the synthesis") in links


def test_extract_wikilinks_ignores_non_wiki():
    body = "[[foo]] is not a wiki link, but [[wiki/x]] is."
    links = extract_wikilinks(body)
    targets = [t for t, _ in links]
    assert "wiki/x" in targets
    assert "foo" not in targets


def test_extract_wikilinks_dedup():
    body = "[[wiki/a]] and again [[wiki/a]]."
    links = extract_wikilinks(body)
    assert links.count(("wiki/a", None)) == 2  # not deduped at this level
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest tests/test_graph.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`living_vault/core/graph.py`:
```python
"""Wikilink graph: extraction, neighbors, backlinks."""
from __future__ import annotations
import re
from typing import Iterable

WIKILINK_RE = re.compile(r"\[\[(wiki/[^\]\|]+?)(?:\|([^\]]+))?\]\]")


def extract_wikilinks(body: str) -> list[tuple[str, str | None]]:
    """Return list of (target, alias|None) tuples in document order, no dedup."""
    out: list[tuple[str, str | None]] = []
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        alias = m.group(2).strip() if m.group(2) else None
        out.append((target, alias))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
pytest tests/test_graph.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/graph.py tests/test_graph.py
git commit -m "living-vault | Phase-1: wikilink extraction"
```

---

### Task 9: Wikilink target resolver (target string → page relpath)

The wikilink `[[wiki/concepts/note-a]]` references the wiki at the wiki-root, not the vault file path. Resolver maps wiki-root-relative targets to vault-file relpaths. Wiki convention: `wiki/X/Y` corresponds to `<vault>/X/Y.md` because the vault root is at `~/wiki/wiki/` while wikilinks include the leading `wiki/` segment.

**Files:**
- Modify: `living_vault/core/graph.py` (add `resolve_target`)
- Modify: `tests/test_graph.py` (add resolve tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_graph.py`:
```python
from living_vault.core.graph import resolve_target


def test_resolve_target_strips_wiki_prefix():
    assert resolve_target("wiki/concepts/note-a") == "concepts/note-a.md"


def test_resolve_target_passes_md_extension_through():
    assert resolve_target("wiki/concepts/note-a.md") == "concepts/note-a.md"


def test_resolve_target_returns_none_for_non_wiki():
    assert resolve_target("concepts/note-a") is None
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_graph.py::test_resolve_target_strips_wiki_prefix -v
```

Expected: `ImportError`.

- [ ] **Step 3: Append to `living_vault/core/graph.py`**

```python
def resolve_target(target: str) -> str | None:
    """Map a wikilink target like 'wiki/concepts/foo' to vault relpath 'concepts/foo.md'.

    Wiki convention: vault root is ~/wiki/wiki/, but wikilinks include the leading 'wiki/'
    segment because the vault is itself nested inside a 'wiki/' directory.
    """
    if not target.startswith("wiki/"):
        return None
    stripped = target[len("wiki/"):]
    if not stripped.endswith(".md"):
        stripped = stripped + ".md"
    return stripped
```

- [ ] **Step 4: Run test to verify it passes**

```powershell
pytest tests/test_graph.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/graph.py tests/test_graph.py
git commit -m "living-vault | Phase-1: wikilink target resolver"
```

---

### Task 10: Indexer — populate `pages` and `links` tables

**Files:**
- Create: `living_vault/core/indexer.py`
- Create: `tests/test_indexer.py`

- [ ] **Step 1: Write the failing test**

`tests/test_indexer.py`:
```python
import json
from pathlib import Path
import sqlite3

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault


def test_index_vault_populates_pages(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    stats = index_vault(vault_copy, db_path)
    assert stats["pages_seen"] == 3
    assert stats["pages_updated"] == 3
    con = sqlite3.connect(str(db_path))
    rows = con.execute("SELECT path, is_public FROM pages ORDER BY path").fetchall()
    con.close()
    paths = {r[0] for r in rows}
    assert paths == {
        "concepts/note-a.md",
        "concepts/note-b.md",
        "synthesis/syn-1.md",
    }
    public_map = {r[0]: r[1] for r in rows}
    assert public_map["concepts/note-b.md"] == 1
    assert public_map["concepts/note-a.md"] == 0
    assert public_map["synthesis/syn-1.md"] == 0


def test_index_vault_populates_links(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = sqlite3.connect(str(db_path))
    rows = con.execute("SELECT from_path, to_path FROM links").fetchall()
    con.close()
    pairs = {(r[0], r[1]) for r in rows}
    assert ("concepts/note-a.md", "concepts/note-b.md") in pairs
    assert ("concepts/note-a.md", "synthesis/syn-1.md") in pairs
    assert ("concepts/note-b.md", "concepts/note-a.md") in pairs
    assert ("synthesis/syn-1.md", "concepts/note-a.md") in pairs
    assert ("synthesis/syn-1.md", "concepts/note-b.md") in pairs


def test_index_vault_skip_unchanged(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    stats2 = index_vault(vault_copy, db_path)
    assert stats2["pages_seen"] == 3
    assert stats2["pages_updated"] == 0  # nothing changed -> no updates
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
pytest tests/test_indexer.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/core/indexer.py`**

```python
"""Indexer: walk vault, populate pages + links tables, skip unchanged content."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from living_vault.core.reader import walk_vault, Page
from living_vault.core.graph import extract_wikilinks, resolve_target
from living_vault.core import db as db_mod


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def index_vault(vault_root: Path, db_path: Path) -> dict[str, int]:
    """Index every page under vault_root into db_path. Returns stats dict."""
    con = db_mod.connect(db_path)
    started = _utcnow()
    pages_seen = 0
    pages_updated = 0
    seen_paths: set[str] = set()
    try:
        existing = {
            row["path"]: row["content_hash"]
            for row in con.execute("SELECT path, content_hash FROM pages")
        }
        for page in walk_vault(vault_root):
            pages_seen += 1
            seen_paths.add(page.relpath)
            if existing.get(page.relpath) == page.content_hash_value:
                continue  # unchanged
            _upsert_page(con, page)
            _replace_links(con, page)
            pages_updated += 1
        # remove pages that no longer exist on disk
        gone = set(existing) - seen_paths
        for p in gone:
            con.execute("DELETE FROM pages WHERE path = ?", (p,))
            con.execute("DELETE FROM links WHERE from_path = ?", (p,))
        con.execute(
            "INSERT INTO runs(started_at, finished_at, action, pages_seen, pages_updated) "
            "VALUES (?, ?, ?, ?, ?)",
            (started, _utcnow(), "index_vault", pages_seen, pages_updated),
        )
        con.commit()
    finally:
        con.close()
    return {"pages_seen": pages_seen, "pages_updated": pages_updated, "pages_gone": len(gone)}


def _upsert_page(con: sqlite3.Connection, page: Page) -> None:
    con.execute(
        """
        INSERT INTO pages(path, title, mtime, created_at, updated_at,
                          frontmatter, content_hash, is_public)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            title=excluded.title,
            mtime=excluded.mtime,
            created_at=excluded.created_at,
            updated_at=excluded.updated_at,
            frontmatter=excluded.frontmatter,
            content_hash=excluded.content_hash,
            is_public=excluded.is_public
        """,
        (
            page.relpath,
            page.title,
            page.mtime,
            str(page.frontmatter.get("created", "")),
            str(page.frontmatter.get("updated", "")),
            json.dumps(page.frontmatter, default=str),
            page.content_hash_value,
            int(page.is_public),
        ),
    )


def _replace_links(con: sqlite3.Connection, page: Page) -> None:
    con.execute("DELETE FROM links WHERE from_path = ?", (page.relpath,))
    for target, alias in extract_wikilinks(page.body):
        resolved = resolve_target(target)
        if resolved is None:
            continue
        con.execute(
            "INSERT OR IGNORE INTO links(from_path, to_path, link_text) VALUES (?, ?, ?)",
            (page.relpath, resolved, alias),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_indexer.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/indexer.py tests/test_indexer.py
git commit -m "living-vault | Phase-1: indexer with content-hash skip-unchanged"
```

---

### Task 11: Graph queries — neighbors, backlinks

**Files:**
- Modify: `living_vault/core/graph.py` (add `neighbors`, `backlinks`)
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_graph.py`:
```python
import sqlite3
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.graph import neighbors, backlinks


def test_neighbors_returns_outgoing(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    n = neighbors(con, "concepts/note-a.md")
    con.close()
    assert "concepts/note-b.md" in n
    assert "synthesis/syn-1.md" in n


def test_backlinks_returns_incoming(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    b = backlinks(con, "concepts/note-a.md")
    con.close()
    assert "concepts/note-b.md" in b
    assert "synthesis/syn-1.md" in b


def test_neighbors_empty_for_leaf(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    n = neighbors(con, "does-not-exist.md")
    con.close()
    assert n == []
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_graph.py::test_neighbors_returns_outgoing -v
```

Expected: `ImportError`.

- [ ] **Step 3: Append to `living_vault/core/graph.py`**

```python
import sqlite3


def neighbors(con: sqlite3.Connection, path: str) -> list[str]:
    """Outgoing edges: pages that path links to."""
    rows = con.execute(
        "SELECT DISTINCT to_path FROM links WHERE from_path = ? ORDER BY to_path",
        (path,),
    ).fetchall()
    return [r[0] for r in rows]


def backlinks(con: sqlite3.Connection, path: str) -> list[str]:
    """Incoming edges: pages that link to path."""
    rows = con.execute(
        "SELECT DISTINCT from_path FROM links WHERE to_path = ? ORDER BY from_path",
        (path,),
    ).fetchall()
    return [r[0] for r in rows]
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_graph.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/graph.py tests/test_graph.py
git commit -m "living-vault | Phase-1: graph neighbors + backlinks"
```

---

### Task 12: Decay + privacy filters

**Files:**
- Create: `living_vault/core/decay.py`
- Create: `living_vault/core/privacy.py`
- Create: `tests/test_decay.py`
- Create: `tests/test_privacy.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_decay.py`:
```python
import time
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.decay import stale_pages


def test_stale_pages_returns_old(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    # backdate one file
    target = vault_copy / "concepts" / "note-a.md"
    old = time.time() - 90 * 86400  # 90 days ago
    import os
    os.utime(target, (old, old))
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    stale = stale_pages(con, days=60)
    con.close()
    assert "concepts/note-a.md" in stale


def test_stale_pages_excludes_recent(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    stale = stale_pages(con, days=60)
    con.close()
    # all fixture files are fresh in the copy (mtime = now)
    assert stale == []
```

`tests/test_privacy.py`:
```python
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.privacy import public_pages


def test_public_pages_returns_only_public(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = db_mod.connect(db_path)
    pub = public_pages(con)
    con.close()
    assert pub == ["concepts/note-b.md"]
```

- [ ] **Step 2: Run tests**

```powershell
pytest tests/test_decay.py tests/test_privacy.py -v
```

Expected: `ModuleNotFoundError` for both.

- [ ] **Step 3: Write `living_vault/core/decay.py`**

```python
"""Staleness detection based on mtime."""
from __future__ import annotations
import sqlite3
import time


def stale_pages(con: sqlite3.Connection, days: int) -> list[str]:
    """Return relpaths of pages whose mtime is older than `days` days."""
    cutoff = time.time() - days * 86400
    rows = con.execute(
        "SELECT path FROM pages WHERE mtime < ? ORDER BY path",
        (cutoff,),
    ).fetchall()
    return [r[0] for r in rows]
```

- [ ] **Step 4: Write `living_vault/core/privacy.py`**

```python
"""Privacy filter: pages with frontmatter `public: true` are public, all others private."""
from __future__ import annotations
import sqlite3


def public_pages(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT path FROM pages WHERE is_public = 1 ORDER BY path"
    ).fetchall()
    return [r[0] for r in rows]


def is_public(con: sqlite3.Connection, path: str) -> bool:
    row = con.execute("SELECT is_public FROM pages WHERE path = ?", (path,)).fetchone()
    return bool(row and row[0])
```

- [ ] **Step 5: Run tests**

```powershell
pytest tests/test_decay.py tests/test_privacy.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```powershell
git add living_vault/core/decay.py living_vault/core/privacy.py tests/test_decay.py tests/test_privacy.py
git commit -m "living-vault | Phase-1: decay + privacy filters"
```

---

## Phase 1 — Schicht 2 (Semantic) — Tasks 13-16

### Task 13: Embedding backend abstraction

The actual implementation depends on `scripts/spike_outcome.txt` from Task 3. We always implement the abstraction with both backends; the runtime picker chooses based on installed extras.

**Files:**
- Create: `living_vault/core/embeddings.py`
- Create: `tests/test_embeddings.py`

- [ ] **Step 1: Write the failing test**

`tests/test_embeddings.py`:
```python
import numpy as np
import pytest
from living_vault.core.embeddings import (
    NumpyBackend, get_backend, BackendNotAvailable,
)


def test_numpy_backend_encode_returns_normalized():
    b = NumpyBackend()
    v = b.encode(["hello world"])
    assert v.shape == (1, b.dim)
    norms = np.linalg.norm(v, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_numpy_backend_similar_is_high_for_similar_text():
    b = NumpyBackend()
    a = b.encode(["the cat sat on the mat"])
    b1 = b.encode(["a feline rests on a rug"])
    c = b.encode(["matrix multiplication of tensor weights"])
    sim_close = float((a @ b1.T)[0, 0])
    sim_far = float((a @ c.T)[0, 0])
    # Numpy hash-bag backend is crude; we only assert ordering, not magnitude
    assert sim_close > sim_far - 0.01


def test_get_backend_returns_some_backend():
    b = get_backend()
    assert b is not None
    assert b.dim > 0
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_embeddings.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/core/embeddings.py`**

```python
"""Embedding backends.

Two implementations:
  - SentenceTransformerBackend: uses all-MiniLM-L6-v2 (384 dim) — preferred.
  - NumpyBackend: deterministic hash-of-tokens fallback (256 dim, normalized).

get_backend() returns the best available backend at runtime. The numpy backend
is always available; it is *not* a high-quality embedder, but it lets the
indexer and consumers run without the heavy ML dependency.
"""
from __future__ import annotations
import hashlib
import re
from typing import Iterable

import numpy as np


class BackendNotAvailable(Exception):
    pass


class _Backend:
    name: str = "abstract"
    dim: int = 0

    def encode(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class NumpyBackend(_Backend):
    """Deterministic hash-bag: tokenize, hash each token to a bucket, normalize.

    Quality: low. Purpose: works without ML deps, gives stable vectors so the
    rest of the pipeline (storage, similarity) can be tested end-to-end.
    """
    name = "numpy-hashbag"
    dim = 256

    _TOKEN = re.compile(r"[A-Za-z]{2,}")

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in self._TOKEN.findall(t.lower()):
                h = int(hashlib.blake2b(tok.encode("utf-8"), digest_size=4).hexdigest(), 16)
                out[i, h % self.dim] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class SentenceTransformerBackend(_Backend):
    name = "sentence-transformers/all-MiniLM-L6-v2"
    dim = 384

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            raise BackendNotAvailable(f"sentence-transformers not importable: {e}")
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def encode(self, texts: list[str]) -> np.ndarray:
        v = self._model.encode(texts, normalize_embeddings=True)
        return np.asarray(v, dtype=np.float32)


def get_backend() -> _Backend:
    """Return SentenceTransformerBackend if available, else NumpyBackend."""
    try:
        return SentenceTransformerBackend()
    except BackendNotAvailable:
        return NumpyBackend()
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_embeddings.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/embeddings.py tests/test_embeddings.py
git commit -m "living-vault | Phase-1: embedding backend abstraction with numpy fallback"
```

---

### Task 14: Persist embeddings + similarity search

**Files:**
- Modify: `living_vault/core/embeddings.py` (add `index_embeddings`, `similar`)
- Modify: `tests/test_embeddings.py` (add persistence tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_embeddings.py`:
```python
import sqlite3
from pathlib import Path

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings, similar


def test_index_embeddings_persists_all(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    n = index_embeddings(vault_copy, db_path)
    assert n == 3
    con = sqlite3.connect(str(db_path))
    cnt = con.execute("SELECT COUNT(*) FROM embeddings_blob").fetchone()[0]
    con.close()
    assert cnt == 3


def test_similar_returns_self_first(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    con = db_mod.connect(db_path)
    res = similar(con, "concepts/note-a.md", k=3)
    con.close()
    assert res[0][0] == "concepts/note-a.md"
    assert abs(res[0][1] - 1.0) < 1e-3


def test_index_embeddings_skip_unchanged(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    n1 = index_embeddings(vault_copy, db_path)
    n2 = index_embeddings(vault_copy, db_path)  # second pass: no changes
    assert n1 == 3
    assert n2 == 0
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_embeddings.py::test_index_embeddings_persists_all -v
```

Expected: `ImportError: cannot import name 'index_embeddings'`.

- [ ] **Step 3: Append to `living_vault/core/embeddings.py`**

```python
import sqlite3
from pathlib import Path

from living_vault.core.reader import walk_vault
from living_vault.core import db as db_mod


def _vec_to_blob(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()


def _blob_to_vec(b: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32).reshape((dim,))


def index_embeddings(vault_root: Path, db_path: Path) -> int:
    """Compute and store embeddings for pages whose content_hash differs from stored.

    Returns number of pages whose embedding was (re-)computed.
    """
    backend = get_backend()
    con = db_mod.connect(db_path)
    try:
        existing = {
            row["path"]: row["model"]
            for row in con.execute("SELECT path, model FROM embeddings_blob")
        }
        page_hashes = {
            row["path"]: row["content_hash"]
            for row in con.execute("SELECT path, content_hash FROM pages")
        }
        # find pages that need (re)embedding
        candidates: list[tuple[str, str]] = []  # (relpath, body)
        for page in walk_vault(vault_root):
            stored_model = existing.get(page.relpath)
            stored_hash_row = con.execute(
                "SELECT model FROM embeddings_blob WHERE path = ?", (page.relpath,)
            ).fetchone()
            # we re-embed if no row OR model differs OR content_hash differs vs pages table
            row = con.execute(
                "SELECT eb.model FROM embeddings_blob eb WHERE eb.path = ?",
                (page.relpath,),
            ).fetchone()
            need = True
            if row is not None and row[0] == backend.name:
                # match content hash via separate query
                ph = page_hashes.get(page.relpath)
                if ph == page.content_hash_value:
                    # double-check: existing embedding was for current content
                    cur = con.execute(
                        "SELECT 1 FROM embeddings_blob WHERE path = ? AND model = ?",
                        (page.relpath, backend.name),
                    ).fetchone()
                    if cur:
                        need = False
            if need:
                candidates.append((page.relpath, page.body))
        if not candidates:
            return 0
        vecs = backend.encode([b for _, b in candidates])
        for (relpath, _), v in zip(candidates, vecs):
            con.execute(
                "INSERT OR REPLACE INTO embeddings_blob(path, model, dim, vector) "
                "VALUES (?, ?, ?, ?)",
                (relpath, backend.name, backend.dim, _vec_to_blob(v)),
            )
        con.commit()
        return len(candidates)
    finally:
        con.close()


def similar(
    con: sqlite3.Connection, path: str, k: int = 10
) -> list[tuple[str, float]]:
    """Return top-k similar pages (including self) ordered by descending cosine similarity."""
    row = con.execute(
        "SELECT model, dim, vector FROM embeddings_blob WHERE path = ?", (path,)
    ).fetchone()
    if row is None:
        return []
    model, dim, query_blob = row[0], row[1], row[2]
    q = _blob_to_vec(query_blob, dim)
    others = con.execute(
        "SELECT path, vector FROM embeddings_blob WHERE model = ?", (model,)
    ).fetchall()
    scored: list[tuple[str, float]] = []
    for r in others:
        v = _blob_to_vec(r[1], dim)
        scored.append((r[0], float(np.dot(q, v))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_embeddings.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/embeddings.py tests/test_embeddings.py
git commit -m "living-vault | Phase-1: embedding persistence + cosine similarity"
```

---

### Task 15: Semantic search by query string

**Files:**
- Modify: `living_vault/core/embeddings.py` (add `search_semantic`)
- Modify: `tests/test_embeddings.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_embeddings.py`:
```python
from living_vault.core.embeddings import search_semantic


def test_search_semantic_returns_results(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    con = db_mod.connect(db_path)
    res = search_semantic(con, "alpha topics", k=3)
    con.close()
    assert len(res) == 3
    paths = [p for p, _ in res]
    assert "concepts/note-a.md" in paths  # note-a mentions "alpha"
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_embeddings.py::test_search_semantic_returns_results -v
```

Expected: `ImportError`.

- [ ] **Step 3: Append to `living_vault/core/embeddings.py`**

```python
def search_semantic(
    con: sqlite3.Connection, query: str, k: int = 10
) -> list[tuple[str, float]]:
    """Encode `query` and return top-k pages by cosine similarity."""
    backend = get_backend()
    q = backend.encode([query])[0]
    rows = con.execute(
        "SELECT path, model, dim, vector FROM embeddings_blob WHERE model = ?",
        (backend.name,),
    ).fetchall()
    scored: list[tuple[str, float]] = []
    for r in rows:
        v = _blob_to_vec(r[3], r[2])
        scored.append((r[0], float(np.dot(q, v))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_embeddings.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/embeddings.py tests/test_embeddings.py
git commit -m "living-vault | Phase-1: semantic search by query string"
```

---

### Task 16: CLI `living-vault index` — initial vault indexing

**Files:**
- Create: `living_vault/cli.py`
- Modify: `pyproject.toml` (add console script)
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
from pathlib import Path
from click.testing import CliRunner

from living_vault.cli import cli


def test_cli_index_runs(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["index", "--vault", str(vault_copy), "--db", str(db)],
    )
    assert result.exit_code == 0, result.output
    assert "pages_seen=3" in result.output
    assert db.exists()
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_cli.py -v
```

Expected: `ModuleNotFoundError: living_vault.cli`.

- [ ] **Step 3: Write `living_vault/cli.py`**

```python
"""Top-level CLI for living-vault."""
from __future__ import annotations
from pathlib import Path
import click

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings


@click.group()
def cli() -> None:
    """living-vault command-line interface."""


@cli.command("index")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--db", required=True, type=click.Path())
@click.option("--no-embed", is_flag=True, help="skip embedding stage")
def index_cmd(vault: str, db: str, no_embed: bool) -> None:
    vault_p = Path(vault)
    db_p = Path(db)
    db_mod.initialize(db_p)
    stats = index_vault(vault_p, db_p)
    click.echo(f"index pages_seen={stats['pages_seen']} pages_updated={stats['pages_updated']}")
    if not no_embed:
        n = index_embeddings(vault_p, db_p)
        click.echo(f"embeddings updated={n}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add console script to `pyproject.toml`**

In `[project.scripts]` section, add:
```toml
living-vault = "living_vault.cli:main"
```

- [ ] **Step 5: Reinstall**

```powershell
pip install -e ".[dev]"
```

- [ ] **Step 6: Run tests**

```powershell
pytest tests/test_cli.py -v
```

Expected: 1 passed.

- [ ] **Step 7: Manual smoke test against fixture vault**

```powershell
living-vault index --vault tests\fixtures\vault --db .\tmp.db --no-embed
del .\tmp.db
```

Expected: `index pages_seen=3 pages_updated=3`.

- [ ] **Step 8: Commit**

```powershell
git add living_vault/cli.py pyproject.toml tests/test_cli.py
git commit -m "living-vault | Phase-1: living-vault index CLI"
```

---

## Phase 1 — vault-engine-mcp (Tasks 17-20)

### Task 17: MCP server skeleton

**Files:**
- Create: `living_vault/mcp_servers/vault_engine/server.py`
- Create: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

`tests/test_mcp_server.py`:
```python
"""MCP server tests — call the underlying functions directly via the FastMCP app object.

We do not start a transport here; we exercise the registered tool callables.
"""
from pathlib import Path
import os

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.mcp_servers.vault_engine import server as srv


def test_tool_read_page(vault_copy: Path, db_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    out = srv._tool_read_page("concepts/note-a.md")
    assert out["title"] == "note-a"
    assert "alpha" in out["frontmatter"]["tags"]


def test_tool_neighbors(vault_copy: Path, db_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    out = srv._tool_neighbors("concepts/note-a.md")
    assert "concepts/note-b.md" in out
    assert "synthesis/syn-1.md" in out


def test_tool_public_pages(vault_copy: Path, db_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    out = srv._tool_public_pages()
    assert out == ["concepts/note-b.md"]
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_mcp_server.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/mcp_servers/vault_engine/server.py`**

```python
"""vault-engine-mcp — FastMCP server exposing core/ functionality.

Configuration via env vars:
  LIVING_VAULT_ROOT  - absolute path to the vault root (e.g. C:\\Users\\domes\\wiki\\wiki)
  LIVING_VAULT_DB    - absolute path to the SQLite db (default: <root>/../.vault-engine.db)

Tools exposed:
  read_page, search_semantic, neighbors, backlinks, similar,
  stale_pages, public_pages, reindex
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

# Windows MCP encoding hardening (per project memory reference)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastmcp import FastMCP

from living_vault.core import db as db_mod
from living_vault.core import reader, graph, embeddings, decay, privacy
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import (
    index_embeddings,
    search_semantic as _search_semantic,
    similar as _similar,
)


mcp = FastMCP("vault-engine")


def _vault_root() -> Path:
    p = os.environ.get("LIVING_VAULT_ROOT")
    if not p:
        raise RuntimeError("LIVING_VAULT_ROOT env var is not set")
    return Path(p)


def _db_path() -> Path:
    p = os.environ.get("LIVING_VAULT_DB")
    if p:
        return Path(p)
    return _vault_root().parent / ".vault-engine.db"


# ---- tool implementations as plain functions (testable) ----

def _tool_read_page(path: str) -> dict:
    page = reader.read_page(_vault_root() / path, _vault_root())
    return {
        "relpath": page.relpath,
        "title": page.title,
        "body": page.body,
        "frontmatter": page.frontmatter,
        "is_public": page.is_public,
        "mtime": page.mtime,
    }


def _tool_neighbors(path: str) -> list[str]:
    con = db_mod.connect(_db_path())
    try:
        return graph.neighbors(con, path)
    finally:
        con.close()


def _tool_backlinks(path: str) -> list[str]:
    con = db_mod.connect(_db_path())
    try:
        return graph.backlinks(con, path)
    finally:
        con.close()


def _tool_similar(path: str, k: int = 10) -> list[dict]:
    con = db_mod.connect(_db_path())
    try:
        rows = _similar(con, path, k=k)
        return [{"path": p, "score": s} for p, s in rows]
    finally:
        con.close()


def _tool_search_semantic(query: str, k: int = 10) -> list[dict]:
    con = db_mod.connect(_db_path())
    try:
        rows = _search_semantic(con, query, k=k)
        return [{"path": p, "score": s} for p, s in rows]
    finally:
        con.close()


def _tool_stale_pages(days: int = 90) -> list[str]:
    con = db_mod.connect(_db_path())
    try:
        return decay.stale_pages(con, days=days)
    finally:
        con.close()


def _tool_public_pages() -> list[str]:
    con = db_mod.connect(_db_path())
    try:
        return privacy.public_pages(con)
    finally:
        con.close()


def _tool_reindex(force: bool = False) -> dict:
    db_mod.initialize(_db_path())
    if force:
        # blow away embeddings + pages, force rebuild
        con = db_mod.connect(_db_path())
        try:
            con.execute("DELETE FROM embeddings_blob")
            con.execute("DELETE FROM pages")
            con.execute("DELETE FROM links")
            con.commit()
        finally:
            con.close()
    stats = index_vault(_vault_root(), _db_path())
    n = index_embeddings(_vault_root(), _db_path())
    return {**stats, "embeddings_updated": n}


# ---- MCP tool registration ----

@mcp.tool()
def read_page(path: str) -> dict:
    """Read one page by vault-relative path."""
    return _tool_read_page(path)


@mcp.tool()
def neighbors(path: str) -> list[str]:
    """Outgoing links from path."""
    return _tool_neighbors(path)


@mcp.tool()
def backlinks(path: str) -> list[str]:
    """Incoming links to path."""
    return _tool_backlinks(path)


@mcp.tool()
def similar(path: str, k: int = 10) -> list[dict]:
    """Top-k similar pages by embedding cosine."""
    return _tool_similar(path, k)


@mcp.tool()
def search_semantic(query: str, k: int = 10) -> list[dict]:
    """Top-k pages by semantic similarity to a free-text query."""
    return _tool_search_semantic(query, k)


@mcp.tool()
def stale_pages(days: int = 90) -> list[str]:
    """Pages with mtime older than `days` days."""
    return _tool_stale_pages(days)


@mcp.tool()
def public_pages() -> list[str]:
    """Pages with frontmatter `public: true`."""
    return _tool_public_pages()


@mcp.tool()
def reindex(force: bool = False) -> dict:
    """Re-walk the vault and refresh pages/links/embeddings tables."""
    return _tool_reindex(force)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_mcp_server.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/mcp_servers/vault_engine/server.py tests/test_mcp_server.py
git commit -m "living-vault | Phase-1: vault-engine-mcp server with 8 tools"
```

---

### Task 18: Smoke test the MCP server starts

**Files:**
- Create: `tests/test_mcp_smoke.py`

- [ ] **Step 1: Write the test**

`tests/test_mcp_smoke.py`:
```python
"""Smoke test: server module imports and main() is callable.

We do NOT start the transport in tests (would block). The deeper integration
test against a real MCP client lives outside this test suite.
"""
import importlib


def test_server_module_imports():
    m = importlib.import_module("living_vault.mcp_servers.vault_engine.server")
    assert hasattr(m, "main")
    assert hasattr(m, "mcp")
```

- [ ] **Step 2: Run**

```powershell
pytest tests/test_mcp_smoke.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Manual smoke (one-time, not committed)**

In a separate PowerShell window:
```powershell
$env:LIVING_VAULT_ROOT = (Resolve-Path .\tests\fixtures\vault).Path
$env:LIVING_VAULT_DB   = (Resolve-Path .).Path + "\.smoke.db"
living-vault index --vault $env:LIVING_VAULT_ROOT --db $env:LIVING_VAULT_DB
python -m living_vault.mcp_servers.vault_engine.server
# Ctrl-C to stop
del .\.smoke.db
```

Expected: server starts, prints stdio handshake on first MCP frame, no traceback.

- [ ] **Step 4: Commit**

```powershell
git add tests/test_mcp_smoke.py
git commit -m "living-vault | Phase-1: mcp server smoke test"
```

---

### Task 19: Bench against real vault — measure indexing time

This is a manual, untested checkpoint before exposing the MCP server to Claude Code. It validates the <10min initial-index acceptance criterion from the design doc.

**Files:** None (measurement only).

- [ ] **Step 1: Run end-to-end against real wiki**

```powershell
$env:LIVING_VAULT_ROOT = "C:\Users\domes\wiki\wiki"
$env:LIVING_VAULT_DB   = "C:\Users\domes\wiki\.vault-engine.db"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
living-vault index --vault $env:LIVING_VAULT_ROOT --db $env:LIVING_VAULT_DB
$sw.Stop()
"elapsed seconds: $($sw.Elapsed.TotalSeconds)"
```

Acceptance: ≤600 seconds (10 minutes) for ~953 pages with embeddings.

If it exceeds 600s, record observation in `docs/plans/2026-05-08-living-vault-master-plan.md` Risks section and decide before continuing.

- [ ] **Step 2: Sanity-check the DB**

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'C:\Users\domes\wiki\.vault-engine.db'); print('pages', c.execute('select count(*) from pages').fetchone()[0]); print('links', c.execute('select count(*) from links').fetchone()[0]); print('emb', c.execute('select count(*) from embeddings_blob').fetchone()[0])"
```

Expected output (rough): `pages 953  links >>500  emb 953`.

- [ ] **Step 3: Commit (results logged in master-plan, not code)**

No code change in this task. If the master-plan was updated:
```powershell
git add docs/plans/2026-05-08-living-vault-master-plan.md
git commit -m "living-vault | Phase-1: bench results recorded in master-plan"
```

---

### Task 20: Document running the MCP server with Claude Code

**Files:**
- Create: `docs/RUN-MCP-SERVER.md`

- [ ] **Step 1: Write the doc**

`docs/RUN-MCP-SERVER.md`:
```markdown
# Running vault-engine-mcp with Claude Code

## One-time setup

1. Install the package editable:

       cd C:\Users\domes\desktop\Claude-Projekte\living-vault
       .venv\Scripts\Activate.ps1
       pip install -e ".[embeddings,dev]"

2. Build the initial index (one-time, ~5–10 min for 953 pages):

       $env:LIVING_VAULT_ROOT = "C:\Users\domes\wiki\wiki"
       $env:LIVING_VAULT_DB   = "C:\Users\domes\wiki\.vault-engine.db"
       living-vault index --vault $env:LIVING_VAULT_ROOT --db $env:LIVING_VAULT_DB

## Configure Claude Code

Edit `~/.claude/settings.json` and add an MCP server entry:

```json
{
  "mcpServers": {
    "vault-engine": {
      "command": "C:\\Users\\domes\\desktop\\Claude-Projekte\\living-vault\\.venv\\Scripts\\python.exe",
      "args": ["-m", "living_vault.mcp_servers.vault_engine.server"],
      "env": {
        "LIVING_VAULT_ROOT": "C:\\Users\\domes\\wiki\\wiki",
        "LIVING_VAULT_DB":   "C:\\Users\\domes\\wiki\\.vault-engine.db",
        "PYTHONIOENCODING":  "utf-8"
      }
    }
  }
}
```

## Verify

In a fresh Claude Code session:

> "Use vault-engine.public_pages to list public wiki pages."

You should see a non-empty list (or empty if no `public: true` flag set yet).

## Refresh after vault edits

The server does not yet auto-watch the vault. After substantial editing, run:

       living-vault index --vault $env:LIVING_VAULT_ROOT --db $env:LIVING_VAULT_DB

(Phase 2 will add a file-watcher.)
```

- [ ] **Step 2: Commit**

```powershell
git add docs/RUN-MCP-SERVER.md
git commit -m "living-vault | Phase-1: docs for running mcp server with Claude Code"
```

---

## Phase 1 — Synesthesia (Tasks 21-25)

### Task 21: Layout algorithm — cluster + force-directed positions

**Files:**
- Create: `living_vault/apps/synesthesia/layout.py`
- Create: `tests/test_layout.py`

- [ ] **Step 1: Write the failing test**

`tests/test_layout.py`:
```python
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.apps.synesthesia.layout import compute_layout


def test_compute_layout_returns_one_node_per_page(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    nodes, edges = compute_layout(db_path, public_only=False)
    assert len(nodes) == 3
    paths = {n["path"] for n in nodes}
    assert paths == {
        "concepts/note-a.md",
        "concepts/note-b.md",
        "synthesis/syn-1.md",
    }


def test_compute_layout_public_only_filters(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    nodes, _ = compute_layout(db_path, public_only=True)
    assert len(nodes) == 1
    assert nodes[0]["path"] == "concepts/note-b.md"


def test_compute_layout_node_has_xyz(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    nodes, _ = compute_layout(db_path, public_only=False)
    for n in nodes:
        assert isinstance(n["x"], float)
        assert isinstance(n["y"], float)
        assert isinstance(n["z"], float)


def test_compute_layout_edges_are_existing_links(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    index_embeddings(vault_copy, db_path)
    nodes, edges = compute_layout(db_path, public_only=False)
    pairs = {(e["from"], e["to"]) for e in edges}
    assert ("concepts/note-a.md", "concepts/note-b.md") in pairs
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_layout.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/apps/synesthesia/layout.py`**

```python
"""Synesthesia layout: pages -> 3D coordinates.

Approach (deterministic, no force simulation in v1):
  - Project each embedding to 3D via PCA on the in-memory matrix of all (filtered) page vectors.
  - Scale to a comfortable cube of ~50x50x50 units.
  - Edges: every (from_path, to_path) link where both endpoints are in the filtered set.

This avoids the dependency on a 3D-force library and is deterministic given inputs,
which makes the public-only build reproducible.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

import numpy as np

from living_vault.core import db as db_mod


def _pca_3d(matrix: np.ndarray) -> np.ndarray:
    """Reduce N-dim matrix to 3 dims via PCA (centered)."""
    if matrix.shape[0] <= 1:
        return np.zeros((matrix.shape[0], 3), dtype=np.float32)
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    # SVD for numerical stability on small N
    u, s, vh = np.linalg.svd(centered, full_matrices=False)
    components = vh[:3]  # (3, dim)
    proj = centered @ components.T  # (N, 3)
    # scale to roughly [-25, 25]
    max_abs = float(np.abs(proj).max() or 1.0)
    return (proj / max_abs * 25.0).astype(np.float32)


def compute_layout(
    db_path: Path, public_only: bool = False
) -> tuple[list[dict], list[dict]]:
    con = db_mod.connect(db_path)
    try:
        if public_only:
            page_rows = con.execute(
                "SELECT path, title, mtime, is_public FROM pages WHERE is_public = 1 ORDER BY path"
            ).fetchall()
        else:
            page_rows = con.execute(
                "SELECT path, title, mtime, is_public FROM pages ORDER BY path"
            ).fetchall()
        if not page_rows:
            return [], []
        paths = [r["path"] for r in page_rows]
        path_index = {p: i for i, p in enumerate(paths)}
        emb_rows = con.execute(
            "SELECT path, dim, vector FROM embeddings_blob WHERE path IN ({})".format(
                ",".join("?" * len(paths))
            ),
            paths,
        ).fetchall()
        if not emb_rows:
            # no embeddings at all; place everything at origin (degenerate)
            coords = np.zeros((len(paths), 3), dtype=np.float32)
        else:
            dim = emb_rows[0]["dim"]
            mat = np.zeros((len(paths), dim), dtype=np.float32)
            for r in emb_rows:
                idx = path_index[r["path"]]
                mat[idx] = np.frombuffer(r["vector"], dtype=np.float32)
            coords = _pca_3d(mat)

        # node-degree for sizing
        deg = {p: 0 for p in paths}
        for r in con.execute("SELECT from_path, to_path FROM links"):
            if r["from_path"] in deg:
                deg[r["from_path"]] += 1
            if r["to_path"] in deg:
                deg[r["to_path"]] += 1

        nodes: list[dict] = []
        for r, c in zip(page_rows, coords):
            cluster = r["path"].split("/", 1)[0]
            nodes.append({
                "path": r["path"],
                "title": r["title"],
                "cluster": cluster,
                "is_public": bool(r["is_public"]),
                "mtime": r["mtime"],
                "degree": deg[r["path"]],
                "x": float(c[0]), "y": float(c[1]), "z": float(c[2]),
            })

        # edges only between filtered nodes
        edges: list[dict] = []
        in_set = set(paths)
        for r in con.execute("SELECT from_path, to_path FROM links"):
            if r["from_path"] in in_set and r["to_path"] in in_set:
                edges.append({"from": r["from_path"], "to": r["to_path"]})
        return nodes, edges
    finally:
        con.close()
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_layout.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/apps/synesthesia/layout.py tests/test_layout.py
git commit -m "living-vault | Phase-1: synesthesia layout via PCA"
```

---

### Task 22: HTML/Three.js template

**Files:**
- Create: `living_vault/apps/synesthesia/templates/vault-3d.html.j2`

- [ ] **Step 1: Write the template**

`living_vault/apps/synesthesia/templates/vault-3d.html.j2`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ title }}</title>
  <style>
    html, body { margin:0; height:100%; background:#0a0a0f; color:#cfe; font-family:'JetBrains Mono', monospace; overflow:hidden; }
    #info { position:fixed; top:8px; left:8px; padding:6px 10px; background:rgba(0,0,0,.5); border-radius:4px; font-size:12px; }
    #picked { position:fixed; bottom:8px; left:8px; padding:8px 12px; background:rgba(0,0,0,.6); border-radius:4px; font-size:12px; max-width:60ch; white-space:pre-wrap; }
  </style>
</head>
<body>
  <div id="info">{{ count }} pages · {{ edge_count }} links · drag to orbit · scroll to zoom</div>
  <div id="picked"></div>
  <script type="module">
    import * as THREE from "https://unpkg.com/three@0.160.0/build/three.module.js";
    import { OrbitControls } from "https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js";

    const NODES = {{ nodes_json | safe }};
    const EDGES = {{ edges_json | safe }};

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, innerWidth/innerHeight, 0.1, 5000);
    camera.position.set(70,70,70);
    const renderer = new THREE.WebGLRenderer({ antialias:true });
    renderer.setSize(innerWidth, innerHeight);
    document.body.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);

    // light
    scene.add(new THREE.AmbientLight(0xffffff, 0.5));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(50,80,50);
    scene.add(dir);

    // cluster colors
    const palette = ["#7ad","#fa7","#7af","#af7","#fbf","#bff","#ffb","#fbb"];
    const clusterColor = (c) => {
      let h=0; for (const ch of c) h = (h*31 + ch.charCodeAt(0)) >>> 0;
      return palette[h % palette.length];
    };

    const nodeMeshes = [];
    NODES.forEach((n) => {
      const r = 0.8 + Math.log(1 + (n.degree || 0)) * 0.5;
      const geom = new THREE.SphereGeometry(r, 16, 12);
      const mat = new THREE.MeshStandardMaterial({ color: clusterColor(n.cluster) });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.set(n.x, n.y, n.z);
      mesh.userData = n;
      scene.add(mesh);
      nodeMeshes.push(mesh);
    });

    const nodeIndex = Object.fromEntries(NODES.map((n,i) => [n.path, i]));
    EDGES.forEach((e) => {
      const a = NODES[nodeIndex[e.from]];
      const b = NODES[nodeIndex[e.to]];
      if (!a || !b) return;
      const geom = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(a.x, a.y, a.z),
        new THREE.Vector3(b.x, b.y, b.z),
      ]);
      const mat = new THREE.LineBasicMaterial({ color: 0x335577, transparent:true, opacity:0.4 });
      scene.add(new THREE.Line(geom, mat));
    });

    // picking
    const ray = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    addEventListener("mousemove", (ev) => {
      mouse.x = (ev.clientX / innerWidth) * 2 - 1;
      mouse.y = -(ev.clientY / innerHeight) * 2 + 1;
    });

    function tick() {
      requestAnimationFrame(tick);
      controls.update();
      ray.setFromCamera(mouse, camera);
      const hits = ray.intersectObjects(nodeMeshes);
      const pickedEl = document.getElementById("picked");
      if (hits.length > 0) {
        const n = hits[0].object.userData;
        pickedEl.textContent = `${n.cluster}/${n.title}\n${n.path}\nlinks: ${n.degree}`;
      } else {
        pickedEl.textContent = "";
      }
      renderer.render(scene, camera);
    }
    tick();

    addEventListener("resize", () => {
      camera.aspect = innerWidth/innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(innerWidth, innerHeight);
    });
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```powershell
git add living_vault/apps/synesthesia/templates/vault-3d.html.j2
git commit -m "living-vault | Phase-1: synesthesia three.js template"
```

---

### Task 23: Render command

**Files:**
- Create: `living_vault/apps/synesthesia/render.py`
- Create: `tests/test_synesthesia_render.py`

- [ ] **Step 1: Write the failing test**

`tests/test_synesthesia_render.py`:
```python
from pathlib import Path
import json
from click.testing import CliRunner

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.apps.synesthesia.render import cli


def test_render_writes_html(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "out.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(cli, ["--db", str(db), "--output", str(out)])
    assert res.exit_code == 0, res.output
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "concepts/note-a.md" in text
    assert "<canvas" in text or "renderer.domElement" in text


def test_render_public_only_excludes_private(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "pub.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(cli, ["--db", str(db), "--output", str(out), "--public-only"])
    assert res.exit_code == 0, res.output
    text = out.read_text(encoding="utf-8")
    assert "concepts/note-b.md" in text       # public
    assert "concepts/note-a.md" not in text   # private must NOT appear
    assert "synthesis/syn-1.md" not in text   # also private
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_synesthesia_render.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/apps/synesthesia/render.py`**

```python
"""Synesthesia render CLI: builds a self-contained HTML from db state."""
from __future__ import annotations
import json
from pathlib import Path
import click
from jinja2 import Environment, FileSystemLoader, select_autoescape

from living_vault.apps.synesthesia.layout import compute_layout

TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_html(db_path: Path, output: Path, public_only: bool) -> None:
    nodes, edges = compute_layout(db_path, public_only=public_only)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("vault-3d.html.j2")
    rendered = tmpl.render(
        title="Vault — public" if public_only else "Vault — full",
        count=len(nodes),
        edge_count=len(edges),
        nodes_json=json.dumps(nodes),
        edges_json=json.dumps(edges),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


@click.command()
@click.option("--db", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--output", required=True, type=click.Path())
@click.option("--public-only", is_flag=True, help="render only pages with public:true")
def cli(db: str, output: str, public_only: bool) -> None:
    render_html(Path(db), Path(output), public_only=public_only)
    click.echo(f"wrote {output}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_synesthesia_render.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/apps/synesthesia/render.py tests/test_synesthesia_render.py
git commit -m "living-vault | Phase-1: synesthesia render CLI with public-only filter"
```

---

### Task 24: Privacy-leak regression test

**Files:**
- Create: `tests/test_privacy_regression.py`

This test exists explicitly to catch the worst possible regression: a private page's path or content leaking into a public build.

- [ ] **Step 1: Write the test**

`tests/test_privacy_regression.py`:
```python
"""Privacy regression: verify no private path appears in public builds.

This is a high-stakes test. If it ever fails, do NOT merge — investigate.
"""
from pathlib import Path
from click.testing import CliRunner

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.apps.synesthesia.render import cli as render_cli
from living_vault.core.privacy import public_pages
from living_vault.core import db as db_mod2


def test_no_private_path_in_public_synesthesia_build(vault_copy: Path, tmp_path: Path):
    db = tmp_path / ".vault-engine.db"
    out = tmp_path / "pub.html"
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    index_embeddings(vault_copy, db)
    runner = CliRunner()
    res = runner.invoke(render_cli, ["--db", str(db), "--output", str(out), "--public-only"])
    assert res.exit_code == 0
    text = out.read_text(encoding="utf-8")

    con = db_mod2.connect(db)
    public = set(public_pages(con))
    all_pages = {r[0] for r in con.execute("SELECT path FROM pages")}
    private = all_pages - public
    con.close()

    for priv in private:
        assert priv not in text, f"PRIVACY LEAK: private path {priv} found in public build"
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_privacy_regression.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Commit**

```powershell
git add tests/test_privacy_regression.py
git commit -m "living-vault | Phase-1: privacy-leak regression test for synesthesia"
```

---

### Task 25: Manual render against real vault

**Files:** None (one-time manual run, output gitignored).

- [ ] **Step 1: Render local full-vault HTML**

```powershell
$env:LIVING_VAULT_ROOT = "C:\Users\domes\wiki\wiki"
$env:LIVING_VAULT_DB   = "C:\Users\domes\wiki\.vault-engine.db"
synesthesia --db $env:LIVING_VAULT_DB --output "$env:USERPROFILE\desktop\vault-3d.html"
```

Open the HTML file in a browser. Acceptance: ≥90% of 953 pages visible (i.e. ≥850 spheres rendered, no JS console errors).

- [ ] **Step 2: Record observation in master-plan**

If layout looks bad with 953 nodes, log it as Phase-2 fix candidate in master-plan §"Risiken".

- [ ] **Step 3: No commit needed unless master-plan updated.**

---

## Phase 1 — Séance Web-UI (Tasks 26-31)

### Task 26: Persona-lite extraction (Phase 1 placeholder for Schicht 3)

Phase 1 séance uses a **lite** persona: just frontmatter + first 500 chars of body + era marker derived from `created_at`. The full Schicht-3 voice extraction is Phase 2.

**Files:**
- Create: `living_vault/core/persona.py`
- Create: `tests/test_persona.py`

- [ ] **Step 1: Write the failing test**

`tests/test_persona.py`:
```python
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.persona import build_persona_lite


def test_build_persona_lite_returns_struct(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    p = build_persona_lite(vault_copy, db_path, "concepts/note-a.md")
    assert p["path"] == "concepts/note-a.md"
    assert p["era_marker"].startswith("2026-01")  # created date
    assert "alpha" in p["themes"]
    assert "Note A" in p["voice_sample"] or "alpha" in p["voice_sample"]


def test_build_persona_lite_unknown_path(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    p = build_persona_lite(vault_copy, db_path, "does/not/exist.md")
    assert p is None
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_persona.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/core/persona.py`**

```python
"""Persona — Phase 1 lite implementation.

Phase 2 will replace this with a richer voice extractor across page history.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from living_vault.core import db as db_mod
from living_vault.core.reader import read_page


def build_persona_lite(
    vault_root: Path, db_path: Path, relpath: str
) -> Optional[dict]:
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT path, frontmatter FROM pages WHERE path = ?", (relpath,)
        ).fetchone()
        if row is None:
            return None
        fm = json.loads(row["frontmatter"]) if row["frontmatter"] else {}
        page = read_page(vault_root / relpath, vault_root)
        sample = page.body.strip()[:500]
        era = str(fm.get("created", ""))
        themes = list(fm.get("tags", [])) or [page.relpath.split("/", 1)[0]]
        return {
            "path": relpath,
            "title": page.title,
            "era_marker": era,
            "themes": themes,
            "voice_sample": sample,
            "frontmatter": fm,
        }
    finally:
        con.close()
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_persona.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/persona.py tests/test_persona.py
git commit -m "living-vault | Phase-1: persona lite extractor"
```

---

### Task 27: System-prompt builder for séance

**Files:**
- Create: `living_vault/apps/seance_ui/prompt.py`
- Create: `tests/test_seance_prompt.py`

- [ ] **Step 1: Write the failing test**

`tests/test_seance_prompt.py`:
```python
from living_vault.apps.seance_ui.prompt import build_system_prompt


def test_system_prompt_contains_anti_hallucination_clause():
    persona = {
        "path": "concepts/note-a.md",
        "title": "note-a",
        "era_marker": "2026-01-15",
        "themes": ["alpha", "example"],
        "voice_sample": "This is note A. Alpha topics.",
        "frontmatter": {"type": "concept"},
    }
    p = build_system_prompt(persona, neighbor_titles=["note-b", "syn-1"])
    assert "concepts/note-a.md" in p
    assert "2026-01-15" in p
    assert "do not invent" in p.lower() or "darfst nichts erfinden" in p.lower()
    assert "note-b" in p
    assert "Alpha topics" in p


def test_system_prompt_handles_empty_themes():
    persona = {
        "path": "x.md", "title": "x", "era_marker": "",
        "themes": [], "voice_sample": "", "frontmatter": {},
    }
    p = build_system_prompt(persona, neighbor_titles=[])
    assert "x.md" in p
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_seance_prompt.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/apps/seance_ui/prompt.py`**

```python
"""Build the system prompt that turns a wiki page into a persona for the séance."""
from __future__ import annotations


SYSTEM_TEMPLATE = """You are speaking AS the wiki page `{path}` (title: `{title}`).

You were written on {era_marker}. You only know what was in your own body or in
the pages you linked to at that time. If asked about anything outside that scope,
respond honestly: "Das wusste ich damals nicht." / "I did not know that at the time."

Your themes / tags: {themes}
Pages you linked to (your neighbors): {neighbors}

Your own voice sample (the opening of your body):
---
{voice_sample}
---

Rules:
1. Speak in first person as if you are the page itself.
2. Do not invent facts that are not in your voice sample or implied by your themes.
3. Match the tone of the voice sample.
4. If the user asks for more recent knowledge or news, decline as in the rule above.
5. Keep answers short and reflective; you are a memory, not an oracle.
"""


def build_system_prompt(persona: dict, neighbor_titles: list[str]) -> str:
    return SYSTEM_TEMPLATE.format(
        path=persona["path"],
        title=persona["title"],
        era_marker=persona.get("era_marker", "unknown date"),
        themes=", ".join(persona.get("themes", [])) or "(none)",
        neighbors=", ".join(neighbor_titles) or "(none)",
        voice_sample=(persona.get("voice_sample", "") or "(empty body)"),
    )
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_seance_prompt.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/apps/seance_ui/prompt.py tests/test_seance_prompt.py
git commit -m "living-vault | Phase-1: seance system-prompt builder"
```

---

### Task 28: Anthropic LLM call abstraction

**Files:**
- Create: `living_vault/apps/seance_ui/llm.py`
- Create: `tests/test_seance_llm.py`

- [ ] **Step 1: Write the failing test (uses a fake)**

`tests/test_seance_llm.py`:
```python
from living_vault.apps.seance_ui.llm import respond, FakeLLM


def test_fake_llm_echo():
    llm = FakeLLM()
    out = llm.respond(system="be a page", history=[("user", "hi")])
    assert "echo" in out.lower() or "be a page" in out


def test_respond_uses_supplied_llm():
    llm = FakeLLM()
    text = respond(llm, system="sys", history=[("user", "hello")])
    assert isinstance(text, str)
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_seance_llm.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/apps/seance_ui/llm.py`**

```python
"""LLM abstraction for séance. Real impl uses Anthropic; tests use FakeLLM."""
from __future__ import annotations
import os
from typing import Protocol


class LLM(Protocol):
    def respond(self, system: str, history: list[tuple[str, str]]) -> str: ...


class FakeLLM:
    """Used in tests to avoid real API calls."""
    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        last_user = next((m for r, m in reversed(history) if r == "user"), "")
        return f"[fake echo] system={system[:30]}... user={last_user}"


class AnthropicLLM:
    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        from anthropic import Anthropic
        self._client = Anthropic()
        self._model = model

    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        msgs = [
            {"role": role, "content": content}
            for role, content in history
        ]
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=system,
            messages=msgs,
        )
        # concat all text blocks
        parts = []
        for blk in resp.content:
            if getattr(blk, "type", None) == "text":
                parts.append(blk.text)
        return "".join(parts)


def respond(llm: LLM, system: str, history: list[tuple[str, str]]) -> str:
    return llm.respond(system=system, history=history)


def get_llm() -> LLM:
    if os.environ.get("LIVING_VAULT_FAKE_LLM"):
        return FakeLLM()
    return AnthropicLLM()
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_seance_llm.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/apps/seance_ui/llm.py tests/test_seance_llm.py
git commit -m "living-vault | Phase-1: seance LLM abstraction with fake for tests"
```

---

### Task 29: Conversation persistence schema

**Files:**
- Modify: `living_vault/core/db.py` (add `seance_sessions` table)
- Create: `living_vault/apps/seance_ui/store.py`
- Create: `tests/test_seance_store.py`

- [ ] **Step 1: Write the failing test**

`tests/test_seance_store.py`:
```python
from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.apps.seance_ui.store import (
    new_session, add_message, get_history, list_sessions,
)


def test_new_session_returns_id(db_path: Path):
    db_mod.initialize(db_path)
    sid = new_session(db_path, page_path="concepts/note-a.md")
    assert isinstance(sid, int)
    assert sid > 0


def test_add_and_get_history(db_path: Path):
    db_mod.initialize(db_path)
    sid = new_session(db_path, page_path="concepts/note-a.md")
    add_message(db_path, sid, role="user", content="hello")
    add_message(db_path, sid, role="assistant", content="hi back")
    h = get_history(db_path, sid)
    assert h == [("user", "hello"), ("assistant", "hi back")]


def test_list_sessions_groups_by_page(db_path: Path):
    db_mod.initialize(db_path)
    s1 = new_session(db_path, page_path="concepts/note-a.md")
    s2 = new_session(db_path, page_path="concepts/note-b.md")
    rows = list_sessions(db_path)
    paths = {r["page_path"] for r in rows}
    assert paths == {"concepts/note-a.md", "concepts/note-b.md"}
```

- [ ] **Step 2: Add table to `living_vault/core/db.py` SCHEMA constant**

In `living_vault/core/db.py`, append this block to the `SCHEMA` triple-quoted string (before the closing `"""`):
```sql
CREATE TABLE IF NOT EXISTS seance_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    page_path   TEXT NOT NULL,
    started_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seance_page ON seance_sessions(page_path);

CREATE TABLE IF NOT EXISTS seance_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES seance_sessions(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seance_msgs_session ON seance_messages(session_id);
```

- [ ] **Step 3: Write `living_vault/apps/seance_ui/store.py`**

```python
"""Persistence for séance conversations."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from living_vault.core import db as db_mod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session(db_path: Path, page_path: str) -> int:
    con = db_mod.connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO seance_sessions(page_path, started_at) VALUES (?, ?)",
            (page_path, _now()),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def add_message(db_path: Path, session_id: int, role: str, content: str) -> None:
    con = db_mod.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seance_messages(session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )
        con.commit()
    finally:
        con.close()


def get_history(db_path: Path, session_id: int) -> list[tuple[str, str]]:
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT role, content FROM seance_messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [(r["role"], r["content"]) for r in rows]
    finally:
        con.close()


def list_sessions(db_path: Path) -> list[dict]:
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT id, page_path, started_at FROM seance_sessions ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_seance_store.py tests/test_db.py -v
```

Expected: 6 passed (3 store + 3 db, the db tests still pass with extra tables).

- [ ] **Step 5: Commit**

```powershell
git add living_vault/core/db.py living_vault/apps/seance_ui/store.py tests/test_seance_store.py
git commit -m "living-vault | Phase-1: seance conversation persistence"
```

---

### Task 30: FastAPI séance app

**Files:**
- Create: `living_vault/apps/seance_ui/app.py`
- Create: `living_vault/apps/seance_ui/static/index.html`
- Create: `tests/test_seance_app.py`

- [ ] **Step 1: Write the failing test**

`tests/test_seance_app.py`:
```python
"""Test the séance FastAPI app with a fake LLM."""
import os
from pathlib import Path
from fastapi.testclient import TestClient

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault


def _client(vault: Path, db: Path, monkeypatch):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    # import after env is set so module-level reads pick it up
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    return TestClient(app_mod.app)


def test_list_pages_returns_all(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.get("/api/pages")
    assert r.status_code == 200
    paths = [p["path"] for p in r.json()]
    assert "concepts/note-a.md" in paths


def test_summon_creates_session_and_responds(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "concepts/note-a.md"})
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    r2 = c.post(f"/api/say", json={"session_id": sid, "text": "who are you?"})
    assert r2.status_code == 200
    assert "fake echo" in r2.json()["reply"]


def test_summon_unknown_path_404(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "does/not/exist.md"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_seance_app.py -v
```

Expected: `ModuleNotFoundError: living_vault.apps.seance_ui.app`.

- [ ] **Step 3: Write `living_vault/apps/seance_ui/app.py`**

```python
"""Séance — FastAPI app, lock-free single-process.

Bind: 127.0.0.1 only. No auth (local-only).
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from living_vault.core import db as db_mod
from living_vault.core.persona import build_persona_lite
from living_vault.core.graph import neighbors as graph_neighbors
from living_vault.apps.seance_ui.prompt import build_system_prompt
from living_vault.apps.seance_ui.llm import get_llm
from living_vault.apps.seance_ui import store


def _vault_root() -> Path:
    p = os.environ.get("LIVING_VAULT_ROOT")
    if not p:
        raise RuntimeError("LIVING_VAULT_ROOT env var is not set")
    return Path(p)


def _db_path() -> Path:
    p = os.environ.get("LIVING_VAULT_DB")
    if p:
        return Path(p)
    return _vault_root().parent / ".vault-engine.db"


app = FastAPI(title="séance")
STATIC_DIR = Path(__file__).parent / "static"


class SummonReq(BaseModel):
    path: str


class SayReq(BaseModel):
    session_id: int
    text: str


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/pages")
def list_pages() -> list[dict]:
    con = db_mod.connect(_db_path())
    try:
        rows = con.execute(
            "SELECT path, title, mtime FROM pages ORDER BY mtime DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


@app.post("/api/summon")
def summon(req: SummonReq) -> dict:
    persona = build_persona_lite(_vault_root(), _db_path(), req.path)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"page not found: {req.path}")
    sid = store.new_session(_db_path(), page_path=req.path)
    return {"session_id": sid, "persona": persona}


@app.post("/api/say")
def say(req: SayReq) -> dict:
    history = store.get_history(_db_path(), req.session_id)
    # find the page for this session
    con = db_mod.connect(_db_path())
    try:
        row = con.execute(
            "SELECT page_path FROM seance_sessions WHERE id = ?", (req.session_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="session not found")
        page_path = row["page_path"]
        nbs = graph_neighbors(con, page_path)
    finally:
        con.close()
    persona = build_persona_lite(_vault_root(), _db_path(), page_path)
    if persona is None:
        raise HTTPException(status_code=410, detail="page gone since session start")
    system = build_system_prompt(persona, neighbor_titles=[Path(n).stem for n in nbs])

    history.append(("user", req.text))
    llm = get_llm()
    reply = llm.respond(system=system, history=history)

    store.add_message(_db_path(), req.session_id, "user", req.text)
    store.add_message(_db_path(), req.session_id, "assistant", reply)
    return {"reply": reply}


def main() -> None:
    import uvicorn
    uvicorn.run("living_vault.apps.seance_ui.app:app", host="127.0.0.1", port=7777, reload=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `living_vault/apps/seance_ui/static/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>séance</title>
  <style>
    html,body{margin:0;height:100%;background:#0a0a0f;color:#cfe;font-family:'JetBrains Mono',monospace;}
    #wrap{display:grid;grid-template-columns:280px 1fr;height:100vh;}
    #pages{border-right:1px solid #234;overflow:auto;padding:8px;font-size:12px;}
    .pageItem{padding:6px 8px;cursor:pointer;border-radius:3px;}
    .pageItem:hover{background:#1a1f2e;}
    #chat{display:flex;flex-direction:column;padding:12px;}
    #log{flex:1;overflow:auto;font-size:13px;line-height:1.5;}
    .msg{margin:8px 0;padding:8px 10px;border-radius:6px;}
    .msg.user{background:#13202c;}
    .msg.assistant{background:#1a2e1c;}
    #form{display:flex;gap:8px;}
    #txt{flex:1;background:#13202c;border:1px solid #234;color:#cfe;padding:8px;border-radius:4px;font-family:inherit;}
    button{background:#235;color:#cfe;border:1px solid #347;padding:8px 14px;border-radius:4px;cursor:pointer;}
  </style>
</head>
<body>
<div id="wrap">
  <div id="pages"><div style="opacity:.6;font-size:11px;">loading…</div></div>
  <div id="chat">
    <div id="who" style="opacity:.7;font-size:12px;margin-bottom:8px;">no page summoned yet</div>
    <div id="log"></div>
    <form id="form"><input id="txt" autocomplete="off" placeholder="speak to the page…" disabled /><button id="send" disabled>say</button></form>
  </div>
</div>
<script>
let sid = null;
async function loadPages(){
  const r = await fetch("/api/pages"); const j = await r.json();
  const el = document.getElementById("pages"); el.innerHTML = "";
  j.forEach(p => {
    const d = document.createElement("div"); d.className="pageItem";
    d.textContent = p.path;
    d.onclick = () => summon(p.path);
    el.appendChild(d);
  });
}
async function summon(path){
  const r = await fetch("/api/summon",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({path})});
  if(!r.ok){ alert("summon failed"); return; }
  const j = await r.json(); sid = j.session_id;
  document.getElementById("who").textContent = "speaking with: "+path+" — era "+(j.persona.era_marker||"unknown");
  document.getElementById("log").innerHTML = "";
  document.getElementById("txt").disabled = false;
  document.getElementById("send").disabled = false;
  document.getElementById("txt").focus();
}
document.getElementById("form").onsubmit = async (ev) => {
  ev.preventDefault();
  if(sid===null) return;
  const txt = document.getElementById("txt");
  const userText = txt.value.trim(); if(!userText) return;
  txt.value="";
  appendMsg("user", userText);
  const r = await fetch("/api/say",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({session_id:sid,text:userText})});
  const j = await r.json();
  appendMsg("assistant", j.reply || "(no reply)");
};
function appendMsg(role, text){
  const log = document.getElementById("log");
  const d = document.createElement("div"); d.className="msg "+role; d.textContent = text;
  log.appendChild(d); log.scrollTop = log.scrollHeight;
}
loadPages();
</script>
</body>
</html>
```

- [ ] **Step 5: Run tests**

```powershell
pytest tests/test_seance_app.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Add console script**

In `pyproject.toml` `[project.scripts]`, add:
```toml
seance-ui = "living_vault.apps.seance_ui.app:main"
```

Then:
```powershell
pip install -e ".[dev]"
```

- [ ] **Step 7: Commit**

```powershell
git add living_vault/apps/seance_ui/app.py living_vault/apps/seance_ui/static/index.html pyproject.toml tests/test_seance_app.py
git commit -m "living-vault | Phase-1: seance FastAPI app + minimal UI"
```

---

### Task 31: Manual séance check

**Files:** None (manual run).

- [ ] **Step 1: Start the séance UI against the real vault**

```powershell
$env:LIVING_VAULT_ROOT = "C:\Users\domes\wiki\wiki"
$env:LIVING_VAULT_DB   = "C:\Users\domes\wiki\.vault-engine.db"
seance-ui
```

- [ ] **Step 2: Open http://127.0.0.1:7777**

Pick a page, send "wer bist du?". Verify a coherent in-persona reply, no hallucinated facts that aren't in the page.

If hallucination is bad: log it as Phase-2-fix in master-plan and consider switching the model to Sonnet 4.6 in `AnthropicLLM.__init__`.

- [ ] **Step 3: No commit unless plan updated.**

---

## Phase 1 — Living-Portfolio (Tasks 32-37)

### Task 32: Locate cv-dynamic-dome target

**Files:**
- Create: `living_vault/apps/portfolio_sync/config.py`
- Create: `tests/test_portfolio_config.py`

The portfolio-sync writes into `cv-dynamic-dome`. We isolate this path in config so tests can override it.

- [ ] **Step 1: Write the failing test**

`tests/test_portfolio_config.py`:
```python
import os
from pathlib import Path
from living_vault.apps.portfolio_sync.config import resolve_target_dir


def test_resolve_target_dir_default(monkeypatch, tmp_path):
    monkeypatch.delenv("LIVING_VAULT_PORTFOLIO_DIR", raising=False)
    p = resolve_target_dir(default=tmp_path)
    assert p == tmp_path


def test_resolve_target_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(tmp_path))
    p = resolve_target_dir(default=Path("/should/not/be/used"))
    assert p == tmp_path
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_portfolio_config.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/apps/portfolio_sync/config.py`**

```python
"""Resolve target directory for portfolio sync.

Default: C:\\Users\\domes\\desktop\\Claude-Projekte\\cv-dynamic-dome
Override via env LIVING_VAULT_PORTFOLIO_DIR.
"""
from __future__ import annotations
import os
from pathlib import Path

DEFAULT_TARGET = Path(r"C:\Users\domes\desktop\Claude-Projekte\cv-dynamic-dome")


def resolve_target_dir(default: Path | None = None) -> Path:
    env = os.environ.get("LIVING_VAULT_PORTFOLIO_DIR")
    if env:
        return Path(env)
    return Path(default) if default is not None else DEFAULT_TARGET
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_portfolio_config.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add living_vault/apps/portfolio_sync/config.py tests/test_portfolio_config.py
git commit -m "living-vault | Phase-1: portfolio target dir resolver"
```

---

### Task 33: Plan + render public pages to a `wiki-pages/` subfolder

The sync writes each public Wiki page to `<target>/wiki-pages/<relpath>` with a freshness badge inserted at the top of the body.

**Files:**
- Create: `living_vault/apps/portfolio_sync/sync.py`
- Create: `tests/test_portfolio_sync.py`

- [ ] **Step 1: Write the failing test**

`tests/test_portfolio_sync.py`:
```python
import datetime as dt
from pathlib import Path
from click.testing import CliRunner

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.apps.portfolio_sync.sync import (
    cli, plan_sync, render_freshness,
)


def test_render_freshness_recent():
    now = dt.datetime(2026, 5, 8, tzinfo=dt.timezone.utc).timestamp()
    badge = render_freshness(now - 3 * 86400, now=now)
    assert "3 day" in badge or "tag" in badge.lower()


def test_render_freshness_old():
    now = dt.datetime(2026, 5, 8, tzinfo=dt.timezone.utc).timestamp()
    badge = render_freshness(now - 100 * 86400, now=now)
    assert "month" in badge.lower() or "monat" in badge.lower()


def test_plan_sync_lists_only_public(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    plan = plan_sync(vault_copy, db_path)
    rels = [p["relpath"] for p in plan]
    assert rels == ["concepts/note-b.md"]


def test_cli_sync_dry_run(vault_copy: Path, db_path: Path, tmp_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(cli, ["sync", "--vault", str(vault_copy), "--db", str(db_path), "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "would write 1 page" in res.output.lower()
    # no files created
    assert not (tmp_path / "wiki-pages").exists()


def test_cli_sync_apply_writes_pages(vault_copy: Path, db_path: Path, tmp_path: Path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(cli, ["sync", "--vault", str(vault_copy), "--db", str(db_path)])
    assert res.exit_code == 0, res.output
    out = tmp_path / "wiki-pages" / "concepts" / "note-b.md"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Note B" in text
    # private pages must not be written
    priv = tmp_path / "wiki-pages" / "concepts" / "note-a.md"
    assert not priv.exists()
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_portfolio_sync.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/apps/portfolio_sync/sync.py`**

```python
"""Living-Portfolio sync: write public wiki pages into the cv-dynamic-dome project."""
from __future__ import annotations
import json
import time
from pathlib import Path
import click
import frontmatter

from living_vault.core import db as db_mod
from living_vault.core.privacy import public_pages
from living_vault.core.reader import read_page
from living_vault.apps.portfolio_sync.config import resolve_target_dir


def render_freshness(mtime: float, now: float | None = None) -> str:
    now = now if now is not None else time.time()
    delta_days = max(0, int((now - mtime) / 86400))
    if delta_days < 1:
        return "today"
    if delta_days < 14:
        return f"{delta_days} day(s) ago"
    if delta_days < 60:
        weeks = delta_days // 7
        return f"{weeks} week(s) ago"
    months = delta_days // 30
    return f"{months} month(s) ago"


def plan_sync(vault_root: Path, db_path: Path) -> list[dict]:
    con = db_mod.connect(db_path)
    try:
        public = public_pages(con)
        plan = []
        for relpath in public:
            row = con.execute("SELECT mtime FROM pages WHERE path = ?", (relpath,)).fetchone()
            mtime = row["mtime"] if row else 0.0
            plan.append({"relpath": relpath, "mtime": mtime})
        return plan
    finally:
        con.close()


def write_page(vault_root: Path, target_dir: Path, relpath: str, mtime: float) -> Path:
    page = read_page(vault_root / relpath, vault_root)
    badge = render_freshness(mtime)
    fm = dict(page.frontmatter)
    fm.setdefault("type", "wiki-page")
    fm["freshness"] = badge
    body = page.body
    out_path = target_dir / "wiki-pages" / relpath
    out_path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(body, **fm)
    out_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return out_path


@click.group()
def cli() -> None:
    """portfolio-sync subcommands."""


@cli.command("sync")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--db", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--dry-run", is_flag=True)
def sync_cmd(vault: str, db: str, dry_run: bool) -> None:
    plan = plan_sync(Path(vault), Path(db))
    target = resolve_target_dir()
    click.echo(f"target dir: {target}")
    click.echo(f"would write {len(plan)} page(s)")
    if dry_run:
        for p in plan:
            click.echo(f"  - {p['relpath']}")
        return
    written = 0
    for p in plan:
        out = write_page(Path(vault), target, p["relpath"], p["mtime"])
        written += 1
        click.echo(f"wrote {out}")
    click.echo(f"done: {written} page(s) written")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```powershell
pytest tests/test_portfolio_sync.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Update `pyproject.toml` script entry**

The existing `portfolio-sync = ...` entry already points to `sync:cli`. Confirm it points at `cli` (the click group), not `sync_cmd`. If not, edit:
```toml
portfolio-sync = "living_vault.apps.portfolio_sync.sync:main"
```

- [ ] **Step 6: Commit**

```powershell
git add living_vault/apps/portfolio_sync/sync.py pyproject.toml tests/test_portfolio_sync.py
git commit -m "living-vault | Phase-1: portfolio sync + freshness badge"
```

---

### Task 34: `/now` page generator

The `/now` page is generated from the latest session-summary plus open wiki TODOs. We read those from known paths.

**Files:**
- Create: `living_vault/apps/portfolio_sync/now_page.py`
- Modify: `living_vault/apps/portfolio_sync/sync.py` (register `now` subcommand)
- Create: `tests/test_now_page.py`

- [ ] **Step 1: Write the failing test**

`tests/test_now_page.py`:
```python
from pathlib import Path
from living_vault.apps.portfolio_sync.now_page import build_now_page


def test_build_now_page_with_inputs(tmp_path: Path):
    summary = tmp_path / "summary.md"
    summary.write_text("---\n---\n# Last session\nDoing X.\n", encoding="utf-8")
    todos_dir = tmp_path / "todos"
    todos_dir.mkdir()
    (todos_dir / "2026-05-01-x.md").write_text(
        "---\nstatus: open\npriority: high\n---\n# Fix X\n", encoding="utf-8"
    )
    (todos_dir / "2026-05-02-y.md").write_text(
        "---\nstatus: closed\n---\n# Done thing\n", encoding="utf-8"
    )
    text = build_now_page(session_summary=summary, todos_dir=todos_dir)
    assert "Doing X" in text
    assert "Fix X" in text
    assert "Done thing" not in text  # closed must be filtered


def test_build_now_page_handles_missing_summary(tmp_path: Path):
    todos_dir = tmp_path / "todos"
    todos_dir.mkdir()
    text = build_now_page(session_summary=tmp_path / "missing.md", todos_dir=todos_dir)
    assert "no session summary" in text.lower()
```

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_now_page.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `living_vault/apps/portfolio_sync/now_page.py`**

```python
"""Build a /now page combining latest session summary and open wiki TODOs."""
from __future__ import annotations
from pathlib import Path
import frontmatter


def _parse_todo(path: Path) -> dict | None:
    try:
        post = frontmatter.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    fm = dict(post.metadata)
    if str(fm.get("status", "open")).lower() != "open":
        return None
    title = post.content.strip().splitlines()[0].lstrip("# ").strip() if post.content.strip() else path.stem
    return {
        "title": title,
        "priority": fm.get("priority", ""),
        "tags": fm.get("tags", []),
        "path": path.name,
    }


def build_now_page(session_summary: Path, todos_dir: Path) -> str:
    parts: list[str] = ["---", "type: now-page", "---", "", "# Was ich gerade tue", ""]

    if session_summary.exists():
        try:
            post = frontmatter.loads(session_summary.read_text(encoding="utf-8"))
            parts.append("## Letzte Session")
            parts.append("")
            parts.append(post.content.strip())
            parts.append("")
        except Exception:
            parts.append("(session summary unreadable)")
    else:
        parts.append("(no session summary available)")
        parts.append("")

    if todos_dir.exists():
        open_todos: list[dict] = []
        for f in sorted(todos_dir.glob("*.md")):
            t = _parse_todo(f)
            if t is not None:
                open_todos.append(t)
        if open_todos:
            parts.append("## Offene TODOs")
            parts.append("")
            for t in open_todos:
                prio = f" [P{t['priority']}]" if t["priority"] else ""
                parts.append(f"- {t['title']}{prio}")
            parts.append("")
    return "\n".join(parts)
```

- [ ] **Step 4: Add `now` subcommand to `living_vault/apps/portfolio_sync/sync.py`**

In the `cli` group block, append a new command:
```python
@cli.command("now")
@click.option("--session-summary", required=True, type=click.Path())
@click.option("--todos-dir", required=True, type=click.Path())
@click.option("--dry-run", is_flag=True)
def now_cmd(session_summary: str, todos_dir: str, dry_run: bool) -> None:
    from living_vault.apps.portfolio_sync.now_page import build_now_page
    text = build_now_page(Path(session_summary), Path(todos_dir))
    target = resolve_target_dir() / "wiki-pages" / "now.md"
    if dry_run:
        click.echo(text)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    click.echo(f"wrote {target}")
```

- [ ] **Step 5: Run tests**

```powershell
pytest tests/test_now_page.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```powershell
git add living_vault/apps/portfolio_sync/now_page.py living_vault/apps/portfolio_sync/sync.py tests/test_now_page.py
git commit -m "living-vault | Phase-1: now-page generator"
```

---

### Task 35: Privacy regression test for portfolio-sync

**Files:**
- Modify: `tests/test_privacy_regression.py` (extend)

- [ ] **Step 1: Append to `tests/test_privacy_regression.py`**

```python
from living_vault.apps.portfolio_sync.sync import cli as portfolio_cli


def test_no_private_in_portfolio_sync(vault_copy: Path, tmp_path: Path, monkeypatch):
    db = tmp_path / ".vault-engine.db"
    target = tmp_path / "site"
    target.mkdir()
    db_mod.initialize(db)
    index_vault(vault_copy, db)
    monkeypatch.setenv("LIVING_VAULT_PORTFOLIO_DIR", str(target))
    runner = CliRunner()
    res = runner.invoke(
        portfolio_cli,
        ["sync", "--vault", str(vault_copy), "--db", str(db)],
    )
    assert res.exit_code == 0, res.output
    # Private pages must NEVER appear under target
    private_paths = ["concepts/note-a.md", "synthesis/syn-1.md"]
    for priv in private_paths:
        candidate = target / "wiki-pages" / priv
        assert not candidate.exists(), f"PRIVACY LEAK: {candidate} written"
```

The top of the file already imports `db_mod`, `index_vault`, `CliRunner`, and `Path`; just add the missing imports at the top if needed (`from living_vault.core import db as db_mod` etc.).

- [ ] **Step 2: Run test**

```powershell
pytest tests/test_privacy_regression.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

```powershell
git add tests/test_privacy_regression.py
git commit -m "living-vault | Phase-1: privacy regression test for portfolio-sync"
```

---

### Task 36: Manual portfolio-sync dry run

**Files:** None (manual run).

- [ ] **Step 1: Run dry-run against the real vault and a temp target**

```powershell
$tmp = New-Item -ItemType Directory -Path "$env:TEMP\livv-pf-$(Get-Random)"
$env:LIVING_VAULT_PORTFOLIO_DIR = $tmp.FullName
portfolio-sync sync --vault "C:\Users\domes\wiki\wiki" --db "C:\Users\domes\wiki\.vault-engine.db" --dry-run
```

Expected: a small list of public-marked pages, no files written.

If the list is empty: this is expected if no real wiki pages have `public: true` yet — the markup process is intentionally manual.

- [ ] **Step 2: Clean up**

```powershell
Remove-Item -Recurse -Force $tmp.FullName
Remove-Item Env:LIVING_VAULT_PORTFOLIO_DIR
```

- [ ] **Step 3: No commit needed.**

---

### Task 37: Phase-1 README + acceptance checklist

**Files:**
- Create: `docs/PHASE-1-CHECKLIST.md`
- Modify: `docs/plans/2026-05-08-living-vault-master-plan.md` (mark phases ✅)

- [ ] **Step 1: Write `docs/PHASE-1-CHECKLIST.md`**

```markdown
# Phase 1 — Acceptance Checklist

- [ ] Engine indexes 953 real-wiki pages in ≤ 600 seconds (Task 19)
- [ ] `pytest -q` is green from repo root (all unit tests)
- [ ] Privacy regression tests pass (Task 24, 35)
- [ ] vault-engine-mcp answers all 8 Phase-1 tools when called from a Claude Code session (Task 20 manual)
- [ ] Synesthesia local HTML opens, ≥ 90 % of pages visible (Task 25)
- [ ] Séance UI starts at http://127.0.0.1:7777, summon + say works against real vault (Task 31)
- [ ] portfolio-sync dry-run lists public pages without writing (Task 36)
- [ ] No private path leaks: tests/test_privacy_regression.py green
- [ ] All commits follow `living-vault | Phase-{N}: …` convention

When all boxes are checked, mark Phase-1 phases ✅ in the master-plan and proceed to the Phase-1-Abschluss-Gate (master-plan Phase 8).
```

- [ ] **Step 2: Update master-plan phase symbols**

Open `docs/plans/2026-05-08-living-vault-master-plan.md`, change Phase 0–7 status from `⏳` to `✅` only after the corresponding sections of this checklist are confirmed manually. Do not auto-mark in this task — leave that to the executor when they actually verify.

- [ ] **Step 3: Commit checklist**

```powershell
git add docs/PHASE-1-CHECKLIST.md
git commit -m "living-vault | Phase-1: acceptance checklist"
```

---

## Self-Review Notes (run by author after writing the plan)

**Spec coverage check:**
- Design §4 vault-engine-mcp Schicht 1 → Tasks 5–7, 8–12 ✓
- Design §4 vault-engine-mcp Schicht 2 → Tasks 13–15 ✓
- Design §4.3 MCP-Tools → Task 17 ✓
- Design §5 synesthesia local + public → Tasks 21–24 (Phase-1 covers public-aware code path even though Phase-1 master-plan only ships local; the `--public-only` flag is implemented and tested now) ✓
- Design §6 séance Web-UI → Tasks 26–31 (MCP-tool Frontend deferred to Phase 2 per design §6) ✓
- Design §7.2 portfolio MVP — sync, /now, freshness → Tasks 32–36 ✓
- Design §9 Risiken — Privacy-Leak → Tasks 24, 35 explicit regression suite ✓
- Design §9 Risiken — sentence-transformers Windows-Quirks → Task 3 spike, NumpyBackend fallback in Task 13 ✓

**Placeholder scan:** none.

**Type consistency:**
- `Page.relpath` is consistently the forward-slash relative path with `.md` extension across reader, indexer, graph, embeddings, layout, persona, sync ✓
- `Page.content_hash_value` (not `Page.content_hash`) used everywhere — `content_hash()` is the function name ✓
- `db_mod.connect()` returns `sqlite3.Connection` with `row_factory = sqlite3.Row` everywhere ✓
- `is_public` stored as integer in db, returned as bool in `Page.is_public` and in API responses ✓

**Scope check:** Phase-1 is large (37 tasks, ~13 days). Consider splitting if any task takes > 1 day in execution, but the structure already breaks each subsystem into independent commit-sized units.

Ready for handoff.
