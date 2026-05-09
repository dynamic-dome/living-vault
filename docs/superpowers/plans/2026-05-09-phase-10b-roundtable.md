# Phase 10b — Multi-Persona-Roundtable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Multi-Persona-Roundtable to séance: user can summon N pages (1-8) with a mode (round-robin/moderator/free-for-all). Each persona shares a common conversation history, can call `consult_neighbor` on its own wiki neighbors AND on the other roundtable participants. UI renders persona-labeled bubbles with hash-based deterministic colors.

**Architecture:** Approach A — Symmetrische Architektur. Roundtable is a wrapper around N parallel persona-states; reuses the Phase-10a tool-use loop (`respond_with_tools`, `consult_neighbor`) per persona unchanged. New module `apps/seance_ui/roundtable.py` owns mode-logic (`pick_speakers`), color hashing, and the shared-history rendering. The `say()` endpoint branches on `session.mode` — single → existing Phase-10a path, otherwise → `roundtable_say()`.

**Tech Stack:** Python 3.11+, FastAPI, sqlite3, Anthropic SDK, pytest, FastAPI TestClient, vanilla JS in static/index.html.

**Spec:** [`../specs/2026-05-09-phase-10b-roundtable-design.md`](../specs/2026-05-09-phase-10b-roundtable-design.md)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `living_vault/core/db.py` | modify | Add `seance_sessions.mode` migration (idempotent) + `seance_session_personas` table (CREATE IF NOT EXISTS) |
| `living_vault/apps/seance_ui/store.py` | modify | `new_session(mode=)`, `add_session_persona`, `get_session_personas`, `count_user_turns`, `get_session_mode` |
| `living_vault/apps/seance_ui/roundtable.py` | create | `pick_speakers`, `_parse_mentions`, `hash_color`, `shared_history_for_persona`, palette constant, mode-set constant |
| `living_vault/apps/seance_ui/prompt.py` | modify | `build_system_prompt` accepts `teammate_paths` keyword; renders mode-block when set |
| `living_vault/apps/seance_ui/app.py` | modify | `summon` accepts `paths/mode`; `say()` branches on session.mode; new `roundtable_say()` orchestrator |
| `living_vault/apps/seance_ui/static/index.html` | modify | Multi-Select page picker, mode dropdown, per-persona bubbles with color, cost-disclaimer toast |
| `tests/test_db_migration.py` | modify | 3 tests for new schema migration |
| `tests/test_roundtable_speakers.py` | create | 9 tests for pick_speakers + mention parser + hash_color |
| `tests/test_seance_store.py` | modify | 4 tests for new store functions |
| `tests/test_roundtable_history.py` | create | 5 tests for shared_history_for_persona |
| `tests/test_seance_prompt.py` | modify | 3 tests for teammate_paths kw-arg |
| `tests/test_roundtable_app.py` | create | 10 tests for end-to-end roundtable through FastAPI |
| `tests/test_seance_app.py` | modify | 3 tests for backward-compat (single-mode summon, mode branching) |

Test files are flat under `tests/` per existing project layout.

**Test runner — CRITICAL:** Use `.venv/Scripts/python.exe -m pytest`, NOT bare `pytest`. The system `python` on this machine is 3.14 without project deps; tests will fail with `ModuleNotFoundError: No module named 'frontmatter'` against the wrong interpreter. This is documented in the project memory file `project_test_runner_uses_venv.md`.

---

## Task 1: Schema Migration — `seance_sessions.mode` + `seance_session_personas` table

**Files:**
- Modify: `living_vault/core/db.py`
- Modify: `tests/test_db_migration.py`

- [ ] **Step 1.1: Write failing tests for new schema**

In `tests/test_db_migration.py`, append:

```python
def test_initialize_adds_mode_to_legacy_seance_sessions(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    # arrange: legacy DB with seance_sessions but without mode
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE seance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_path TEXT NOT NULL,
            started_at TEXT NOT NULL
        );
    """)
    con.execute(
        "INSERT INTO seance_sessions (page_path, started_at) VALUES (?, ?)",
        ("legacy/page.md", "2026-05-08T00:00:00Z"),
    )
    con.commit()
    con.close()

    # act
    db_mod.initialize(db_path)

    # assert: column added, legacy row has default 'single'
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(seance_sessions)")}
    assert "mode" in cols
    row = con.execute(
        "SELECT page_path, mode FROM seance_sessions WHERE id = 1"
    ).fetchone()
    assert row[0] == "legacy/page.md"
    assert row[1] == "single"
    con.close()


def test_initialize_creates_seance_session_personas_table(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    db_mod.initialize(db_path)

    con = sqlite3.connect(str(db_path))
    # table exists
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "seance_session_personas" in tables

    # columns match spec
    cols = {r[1] for r in con.execute(
        "PRAGMA table_info(seance_session_personas)"
    )}
    assert cols == {"session_id", "persona_path", "color", "seat_idx"}

    # primary key on (session_id, persona_path)
    pk_cols = [
        r[1] for r in con.execute("PRAGMA table_info(seance_session_personas)")
        if r[5] > 0  # pk column index > 0 means part of PK
    ]
    assert set(pk_cols) == {"session_id", "persona_path"}
    con.close()


def test_phase_10b_migrations_idempotent(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call must not raise
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(seance_sessions)")}
    assert "mode" in cols
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "seance_session_personas" in tables
    con.close()
```

- [ ] **Step 1.2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_db_migration.py -v -k "mode_to_legacy or session_personas or phase_10b"`
Expected: 3× FAIL (column missing, table missing)

- [ ] **Step 1.3: Add migration code in `db.py`**

In `living_vault/core/db.py`, after the `_PHASE_10A_SEANCE_MESSAGES_COLUMNS` constant, add:

```python
# Phase-10b additive columns + new tables.
_PHASE_10B_SEANCE_SESSIONS_COLUMNS = [
    ("mode", "TEXT NOT NULL DEFAULT 'single'"),
]

_PHASE_10B_NEW_TABLES = """
CREATE TABLE IF NOT EXISTS seance_session_personas (
    session_id   INTEGER NOT NULL REFERENCES seance_sessions(id),
    persona_path TEXT NOT NULL,
    color        TEXT NOT NULL,
    seat_idx     INTEGER NOT NULL,
    PRIMARY KEY (session_id, persona_path)
);
CREATE INDEX IF NOT EXISTS idx_ssp_session ON seance_session_personas(session_id);
"""
```

In the `initialize()` function, after the existing Phase-10a loop (the one for `_PHASE_10A_SEANCE_MESSAGES_COLUMNS`), add:

```python
        # Phase-10b: new tables (idempotent via IF NOT EXISTS)
        con.executescript(_PHASE_10B_NEW_TABLES)
        # Phase-10b: additive columns on seance_sessions
        for col, sqltype in _PHASE_10B_SEANCE_SESSIONS_COLUMNS:
            if not _column_exists(con, "seance_sessions", col):
                con.execute(f"ALTER TABLE seance_sessions ADD COLUMN {col} {sqltype}")
```

The existing `con.commit()` at the end covers the new statements.

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_db_migration.py -v`
Expected: all migration tests PASS (4 phase-9 + 2 phase-10a + 3 phase-10b = 9 wait... actually 2+2+3=7 — confirm count by running)

- [ ] **Step 1.5: Run full suite for regression**

Run: `.venv/Scripts/python.exe -m pytest tests/ --tb=short 2>&1 | tail -3`
Expected: 156 + 3 = 159 passed.

- [ ] **Step 1.6: Commit**

```bash
git add living_vault/core/db.py tests/test_db_migration.py
git commit -m "living-vault | Phase-10b: schema migration mode + seance_session_personas (idempotent)"
```

---

## Task 2: store API extensions — `add_session_persona`, `get_session_personas`, `count_user_turns`, `new_session(mode=)`

**Files:**
- Modify: `living_vault/apps/seance_ui/store.py`
- Modify: `tests/test_seance_store.py`

- [ ] **Step 2.1: Write failing tests**

Append to `tests/test_seance_store.py`:

```python
def test_new_session_persists_mode(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md", mode="freeforall")
    # mode is persisted in seance_sessions
    import sqlite3
    con = sqlite3.connect(str(db_path))
    row = con.execute("SELECT mode FROM seance_sessions WHERE id = ?", (sid,)).fetchone()
    con.close()
    assert row[0] == "freeforall"


def test_new_session_default_mode_is_single(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md")  # no mode kwarg
    import sqlite3
    con = sqlite3.connect(str(db_path))
    row = con.execute("SELECT mode FROM seance_sessions WHERE id = ?", (sid,)).fetchone()
    con.close()
    assert row[0] == "single"


def test_add_and_get_session_personas(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/a.md", mode="roundrobin")
    store.add_session_persona(db_path, sid, "concepts/a.md", color="#7adfd5", seat_idx=0)
    store.add_session_persona(db_path, sid, "concepts/b.md", color="#a8e6cf", seat_idx=1)
    store.add_session_persona(db_path, sid, "concepts/c.md", color="#c9b3ff", seat_idx=2)

    rows = store.get_session_personas(db_path, sid)
    assert len(rows) == 3
    # ordered by seat_idx
    assert rows[0]["persona_path"] == "concepts/a.md"
    assert rows[0]["color"] == "#7adfd5"
    assert rows[0]["seat_idx"] == 0
    assert rows[1]["persona_path"] == "concepts/b.md"
    assert rows[2]["seat_idx"] == 2


def test_count_user_turns(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md")
    assert store.count_user_turns(db_path, sid) == 0
    store.add_message(db_path, sid, "user", "first")
    assert store.count_user_turns(db_path, sid) == 1
    store.add_message(db_path, sid, "assistant", "reply", persona_path="concepts/x.md")
    assert store.count_user_turns(db_path, sid) == 1  # assistants don't count
    store.add_message(db_path, sid, "user", "second")
    assert store.count_user_turns(db_path, sid) == 2
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seance_store.py -v -k "mode or session_personas or count_user_turns"`
Expected: 4× FAIL (`new_session` doesn't accept `mode`, `add_session_persona` undefined, etc.)

- [ ] **Step 2.3: Update `new_session` signature**

In `living_vault/apps/seance_ui/store.py`, replace the existing `new_session` function:

```python
def new_session(db_path: Path, page_path: str, mode: str = "single") -> int:
    con = db_mod.connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO seance_sessions(page_path, started_at, mode) VALUES (?, ?, ?)",
            (page_path, _now(), mode),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()
```

- [ ] **Step 2.4: Add `add_session_persona`, `get_session_personas`, `count_user_turns`, `get_session_mode`**

Append to the same file:

```python
def add_session_persona(
    db_path: Path,
    session_id: int,
    persona_path: str,
    *,
    color: str,
    seat_idx: int,
) -> None:
    con = db_mod.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seance_session_personas(session_id, persona_path, color, seat_idx) "
            "VALUES (?, ?, ?, ?)",
            (session_id, persona_path, color, seat_idx),
        )
        con.commit()
    finally:
        con.close()


def get_session_personas(db_path: Path, session_id: int) -> list[dict]:
    """Return personas in seat order. Each row: {persona_path, color, seat_idx}."""
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT persona_path, color, seat_idx FROM seance_session_personas "
            "WHERE session_id = ? ORDER BY seat_idx",
            (session_id,),
        ).fetchall()
        return [
            {"persona_path": r["persona_path"], "color": r["color"], "seat_idx": r["seat_idx"]}
            for r in rows
        ]
    finally:
        con.close()


def count_user_turns(db_path: Path, session_id: int) -> int:
    """How many user-role messages exist in this session."""
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM seance_messages "
            "WHERE session_id = ? AND role = 'user'",
            (session_id,),
        ).fetchone()
        return int(row[0])
    finally:
        con.close()


def get_session_mode(db_path: Path, session_id: int) -> str | None:
    """Return the mode of a session, or None if session not found."""
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT mode FROM seance_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return row["mode"] if row else None
    finally:
        con.close()
```

- [ ] **Step 2.5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seance_store.py -v`
Expected: all PASS (existing 10 + 4 new = 14)

- [ ] **Step 2.6: Run full suite for regression**

Run: `.venv/Scripts/python.exe -m pytest tests/ --tb=short 2>&1 | tail -3`
Expected: 159 + 4 = 163 passed.

- [ ] **Step 2.7: Commit**

```bash
git add living_vault/apps/seance_ui/store.py tests/test_seance_store.py
git commit -m "living-vault | Phase-10b: store extensions for mode + session_personas + turn counting"
```

---

## Task 3: roundtable.py — pick_speakers, _parse_mentions, hash_color

**Files:**
- Create: `living_vault/apps/seance_ui/roundtable.py`
- Create: `tests/test_roundtable_speakers.py`

- [ ] **Step 3.1: Write failing tests**

Create `tests/test_roundtable_speakers.py`:

```python
"""Phase-10b: pick_speakers + mention parser + hash_color tests."""
from __future__ import annotations
import pytest
from living_vault.apps.seance_ui.roundtable import (
    pick_speakers,
    _parse_mentions,
    hash_color,
    PALETTE,
)


def _personas() -> list[dict]:
    return [
        {"persona_path": "concepts/alpha.md", "color": "#aaa", "seat_idx": 0},
        {"persona_path": "concepts/beta.md", "color": "#bbb", "seat_idx": 1},
        {"persona_path": "concepts/gamma.md", "color": "#ccc", "seat_idx": 2},
    ]


def test_roundrobin_rotates_by_turn_idx():
    p = _personas()
    assert pick_speakers(mode="roundrobin", user_text="x", personas=p, turn_idx=0) == [p[0]]
    assert pick_speakers(mode="roundrobin", user_text="x", personas=p, turn_idx=1) == [p[1]]
    assert pick_speakers(mode="roundrobin", user_text="x", personas=p, turn_idx=2) == [p[2]]
    assert pick_speakers(mode="roundrobin", user_text="x", personas=p, turn_idx=3) == [p[0]]  # wrap


def test_freeforall_returns_all_in_seat_order():
    p = _personas()
    out = pick_speakers(mode="freeforall", user_text="x", personas=p, turn_idx=42)
    assert out == p  # turn_idx irrelevant for freeforall


def test_moderator_with_mention_picks_matched_persona():
    p = _personas()
    out = pick_speakers(mode="moderator", user_text="@alpha what?", personas=p, turn_idx=0)
    assert out == [p[0]]


def test_moderator_with_multiple_mentions_preserves_order():
    p = _personas()
    out = pick_speakers(mode="moderator", user_text="@gamma and @alpha", personas=p, turn_idx=0)
    # order: gamma first (mentioned first), then alpha
    assert out == [p[2], p[0]]


def test_moderator_without_mention_falls_back_to_roundrobin():
    p = _personas()
    out0 = pick_speakers(mode="moderator", user_text="was meint ihr?", personas=p, turn_idx=0)
    out1 = pick_speakers(mode="moderator", user_text="was meint ihr?", personas=p, turn_idx=1)
    assert out0 == [p[0]]
    assert out1 == [p[1]]


def test_moderator_with_unknown_mention_falls_back_to_roundrobin():
    p = _personas()
    out = pick_speakers(mode="moderator", user_text="@unknown_persona ", personas=p, turn_idx=0)
    assert out == [p[0]]  # fallback to round-robin


def test_parse_mentions_is_case_insensitive():
    p = _personas()
    out = _parse_mentions("@ALPHA tell me", p)
    assert out == [p[0]]


def test_parse_mentions_dedup():
    p = _personas()
    out = _parse_mentions("@alpha and @alpha again", p)
    assert out == [p[0]]


def test_hash_color_is_deterministic_and_in_palette():
    c1 = hash_color("concepts/alpha.md")
    c2 = hash_color("concepts/alpha.md")
    c3 = hash_color("concepts/beta.md")
    assert c1 == c2  # determinism
    assert c1 in PALETTE
    assert c3 in PALETTE
    # colors may or may not differ depending on path-bucket — both are fine
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_roundtable_speakers.py -v`
Expected: 9× FAIL with `ModuleNotFoundError: No module named 'living_vault.apps.seance_ui.roundtable'`

- [ ] **Step 3.3: Create the roundtable module**

Create `living_vault/apps/seance_ui/roundtable.py`:

```python
"""Phase-10b: roundtable orchestration helpers.

This module owns:
  - pick_speakers: mode-logic that returns which personas speak this turn.
  - _parse_mentions: @-mention parsing for moderator mode.
  - hash_color: deterministic persona color from path.
  - shared_history_for_persona: render the shared conversation from one
    persona's view, with [other says]: prefix on teammate replies.

It does NOT call the LLM, write to DB, or know about FastAPI. It's pure
functions over data structures (lists/dicts) so it can be tested cheaply.
"""
from __future__ import annotations
import re
from pathlib import Path


# 8-color palette tuned for the dark séance UI theme.
PALETTE: list[str] = [
    "#7adfd5",   # cyan
    "#a8e6cf",   # mint
    "#c9b3ff",   # lavender
    "#ffd3a5",   # peach
    "#fda4af",   # rose
    "#fde68a",   # gold
    "#bbf7d0",   # sage
    "#a5d8ff",   # sky
]


VALID_MODES = frozenset({"single", "roundrobin", "moderator", "freeforall"})


def hash_color(persona_path: str) -> str:
    """Deterministic color from path. Same path always gets same color
    across processes (Python's built-in hash() is randomized by default
    since 3.3, so we use a stable cheap alternative)."""
    h = sum(ord(c) for c in persona_path)
    return PALETTE[h % len(PALETTE)]


def _parse_mentions(text: str, personas: list[dict]) -> list[dict]:
    """Find @{stem} mentions in text and return matching personas in
    order of first appearance. Case-insensitive, dedup."""
    mentioned: list[dict] = []
    seen_paths: set[str] = set()
    text_lower = text.lower()
    # We scan personas in the order they're given, but resolve to mention
    # position so that @gamma before @alpha returns [gamma, alpha].
    positions: list[tuple[int, dict]] = []
    for p in personas:
        stem = Path(p["persona_path"]).stem.lower()
        # match @stem with word boundary on the right
        for m in re.finditer(rf"@{re.escape(stem)}\b", text_lower):
            positions.append((m.start(), p))
            break  # first occurrence per persona is enough for dedup
    positions.sort(key=lambda t: t[0])
    for _, p in positions:
        if p["persona_path"] not in seen_paths:
            mentioned.append(p)
            seen_paths.add(p["persona_path"])
    return mentioned


def pick_speakers(
    *,
    mode: str,
    user_text: str,
    personas: list[dict],
    turn_idx: int,
) -> list[dict]:
    """Decide which personas speak this turn given the mode.

    Args:
      mode: one of 'roundrobin', 'moderator', 'freeforall'
            ('single' is handled outside this function — say() never
            calls into roundtable_say for single-mode sessions.)
      user_text: the latest user message (used by moderator mode).
      personas: ordered by seat_idx, ascending.
      turn_idx: 0-indexed count of user turns so far in this session.

    Returns: ordered list of personas that should speak this turn.
    """
    if not personas:
        return []

    if mode == "freeforall":
        return list(personas)

    if mode == "moderator":
        mentioned = _parse_mentions(user_text, personas)
        if mentioned:
            return mentioned
        # fall through to round-robin behavior on no-mention
        return [personas[turn_idx % len(personas)]]

    if mode == "roundrobin":
        return [personas[turn_idx % len(personas)]]

    raise ValueError(f"unknown mode: {mode}")
```

- [ ] **Step 3.4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_roundtable_speakers.py -v`
Expected: 9× PASS

- [ ] **Step 3.5: Run full suite for regression**

Run: `.venv/Scripts/python.exe -m pytest tests/ --tb=short 2>&1 | tail -3`
Expected: 163 + 9 = 172 passed.

- [ ] **Step 3.6: Commit**

```bash
git add living_vault/apps/seance_ui/roundtable.py tests/test_roundtable_speakers.py
git commit -m "living-vault | Phase-10b: roundtable.pick_speakers + mention parser + hash_color"
```

---

## Task 4: shared_history_for_persona — labeled-user wrapping

**Files:**
- Modify: `living_vault/apps/seance_ui/roundtable.py` (append `shared_history_for_persona`)
- Create: `tests/test_roundtable_history.py`

- [ ] **Step 4.1: Write failing tests**

Create `tests/test_roundtable_history.py`:

```python
"""Phase-10b: shared_history_for_persona tests."""
from __future__ import annotations
from pathlib import Path

from living_vault.core import db as db_mod
from living_vault.apps.seance_ui import store
from living_vault.apps.seance_ui.roundtable import shared_history_for_persona


def test_history_wraps_other_persona_replies_as_labeled_user(db_path: Path):
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/a.md", mode="freeforall")
    store.add_message(db_path, sid, "user", "hello all")
    store.add_message(db_path, sid, "assistant", "I am A", persona_path="concepts/a.md")
    store.add_message(db_path, sid, "assistant", "I am B", persona_path="concepts/b.md")

    # From A's view: own assistant stays assistant, B's becomes labeled-user
    h_a = shared_history_for_persona(db_path, sid, "concepts/a.md")
    assert h_a == [
        ("user", "hello all"),
        ("assistant", "I am A"),
        ("user", "[b says]: I am B"),
    ]

    # From B's view: opposite
    h_b = shared_history_for_persona(db_path, sid, "concepts/b.md")
    assert h_b == [
        ("user", "hello all"),
        ("user", "[a says]: I am A"),
        ("assistant", "I am B"),
    ]


def test_history_passes_user_messages_through(db_path: Path):
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/a.md", mode="freeforall")
    store.add_message(db_path, sid, "user", "first")
    store.add_message(db_path, sid, "user", "second")

    h = shared_history_for_persona(db_path, sid, "concepts/a.md")
    assert h == [("user", "first"), ("user", "second")]


def test_history_filters_tool_use_rows(db_path: Path):
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/a.md", mode="freeforall")
    store.add_message(db_path, sid, "user", "u1")
    store.add_tool_event(
        db_path, sid,
        persona_path="concepts/a.md",
        tool_name="consult_neighbor",
        tool_args={"neighbor_path": "concepts/b.md"},
        tool_result_summary={"chars": 100},
    )
    store.add_message(db_path, sid, "assistant", "a1", persona_path="concepts/a.md")

    h = shared_history_for_persona(db_path, sid, "concepts/a.md")
    # tool_use is filtered out, regardless of which persona's view
    assert h == [("user", "u1"), ("assistant", "a1")]


def test_history_empty_session_returns_empty_list(db_path: Path):
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/a.md", mode="freeforall")
    assert shared_history_for_persona(db_path, sid, "concepts/a.md") == []


def test_history_handles_three_speakers_interleaved(db_path: Path):
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/a.md", mode="freeforall")
    store.add_message(db_path, sid, "user", "round 1")
    store.add_message(db_path, sid, "assistant", "A1", persona_path="concepts/a.md")
    store.add_message(db_path, sid, "assistant", "B1", persona_path="concepts/b.md")
    store.add_message(db_path, sid, "assistant", "C1", persona_path="concepts/c.md")
    store.add_message(db_path, sid, "user", "round 2")
    store.add_message(db_path, sid, "assistant", "A2", persona_path="concepts/a.md")

    # From C's view
    h_c = shared_history_for_persona(db_path, sid, "concepts/c.md")
    assert h_c == [
        ("user", "round 1"),
        ("user", "[a says]: A1"),
        ("user", "[b says]: B1"),
        ("assistant", "C1"),
        ("user", "round 2"),
        ("user", "[a says]: A2"),
    ]
```

- [ ] **Step 4.2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_roundtable_history.py -v`
Expected: 5× FAIL with `ImportError: cannot import name 'shared_history_for_persona'`

- [ ] **Step 4.3: Add shared_history_for_persona to roundtable.py**

Append to `living_vault/apps/seance_ui/roundtable.py`:

```python
def shared_history_for_persona(
    db_path,
    session_id: int,
    persona_path: str,
) -> list[tuple[str, str]]:
    """Build a persona-specific view of the shared roundtable history.

    Anthropic's API only knows 'user' and 'assistant' roles. We simulate
    'third party persona' by wrapping other personas' replies as labeled
    user-content (e.g. '[alpha says]: ...'), so persona-X can read what
    teammates said as if it were external user context.

    Filtering rules:
      - role == 'user' → ('user', text) unchanged
      - role == 'assistant' AND persona_path == this → ('assistant', text)
      - role == 'assistant' AND other persona → ('user', '[stem says]: text')
      - role == 'tool_use' → SKIPPED (Phase-10a asymmetry preserved)
    """
    from living_vault.core import db as db_mod
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT role, content, persona_path FROM seance_messages "
            "WHERE session_id = ? AND role IN ('user', 'assistant') "
            "ORDER BY id",
            (session_id,),
        ).fetchall()
        out: list[tuple[str, str]] = []
        for r in rows:
            if r["role"] == "user":
                out.append(("user", r["content"]))
                continue
            # role == 'assistant'
            if r["persona_path"] == persona_path:
                out.append(("assistant", r["content"]))
            else:
                other_stem = Path(r["persona_path"] or "").stem
                out.append(("user", f"[{other_stem} says]: {r['content']}"))
        return out
    finally:
        con.close()
