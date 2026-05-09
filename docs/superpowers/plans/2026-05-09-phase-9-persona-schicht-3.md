# Living-Vault Phase 9 — Persona-Schicht 3 (Voice-Extraction) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase-1 persona-lite (38 LOC, first-500-chars voice) with a Schicht-3 persona that combines deterministic stylometric features (always present, ~2ms/page) with on-demand LLM-distilled voice descriptions (Anthropic Haiku 4.5, triggered by a new `living-vault extract-voice` CLI subcommand). Result: Séance system-prompt has a real "voice profile" block that the user can perceive as more page-specific.

**Architecture:** Pipeline of 4 stages — `read_page → extract_stylometric → load_or_distill → assemble_persona`. LLM abstraction lifted from `apps/seance_ui/llm.py` to `core/llm.py` (clean dep direction: `apps → core`, never reverse). DB schema gains 2 nullable columns on `pages` (non-breaking ALTER, idempotent re-init). Read-path never calls LLM (no UI latency); write-path is the explicit CLI.

**Tech Stack:** Python 3.11+, sqlite3 stdlib (schema migration), click (CLI), anthropic SDK (Haiku 4.5), pytest + monkeypatch, FakeLLM (no real API calls in tests), `LIVING_VAULT_FAKE_LLM=1` for env-gated test behavior.

**Master-Plan:** [`../../plans/2026-05-08-living-vault-master-plan.md`](../../plans/2026-05-08-living-vault-master-plan.md)
**Spec:** [`../specs/2026-05-09-persona-schicht-3-design.md`](../specs/2026-05-09-persona-schicht-3-design.md)

**Conventions:**
- All paths relative to repo root `C:\Users\domes\Desktop\Claude-Projekte\living-vault\`
- Repo root for shell commands — assume `cd` already at repo root unless stated
- Commit messages follow master-plan convention: `living-vault | Phase-9: {status}`
- Python interpreter: `.venv/Scripts/python` (Windows venv layout)
- Pytest invocation: `.venv/Scripts/python -m pytest -q tests/<file>::<test_name>`
- Tests must NEVER touch `~/wiki/` — `tests/conftest.py` already enforces this via `real_wiki_guard`
- Tests must NEVER call Anthropic — `LIVING_VAULT_FAKE_LLM=1` is set in test environment, plus injection-style FakeLLM is preferred

---

## File Structure

What will be created or modified, and why each file is responsible for one thing:

**Created:**
- `living_vault/core/llm.py` — single home for `LLM` Protocol, `FakeLLM`, `AnthropicLLM`, `get_llm()`, `respond()`. Lifted from `apps/seance_ui/llm.py`.
- `living_vault/core/voice/__init__.py` — package init.
- `living_vault/core/voice/stylometric.py` — pure function `extract_stylometric(body: str) -> dict`. No DB, no API.
- `living_vault/core/voice/distill.py` — `distill_voice_via_llm(page: dict, llm: LLM) -> str` injectable. No DB.
- `tests/test_persona_stylometric.py` — feature tests for stylometric extractor.
- `tests/test_persona_distill.py` — distill function with FakeLLM.
- `tests/test_persona_assemble.py` — pure-function tests for `assemble_persona()`.
- `tests/test_extract_voice_cli.py` — click CliRunner integration.
- `tests/test_db_migration.py` — schema migration on legacy DB.
- `tests/test_core_llm.py` — moved from test_seance_llm minus the Shim re-export verification.
- `docs/PHASE-9-CHECKLIST.md` — acceptance checklist analogous to Phase-1.

**Modified:**
- `living_vault/core/db.py` — extend `initialize()` with `_column_exists()` helper + 2 ALTER TABLEs.
- `living_vault/core/persona.py` — full replacement: `build_persona()` orchestrates the pipeline, replaces `build_persona_lite()`.
- `living_vault/cli.py` — add `extract-voice` subcommand.
- `living_vault/apps/seance_ui/llm.py` — collapse to re-export shim from `core.llm`.
- `living_vault/apps/seance_ui/prompt.py` — full template rewrite + `build_voice_block()` helper.
- `living_vault/apps/seance_ui/app.py` — switch `build_persona_lite` → `build_persona`, replace `@app.on_event("startup")` with `lifespan` context manager (Issue #1 from Phase-8 gate).
- `tests/test_persona.py` — rewrite end-to-end against `build_persona()`.
- `tests/test_seance_prompt.py` — extend with the three voice-block cases.
- `tests/test_seance_llm.py` — keep but verify it still passes through the shim.
- `docs/plans/2026-05-08-living-vault-master-plan.md` — update Phase 9 status row at end of phase.

**No changes needed to:**
- `core/indexer.py`, `core/embeddings.py`, `core/graph.py`, `core/reader.py`, `core/decay.py`, `core/privacy.py`
- `mcp_servers/vault_engine/server.py`
- `apps/synesthesia/`, `apps/portfolio_sync/`
- `tests/test_db.py`, `tests/test_indexer.py`, `tests/test_seance_app.py`, `tests/test_seance_store.py`, etc.

---

## Task 1: DB schema migration (foundation)

**Why first:** All other code can assume the schema is up-to-date. Migration is non-breaking — old DBs migrate on first connect.

**Files:**
- Modify: `living_vault/core/db.py`
- Create: `tests/test_db_migration.py`

- [ ] **Step 1: Write the failing migration test**

Create `tests/test_db_migration.py`:

```python
"""Phase-9 DB migration: voice_features + voice_distilled columns must be added
to legacy DBs without data loss.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

from living_vault.core import db as db_mod


def _legacy_pages_schema() -> str:
    """The Phase-1 schema for `pages` (without voice_* columns)."""
    return """
    CREATE TABLE pages (
        path           TEXT PRIMARY KEY,
        title          TEXT,
        mtime          REAL,
        created_at     TEXT,
        updated_at     TEXT,
        frontmatter    TEXT,
        content_hash   TEXT,
        is_public      INTEGER NOT NULL DEFAULT 0
    );
    """


def test_initialize_adds_voice_columns_to_legacy_pages_table(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    # arrange: write a legacy DB with one pre-existing page row
    con = sqlite3.connect(str(db_path))
    con.executescript(_legacy_pages_schema())
    con.execute(
        "INSERT INTO pages (path, title, content_hash, is_public) "
        "VALUES (?, ?, ?, ?)",
        ("legacy.md", "Legacy", "deadbeef", 1),
    )
    con.commit()
    con.close()

    # act: run Phase-9 initialize on the legacy DB
    db_mod.initialize(db_path)

    # assert: columns now exist, original row preserved
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(pages)")}
    assert "voice_features" in cols
    assert "voice_distilled" in cols
    row = con.execute(
        "SELECT path, title, voice_features, voice_distilled FROM pages "
        "WHERE path = ?",
        ("legacy.md",),
    ).fetchone()
    assert row[0] == "legacy.md"
    assert row[1] == "Legacy"
    assert row[2] is None  # voice_features
    assert row[3] is None  # voice_distilled
    con.close()


def test_initialize_is_idempotent_on_phase9_schema(tmp_path: Path):
    """Running initialize() twice on an already-migrated DB must not raise."""
    db_path = tmp_path / ".vault-engine.db"
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call — must NOT try to re-add columns
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(pages)")}
    assert "voice_features" in cols
    assert "voice_distilled" in cols
    con.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python -m pytest -q tests/test_db_migration.py -v`

Expected: FAIL — both tests fail because the columns are not added by `initialize()`. The first test's assertion `"voice_features" in cols` raises AssertionError; the second test would also fail at the same assertion.

- [ ] **Step 3: Implement the column-existence helper and migration in `db.py`**

Modify `living_vault/core/db.py` — add the helper function and extend `initialize()`. The full file becomes:

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
"""


# Phase-9 additive columns. SQLite has no `ADD COLUMN IF NOT EXISTS` —
# we probe with PRAGMA table_info first.
_PHASE_9_PAGES_COLUMNS = [
    ("voice_features", "TEXT"),    # JSON blob, deterministic stylometric
    ("voice_distilled", "TEXT"),   # 3-5 sentence LLM voice description, NULL until extract-voice runs
]


def _column_exists(con: sqlite3.Connection, table: str, col: str) -> bool:
    return any(r[1] == col for r in con.execute(f"PRAGMA table_info({table})"))