```

- [ ] **Step 4.4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_roundtable_history.py -v`
Expected: 5× PASS

- [ ] **Step 4.5: Run full suite for regression**

Run: `.venv/Scripts/python.exe -m pytest tests/ --tb=short 2>&1 | tail -3`
Expected: 172 + 5 = 177 passed.

- [ ] **Step 4.6: Commit**

```bash
git add living_vault/apps/seance_ui/roundtable.py tests/test_roundtable_history.py
git commit -m "living-vault | Phase-10b: shared_history_for_persona with labeled-user wrapping"
```

---

## Task 5: build_system_prompt — teammate_paths kw-arg

**Files:**
- Modify: `living_vault/apps/seance_ui/prompt.py`
- Modify: `tests/test_seance_prompt.py`

- [ ] **Step 5.1: Write failing tests**

Append to `tests/test_seance_prompt.py`:

```python
def test_system_prompt_includes_teammate_paths_when_provided():
    """Phase-10b: when in a roundtable, the persona must know who else is at
    the table so it can decide to consult them via consult_neighbor."""
    p = _persona_full()
    out = build_system_prompt(
        p,
        neighbor_titles=["x", "y"],
        neighbor_paths=["concepts/x.md", "concepts/y.md"],
        teammate_paths=["concepts/teammate-a.md", "concepts/teammate-b.md"],
    )
    assert "concepts/teammate-a.md" in out
    assert "concepts/teammate-b.md" in out
    # the prompt mentions the roundtable context
    assert "Tisch" in out or "teammates" in out.lower() or "roundtable" in out.lower()


def test_system_prompt_no_teammate_block_when_paths_empty():
    p = _persona_full()
    out = build_system_prompt(
        p,
        neighbor_titles=["x"],
        neighbor_paths=["concepts/x.md"],
        teammate_paths=[],
    )
    # empty list: no teammate-block content
    assert "Tisch" not in out and "teammates" not in out.lower() and "roundtable" not in out.lower()


def test_system_prompt_teammate_paths_optional_for_phase10a_compat():
    """Phase-10a callers that only pass neighbor_paths must still work."""
    p = _persona_full()
    out = build_system_prompt(
        p,
        neighbor_titles=["x"],
        neighbor_paths=["concepts/x.md"],
    )
    # no teammate context, no roundtable mention
    assert "concepts/x.md" in out
    assert "Tisch" not in out
```

- [ ] **Step 5.2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seance_prompt.py -v -k "teammate"`
Expected: 3× FAIL (`teammate_paths` keyword unknown)

- [ ] **Step 5.3: Update build_system_prompt**

In `living_vault/apps/seance_ui/prompt.py`, locate the existing `_TEMPLATE` constant (it ends with `{tool_use_block}`). Just BEFORE `_TOOL_USE_BLOCK` declaration, add:

```python
_TEAMMATE_BLOCK = """
# Andere Personas am Tisch
Du sitzt aktuell mit weiteren Personas an einem Roundtable. Du kannst sie
über `consult_neighbor` direkt befragen — ihre Pfade sind in der Liste
oben mit aufgeführt. Die Teammates an diesem Tisch sind:
{teammate_lines}
Antworte so, dass dein Beitrag zum Gespräch passt: greife auf, was sie
gesagt haben (siehst du als '[name says]: ...' in der History), korrigiere
oder ergänze, aus deiner Perspektive.
"""
```

Then replace the `build_system_prompt` function with:

```python
def build_system_prompt(
    persona: dict,
    neighbor_titles: list[str],
    neighbor_paths: list[str] | None = None,
    teammate_paths: list[str] | None = None,
) -> str:
    voice_block = build_voice_block(persona)
    themes = ", ".join(persona.get("themes", [])) or "(none)"
    if neighbor_paths is not None:
        neighbors = _format_neighbors_with_paths(neighbor_titles, neighbor_paths)
        tool_use_block = _TOOL_USE_BLOCK
    else:
        neighbors = ", ".join(neighbor_titles) or "(none)"
        tool_use_block = ""

    if teammate_paths:
        teammate_lines = "\n".join(f"  - `{p}`" for p in teammate_paths)
        teammate_block = _TEAMMATE_BLOCK.format(teammate_lines=teammate_lines)
    else:
        teammate_block = ""

    return _TEMPLATE.format(
        path=persona["path"],
        title=persona["title"],
        era_marker=persona.get("era_marker") or "unknown date",
        themes=themes,
        neighbors=neighbors,
        voice_block=voice_block,
        body_excerpt=persona.get("body_excerpt", "") or "(empty body)",
        tool_use_block=tool_use_block + teammate_block,
    )
```

- [ ] **Step 5.4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seance_prompt.py -v`
Expected: all PASS (existing 8 + 3 new = 11)

- [ ] **Step 5.5: Run full suite for regression**

Run: `.venv/Scripts/python.exe -m pytest tests/ --tb=short 2>&1 | tail -3`
Expected: 177 + 3 = 180 passed.

- [ ] **Step 5.6: Commit**

```bash
git add living_vault/apps/seance_ui/prompt.py tests/test_seance_prompt.py
git commit -m "living-vault | Phase-10b: build_system_prompt accepts teammate_paths for roundtable context"
```

---

## Task 6: summon endpoint — multi-page + mode validation

**Files:**
- Modify: `living_vault/apps/seance_ui/app.py`
- Modify: `tests/test_seance_app.py`

- [ ] **Step 6.1: Write failing tests for the new summon shape**

Append to `tests/test_seance_app.py`:

```python
def test_summon_with_paths_and_mode_creates_session_personas(vault_copy, db_path, monkeypatch):
    """Phase-10b: summon with paths=[...]+mode= creates seance_session_personas rows."""
    from living_vault.core import db as db_mod
    from living_vault.core.indexer import index_vault
    from living_vault.apps.seance_ui import store

    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "roundrobin",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    sid = body["session_id"]
    assert body["mode"] == "roundrobin"
    assert len(body["personas"]) == 2
    assert body["personas"][0]["persona_path"] == "concepts/note-a.md"
    assert body["personas"][1]["seat_idx"] == 1

    # personas persisted in DB
    rows = store.get_session_personas(db_path, sid)
    assert len(rows) == 2

    # mode persisted on session
    assert store.get_session_mode(db_path, sid) == "roundrobin"


def test_summon_with_legacy_path_keyword_still_works(vault_copy, db_path, monkeypatch):
    """Phase-10a single-page summon shape must still work after Phase-10b extends."""
    from living_vault.core import db as db_mod
    from living_vault.core.indexer import index_vault

    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"path": "concepts/note-a.md"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "session_id" in body
    # response shape contains persona for backward compat
    assert "persona" in body


def test_summon_rejects_too_many_paths(vault_copy, db_path, monkeypatch):
    from living_vault.core import db as db_mod
    from living_vault.core.indexer import index_vault
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    too_many = ["concepts/note-a.md"] * 9  # 9 > 8
    r = c.post("/api/summon", json={"paths": too_many, "mode": "freeforall"})
    assert r.status_code == 413


def test_summon_rejects_unknown_mode(vault_copy, db_path, monkeypatch):
    from living_vault.core import db as db_mod
    from living_vault.core.indexer import index_vault
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={"paths": ["concepts/note-a.md"], "mode": "wibble"})
    assert r.status_code == 400


def test_summon_with_unknown_path_returns_404(vault_copy, db_path, monkeypatch):
    from living_vault.core import db as db_mod
    from living_vault.core.indexer import index_vault
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    c = _client(vault_copy, db_path, monkeypatch)
    r = c.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/does-not-exist.md"],
        "mode": "roundrobin",
    })
    assert r.status_code == 404
```

- [ ] **Step 6.2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seance_app.py -v -k "summon_with or summon_rejects or summon_with_unknown"`
Expected: 5× FAIL (request body shape mismatch)

- [ ] **Step 6.3: Update summon endpoint**

In `living_vault/apps/seance_ui/app.py`, find the existing `class SummonReq(BaseModel)` and the `summon()` endpoint. Replace the request model with:

```python
class SummonReq(BaseModel):
    # Phase-1 single-path shape (backward-compat):
    path: str | None = None
    # Phase-10b multi-path shape:
    paths: list[str] | None = None
    mode: str = "single"