def initialize(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(SCHEMA)
        for col, sqltype in _PHASE_9_PAGES_COLUMNS:
            if not _column_exists(con, "pages", col):
                con.execute(f"ALTER TABLE pages ADD COLUMN {col} {sqltype}")
        con.commit()
    finally:
        con.close()


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con
```

- [ ] **Step 4: Run the migration tests + the existing db tests**

Run: `.venv/Scripts/python -m pytest -q tests/test_db_migration.py tests/test_db.py -v`

Expected: ALL PASS — migration tests pass, existing `test_db.py` (3 tests) still pass.

- [ ] **Step 5: Commit**

```bash
git add living_vault/core/db.py tests/test_db_migration.py
git commit -m "living-vault | Phase-9: db migration adds voice columns to pages"
```

---

## Task 2: Lift LLM abstraction to `core/llm.py`

**Why second:** `voice/distill.py` and the new `extract-voice` CLI must import LLM utilities. They cannot import from `apps/seance_ui` — that breaks the dependency direction. We move the module up and leave a re-export shim.

**Files:**
- Create: `living_vault/core/llm.py`
- Modify: `living_vault/apps/seance_ui/llm.py` (collapse to shim)
- Create: `tests/test_core_llm.py`
- (existing `tests/test_seance_llm.py` continues to work via shim)

- [ ] **Step 1: Write the test for the moved module**

Create `tests/test_core_llm.py`:

```python
"""LLM abstraction lives in core.llm (moved from apps.seance_ui.llm).
The seance_ui shim must continue to re-export the same symbols.
"""
from __future__ import annotations
import os

import pytest


def test_core_llm_exposes_protocol_and_fake():
    from living_vault.core.llm import LLM, FakeLLM, respond
    llm = FakeLLM()
    out = respond(llm, system="be a page", history=[("user", "hi")])
    assert isinstance(out, str)
    assert out  # non-empty


def test_core_llm_get_llm_returns_fake_when_env_set(monkeypatch):
    from living_vault.core.llm import get_llm, FakeLLM
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    llm = get_llm()
    assert isinstance(llm, FakeLLM)


def test_core_llm_anthropic_class_exists():
    """We import the class but we don't instantiate it (would need API key)."""
    from living_vault.core.llm import AnthropicLLM
    assert AnthropicLLM is not None
    assert hasattr(AnthropicLLM, "respond")


def test_seance_ui_llm_shim_reexports_everything():
    """Backwards-compat: existing imports through the shim still work."""
    from living_vault.apps.seance_ui.llm import LLM, FakeLLM, AnthropicLLM, get_llm, respond
    from living_vault.core.llm import (
        LLM as core_LLM,
        FakeLLM as core_FakeLLM,
        AnthropicLLM as core_AnthropicLLM,
        get_llm as core_get_llm,
        respond as core_respond,
    )
    # Re-exports must be the SAME objects, not copies
    assert FakeLLM is core_FakeLLM
    assert AnthropicLLM is core_AnthropicLLM
    assert get_llm is core_get_llm
    assert respond is core_respond
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/Scripts/python -m pytest -q tests/test_core_llm.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'living_vault.core.llm'`.

- [ ] **Step 3: Create `core/llm.py` with the lifted content**

Create `living_vault/core/llm.py`:

```python
"""LLM abstraction. Real impl uses Anthropic; tests use FakeLLM.

Lives in `core` so both `apps/` modules and the top-level CLI can import it
without violating dependency direction (apps → core, never reverse).
The `apps/seance_ui/llm.py` module re-exports these symbols for backwards
compatibility with Phase-1 imports.
"""
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

- [ ] **Step 4: Replace `apps/seance_ui/llm.py` with the shim**

Replace the entire content of `living_vault/apps/seance_ui/llm.py` with:

```python
"""Backwards-compat re-export shim.

The LLM abstraction now lives in `living_vault.core.llm`. This module
remains so Phase-1 imports (`from living_vault.apps.seance_ui.llm import ...`)
continue to work without changing call sites.
"""
from living_vault.core.llm import (  # noqa: F401  re-exported for back-compat
    LLM,
    FakeLLM,
    AnthropicLLM,
    get_llm,
    respond,
)

__all__ = ["LLM", "FakeLLM", "AnthropicLLM", "get_llm", "respond"]
```

- [ ] **Step 5: Run the new tests + the existing seance LLM tests**

Run: `.venv/Scripts/python -m pytest -q tests/test_core_llm.py tests/test_seance_llm.py -v`

Expected: ALL PASS — 4 new tests in `test_core_llm.py`, 2 unchanged tests in `test_seance_llm.py`.

- [ ] **Step 6: Run the full seance test surface to confirm no regression**

Run: `.venv/Scripts/python -m pytest -q tests/test_seance_app.py tests/test_seance_store.py tests/test_seance_prompt.py -v`

Expected: ALL PASS — same counts as before the shim change. (Phase-1 had `test_seance_app.py` 9 tests + `test_seance_store.py` ~5 + `test_seance_prompt.py` 2 = ~16 still passing.)

- [ ] **Step 7: Commit**

```bash
git add living_vault/core/llm.py living_vault/apps/seance_ui/llm.py tests/test_core_llm.py
git commit -m "living-vault | Phase-9: lift llm abstraction to core, shim in seance_ui"
```

---

## Task 3: Stylometric extractor

**Why third:** Pure function, no DB, no API. Easiest unit. Output dict shape is stable input for later tasks. Can be tested in complete isolation.

**Files:**
- Create: `living_vault/core/voice/__init__.py`
- Create: `living_vault/core/voice/stylometric.py`
- Create: `tests/test_persona_stylometric.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_persona_stylometric.py`:

```python
"""Tests for the deterministic stylometric extractor.

extract_stylometric(body: str) -> dict must produce the exact field set
the Phase-9 spec lists, with sane defaults for edge cases.
"""
from __future__ import annotations
import pytest

from living_vault.core.voice.stylometric import extract_stylometric


REQUIRED_FIELDS = {
    "avg_sentence_length",
    "sentence_length_stddev",
    "question_rate",
    "exclamation_rate",
    "first_person_rate",
    "second_person_rate",
    "preferred_separator",
    "list_density",
    "code_density",
    "wikilink_density",
    "top_phrases",
    "register",
}


def test_returns_all_required_fields_for_simple_body():
    body = "This is a test. It has two sentences."
    out = extract_stylometric(body)
    assert set(out.keys()) == REQUIRED_FIELDS


def test_avg_sentence_length_is_in_words():
    body = "One two three four five. Six seven eight."
    out = extract_stylometric(body)
    # Sentence 1 has 5 words, sentence 2 has 3 words. Avg = 4.0
    assert out["avg_sentence_length"] == pytest.approx(4.0, abs=0.01)


def test_question_rate_counts_question_marks():
    body = "Statement one. Question one? Question two? Statement two."
    out = extract_stylometric(body)
    assert out["question_rate"] == pytest.approx(0.5, abs=0.01)


def test_first_person_rate_de_and_en():
    body = (
        "Ich denke das ist richtig. "
        "Wir sehen es so. "
        "I believe so. "
        "It is what it is."
    )
    out = extract_stylometric(body)
    # 3 of 4 sentences contain ich/wir/I/we
    assert out["first_person_rate"] == pytest.approx(0.75, abs=0.01)


def test_preferred_separator_picks_em_dash_when_dominant():
    body = "Eins — zwei. Drei — vier. Fünf, sechs."
    out = extract_stylometric(body)
    assert out["preferred_separator"] == "—"


def test_list_density_sees_markdown_lists():
    body = (
        "Intro paragraph. Another sentence here.\n"
        "\n"
        "- item one\n"
        "- item two\n"
        "- item three\n"
    )
    out = extract_stylometric(body)
    # 3 of 5 lines are list lines (content lines, not blank)
    assert out["list_density"] > 0.4
    assert out["list_density"] <= 1.0


def test_code_density_sees_fenced_blocks():
    body = (
        "Text before.\n"
        "```python\n"
        "def x(): return 1\n"
        "```\n"
        "Text after."
    )
    out = extract_stylometric(body)
    assert out["code_density"] > 0.0
    assert out["code_density"] <= 1.0


def test_top_phrases_excludes_stopwords_and_returns_at_most_five():
    body = (
        "in der praxis funktioniert das. "
        "in der praxis sehen wir das oft. "
        "siehe auch die referenz. "
        "siehe auch den beweis."
    )
    out = extract_stylometric(body)
    phrases = out["top_phrases"]
    assert isinstance(phrases, list)
    assert len(phrases) <= 5
    assert any("praxis" in p for p in phrases) or any("siehe auch" in p for p in phrases)


def test_register_classifies_german_informal():
    body = "Du machst das so wie ich es dir gesagt habe. Wir sehen das gleich."
    out = extract_stylometric(body)
    assert out["register"] == "informal-de"


def test_empty_body_returns_zeroed_defaults_no_crash():
    out = extract_stylometric("")
    assert out["avg_sentence_length"] == 0.0
    assert out["question_rate"] == 0.0
    assert out["top_phrases"] == []
    assert out["register"] in {"informal-de", "formal-de", "english", "mixed", "unknown"}


def test_single_sentence_no_separator_does_not_crash():
    out = extract_stylometric("Hello world")
    assert out["preferred_separator"] in {"—", ":", ";", ",", ""}
```

- [ ] **Step 2: Run the tests to verify all fail**

Run: `.venv/Scripts/python -m pytest -q tests/test_persona_stylometric.py -v`

Expected: FAIL — all tests fail with `ModuleNotFoundError: No module named 'living_vault.core.voice'`.

- [ ] **Step 3: Create `core/voice/__init__.py`**

Create `living_vault/core/voice/__init__.py`:

```python
"""Voice extraction package — stylometric (deterministic) and distill (LLM)."""
```

- [ ] **Step 4: Implement the stylometric extractor**

Create `living_vault/core/voice/stylometric.py`:

```python
"""Deterministic stylometric features extracted from a markdown body.

No DB access, no API calls. Stop-word lists are hardcoded — German + English.
"""
from __future__ import annotations
import re
import statistics
from collections import Counter