```

Then add this import at the top of the file (after the existing `from living_vault.apps.seance_ui.neighbors import (...)` block):

```python
from living_vault.apps.seance_ui.roundtable import VALID_MODES, hash_color
```

Replace the existing `summon()` endpoint with:

```python
@app.post("/api/summon")
def summon(req: SummonReq) -> dict:
    # Determine path list: legacy `path` or new `paths`
    if req.paths is not None:
        paths = list(req.paths)
    elif req.path is not None:
        paths = [req.path]
    else:
        raise HTTPException(status_code=400, detail="must provide 'path' or 'paths'")

    # Dedup while preserving order
    seen: set[str] = set()
    paths_dedup: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            paths_dedup.append(p)
    paths = paths_dedup

    if len(paths) == 0:
        raise HTTPException(status_code=400, detail="at least one page required")
    if len(paths) > 8:
        raise HTTPException(status_code=413, detail="max 8 personas per roundtable")

    # Validate mode
    if req.mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"unknown mode: {req.mode}")
    # Single page implies single mode
    mode = "single" if len(paths) == 1 and req.mode == "single" else req.mode
    # Multi-page with mode=single is forced to roundrobin (UX safeguard)
    if len(paths) > 1 and mode == "single":
        mode = "roundrobin"

    # Validate each page exists, build personas
    personas_out: list[dict] = []
    for p in paths:
        persona = build_persona(_vault_root(), _db_path(), p)
        if persona is None:
            raise HTTPException(status_code=404, detail=f"page not found: {p}")

    # Create session — page_path is the first path for legacy compatibility
    sid = store.new_session(_db_path(), page_path=paths[0], mode=mode)

    # Add personas with seat_idx + color
    for i, p in enumerate(paths):
        color = hash_color(p)
        store.add_session_persona(_db_path(), sid, p, color=color, seat_idx=i)
        personas_out.append({"persona_path": p, "color": color, "seat_idx": i})

    response: dict = {"session_id": sid, "mode": mode, "personas": personas_out}
    # Backward-compat: also include first persona dict under 'persona' key
    first_persona = build_persona(_vault_root(), _db_path(), paths[0])
    if first_persona is not None:
        response["persona"] = first_persona
    return response
```

- [ ] **Step 6.4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seance_app.py -v`
Expected: all PASS (existing + 5 new)

- [ ] **Step 6.5: Run full suite for regression**

Run: `.venv/Scripts/python.exe -m pytest tests/ --tb=short 2>&1 | tail -3`
Expected: 180 + 5 = 185 passed.

- [ ] **Step 6.6: Commit**

```bash
git add living_vault/apps/seance_ui/app.py tests/test_seance_app.py
git commit -m "living-vault | Phase-10b: summon endpoint accepts paths[] + mode, creates session_personas"
```

---

## Task 7: roundtable_say() orchestrator + say() branching

**Files:**
- Modify: `living_vault/apps/seance_ui/app.py`
- Create: `tests/test_roundtable_app.py`

- [ ] **Step 7.1: Write failing end-to-end tests**

Create `tests/test_roundtable_app.py`:

```python
"""Phase-10b: end-to-end roundtable through FastAPI."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi.testclient import TestClient

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.llm import FakeLLMWithTools
from living_vault.apps.seance_ui import store


def _client_with_iter_llms(vault: Path, db: Path, monkeypatch, scripts: list[list[dict]]):
    """Install N FakeLLMWithTools so each call to get_llm() yields the next one.
    Use this when roundtable will call get_llm() once per persona."""
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    fakes = [FakeLLMWithTools(s) for s in scripts]
    fakes_iter = iter(fakes)
    monkeypatch.setattr(app_mod, "get_llm", lambda: next(fakes_iter))
    return TestClient(app_mod.app), fakes


def test_roundtable_summon_freeforall_three_personas(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [
        [{"type": "text", "text": "I am note-a"}],
        [{"type": "text", "text": "I am note-b"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    r = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    })
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]

    r2 = client.post("/api/say", json={"session_id": sid, "text": "hello all"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert "replies" in body
    assert len(body["replies"]) == 2
    assert body["replies"][0]["persona_path"] == "concepts/note-a.md"
    assert body["replies"][0]["text"] == "I am note-a"
    assert body["replies"][1]["persona_path"] == "concepts/note-b.md"
    assert body["replies"][1]["text"] == "I am note-b"


def test_roundtable_persists_with_persona_path_per_reply(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [
        [{"type": "text", "text": "A"}],
        [{"type": "text", "text": "B"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    client.post("/api/say", json={"session_id": sid, "text": "hi"})

    detail = store.get_session_detail(db_path, sid)
    assistants = [m for m in detail["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 2
    assert assistants[0]["persona_path"] == "concepts/note-a.md"
    assert assistants[0]["content"] == "A"
    assert assistants[1]["persona_path"] == "concepts/note-b.md"


def test_roundrobin_alternates_speakers_across_turns(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # 3 turns × 1 speaker each = 3 fakes
    scripts = [
        [{"type": "text", "text": "A1"}],
        [{"type": "text", "text": "B1"}],
        [{"type": "text", "text": "A2"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "roundrobin",
    }).json()["session_id"]

    r1 = client.post("/api/say", json={"session_id": sid, "text": "q1"})
    r2 = client.post("/api/say", json={"session_id": sid, "text": "q2"})
    r3 = client.post("/api/say", json={"session_id": sid, "text": "q3"})

    assert r1.json()["replies"][0]["persona_path"] == "concepts/note-a.md"
    assert r2.json()["replies"][0]["persona_path"] == "concepts/note-b.md"
    assert r3.json()["replies"][0]["persona_path"] == "concepts/note-a.md"  # wrap


def test_moderator_at_mention_picks_one_persona(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [[{"type": "text", "text": "A says hi"}]]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "moderator",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "@note-a what?"})
    body = r.json()
    assert len(body["replies"]) == 1
    assert body["replies"][0]["persona_path"] == "concepts/note-a.md"


def test_moderator_no_mention_falls_back_to_one_speaker(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [[{"type": "text", "text": "First persona answer"}]]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "moderator",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "no mention here"})
    body = r.json()
    assert len(body["replies"]) == 1  # round-robin fallback picks 1


def test_freeforall_personas_get_color_in_response(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [
        [{"type": "text", "text": "A"}],
        [{"type": "text", "text": "B"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "hi"})
    body = r.json()
    assert body["replies"][0]["color"].startswith("#")
    assert body["replies"][1]["color"].startswith("#")


def test_say_single_mode_still_works_after_phase10b(vault_copy, db_path, monkeypatch):
    """Phase-10a single-mode path is still served correctly."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [[{"type": "text", "text": "I am the page."}]]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "who are you?"})
    assert r.status_code == 200
    body = r.json()
    # Phase-10a response shape: {reply, tool_events}
    assert "reply" in body
    assert body["reply"] == "I am the page."
    assert "tool_events" in body


def test_cross_persona_consult_is_allowed(vault_copy, db_path, monkeypatch):
    """A roundtable persona can consult_neighbor on a teammate's path even if
    the teammate isn't a graph neighbor."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # Persona A consults B (teammate, not necessarily wiki-neighbor), then text.
    scripts = [
        [
            {"type": "tool_use", "name": "consult_neighbor",
             "input": {"neighbor_path": "concepts/note-b.md"}},
            {"type": "text", "text": "I read B's content"},
        ],
        [{"type": "text", "text": "B replies"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "react"})
    assert r.status_code == 200, r.text
    body = r.json()
    # consult succeeded — at least one tool_event captured for A
    assert len(body["tool_events"]) >= 1
    # the consulted neighbor was B (teammate)
    consult_events = [e for e in body["tool_events"] if e["tool_name"] == "consult_neighbor"]
    assert any(e["tool_args"]["neighbor_path"] == "concepts/note-b.md" for e in consult_events)


def test_skip_broken_persona_other_two_still_reply(vault_copy, db_path, monkeypatch):
    """If one of three personas' build_persona fails, the other two must still answer."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # Two replies for the two surviving personas; the broken one is skipped via persona_skipped event.
    scripts = [
        [{"type": "text", "text": "A reply"}],
        [{"type": "text", "text": "C reply"}],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    # Summon with a non-existent path mid-list
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    # Manually delete note-b from the pages table to simulate page-gone-since-summon
    import sqlite3
    con = sqlite3.connect(str(db_path))
    con.execute("DELETE FROM pages WHERE path = ?", ("concepts/note-b.md",))
    con.commit()
    con.close()

    r = client.post("/api/say", json={"session_id": sid, "text": "go"})
    assert r.status_code == 200, r.text
    body = r.json()
    # only A replied; B was skipped
    replies_paths = [reply["persona_path"] for reply in body["replies"]]
    assert "concepts/note-a.md" in replies_paths
    assert "concepts/note-b.md" not in replies_paths
    # tool_events contains a persona_skipped for B
    skipped = [e for e in body["tool_events"] if e["tool_name"] == "persona_skipped"]
    assert len(skipped) == 1
    assert skipped[0]["tool_args"]["persona_path"] == "concepts/note-b.md"


def test_roundtable_response_has_tool_events_aggregated(vault_copy, db_path, monkeypatch):
    """tool_events from all personas are merged into one response list."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    scripts = [
        [
            {"type": "tool_use", "name": "consult_neighbor",
             "input": {"neighbor_path": "concepts/note-b.md"}},
            {"type": "text", "text": "A done"},
        ],
        [
            {"type": "tool_use", "name": "consult_neighbor",
             "input": {"neighbor_path": "concepts/note-a.md"}},
            {"type": "text", "text": "B done"},
        ],
    ]
    client, _ = _client_with_iter_llms(vault_copy, db_path, monkeypatch, scripts)
    sid = client.post("/api/summon", json={
        "paths": ["concepts/note-a.md", "concepts/note-b.md"],
        "mode": "freeforall",
    }).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "go"})
    body = r.json()
    consult_events = [e for e in body["tool_events"] if e["tool_name"] == "consult_neighbor"]
    assert len(consult_events) == 2  # one from A, one from B
```

- [ ] **Step 7.2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_roundtable_app.py -v`
Expected: 10× FAIL (no roundtable_say wired up)

- [ ] **Step 7.3: Add `roundtable_say()` and `say()` branch**

In `living_vault/apps/seance_ui/app.py`, add the import block at the top (after the existing imports):

```python
from living_vault.apps.seance_ui.roundtable import (
    pick_speakers,
    shared_history_for_persona,
)
```

Find the existing `say()` function. **At its very beginning** (right after the `if len(req.text) > _MAX_USER_TEXT_CHARS` check, before `history = store.get_history(...)`), insert this branch:

```python
    # Phase-10b: branch on session.mode. Single-mode keeps the existing path.
    mode = store.get_session_mode(_db_path(), req.session_id)
    if mode is None:
        raise HTTPException(status_code=404, detail="session not found")
    if mode != "single":
        return roundtable_say(req)
```

Then, **after** the existing `say()` function definition, add:

```python
def roundtable_say(req: SayReq) -> dict:
    """Orchestrate a multi-persona turn for roundrobin/moderator/freeforall sessions."""
    personas = store.get_session_personas(_db_path(), req.session_id)
    if not personas:
        raise HTTPException(status_code=410, detail="session has no participants")

    mode = store.get_session_mode(_db_path(), req.session_id)
    turn_idx = store.count_user_turns(_db_path(), req.session_id)  # 0-indexed for THIS upcoming turn

    # Persist user turn first so it's in DB even if any LLM call fails.
    store.add_message(_db_path(), req.session_id, "user", req.text, persona_path=None)

    speakers = pick_speakers(
        mode=mode,
        user_text=req.text,
        personas=personas,
        turn_idx=turn_idx,
    )

    replies: list[dict] = []
    tool_events: list[dict] = []

    persona_paths = {p["persona_path"] for p in personas}

    for speaker in speakers:
        speaker_path = speaker["persona_path"]

        # Build the persona; if it's gone, log a persona_skipped event and continue.
        persona_data = build_persona(_vault_root(), _db_path(), speaker_path)
        if persona_data is None:
            tool_events.append({
                "tool_name": "persona_skipped",
                "tool_args": {"persona_path": speaker_path},
                "tool_result_summary": {"error": "page gone since summon"},
            })
            continue

        # Build the system prompt with neighbors AND teammates
        con = db_mod.connect(_db_path())
        try:
            nbs = graph_neighbors(con, speaker_path)
        finally:
            con.close()
        teammate_paths = [p for p in persona_paths if p != speaker_path]

        system = build_system_prompt(
            persona_data,
            neighbor_titles=[Path(n).stem for n in nbs],
            neighbor_paths=list(nbs),
            teammate_paths=teammate_paths,
        )

        # Allowlist: graph neighbors + teammates (cross-persona consult allowed)
        allowlist = set(nbs) | set(teammate_paths)
        raw_handler = make_consult_neighbor_handler(
            vault_root=_vault_root(),
            db_path=_db_path(),
            session_id=req.session_id,
            persona_path=speaker_path,
            allowlist=allowlist,
        )

        speaker_tool_events: list[dict] = []
        def handler_with_capture(name: str, args: dict, _events=speaker_tool_events, _h=raw_handler):
            result = _h(name, args)
            if isinstance(result, dict) and result.get("is_error"):
                _events.append({
                    "tool_name": name,
                    "tool_args": args,
                    "tool_result_summary": {"error": result["content"]},
                })
            else:
                _events.append({
                    "tool_name": name,
                    "tool_args": args,
                    "tool_result_summary": {"chars": len(result) if isinstance(result, str) else 0},
                })
            return result

        # Build per-speaker history (shared but persona-perspective rendering)
        history_for_llm = shared_history_for_persona(_db_path(), req.session_id, speaker_path)
        history_for_llm = _cap_history(history_for_llm)

        llm = get_llm()
        if hasattr(llm, "respond_with_tools"):
            reply = llm.respond_with_tools(
                system=system,
                history=history_for_llm,
                tools=[CONSULT_NEIGHBOR_TOOL_DEF],
                tool_handler=handler_with_capture,
                max_iterations=5,
            )
        else:
            reply = llm.respond(system=system, history=history_for_llm)

        store.add_message(
            _db_path(), req.session_id, "assistant", reply,
            persona_path=speaker_path,
        )
        replies.append({
            "persona_path": speaker_path,
            "text": reply,
            "color": speaker["color"],
            "seat_idx": speaker["seat_idx"],
        })
        tool_events.extend(speaker_tool_events)

    return {"replies": replies, "tool_events": tool_events}
```

- [ ] **Step 7.4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_roundtable_app.py tests/test_seance_app.py tests/test_seance_say_with_tools.py -v`
Expected: all PASS — 10 new + existing 18+6 = 34 total in these files.

- [ ] **Step 7.5: Run full suite for regression**

Run: `.venv/Scripts/python.exe -m pytest tests/ --tb=short 2>&1 | tail -3`
Expected: 185 + 10 = 195 passed.

- [ ] **Step 7.6: Commit**

```bash
git add living_vault/apps/seance_ui/app.py tests/test_roundtable_app.py
git commit -m "living-vault | Phase-10b: roundtable_say orchestrator + say() mode-branch + 10 e2e tests"
```

---

## Task 8: UI — Multi-Select page picker, mode dropdown, persona-bubbles

**Files:**
- Modify: `living_vault/apps/seance_ui/static/index.html`

This task has no automated tests — it's vanilla JS in a single file. Verify manually after the live-smoke step.

- [ ] **Step 8.1: Add CSS for mode-controls and persona bubbles**

In `living_vault/apps/seance_ui/static/index.html`, inside the existing `<style>` block, after the existing `.toolEvent.budgetWarning` rule, add:

```css
    /* Phase-10b: multi-select page picker + mode dropdown */
    .pageItem.selected{background:#234;border-left:3px solid #4a8;}
    #modeRow{padding:8px;border-top:1px solid #234;display:none;}
    #modeRow.visible{display:flex;gap:8px;align-items:center;font-size:11px;}
    #modeRow select{background:#13202c;color:#cfe;border:1px solid #234;padding:4px;font-family:inherit;font-size:11px;}
    #summonBtn{background:#1a3a1c;color:#cfe;border:1px solid #4a8;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:11px;}
    #summonBtn:disabled{opacity:.4;cursor:not-allowed;}
    /* Phase-10b: persona-labeled assistant bubbles */
    .msg.persona{background:#1a2e1c;border-left:3px solid #4a8;padding-left:10px;}
    .personaLabel{font-size:10px;font-weight:bold;opacity:.85;margin-bottom:4px;}
```