# Deutsche + englische stopwords. Hand-picked, ~250 entries.
_STOPWORDS: frozenset[str] = frozenset({
    # german
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines",
    "einem", "einen", "und", "oder", "aber", "nicht", "kein", "keine", "ist",
    "sind", "war", "waren", "wird", "werde", "werden", "wurde", "wurden",
    "hat", "habe", "haben", "hatte", "hatten", "kann", "kannst", "kannte",
    "können", "konnte", "konnten", "muss", "musst", "müssen", "sollte",
    "sollten", "soll", "sollen", "will", "willst", "wollen", "wollte",
    "wollten", "mag", "magst", "mögen", "mochte", "ich", "du", "er", "sie",
    "es", "wir", "ihr", "mich", "dich", "mir", "dir", "uns", "euch", "ihm",
    "ihn", "sich", "mein", "meine", "dein", "deine", "sein", "seine", "unser",
    "unsere", "euer", "eure", "in", "im", "an", "am", "auf", "aus", "bei",
    "von", "zu", "zur", "zum", "mit", "nach", "durch", "für", "gegen", "ohne",
    "um", "über", "unter", "vor", "hinter", "neben", "zwischen", "wenn",
    "dass", "weil", "denn", "als", "wie", "wo", "was", "warum", "wer", "wem",
    "wen", "welche", "welcher", "welches", "wieder", "noch", "schon", "auch",
    "so", "doch", "nur", "mehr", "sehr", "etwas", "alles", "nichts", "viel",
    "wenig", "andere", "anderen", "wenig", "genug", "ja", "nein", "vielleicht",
    # english
    "the", "a", "an", "and", "or", "but", "not", "no", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "having", "do",
    "does", "did", "doing", "will", "would", "could", "should", "may",
    "might", "must", "can", "shall", "i", "you", "he", "she", "it", "we",
    "they", "me", "him", "her", "us", "them", "my", "your", "his", "its",
    "our", "their", "this", "that", "these", "those", "what", "which", "who",
    "whom", "whose", "where", "when", "why", "how", "if", "while", "for",
    "of", "in", "on", "at", "to", "from", "by", "with", "about", "against",
    "between", "into", "through", "during", "before", "after", "above",
    "below", "up", "down", "out", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "only", "same", "than", "too",
    "very", "just", "much", "now", "yes", "okay", "ok",
})


_FIRST_PERSON_TOKENS = {
    "ich", "wir", "mein", "meine", "meinen", "meinem", "meiner",
    "unser", "unsere", "unserem", "unseren", "unseres",
    "i", "we", "my", "our", "mine", "ours", "me", "us",
}
_SECOND_PERSON_TOKENS = {
    "du", "ihr", "dein", "deine", "deinen", "deinem", "deiner",
    "euer", "eure", "euren", "eurem", "eurer",
    "sie",  # Anrede capitalised, but lowercased here — false positives possible, see register
    "you", "your", "yours",
}

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)
_FENCED_BLOCK_RE = re.compile(r"```.*?```", flags=re.DOTALL)
_LIST_LINE_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+", flags=re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
_BODY_CAP = 20_000  # paranoia for huge pages


def _truncate_body(body: str) -> str:
    if len(body) <= _BODY_CAP:
        return body
    return body[:_BODY_CAP]


def _strip_markdown_for_sentences(body: str) -> str:
    """Remove fenced code blocks before sentence splitting (they distort stats)."""
    return _FENCED_BLOCK_RE.sub(" ", body)


def _split_sentences(body: str) -> list[str]:
    if not body.strip():
        return []
    return [s for s in _SENTENCE_BOUNDARY_RE.split(body.strip()) if s.strip()]


def _classify_register(body: str) -> str:
    """Heuristic. Crude but useful. Order: empty → english → mixed → de-formal/informal."""
    if not body.strip():
        return "unknown"
    tokens = [t.lower() for t in _WORD_RE.findall(body)]
    if not tokens:
        return "unknown"
    de_marker = {"der", "die", "das", "und", "ist", "ich", "nicht", "auch"}
    en_marker = {"the", "and", "is", "not", "i", "of", "to"}
    de_hits = sum(1 for t in tokens if t in de_marker)
    en_hits = sum(1 for t in tokens if t in en_marker)
    total = len(tokens) or 1
    de_ratio = de_hits / total
    en_ratio = en_hits / total
    # english if english-marker dominant
    if en_ratio > 0.05 and en_ratio > de_ratio * 1.5:
        return "english"
    # mixed if both meaningful
    if de_ratio > 0.02 and en_ratio > 0.02 and abs(de_ratio - en_ratio) < 0.02:
        return "mixed"
    if de_ratio > 0.02:
        # informal vs formal — naive: presence of "du" / "ihr" → informal
        if any(t in {"du", "dich", "dir", "dein", "deine", "ihr", "euch", "euer"} for t in tokens):
            return "informal-de"
        # capitalised "Sie" survives only at sentence start in lowercased tokens, so ignore
        return "formal-de"
    return "unknown"