- [ ] **Step 8.2: Add multi-select state + mode dropdown markup**

In the same file, find the `<div id="list">` element. Right after the closing `</div>` for `#side`, add a new mode-row before the closing `</div>` of `#side`. Replace:

```html
    <div id="list"><div style="opacity:.6;font-size:11px;">loading…</div></div>
  </div>
```

With:

```html
    <div id="list"><div style="opacity:.6;font-size:11px;">loading…</div></div>
    <div id="modeRow">
      <label>mode:</label>
      <select id="modeSelect">
        <option value="roundrobin">round-robin</option>
        <option value="moderator">moderator (@-mention)</option>
        <option value="freeforall">free-for-all</option>
      </select>
      <button id="summonBtn" onclick="summonRoundtable()">summon roundtable</button>
    </div>
  </div>
```

- [ ] **Step 8.3: Replace single-click summon with multi-select state**

In the same file, find the `loadPages` function and the `summon(path)` function. Replace the entire `loadPages` function with:

```javascript
let selectedPaths = new Set();

async function loadPages(){
  const r = await fetch("/api/pages"); const j = await r.json();
  const el = document.getElementById("list"); el.innerHTML = "";
  j.forEach(p => {
    const d = document.createElement("div"); d.className="pageItem";
    d.textContent = p.path;
    d.dataset.path = p.path;
    d.onclick = () => togglePageSelection(p.path, d);
    el.appendChild(d);
  });
  updateModeRow();
}

function togglePageSelection(path, el){
  if (selectedPaths.has(path)){
    selectedPaths.delete(path);
    el.classList.remove("selected");
  } else {
    if (selectedPaths.size === 0){
      // First selection: still allow single-summon shortcut on single click
      // by keeping the legacy summon path available. Track selection visually.
      selectedPaths.add(path);
      el.classList.add("selected");
    } else if (selectedPaths.size >= 8){
      toast("max 8 personas per roundtable");
      return;
    } else {
      selectedPaths.add(path);
      el.classList.add("selected");
    }
  }
  updateModeRow();
}

function updateModeRow(){
  const row = document.getElementById("modeRow");
  if (selectedPaths.size >= 2){
    row.classList.add("visible");
  } else {
    row.classList.remove("visible");
  }
}

async function summonRoundtable(){
  if (selectedPaths.size < 2){ toast("pick at least 2 pages"); return; }
  const mode = document.getElementById("modeSelect").value;
  const paths = [...selectedPaths];

  // Cost-disclaimer for free-for-all with ≥3 personas
  if (mode === "freeforall" && paths.length >= 3){
    const ok = confirm(`Free-for-all with ${paths.length} personas: ~${paths.length}× token cost per turn. Continue?`);
    if (!ok) return;
  }

  const r = await fetch("/api/summon", {
    method:"POST",
    headers:{"content-type":"application/json"},
    body: JSON.stringify({paths, mode}),
  });
  if (!r.ok){ toast("summon failed: " + r.status); return; }
  const j = await r.json();
  sid = j.session_id;
  document.getElementById("who").textContent = `${mode} session with ${paths.length} personas`;
  document.getElementById("log").innerHTML = "";
  document.getElementById("txt").disabled = false;
  document.getElementById("send").disabled = false;
  document.getElementById("exportBtn").disabled = false;
  // Clear selection
  selectedPaths.clear();
  document.querySelectorAll(".pageItem.selected").forEach(el => el.classList.remove("selected"));
  updateModeRow();
}
```

Then keep the legacy single-page `summon(path)` function intact for the case when user clicks a single page and wants the original summon-on-click behavior. We've removed the click handler in favor of `togglePageSelection`, so add a separate way to "single-summon": double-click instead of single-click.

After `togglePageSelection`, add:

```javascript
function singleSummonOnDoubleClick(path){
  selectedPaths.clear();
  document.querySelectorAll(".pageItem.selected").forEach(el => el.classList.remove("selected"));
  summon(path);  // legacy single-page summon (Phase-10a path)
}
```

And update `loadPages` to also bind double-click:

```javascript
    d.ondblclick = () => singleSummonOnDoubleClick(p.path);
```

(Add this line right after `d.onclick = ...` inside the forEach in `loadPages`.)

- [ ] **Step 8.4: Render persona-bubbles in form.onsubmit + loadSessionIntoChat**

In the same file, find the `form.onsubmit` handler. Replace its body with:

```javascript
document.getElementById("form").onsubmit = async (ev) => {
  ev.preventDefault();
  if(sid===null) return;
  const txt = document.getElementById("txt");
  const userText = txt.value.trim(); if(!userText) return;
  txt.value="";
  appendMsg("user", userText);
  const r = await fetch("/api/say",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({session_id:sid,text:userText})});
  const j = await r.json();
  if (Array.isArray(j.tool_events)) {
    j.tool_events.forEach((te, idx) => appendToolEvent(te, idx, j.tool_events.length));
  }
  // Phase-10b: replies array (roundtable) takes priority over reply (single-mode)
  if (Array.isArray(j.replies)){
    j.replies.forEach(rep => appendPersonaBubble(rep));
  } else {
    appendMsg("assistant", j.reply || "(no reply)");
  }
};
```

Add the `appendPersonaBubble` function near `appendMsg`:

```javascript
function appendPersonaBubble(rep){
  const log = document.getElementById("log");
  const d = document.createElement("div");
  d.className = "msg persona";
  d.style.borderLeftColor = rep.color || "#4a8";
  const labelEl = document.createElement("div");
  labelEl.className = "personaLabel";
  labelEl.textContent = (rep.persona_path || "").split("/").pop().replace(/\.md$/, "");
  const textEl = document.createElement("div");
  textEl.textContent = rep.text || "";
  d.appendChild(labelEl);
  d.appendChild(textEl);
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
```

- [ ] **Step 8.5: Update loadSessionIntoChat to render historical persona-rows**

In the same file, replace `loadSessionIntoChat`:

```javascript
async function loadSessionIntoChat(sessionId, pagePath){
  const r = await fetch(`/api/sessions/${sessionId}`);
  if (!r.ok) { toast("could not load session"); return; }
  const j = await r.json();
  sid = sessionId;
  document.getElementById("who").textContent = "viewing past session: " + pagePath;
  document.getElementById("log").innerHTML = "";
  j.messages.forEach(m => {
    if (m.role === "tool_use"){
      try {
        const payload = JSON.parse(m.content);
        appendToolEvent({
          tool_name: payload.tool_name,
          tool_args: payload.tool_args,
          tool_result_summary: payload.tool_result_summary,
        }, 0, 1);
      } catch(e) {
        appendMsg("assistant", "(unreadable tool event)");
      }
    } else if (m.role === "assistant" && m.persona_path){
      // Phase-10b: render roundtable assistant rows with persona label
      appendPersonaBubble({
        persona_path: m.persona_path,
        text: m.content,
        color: hashColorJs(m.persona_path),
      });
    } else {
      appendMsg(m.role, m.content);
    }
  });
  document.getElementById("txt").disabled = false;
  document.getElementById("send").disabled = false;
  document.getElementById("exportBtn").disabled = false;
}

// Mirror Python hash_color() so historical replays show same colors as live.
function hashColorJs(path){
  const palette = ["#7adfd5","#a8e6cf","#c9b3ff","#ffd3a5","#fda4af","#fde68a","#bbf7d0","#a5d8ff"];
  let h = 0;
  for (let i = 0; i < path.length; i++) h += path.charCodeAt(i);
  return palette[h % palette.length];
}
```

- [ ] **Step 8.6: Run all tests to verify static-file change didn't break anything**

Run: `.venv/Scripts/python.exe -m pytest tests/ --tb=short 2>&1 | tail -3`
Expected: 195 passed (no UI tests exist; backend untouched).

- [ ] **Step 8.7: Commit**

```bash
git add living_vault/apps/seance_ui/static/index.html
git commit -m "living-vault | Phase-10b: UI multi-select picker + mode dropdown + persona bubbles"
```

---

## Task 9: Live-DB smoke + Phase-10b checklist + master-plan update

**Files:**
- Create: `docs/PHASE-10B-CHECKLIST.md`
- Modify: `docs/plans/2026-05-08-living-vault-master-plan.md` (Wiedereinstieg paragraph)

- [ ] **Step 9.1: Create the Phase-10b checklist**

Create `docs/PHASE-10B-CHECKLIST.md`:

```markdown
# Phase 10b — Multi-Persona-Roundtable Acceptance Checklist

Per spec: [`docs/superpowers/specs/2026-05-09-phase-10b-roundtable-design.md`](superpowers/specs/2026-05-09-phase-10b-roundtable-design.md)
Per plan: [`docs/superpowers/plans/2026-05-09-phase-10b-roundtable.md`](superpowers/plans/2026-05-09-phase-10b-roundtable.md)

## Automated Acceptance

- [ ] Schema-Migration is idempotent against the live DB:
  ```
  python -c "from living_vault.core import db; from pathlib import Path; db.initialize(Path.home() / 'wiki' / '.vault-engine.db')"
  ```
  Run twice — both succeed; `mode` column appears on `seance_sessions`, `seance_session_personas` table exists.
- [ ] pick_speakers tests green (9 tests in test_roundtable_speakers.py)
- [ ] shared_history_for_persona tests green (5 tests in test_roundtable_history.py)
- [ ] Roundtable end-to-end tests green (10 tests in test_roundtable_app.py)
- [ ] Phase-10a single-mode tests still green (existing 6 in test_seance_say_with_tools.py + 13 in test_seance_app.py)
- [ ] Full suite: `.venv/Scripts/python.exe -m pytest tests/ -v` reports approximately 195 passed, 0 failed

## Live-DB Smoke (manual, requires real Anthropic API key)

Three scenarios, all in browser at `http://127.0.0.1:7777`:

### Scenario 1: Round-Robin (3 turns)
- [ ] Pick 3 pages with multi-select (click 3 different pages from list)
- [ ] Mode-Dropdown shows up; select "round-robin"
- [ ] Click "summon roundtable"
- [ ] Header shows "roundrobin session with 3 personas"
- [ ] Ask 3 questions in a row
- [ ] Verify: turn 1 → persona A answers; turn 2 → persona B; turn 3 → persona C
- [ ] Each bubble has a different color, label shows the persona name

### Scenario 2: Moderator (with @-mention)
- [ ] Pick 2 pages
- [ ] Mode-Dropdown: select "moderator (@-mention)"
- [ ] Summon
- [ ] Ask "@persona-x, was meinst du?" — only that persona answers
- [ ] Ask without @-mention — round-robin fallback (1 persona answers)

### Scenario 3: Free-for-all
- [ ] Pick 3 pages
- [ ] Mode-Dropdown: select "free-for-all"
- [ ] Click summon — confirm dialog appears: "Free-for-all with 3 personas: ~3× token cost per turn"
- [ ] Confirm, then ask one question
- [ ] All 3 personas reply, each with own color
- [ ] Verify: persona B and C reference what A said (shared history works)
- [ ] Optional: have one persona @-mention call consult_neighbor on a teammate (mini-bubble appears)

## Performance

- [ ] 3-persona free-for-all turn end-to-end: subjectively ≤ 30s against real Anthropic API.

## Notes

- The export feature renders tool_use events as raw JSON (Phase-10a-leftover). Phase-11+ candidate for polishing.
- Persona-double-click on a single page is the shortcut for legacy single-mode summon (Phase-10a behavior preserved).
```

- [ ] **Step 9.2: Update master-plan Wiedereinstieg**

In `docs/plans/2026-05-08-living-vault-master-plan.md`, find the "Aktuelle Position:" paragraph at the bottom. Update it to:

```markdown
Aktuelle Position: **Phase 8 + 9 + 10a ✅ abgeschlossen**, **Phase 10b ✅ code-complete am 2026-05-09**, Live-Sichtprüfung steht aus (siehe `docs/PHASE-10B-CHECKLIST.md`). Test-Total: ~195 (Phase 9 = 118, +38 Phase-10a, +37 Phase-10b). Alle drei Modi (Round-Robin / Moderator / Free-for-all) implementiert, Cross-Persona-Consult, Geteilte History, hash-deterministische Persona-Colors. Phase 11 = Synesthesia public subset.
```

Also update the phase-table row for Phase 10b:

Find:
```markdown
| 10b | (Phase 2) Nachbar-Gespräche Stufe 3 (Multi-Persona-Roundtable) | Multi-Select Pages + 3 Modi (Round-Robin / Moderator / Free-for-all) + UI-Bubbles mit Persona-Label | 🟡 |
```

Replace with:
```markdown
| 10b | (Phase 2) Nachbar-Gespräche Stufe 3 (Multi-Persona-Roundtable) | Multi-Select Pages + 3 Modi (Round-Robin / Moderator / Free-for-all) + UI-Bubbles mit Persona-Label | ✅ |
```

Note: keep the status as 🟡 if Sichtprüfung is still pending; only flip to ✅ after manual smoke verification.

- [ ] **Step 9.3: Run smoke check (live-DB schema migration)**

```bash
.venv/Scripts/python.exe -c "from living_vault.core import db; from pathlib import Path; db.initialize(Path.home() / 'wiki' / '.vault-engine.db'); print('migration ok')"
.venv/Scripts/python.exe -c "from living_vault.core import db; from pathlib import Path; db.initialize(Path.home() / 'wiki' / '.vault-engine.db'); print('migration ok again')"
```

Verify both succeed. Then verify the column + table:

```bash
.venv/Scripts/python.exe -c "import sqlite3; from pathlib import Path; con = sqlite3.connect(str(Path.home() / 'wiki' / '.vault-engine.db')); cols = [r[1] for r in con.execute('PRAGMA table_info(seance_sessions)')]; print('seance_sessions:', cols); tables = [r[0] for r in con.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]; print('has seance_session_personas:', 'seance_session_personas' in tables)"
```

Expected: `mode` is in cols list, `seance_session_personas` is True.

- [ ] **Step 9.4: Commit**

```bash
git add docs/PHASE-10B-CHECKLIST.md docs/plans/2026-05-08-living-vault-master-plan.md
git commit -m "living-vault | Phase-10b: acceptance checklist + master-plan status update"
```

---

## Self-Review

After writing this plan, comparing against the spec:

**Spec coverage:**
- §3 Architektur — Tasks 6 (summon), 7 (roundtable_say), 8 (UI). ✅
- §4.1 Summon — Task 6. ✅
- §4.2-4.4 Modi-Lebenszyklus — Task 7. ✅
- §4.5 Geteilte History — Task 4. ✅
- §4.6 Cost-Caps — Task 6 (8-personas-413), Task 8 (free-for-all confirm dialog). ✅
- §4.7 Color-Palette — Task 3 (`hash_color`), Task 8 (JS mirror). ✅
- §5 Schema-Migration — Task 1. ✅
- §6 Error-Handling — Task 6 (summon validation), Task 7 (skip-broken-persona, persona_skipped event). ✅
- §7 Testing — 37 spec tests, plan delivers 9+5+10+3+3+4 = 34 explicit + 3 prompt + 4 store + 3 migration = 37. Match. ✅
- §8 Acceptance — Task 9 (checklist mirrors §8). ✅

**Placeholder scan:** No "TBD", no "TODO" in the plan. Each step has full code blocks.

**Type consistency:**
- `pick_speakers(*, mode, user_text, personas, turn_idx)` defined in Task 3, called same way in Task 7. ✅
- `add_session_persona(db_path, session_id, persona_path, *, color, seat_idx)` defined in Task 2, called same way in Task 6 (`store.add_session_persona(_db_path(), sid, p, color=color, seat_idx=i)`). ✅
- `shared_history_for_persona(db_path, session_id, persona_path)` defined in Task 4, called same way in Task 7. ✅
- `build_system_prompt(persona, neighbor_titles, neighbor_paths=None, teammate_paths=None)` extended in Task 5, called same way in Task 7. ✅
- `hash_color(persona_path) -> str` defined in Task 3, called from Task 6 (Python) and Task 8 (JS-mirrored). ✅
- Response shape `{replies: [{persona_path, text, color, seat_idx}], tool_events: [...]}` consistent between Task 7 implementation and Task 7 tests. ✅
- `personas` shape `[{persona_path, color, seat_idx}, ...]` consistent across Task 2, 3, 6, 7. ✅

Plan is internally consistent.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-09-phase-10b-roundtable.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, two-stage review (spec compliance + code quality), fast iteration. Phase 10a used this and produced 156 tests with 6 quality-fix iterations and one Sichtprüfungs-hotfix; the same pattern fits 10b.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch with checkpoints for review.

Which approach?