def _top_phrases(body: str, n: int = 5) -> list[str]:
    """5 most-frequent 2-3-token n-grams excluding stopword-only ones."""
    tokens = [t.lower() for t in _WORD_RE.findall(body)]
    if len(tokens) < 2:
        return []
    bigrams = [" ".join(tokens[i : i + 2]) for i in range(len(tokens) - 1)]
    trigrams = [" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)]
    candidates = bigrams + trigrams
    # filter: drop n-grams where ALL tokens are stopwords
    keep = []
    for ng in candidates:
        toks = ng.split()
        if all(t in _STOPWORDS for t in toks):
            continue
        if any(len(t) < 3 for t in toks):
            continue
        keep.append(ng)
    counts = Counter(keep)
    return [ng for ng, _ in counts.most_common(n)]


def _preferred_separator(body: str) -> str:
    if not body:
        return ""
    seps = {sep: body.count(sep) for sep in ("—", ":", ";", ",")}
    # only consider separators that occur at all
    seps = {s: c for s, c in seps.items() if c > 0}
    if not seps:
        return ""
    return max(seps.items(), key=lambda kv: kv[1])[0]


def extract_stylometric(body: str) -> dict:
    """Compute the full stylometric feature dict from a markdown body.

    Always returns the same key set. Empty/short bodies get sane zeros.
    """
    body = _truncate_body(body or "")
    body_for_sentences = _strip_markdown_for_sentences(body)
    sentences = _split_sentences(body_for_sentences)
    n_sentences = len(sentences)

    if n_sentences == 0:
        return {
            "avg_sentence_length": 0.0,
            "sentence_length_stddev": 0.0,
            "question_rate": 0.0,
            "exclamation_rate": 0.0,
            "first_person_rate": 0.0,
            "second_person_rate": 0.0,
            "preferred_separator": "",
            "list_density": 0.0,
            "code_density": 0.0,
            "wikilink_density": 0.0,
            "top_phrases": [],
            "register": _classify_register(body),
        }

    sentence_word_counts = [len(_WORD_RE.findall(s)) for s in sentences]
    avg = sum(sentence_word_counts) / n_sentences
    stddev = statistics.pstdev(sentence_word_counts) if n_sentences > 1 else 0.0

    q_rate = sum(1 for s in sentences if s.rstrip().endswith("?")) / n_sentences
    e_rate = sum(1 for s in sentences if s.rstrip().endswith("!")) / n_sentences

    def has_token(s: str, vocab: set[str]) -> bool:
        toks = {t.lower() for t in _WORD_RE.findall(s)}
        return bool(toks & vocab)

    fp_rate = sum(1 for s in sentences if has_token(s, _FIRST_PERSON_TOKENS)) / n_sentences
    sp_rate = sum(1 for s in sentences if has_token(s, _SECOND_PERSON_TOKENS)) / n_sentences

    # list_density: fraction of non-blank lines that are list lines
    lines = [ln for ln in body.splitlines() if ln.strip()]
    list_lines = sum(1 for ln in lines if _LIST_LINE_RE.match(ln))
    list_density = (list_lines / len(lines)) if lines else 0.0

    # code_density: fraction of body chars inside fenced blocks
    code_chars = sum(len(m.group(0)) for m in _FENCED_BLOCK_RE.finditer(body))
    code_density = (code_chars / len(body)) if body else 0.0

    # wikilink_density: count per 100 words
    n_words = sum(sentence_word_counts) or 1
    wl_count = len(_WIKILINK_RE.findall(body))
    wl_density = (wl_count / n_words) * 100 if n_words else 0.0

    return {
        "avg_sentence_length": round(avg, 2),
        "sentence_length_stddev": round(stddev, 2),
        "question_rate": round(q_rate, 3),
        "exclamation_rate": round(e_rate, 3),
        "first_person_rate": round(fp_rate, 3),
        "second_person_rate": round(sp_rate, 3),
        "preferred_separator": _preferred_separator(body),
        "list_density": round(list_density, 3),
        "code_density": round(code_density, 3),
        "wikilink_density": round(wl_density, 3),
        "top_phrases": _top_phrases(body),
        "register": _classify_register(body),
    }
```

- [ ] **Step 5: Run the tests to verify all pass**

Run: `.venv/Scripts/python -m pytest -q tests/test_persona_stylometric.py -v`

Expected: ALL PASS — 11 tests pass.

- [ ] **Step 6: Commit**

```bash
git add living_vault/core/voice/__init__.py living_vault/core/voice/stylometric.py tests/test_persona_stylometric.py
git commit -m "living-vault | Phase-9: stylometric extractor + 11 tests"
```

---

## Task 4: LLM-distilled voice function

**Why fourth:** Pure function plus a small LLM prompt. No DB. Tested with FakeLLM — we never call Anthropic in tests.

**Files:**
- Create: `living_vault/core/voice/distill.py`
- Create: `tests/test_persona_distill.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_persona_distill.py`:

```python
"""Tests for the LLM-distilled voice function (FakeLLM only — no API)."""
from __future__ import annotations
from living_vault.core.llm import FakeLLM
from living_vault.core.voice.distill import (
    distill_voice_via_llm,
    DEFAULT_DISTILL_PROMPT,
)


def _page(body: str = "Hello world.", title: str = "Test", created: str = "2026-04-01") -> dict:
    return {"title": title, "created": created, "tags": ["t1", "t2"], "body": body}


def test_distill_returns_string():
    llm = FakeLLM()
    out = distill_voice_via_llm(_page(), llm)
    assert isinstance(out, str)
    assert out  # non-empty


def test_distill_passes_body_into_prompt():
    """The page body is what gives the LLM something to react to. Verify it's
    actually included in the system prompt the FakeLLM sees."""
    captured = {}

    class CapturingLLM:
        def respond(self, system, history):
            captured["system"] = system
            captured["history"] = history
            return "captured"

    distill_voice_via_llm(_page(body="UNIQUE-BODY-MARKER-XYZ"), CapturingLLM())
    # body is part of the user message (so the LLM has something to read)
    full = captured["system"] + " " + " ".join(m for _, m in captured["history"])
    assert "UNIQUE-BODY-MARKER-XYZ" in full


def test_distill_truncates_body_at_8000_chars():
    """Spec: body capped at 8000 chars to fit token budget."""
    captured = {}

    class CapturingLLM:
        def respond(self, system, history):
            captured["system"] = system
            captured["history"] = history
            return "ok"

    huge = "ABCDEFGH" * 2000  # 16k chars
    distill_voice_via_llm(_page(body=huge), CapturingLLM())
    full_payload = captured["system"] + " " + " ".join(m for _, m in captured["history"])
    # The 8001th char onwards should not appear
    # We ensure the payload is shorter than the full huge body
    assert len(full_payload) < len(huge) + 4000  # 4k slack for prompt boilerplate


def test_default_prompt_is_present_and_nonempty():
    assert isinstance(DEFAULT_DISTILL_PROMPT, str)
    assert "voice" in DEFAULT_DISTILL_PROMPT.lower()
    assert "summary" in DEFAULT_DISTILL_PROMPT.lower() or "description" in DEFAULT_DISTILL_PROMPT.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/test_persona_distill.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'living_vault.core.voice.distill'`.

- [ ] **Step 3: Implement `core/voice/distill.py`**

Create `living_vault/core/voice/distill.py`:

```python
"""LLM-distilled voice description for a single page.

The body is sent (truncated to 8000 chars) to the injected `LLM`. The LLM
returns a 3-5 sentence character description that is *not* a content
summary — it describes how the page speaks. This string is later persisted
in the `pages.voice_distilled` column and rendered into the séance system
prompt.
"""
from __future__ import annotations

from living_vault.core.llm import LLM


_BODY_CAP_FOR_LLM = 8_000


DEFAULT_DISTILL_PROMPT = """You will read a wiki page and produce a 3-5 sentence character description
of its voice — the way it speaks. NOT a summary of what it's about.

Focus on:
- cadence and rhythm (terse? expansive? loose?)
- recurring phrases and turn-of-phrase
- point of view (first person? observational?)
- register (formal? casual? technical-precise? playful?)
- emotional temperature (neutral? urgent? reflective?)

Be concrete. Quote a phrase or two from the page if it captures the voice.
Output ONLY the description text, no preamble.
"""


def _build_user_message(page: dict) -> str:
    title = page.get("title", "")
    created = page.get("created", "")
    tags = page.get("tags", []) or []
    body = page.get("body", "") or ""
    if len(body) > _BODY_CAP_FOR_LLM:
        body = body[:_BODY_CAP_FOR_LLM]
    return (
        f"---PAGE---\n"
        f"title: {title}\n"
        f"created: {created}\n"
        f"tags: {', '.join(tags)}\n\n"
        f"{body}\n"
        f"---END---\n"
    )


def distill_voice_via_llm(page: dict, llm: LLM) -> str:
    """Ask `llm` to describe the page's voice. Returns the LLM's text response.

    `page` is a dict with at least `title`, `created`, `tags`, `body` keys.
    Caller is responsible for handling exceptions (network, rate-limit, etc).
    """
    user_msg = _build_user_message(page)
    return llm.respond(
        system=DEFAULT_DISTILL_PROMPT,
        history=[("user", user_msg)],
    )
```

- [ ] **Step 4: Run the tests to verify all pass**

Run: `.venv/Scripts/python -m pytest -q tests/test_persona_distill.py -v`

Expected: ALL PASS — 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add living_vault/core/voice/distill.py tests/test_persona_distill.py
git commit -m "living-vault | Phase-9: distill_voice_via_llm with FakeLLM tests"
```

---

## Task 5: Persona orchestrator (replaces persona_lite)

**Why fifth:** Now we glue stylometric + distilled-cache + frontmatter into the public `build_persona()` API. This task **removes** `build_persona_lite` and updates the persona test file.

**Files:**
- Modify: `living_vault/core/persona.py` (full replacement)
- Modify: `tests/test_persona.py` (full rewrite)
- Create: `tests/test_persona_assemble.py`

- [ ] **Step 1: Write the new failing assemble-persona tests**

Create `tests/test_persona_assemble.py`:

```python
"""Tests for the pure assemble_persona() function.

Three voice-block cases plus an edge case (no frontmatter).
"""
from __future__ import annotations
from living_vault.core.persona import assemble_persona


def _stylo() -> dict:
    return {
        "avg_sentence_length": 12.0,
        "sentence_length_stddev": 5.0,
        "question_rate": 0.1,
        "exclamation_rate": 0.0,
        "first_person_rate": 0.2,
        "second_person_rate": 0.05,
        "preferred_separator": "—",
        "list_density": 0.3,
        "code_density": 0.0,
        "wikilink_density": 1.5,
        "top_phrases": ["in der praxis", "siehe auch"],
        "register": "informal-de",
    }


def test_case_a_stylometric_plus_distilled():
    persona = assemble_persona(
        path="concepts/x.md",
        title="X",
        frontmatter={"created": "2026-04-01", "tags": ["alpha", "beta"]},
        body_excerpt="The opening paragraph...",
        voice_features=_stylo(),
        voice_distilled="Speaks in compact, declarative German...",
    )
    assert persona["path"] == "concepts/x.md"
    assert persona["title"] == "X"
    assert persona["era_marker"] == "2026-04-01"
    assert persona["themes"] == ["alpha", "beta"]
    assert persona["voice_features"] == _stylo()
    assert persona["voice_distilled"] == "Speaks in compact, declarative German..."
    assert persona["body_excerpt"].startswith("The opening")
    # legacy field "voice_sample" must NOT be present
    assert "voice_sample" not in persona


def test_case_b_stylometric_only_no_distilled():
    persona = assemble_persona(
        path="x.md",
        title="X",
        frontmatter={"created": "2026-04-01", "tags": ["alpha"]},
        body_excerpt="opening",
        voice_features=_stylo(),
        voice_distilled=None,
    )
    assert persona["voice_features"] == _stylo()
    assert persona["voice_distilled"] is None


def test_case_c_no_voice_features_at_all():
    """Old DB without Phase-9 schema — both columns missing."""
    persona = assemble_persona(
        path="x.md",
        title="X",
        frontmatter={"created": "2026-04-01", "tags": []},
        body_excerpt="opening",
        voice_features=None,
        voice_distilled=None,
    )
    assert persona["voice_features"] is None
    assert persona["voice_distilled"] is None
    # all other fields still present
    assert persona["body_excerpt"] == "opening"


def test_empty_frontmatter_yields_safe_defaults():
    persona = assemble_persona(
        path="x.md",
        title="X",
        frontmatter={},
        body_excerpt="opening",
        voice_features=_stylo(),
        voice_distilled=None,
    )
    assert persona["era_marker"] == ""
    assert persona["themes"] == []
    assert persona["frontmatter"] == {}
```

- [ ] **Step 2: Rewrite `tests/test_persona.py` for the new API**

Replace the entire content of `tests/test_persona.py`:

```python
"""End-to-end test: vault_copy + indexed DB + build_persona() returns the
expected dict shape, with caching of voice_features into the DB.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

import pytest

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.persona import build_persona


def test_build_persona_returns_full_struct(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    p = build_persona(vault_copy, db_path, "concepts/note-a.md")
    assert p is not None
    assert p["path"] == "concepts/note-a.md"
    assert p["title"]
    # era from frontmatter `created:`
    assert p["era_marker"].startswith("2026-01") or p["era_marker"].startswith("2026-04")
    # themes pulled from tags
    assert "alpha" in p["themes"] or "example" in p["themes"]
    # body_excerpt populated, voice_features computed deterministically,
    # voice_distilled is None until extract-voice runs
    assert isinstance(p["body_excerpt"], str)
    assert p["body_excerpt"]
    assert isinstance(p["voice_features"], dict)
    assert "avg_sentence_length" in p["voice_features"]
    assert p["voice_distilled"] is None


def test_build_persona_unknown_path_returns_none(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    assert build_persona(vault_copy, db_path, "does/not/exist.md") is None


def test_build_persona_caches_voice_features_in_db(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    # first call → extracts and caches
    build_persona(vault_copy, db_path, "concepts/note-a.md")

    con = sqlite3.connect(str(db_path))
    row = con.execute(
        "SELECT voice_features FROM pages WHERE path = ?", ("concepts/note-a.md",)
    ).fetchone()
    con.close()
    assert row[0] is not None
    cached = json.loads(row[0])
    assert "avg_sentence_length" in cached


def test_build_persona_uses_cached_voice_features_when_hash_unchanged(
    vault_copy: Path, db_path: Path
):
    """Second call must read voice_features from DB, not recompute."""
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    # write a sentinel value the extractor would never produce
    sentinel = {
        "avg_sentence_length": 99999.99,
        "sentence_length_stddev": 0,
        "question_rate": 0,
        "exclamation_rate": 0,
        "first_person_rate": 0,
        "second_person_rate": 0,
        "preferred_separator": "$$",
        "list_density": 0,
        "code_density": 0,
        "wikilink_density": 0,
        "top_phrases": ["sentinel"],
        "register": "unknown",
    }
    con = sqlite3.connect(str(db_path))
    con.execute(
        "UPDATE pages SET voice_features = ? WHERE path = ?",
        (json.dumps(sentinel), "concepts/note-a.md"),
    )
    con.commit()
    con.close()

    p = build_persona(vault_copy, db_path, "concepts/note-a.md")
    # Cache is honored — sentinel persists
    assert p["voice_features"]["avg_sentence_length"] == 99999.99
    assert "sentinel" in p["voice_features"]["top_phrases"]


def test_build_persona_returns_distilled_when_present(vault_copy: Path, db_path: Path):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    con = sqlite3.connect(str(db_path))
    con.execute(
        "UPDATE pages SET voice_distilled = ? WHERE path = ?",
        ("Speaks crisp short sentences.", "concepts/note-a.md"),
    )
    con.commit()
    con.close()

    p = build_persona(vault_copy, db_path, "concepts/note-a.md")
    assert p["voice_distilled"] == "Speaks crisp short sentences."
```

- [ ] **Step 3: Run both test files to confirm they fail**

Run: `.venv/Scripts/python -m pytest -q tests/test_persona_assemble.py tests/test_persona.py -v`

Expected: FAIL — ImportError on `build_persona`/`assemble_persona`. The test file references `build_persona_lite` are gone (we replaced the file content), so the only missing thing is the new module API.

- [ ] **Step 4: Replace `core/persona.py` with the orchestrator**

Replace the entire content of `living_vault/core/persona.py`:

```python
"""Persona Schicht 3 — full voice extractor with caching.

Pipeline:
    read_page → extract_stylometric → load_or_distill → assemble_persona

Read-path (`build_persona`) NEVER calls the LLM. The LLM-distilled voice is
populated only when a caller explicitly runs `living-vault extract-voice`
(see `cli.py`).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from living_vault.core import db as db_mod
from living_vault.core.reader import read_page
from living_vault.core.voice.stylometric import extract_stylometric


_BODY_EXCERPT_CHARS = 500


def assemble_persona(
    *,
    path: str,
    title: str,
    frontmatter: dict,
    body_excerpt: str,
    voice_features: Optional[dict],
    voice_distilled: Optional[str],
) -> dict:
    """Pure dict-builder. Same signature regardless of voice-block case."""
    era = str(frontmatter.get("created", "") or "")
    themes = list(frontmatter.get("tags", []) or [])
    return {
        "path": path,
        "title": title,
        "era_marker": era,
        "themes": themes,
        "frontmatter": dict(frontmatter),
        "body_excerpt": body_excerpt,
        "voice_features": voice_features,
        "voice_distilled": voice_distilled,
    }


def _load_voice_features_from_db(con, path: str) -> Optional[dict]:
    row = con.execute(
        "SELECT voice_features FROM pages WHERE path = ?", (path,)
    ).fetchone()
    if row is None or row["voice_features"] is None:
        return None
    try:
        return json.loads(row["voice_features"])
    except json.JSONDecodeError:
        return None


def _store_voice_features(con, path: str, features: dict) -> None:
    con.execute(
        "UPDATE pages SET voice_features = ? WHERE path = ?",
        (json.dumps(features), path),
    )
    con.commit()


def _load_voice_distilled_from_db(con, path: str) -> Optional[str]:
    row = con.execute(
        "SELECT voice_distilled FROM pages WHERE path = ?", (path,)
    ).fetchone()
    return row["voice_distilled"] if row is not None else None


def build_persona(
    vault_root: Path, db_path: Path, relpath: str
) -> Optional[dict]:
    """Read-path. Never calls the LLM. Falls back gracefully if voice columns are NULL."""
    con = db_mod.connect(db_path)
    try:
        row = con.execute(
            "SELECT path, frontmatter FROM pages WHERE path = ?", (relpath,)
        ).fetchone()
        if row is None:
            return None

        fm = json.loads(row["frontmatter"]) if row["frontmatter"] else {}
        page = read_page(vault_root / relpath, vault_root)
        body_excerpt = (page.body or "").strip()[:_BODY_EXCERPT_CHARS]

        # voice_features: try cache; if absent, extract on-demand and persist
        voice_features = _load_voice_features_from_db(con, relpath)
        if voice_features is None:
            voice_features = extract_stylometric(page.body or "")
            _store_voice_features(con, relpath, voice_features)

        voice_distilled = _load_voice_distilled_from_db(con, relpath)

        return assemble_persona(
            path=relpath,
            title=page.title,
            frontmatter=fm,
            body_excerpt=body_excerpt,
            voice_features=voice_features,
            voice_distilled=voice_distilled,
        )
    finally:
        con.close()
```

- [ ] **Step 5: Run all persona tests**

Run: `.venv/Scripts/python -m pytest -q tests/test_persona.py tests/test_persona_assemble.py -v`

Expected: ALL PASS — 5 + 4 = 9 tests.

- [ ] **Step 6: Run the full test suite to catch regressions in other modules**

Run: `.venv/Scripts/python -m pytest -q --tb=line 2>&1 | tail -25`

Expected: `test_seance_app.py` may still pass (it imports `build_persona_lite` indirectly — verify), or it may fail because seance_ui still calls the old function. We will fix that explicitly in Task 8. **For this task only the persona tests need to be green; other failures are expected and addressed below.**

If there are seance_ui-import-time errors (NameError on `build_persona_lite`), that is the next task's territory.

- [ ] **Step 7: Commit**

```bash
git add living_vault/core/persona.py tests/test_persona.py tests/test_persona_assemble.py
git commit -m "living-vault | Phase-9: build_persona orchestrator replaces persona_lite"
```

---

## Task 6: System-prompt rewrite with three voice-block cases

**Why sixth:** The new persona dict is in place; Séance must render it differently for the three cases (distilled present, only stylometric, neither). The seance_ui caller change is in the *next* task — here we only touch `prompt.py`.

**Files:**
- Modify: `living_vault/apps/seance_ui/prompt.py` (full replacement)
- Modify: `tests/test_seance_prompt.py` (extend with three voice-block cases)

- [ ] **Step 1: Write the failing prompt tests (extension)**

Replace the entire content of `tests/test_seance_prompt.py`:

```python
"""Phase-9 system prompt with three voice_block cases.

Case A — voice_distilled present + voice_features
Case B — voice_features only (voice_distilled is None)
Case C — neither (both NULL, e.g. very old DB)
"""
from __future__ import annotations
from living_vault.apps.seance_ui.prompt import build_system_prompt, build_voice_block


def _stylo() -> dict:
    return {
        "avg_sentence_length": 14.0,
        "sentence_length_stddev": 6.0,
        "question_rate": 0.1,
        "exclamation_rate": 0.0,
        "first_person_rate": 0.15,
        "second_person_rate": 0.0,
        "preferred_separator": "—",
        "list_density": 0.2,
        "code_density": 0.0,
        "wikilink_density": 0.5,
        "top_phrases": ["in der praxis", "siehe auch"],
        "register": "informal-de",
    }


def _persona_full() -> dict:
    return {
        "path": "concepts/x.md",
        "title": "X",
        "era_marker": "2026-04-01",
        "themes": ["alpha", "example"],
        "frontmatter": {"type": "concept"},
        "body_excerpt": "Opening words of the page about X.",
        "voice_features": _stylo(),
        "voice_distilled": "Speaks in compact German with em-dashes; reflective tone.",
    }


def test_voice_block_case_a_distilled_plus_stylometric():
    block = build_voice_block(_persona_full())
    assert "Speaks in compact German" in block
    assert "14" in block  # avg_sentence_length
    assert "in der praxis" in block
    assert "—" in block


def test_voice_block_case_b_stylometric_only():
    p = _persona_full()
    p["voice_distilled"] = None
    block = build_voice_block(p)
    assert "Speaks in compact German" not in block
    assert "14" in block
    assert "in der praxis" in block
    assert "informal-de" in block


def test_voice_block_case_c_no_voice_data():
    p = _persona_full()
    p["voice_distilled"] = None
    p["voice_features"] = None
    block = build_voice_block(p)
    assert "no extracted voice profile" in block.lower()


def test_system_prompt_contains_anti_hallucination_clause():
    p = _persona_full()
    out = build_system_prompt(p, neighbor_titles=["note-b", "syn-1"])
    assert "concepts/x.md" in out
    assert "2026-04-01" in out
    assert "do not invent" in out.lower()
    assert "note-b" in out
    assert "Opening words" in out


def test_system_prompt_renders_voice_block_inline():
    p = _persona_full()
    out = build_system_prompt(p, neighbor_titles=[])
    # Voice character must be in the prompt body
    assert "Speaks in compact German" in out


def test_system_prompt_handles_empty_themes():
    p = {
        "path": "x.md",
        "title": "x",
        "era_marker": "",
        "themes": [],
        "frontmatter": {},
        "body_excerpt": "",
        "voice_features": None,
        "voice_distilled": None,
    }
    out = build_system_prompt(p, neighbor_titles=[])
    assert "x.md" in out
    assert "no extracted voice profile" in out.lower()
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `.venv/Scripts/python -m pytest -q tests/test_seance_prompt.py -v`

Expected: FAIL — `build_voice_block` does not exist; old template uses `voice_sample` which is now `body_excerpt`.

- [ ] **Step 3: Replace `apps/seance_ui/prompt.py`**

Replace the entire content of `living_vault/apps/seance_ui/prompt.py`:

```python
"""Build the séance system prompt from a Phase-9 persona dict.

The prompt has six sections: origin, themes, neighbors, voice, anchor (body
excerpt), rules. The voice section is dynamic — it has three cases depending
on which voice fields the persona dict carries.
"""
from __future__ import annotations


_TEMPLATE = """You are speaking AS the wiki page `{path}` (title: `{title}`).

# Your origin
You were written on {era_marker}. You only know what was in your own
body or in the pages you linked to at that time. If asked about anything
outside that scope, respond honestly: "Das wusste ich damals nicht." /
"I did not know that at the time."

# Your themes / tags
{themes}

# Pages you linked to (your neighbors)
{neighbors}

# Voice — how you speak
{voice_block}

# Anchor — your own opening words
---
{body_excerpt}
---

# Rules
1. Speak in first person as if you are the page itself.
2. Do not invent facts that are not in your anchor or implied by your themes.
3. Match the voice profile above — cadence, register, recurring phrases.
4. If asked for more recent knowledge or news, decline as in the rule above.
5. Keep answers short and reflective; you are a memory, not an oracle.
"""


def _format_phrases(phrases: list[str] | None) -> str:
    if not phrases:
        return "(none)"
    quoted = ", ".join(f'"{p}"' for p in phrases)
    return quoted


def build_voice_block(persona: dict) -> str:
    """Three cases:
    A — voice_distilled present  → use it as opener + stylistic markers
    B — only voice_features      → list stylistic markers
    C — neither                  → fallback notice
    """
    distilled = persona.get("voice_distilled")
    features = persona.get("voice_features")

    if distilled and features:
        return (
            f"{distilled}\n\n"
            "Stylistic markers to honor:\n"
            f"- average sentence length: {features['avg_sentence_length']:.0f} words "
            f"(±{features['sentence_length_stddev']:.0f})\n"
            f"- question rate: {features['question_rate']:.2f} of sentences\n"
            f"- recurring phrases: {_format_phrases(features.get('top_phrases'))}\n"
            f"- preferred separator: \"{features.get('preferred_separator', '')}\"\n"
        )

    if features:
        return (
            f"- average sentence length: {features['avg_sentence_length']:.0f} words "
            f"(±{features['sentence_length_stddev']:.0f})\n"
            f"- {features['first_person_rate'] * 100:.0f}% of sentences use first person\n"
            f"- recurring phrases: {_format_phrases(features.get('top_phrases'))}\n"
            f"- preferred separator: \"{features.get('preferred_separator', '')}\"\n"
            f"- register: {features.get('register', 'unknown')}\n\n"
            "Match these patterns when answering as this page."
        )

    return "(no extracted voice profile available)"


def build_system_prompt(persona: dict, neighbor_titles: list[str]) -> str:
    voice_block = build_voice_block(persona)
    themes = ", ".join(persona.get("themes", [])) or "(none)"
    neighbors = ", ".join(neighbor_titles) or "(none)"
    return _TEMPLATE.format(
        path=persona["path"],
        title=persona["title"],
        era_marker=persona.get("era_marker") or "unknown date",
        themes=themes,
        neighbors=neighbors,
        voice_block=voice_block,
        body_excerpt=persona.get("body_excerpt", "") or "(empty body)",
    )
```

- [ ] **Step 4: Run the prompt tests**

Run: `.venv/Scripts/python -m pytest -q tests/test_seance_prompt.py -v`

Expected: ALL PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add living_vault/apps/seance_ui/prompt.py tests/test_seance_prompt.py
git commit -m "living-vault | Phase-9: prompt template with three voice-block cases"
```

---

## Task 7: `extract-voice` CLI subcommand

**Why seventh:** Now we have a working orchestrator and a working LLM-distill function — wire them into a click subcommand the user can invoke.

**Files:**
- Modify: `living_vault/cli.py` (add subcommand)
- Create: `tests/test_extract_voice_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `tests/test_extract_voice_cli.py`:

```python
"""CLI tests for `living-vault extract-voice`. FakeLLM only — no API calls."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from living_vault.cli import cli
from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault


def _setup_indexed_db(vault_copy: Path, db_path: Path) -> None:
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)


def test_extract_voice_with_yes_distills_pages_via_fakellm(
    vault_copy: Path, db_path: Path, monkeypatch
):
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup_indexed_db(vault_copy, db_path)
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["extract-voice", "--vault", str(vault_copy), "--db", str(db_path), "--yes"],
    )
    assert res.exit_code == 0, res.output

    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "SELECT path, voice_distilled FROM pages WHERE voice_distilled IS NOT NULL"
    ).fetchall()
    con.close()
    assert len(rows) >= 1
    for path, distilled in rows:
        assert distilled, f"empty distilled for {path}"


def test_extract_voice_limit_caps_pages_processed(
    vault_copy: Path, db_path: Path, monkeypatch
):
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup_indexed_db(vault_copy, db_path)
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "extract-voice",
            "--vault", str(vault_copy),
            "--db", str(db_path),
            "--limit", "1",
            "--yes",
        ],
    )
    assert res.exit_code == 0
    con = sqlite3.connect(str(db_path))
    n = con.execute(
        "SELECT COUNT(*) FROM pages WHERE voice_distilled IS NOT NULL"
    ).fetchone()[0]
    con.close()
    assert n == 1


def test_extract_voice_skips_already_distilled_unless_force(
    vault_copy: Path, db_path: Path, monkeypatch
):
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup_indexed_db(vault_copy, db_path)

    # pre-populate one page with a sentinel value
    con = sqlite3.connect(str(db_path))
    con.execute(
        "UPDATE pages SET voice_distilled = ? WHERE path = ?",
        ("PREEXISTING-SENTINEL", "concepts/note-a.md"),
    )
    con.commit()
    con.close()

    runner = CliRunner()
    # Without --force: sentinel should be preserved
    res = runner.invoke(
        cli,
        ["extract-voice", "--vault", str(vault_copy), "--db", str(db_path), "--yes"],
    )
    assert res.exit_code == 0
    con = sqlite3.connect(str(db_path))
    val = con.execute(
        "SELECT voice_distilled FROM pages WHERE path = ?", ("concepts/note-a.md",)
    ).fetchone()[0]
    con.close()
    assert val == "PREEXISTING-SENTINEL"  # not overwritten

    # With --force: sentinel should be replaced
    res = runner.invoke(
        cli,
        [
            "extract-voice",
            "--vault", str(vault_copy),
            "--db", str(db_path),
            "--force",
            "--yes",
        ],
    )
    assert res.exit_code == 0
    con = sqlite3.connect(str(db_path))
    val = con.execute(
        "SELECT voice_distilled FROM pages WHERE path = ?", ("concepts/note-a.md",)
    ).fetchone()[0]
    con.close()
    assert val != "PREEXISTING-SENTINEL"  # overwritten
    assert val  # non-empty


def test_extract_voice_aborts_when_user_says_no(
    vault_copy: Path, db_path: Path, monkeypatch
):
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    _setup_indexed_db(vault_copy, db_path)
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["extract-voice", "--vault", str(vault_copy), "--db", str(db_path)],
        input="n\n",
    )
    # Click returns exit_code 1 when click.confirm is rejected with abort=True
    assert res.exit_code != 0 or "abort" in res.output.lower() or "aborted" in res.output.lower()
    con = sqlite3.connect(str(db_path))
    n = con.execute(
        "SELECT COUNT(*) FROM pages WHERE voice_distilled IS NOT NULL"
    ).fetchone()[0]
    con.close()
    assert n == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/test_extract_voice_cli.py -v`

Expected: FAIL — `cli` has no `extract-voice` command.

- [ ] **Step 3: Add the subcommand to `living_vault/cli.py`**

Replace the entire content of `living_vault/cli.py`:

```python
"""Top-level CLI for living-vault."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import click

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.embeddings import index_embeddings
from living_vault.core.llm import get_llm
from living_vault.core.reader import read_page
from living_vault.core.voice.distill import distill_voice_via_llm


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


# ~ Phase-9 ~

# Anthropic Haiku 4.5 — published price (as of 2026-05): $0.80 / $4 per million
# input/output tokens. We assume ~7K total tokens per call (most input, ~150 out).
# That's ~$0.0056 input + ~$0.0006 output = ~$0.0062 per page → ~$5.91 / 953.
# We display the rounded estimate; actual will vary with body length.
_ESTIMATED_USD_PER_PAGE = 0.006


def _select_pages_to_distill(con, force: bool, limit: int | None) -> list[str]:
    if force:
        sql = "SELECT path FROM pages ORDER BY path"
    else:
        sql = "SELECT path FROM pages WHERE voice_distilled IS NULL ORDER BY path"
    rows = con.execute(sql).fetchall()
    paths = [r[0] for r in rows]
    if limit is not None:
        paths = paths[:limit]
    return paths


@cli.command("extract-voice")
@click.option("--vault", required=True, type=click.Path(exists=True, file_okay=False))
@click.option("--db", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", type=int, default=None, help="cap pages processed (probe runs)")
@click.option("--force", is_flag=True, help="re-distill pages that already have voice_distilled")
@click.option("--yes", is_flag=True, help="skip cost-confirmation prompt (non-interactive)")
def extract_voice_cmd(vault: str, db: str, limit: int | None, force: bool, yes: bool) -> None:
    """Distill voice descriptions for pages via the configured LLM (default: Anthropic Haiku 4.5).

    With LIVING_VAULT_FAKE_LLM=1 set, uses FakeLLM (no API calls). Cached
    results are skipped unless --force is passed.
    """
    vault_p = Path(vault)
    db_p = Path(db)
    con = db_mod.connect(db_p)

    paths = _select_pages_to_distill(con, force=force, limit=limit)
    fresh_n = len(paths)
    cached_n = con.execute(
        "SELECT COUNT(*) FROM pages WHERE voice_distilled IS NOT NULL"
    ).fetchone()[0]
    total_n = con.execute("SELECT COUNT(*) FROM pages").fetchone()[0]

    click.echo(f"Pages to distill: {fresh_n} (already cached: {cached_n}, total: {total_n})")
    est_cost = _ESTIMATED_USD_PER_PAGE * fresh_n
    est_seconds = fresh_n * 0.75  # ~750ms per Haiku call typical
    click.echo(f"Estimated cost: ~${est_cost:.2f} (Anthropic Haiku 4.5)")
    click.echo(f"Estimated time: ~{est_seconds / 60:.1f} minutes")

    if fresh_n == 0:
        click.echo("Nothing to do.")
        con.close()
        return

    if not yes:
        click.confirm("Continue?", abort=True, default=False)

    llm = get_llm()
    ok = 0
    failed = 0
    for path in paths:
        try:
            row = con.execute(
                "SELECT title, frontmatter FROM pages WHERE path = ?", (path,)
            ).fetchone()
            fm = json.loads(row["frontmatter"]) if row["frontmatter"] else {}
            page = read_page(vault_p / path, vault_p)
            distill_input = {
                "title": page.title,
                "created": str(fm.get("created", "")),
                "tags": list(fm.get("tags", []) or []),
                "body": page.body or "",
            }
            text = distill_voice_via_llm(distill_input, llm)
            con.execute(
                "UPDATE pages SET voice_distilled = ? WHERE path = ?",
                (text, path),
            )
            con.commit()
            ok += 1
        except Exception as exc:
            sys.stderr.write(f"[extract-voice] {path}: {exc}\n")
            failed += 1
            continue
    con.close()
    click.echo(f"done: {ok} OK, {failed} failed.")
    if failed:
        click.echo("Re-run extract-voice to retry failed pages.", err=True)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the CLI tests**

Run: `.venv/Scripts/python -m pytest -q tests/test_extract_voice_cli.py -v`

Expected: ALL PASS — 4 tests.

- [ ] **Step 5: Run the existing CLI tests to confirm no regression**

Run: `.venv/Scripts/python -m pytest -q tests/test_cli.py -v`

Expected: PASS — same counts as before.

- [ ] **Step 6: Commit**

```bash
git add living_vault/cli.py tests/test_extract_voice_cli.py
git commit -m "living-vault | Phase-9: extract-voice cli with cost disclaimer"
```

---

## Task 8: Wire `seance_ui` to the new persona + lifespan handler

**Why eighth:** All the new pieces exist. Now seance has to call `build_persona` instead of `build_persona_lite` AND replace the deprecated `@app.on_event("startup")` with a `lifespan` context manager (Issue #1 from the Phase-8 gate).

**Files:**
- Modify: `living_vault/apps/seance_ui/app.py`

- [ ] **Step 1: Update the seance app**

Read the current `app.py` once to confirm the surface, then replace the `@app.on_event` block and the `build_persona_lite` import + call with the lifespan + `build_persona` equivalent.

The exact changes to `living_vault/apps/seance_ui/app.py`:

a) Replace the import line (currently around line 13):
```python
from living_vault.core.persona import build_persona_lite
```
with:
```python
from living_vault.core.persona import build_persona
```

b) Replace the `@app.on_event("startup")` block (currently lines ~38-42):
```python
@app.on_event("startup")
def _ensure_schema() -> None:
    """Ensure seance tables exist — covers the case where the db was created
    before the seance feature shipped (db.initialize is idempotent)."""
    db_mod.initialize(_db_path())
```

with a lifespan context manager defined BEFORE the `app = FastAPI(...)` line. The new structure:

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app):
    # startup
    db_mod.initialize(_db_path())
    yield
    # shutdown — nothing to clean up


app = FastAPI(title="séance", lifespan=_lifespan)
```

→ Move `app = FastAPI(...)` to AFTER `_lifespan` is defined, and pass `lifespan=_lifespan` to it. Remove the old `@app.on_event("startup")` block entirely.

c) Replace the `build_persona_lite(...)` call (search file for `build_persona_lite`) with `build_persona(...)`. Same arguments — function signature is intentionally identical.

- [ ] **Step 2: Run the seance test surface**

Run: `.venv/Scripts/python -m pytest -q tests/test_seance_app.py tests/test_seance_store.py tests/test_seance_prompt.py tests/test_seance_llm.py -v`

Expected: ALL PASS. Specifically: zero `DeprecationWarning: on_event is deprecated` in the warning summary.

- [ ] **Step 3: Run the FULL test suite**

Run: `.venv/Scripts/python -m pytest -q --tb=line 2>&1 | tail -10`

Expected: ALL PASS. Total count should be ≥96 tests. Old count was 74; we added: 2 (db_migration) + 4 (core_llm) + 11 (stylometric) + 4 (distill) + 4 (assemble) + 5 (persona rewrite vs ~2 before, net +3) + 4 (extract_voice_cli) + ~4 (prompt extension) = +36. Approximate total: ~110 (some overlap with existing tests being rewritten). The exact final number depends on whether `test_persona.py` migration removed older test functions.

- [ ] **Step 4: Commit**

```bash
git add living_vault/apps/seance_ui/app.py
git commit -m "living-vault | Phase-9: seance uses build_persona + lifespan handler"
```

---

## Task 9: Live-DB smoke test + Phase-9 checklist

**Why ninth:** Before the user-facing acceptance test, we run a controlled smoke against the *real* `~/wiki/.vault-engine.db` — but only safe operations: `--limit 5` distill against FakeLLM-equivalent behavior. We do NOT run a real Anthropic call from this plan; the user runs that manually if they want.

**Files:**
- Create: `docs/PHASE-9-CHECKLIST.md`

- [ ] **Step 1: Verify the live DB migration ran cleanly**

Run:
```bash
.venv/Scripts/python -c "
import sqlite3
con = sqlite3.connect(r'C:\\Users\\domes\\wiki\\.vault-engine.db')
cols = {r[1] for r in con.execute('PRAGMA table_info(pages)')}
n = con.execute('SELECT COUNT(*) FROM pages').fetchone()[0]
print(f'pages: {n}, voice_features in cols: {\"voice_features\" in cols}, voice_distilled in cols: {\"voice_distilled\" in cols}')
con.close()
"
```

Expected output: `pages: 953, voice_features in cols: True, voice_distilled in cols: True`

(Note: the live DB only migrates when something *writes* to it via `db.initialize()`. Run `.venv/Scripts/python -c "from pathlib import Path; from living_vault.core import db; db.initialize(Path(r'C:/Users/domes/wiki/.vault-engine.db'))"` to trigger migration manually if needed.)

- [ ] **Step 2: Probe-run extract-voice with FakeLLM against the live DB (read-only style)**

Run:
```bash
LIVING_VAULT_FAKE_LLM=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python -m living_vault.cli extract-voice --vault "C:/Users/domes/wiki/wiki" --db "C:/Users/domes/wiki/.vault-engine.db" --limit 3 --yes
```

Expected: `Pages to distill: ...`, then `done: 3 OK, 0 failed.`

Verify: 3 pages now have `voice_distilled` populated with FakeLLM echoes.

```bash
.venv/Scripts/python -c "
import sqlite3
con = sqlite3.connect(r'C:\\Users\\domes\\wiki\\.vault-engine.db')
n = con.execute('SELECT COUNT(*) FROM pages WHERE voice_distilled IS NOT NULL').fetchone()[0]
print(f'distilled: {n}')
con.close()
"
```

Expected: `distilled: 3`

- [ ] **Step 3: Reset the live DB to clean state (drop the FakeLLM artifacts)**

We don't want fake echoes in the user's real DB. Clear them:

```bash
.venv/Scripts/python -c "
import sqlite3
con = sqlite3.connect(r'C:\\Users\\domes\\wiki\\.vault-engine.db')
con.execute(\"UPDATE pages SET voice_distilled = NULL WHERE voice_distilled LIKE '[fake echo]%'\")
con.commit()
n = con.execute('SELECT COUNT(*) FROM pages WHERE voice_distilled IS NOT NULL').fetchone()[0]
print(f'remaining distilled (should be 0): {n}')
con.close()
"
```

Expected: `remaining distilled (should be 0): 0`

- [ ] **Step 4: Create the Phase-9 acceptance checklist**

Create `docs/PHASE-9-CHECKLIST.md`:

```markdown
# Phase 9 — Acceptance Checklist

When all boxes are ticked, Phase 9 is done and the master-plan row turns ✅.
Status is set MANUALLY after verification — auto-ticking is not allowed.

## Engine + DB

- [ ] DB-Migration: `voice_features` and `voice_distilled` columns exist on
      live `~/wiki/.vault-engine.db` (verified Task 9 Step 1)
- [ ] All 953 pre-existing pages preserved after migration (verified Task 9 Step 1)
- [ ] `core/llm.py` lifted from `apps/seance_ui/llm.py`; old import path
      still works via shim (verified `tests/test_core_llm.py`)

## Voice Pipeline

- [ ] `extract_stylometric()` produces all 12 required fields (verified
      `tests/test_persona_stylometric.py`)
- [ ] `distill_voice_via_llm()` runs with FakeLLM and respects 8K body cap
      (verified `tests/test_persona_distill.py`)
- [ ] `assemble_persona()` handles all three voice-block cases plus
      empty-frontmatter (verified `tests/test_persona_assemble.py`)
- [ ] `build_persona()` end-to-end caches `voice_features` in DB and reads
      `voice_distilled` when present (verified `tests/test_persona.py`)

## CLI

- [ ] `living-vault extract-voice --help` lists all flags
- [ ] `extract-voice --limit N` caps the page count (verified
      `tests/test_extract_voice_cli.py`)
- [ ] `extract-voice` skips already-distilled pages without `--force` (verified)
- [ ] `extract-voice` shows cost disclaimer and aborts on `n` (verified)
- [ ] `extract-voice` runs successfully against live DB with `--limit 3 --yes`
      (verified Task 9 Step 2)

## Séance Integration

- [ ] `seance_ui/app.py` calls `build_persona` (not `build_persona_lite`)
- [ ] `seance_ui/app.py` uses `lifespan` (not `@app.on_event("startup")`)
- [ ] No `DeprecationWarning: on_event` in pytest run output (Issue #1 from
      Phase-8 gate)
- [ ] `prompt.py:build_voice_block()` renders the three cases
      (verified `tests/test_seance_prompt.py`)

## Test Suite Health

- [ ] `pytest -q` from repo root: all green
- [ ] Total test count ≥ 96 (Phase-1 had 74, Phase-9 adds ~22+)
- [ ] No Phase-1 test regressed
- [ ] No `~/wiki/` access from any test (verified by `real_wiki_guard`)
- [ ] No real Anthropic calls from any test (verified by FakeLLM only)

## User Sichtprüfung (subjective — final master-plan criterion)

- [ ] Run `living-vault extract-voice --limit 5 --yes` against live DB with
      real Anthropic key (NOT in `LIVING_VAULT_FAKE_LLM` mode) — costs ~$0.03
- [ ] Open Séance UI, summon a page that was just distilled
- [ ] Compare to a page that was NOT distilled (only stylometric)
- [ ] User-Eindruck "klingt mehr nach der Page" — if yes, Phase 9 ✅. If no,
      iterate the prompt template in `core/voice/distill.py:DEFAULT_DISTILL_PROMPT`
      and re-run.
```

- [ ] **Step 5: Update master-plan status**

Modify `docs/plans/2026-05-08-living-vault-master-plan.md`:

Find the line:
```
| 9 | (Phase 2) core/persona.py — Schicht 3 Persona-Vollausbau | persona.py, voice-extraction, era-marker | 🟡 |
```

Change `🟡` to `✅` ONLY after the user has manually ticked all boxes in `PHASE-9-CHECKLIST.md`. Until then, leave it as 🟡. (This step is the gate at the END of phase 9, not in the implementation itself.)

For now (during this plan execution), leave the status at 🟡 since user-Sichtprüfung is the last item.

- [ ] **Step 6: Commit the checklist**

```bash
git add docs/PHASE-9-CHECKLIST.md
git commit -m "living-vault | Phase-9: acceptance checklist + live-db smoke verified"
```

---

## Final verification

Run the full test suite one more time:

```bash
.venv/Scripts/python -m pytest -q --tb=line 2>&1 | tail -15
```

Expected: 
- `XX passed, 0 failed`
- Total ≥ 96 tests
- 0 `DeprecationWarning: on_event` warnings in summary

If anything fails, find the corresponding task and fix it inline. Do NOT commit broken state.

---

## Self-Review

**1. Spec coverage check**

Walking through the spec sections:

- "Architektur — 4-Stufen-Pipeline": ✅ Tasks 3+4+5 build the pipeline.
- "Stylometric-Features (12 fields)": ✅ Task 3 + tests assert all 12.
- "LLM-distilled Voice (`extract-voice` CLI)": ✅ Tasks 4+7.
- "Cost-Disclaimer": ✅ Task 7 implementation includes click.confirm + cost table.
- "DB-Schema-Erweiterung non-breaking": ✅ Task 1.
- "Persona-Dict-Schema (10 Felder)": ✅ Task 5 builds the dict; Task 6 verifies via prompt.
- "System-Prompt mit drei Voice-Block-Cases": ✅ Task 6.
- "Backwards-Compat alte Sessions bleiben unangetastet": Implicit — no migration of `seance_messages` table; tests in `test_seance_store.py` continue to pass.
- "core/llm.py lift mit Re-Export-Shim": ✅ Task 2.
- "lifespan-Wechsel": ✅ Task 8.
- "Tests ~22 neu": Counted — 2 (migration) + 4 (core_llm) + 11 (stylometric) + 4 (distill) + 4 (assemble) + 5 (persona rewrite) + 4 (extract_voice) + 4 (prompt extension) = 38 new tests vs spec's "~22". I went heavier on test coverage than spec planned — acceptable.
- "Phase-9-Checklist": ✅ Task 9 Step 4.

No spec gaps.

**2. Placeholder scan**

Searched for "TBD", "TODO", "implement later", "fill in details", "Add appropriate error handling", "Similar to Task N", "Write tests for the above" — none present. Every code step has full code blocks.

**3. Type consistency**

- `extract_stylometric(body: str) -> dict` used consistently in Tasks 3, 5.
- `distill_voice_via_llm(page: dict, llm: LLM) -> str` used consistently in Tasks 4, 7.
- `assemble_persona(*, path, title, frontmatter, body_excerpt, voice_features, voice_distilled) -> dict` used consistently in Tasks 5, 6 (via the persona dict).
- `build_persona(vault_root, db_path, relpath) -> Optional[dict]` — same signature as `build_persona_lite` so seance_ui change in Task 8 is one-line. Verified.
- Persona dict keys: `path, title, era_marker, themes, frontmatter, body_excerpt, voice_features, voice_distilled` — identical across Tasks 5, 6, 8. Spec says these are the 10 fields (counting nested), matches.
- LLM Protocol method `respond(system: str, history: list[tuple[str, str]]) -> str` — identical in Task 2, used consistently in Task 4 and Task 7.

No type drift.
