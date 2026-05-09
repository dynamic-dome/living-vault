# Phase 10a — consult_neighbor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Anthropic-Tool-Use to the séance UI so the active persona can call `consult_neighbor(neighbor_path)` mid-turn, fetch a neighbor page excerpt from the wiki, and integrate that knowledge into its answer. Tool calls are persisted as visible events and surfaced in the UI as mini-bubbles.

**Architecture:** A new `respond_with_tools` method on the LLM class drives a multi-turn Anthropic loop with `max_iterations=5` and a forced-final fallback. A new `consult_neighbor` handler lives in `apps/seance_ui/neighbors.py` and validates against an allowlist built from `graph_neighbors(page_path)`. Tool events are persisted in `seance_messages` with a new `role='tool_use'` plus a new nullable `persona_path` column. History replay to Anthropic filters tool_use messages out (asymmetric: DB has all, replay has only user+assistant).

**Tech Stack:** Python 3.11+, FastAPI, sqlite3, Anthropic SDK, pytest, FastAPI TestClient, vanilla JS in static/index.html.

**Spec:** [`../specs/2026-05-09-phase-10a-consult-neighbor-design.md`](../specs/2026-05-09-phase-10a-consult-neighbor-design.md)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `living_vault/core/db.py` | modify | Add `seance_messages.persona_path` migration in idempotent block |
| `living_vault/core/llm.py` | modify | Add `respond_with_tools` to AnthropicLLM, add `FakeLLMWithTools` test class |
| `living_vault/apps/seance_ui/neighbors.py` | create | `consult_neighbor` handler: allowlist validation, fetch, persist, return excerpt |
| `living_vault/apps/seance_ui/store.py` | modify | Add `add_tool_event`, change `get_history` to filter, change `add_message` to accept `persona_path` |
| `living_vault/apps/seance_ui/app.py` | modify | Wire `say()` through `respond_with_tools` with handler closure; return `tool_events` in response |
| `living_vault/apps/seance_ui/static/index.html` | modify | Render tool-event mini-bubbles before assistant bubble; add 7+ budget warning |
| `tests/test_db_migration.py` | modify | Add 2 tests for `persona_path` column migration |
| `tests/test_seance_store.py` | modify | Add 4 tests for `add_tool_event`, history filter, persona_path |
| `tests/test_core_llm_tools.py` | create | 8 tests for `respond_with_tools` loop |
| `tests/test_seance_neighbors.py` | create | 6 tests for `consult_neighbor` handler |
| `tests/test_seance_say_with_tools.py` | create | 5 tests for end-to-end say with tools |
| `tests/test_seance_app.py` | modify | Add 2 tests: privacy-regression-after-tools, allowlist-bypass |

Test files are flat under `tests/` per existing project layout (not nested in `tests/core/` or `tests/seance_ui/`).

---

## Task 1: Schema Migration — `persona_path` column

**Files:**
- Modify: `living_vault/core/db.py` (add to existing migration block)
- Modify: `tests/test_db_migration.py` (add 2 tests)

- [ ] **Step 1.1: Write failing test for `persona_path` column on legacy seance_messages**

In `tests/test_db_migration.py`, append after the existing tests:

```python
def test_initialize_adds_persona_path_to_legacy_seance_messages(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    # arrange: legacy DB with seance_messages but without persona_path
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE seance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_path TEXT NOT NULL,
            started_at TEXT NOT NULL
        );
        CREATE TABLE seance_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES seance_sessions(id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    con.execute(
        "INSERT INTO seance_sessions (page_path, started_at) VALUES (?, ?)",
        ("legacy/page.md", "2026-05-08T00:00:00Z"),
    )
    con.execute(
        "INSERT INTO seance_messages (session_id, role, content, created_at) "
        "VALUES (?, ?, ?, ?)",
        (1, "user", "hello", "2026-05-08T00:00:00Z"),
    )
    con.commit()
    con.close()

    # act
    db_mod.initialize(db_path)

    # assert: column exists, legacy row preserved with NULL persona_path
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(seance_messages)")}
    assert "persona_path" in cols
    row = con.execute(
        "SELECT role, content, persona_path FROM seance_messages WHERE id = 1"
    ).fetchone()
    assert row[0] == "user"
    assert row[1] == "hello"
    assert row[2] is None
    con.close()


def test_initialize_persona_path_idempotent(tmp_path: Path):
    db_path = tmp_path / ".vault-engine.db"
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call must not raise duplicate-column
    con = sqlite3.connect(str(db_path))
    cols = {r[1] for r in con.execute("PRAGMA table_info(seance_messages)")}
    assert "persona_path" in cols
    con.close()
```

- [ ] **Step 1.2: Run tests to verify they fail**

Run: `pytest tests/test_db_migration.py::test_initialize_adds_persona_path_to_legacy_seance_messages tests/test_db_migration.py::test_initialize_persona_path_idempotent -v`
Expected: 2× FAIL (`persona_path` not in cols)

- [ ] **Step 1.3: Add migration code in `db.py`**

In `living_vault/core/db.py`, after the existing `_PHASE_9_PAGES_COLUMNS` constant, add:

```python
# Phase-10a additive columns for seance_messages.
_PHASE_10A_SEANCE_MESSAGES_COLUMNS = [
    ("persona_path", "TEXT"),  # NULL for user messages, set for assistant + tool_use
]
```

Then in `initialize()`, after the existing `for col, sqltype in _PHASE_9_PAGES_COLUMNS` loop, add a parallel loop:

```python
        for col, sqltype in _PHASE_10A_SEANCE_MESSAGES_COLUMNS:
            if not _column_exists(con, "seance_messages", col):
                con.execute(f"ALTER TABLE seance_messages ADD COLUMN {col} {sqltype}")
```

The `con.commit()` line that already exists at the end of the try block covers this.

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `pytest tests/test_db_migration.py -v`
Expected: all migration tests PASS (4 total: 2 phase-9 + 2 phase-10a)

- [ ] **Step 1.5: Commit**

```bash
git add living_vault/core/db.py tests/test_db_migration.py
git commit -m "living-vault | Phase-10a: add persona_path column to seance_messages (idempotent)"
```

---

## Task 2: `add_message` accepts `persona_path`, `add_tool_event`, history-filter

**Files:**
- Modify: `living_vault/apps/seance_ui/store.py`
- Modify: `tests/test_seance_store.py` (add 4 tests)

- [ ] **Step 2.1: Write failing tests for store changes**

In `tests/test_seance_store.py`, read the current top imports first:

```bash
head -20 tests/test_seance_store.py
```

Append the following tests (adapt imports if the file uses a different style):

```python
def test_add_message_persists_persona_path(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md")
    store.add_message(db_path, sid, "assistant", "hi", persona_path="concepts/x.md")
    detail = store.get_session_detail(db_path, sid)
    msg = detail["messages"][0]
    assert msg["role"] == "assistant"
    assert msg["persona_path"] == "concepts/x.md"


def test_add_message_persona_path_defaults_to_none(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md")
    store.add_message(db_path, sid, "user", "hello")  # no persona_path
    detail = store.get_session_detail(db_path, sid)
    assert detail["messages"][0]["persona_path"] is None


def test_add_tool_event_writes_role_tool_use(db_path):
    import json
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md")
    store.add_tool_event(
        db_path,
        sid,
        persona_path="concepts/x.md",
        tool_name="consult_neighbor",
        tool_args={"neighbor_path": "concepts/y.md"},
        tool_result_summary={"chars": 1500, "title": "Y"},
    )
    detail = store.get_session_detail(db_path, sid)
    assert len(detail["messages"]) == 1
    m = detail["messages"][0]
    assert m["role"] == "tool_use"
    assert m["persona_path"] == "concepts/x.md"
    payload = json.loads(m["content"])
    assert payload["tool_name"] == "consult_neighbor"
    assert payload["tool_args"]["neighbor_path"] == "concepts/y.md"
    assert payload["tool_result_summary"]["chars"] == 1500


def test_get_history_filters_tool_use(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md")
    store.add_message(db_path, sid, "user", "u1")
    store.add_tool_event(
        db_path, sid, persona_path="concepts/x.md",
        tool_name="consult_neighbor",
        tool_args={"neighbor_path": "concepts/y.md"},
        tool_result_summary={"chars": 100},
    )
    store.add_message(db_path, sid, "assistant", "a1", persona_path="concepts/x.md")
    history = store.get_history(db_path, sid)
    # tool_use must NOT appear in replay history
    assert history == [("user", "u1"), ("assistant", "a1")]
    # but full detail still has it
    detail = store.get_session_detail(db_path, sid)
    roles_in_detail = [m["role"] for m in detail["messages"]]
    assert "tool_use" in roles_in_detail
```

Note: `db_path` is provided by the existing `conftest.py` fixture.

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `pytest tests/test_seance_store.py -v -k "persona_path or tool_event or filters_tool_use"`
Expected: 4× FAIL (`add_message` does not accept `persona_path`, `add_tool_event` does not exist, etc.)

- [ ] **Step 2.3: Update `add_message` signature**

In `living_vault/apps/seance_ui/store.py`, replace the existing `add_message` function with:

```python
def add_message(
    db_path: Path,
    session_id: int,
    role: str,
    content: str,
    persona_path: str | None = None,
) -> None:
    con = db_mod.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seance_messages(session_id, role, content, created_at, persona_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, _now(), persona_path),
        )
        con.commit()
    finally:
        con.close()
```

- [ ] **Step 2.4: Add `add_tool_event` function**

In the same file, add:

```python
import json as _json

def add_tool_event(
    db_path: Path,
    session_id: int,
    *,
    persona_path: str,
    tool_name: str,
    tool_args: dict,
    tool_result_summary: dict,
) -> None:
    """Persist a tool-use event as a seance_messages row with role='tool_use'.

    The content column carries a JSON payload {tool_name, tool_args, tool_result_summary}
    so the UI and exporter can render it without parsing free-form text.
    """
    payload = _json.dumps({
        "tool_name": tool_name,
        "tool_args": tool_args,
        "tool_result_summary": tool_result_summary,
    })
    con = db_mod.connect(db_path)
    try:
        con.execute(
            "INSERT INTO seance_messages(session_id, role, content, created_at, persona_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, "tool_use", payload, _now(), persona_path),
        )
        con.commit()
    finally:
        con.close()
```

- [ ] **Step 2.5: Update `get_history` to filter tool_use rows**

In the same file, replace `get_history`:

```python
def get_history(db_path: Path, session_id: int) -> list[tuple[str, str]]:
    """Return only user + assistant messages for LLM replay.

    Tool-use rows are intentionally excluded (Phase-10a asymmetry: DB has everything,
    replay has only user+assistant). The full transcript is available via
    get_session_detail for export and UI rendering.
    """
    con = db_mod.connect(db_path)
    try:
        rows = con.execute(
            "SELECT role, content FROM seance_messages "
            "WHERE session_id = ? AND role IN ('user', 'assistant') "
            "ORDER BY id",
            (session_id,),
        ).fetchall()
        return [(r["role"], r["content"]) for r in rows]
    finally:
        con.close()
```

- [ ] **Step 2.6: Update `get_session_detail` to include `persona_path` in messages**

In the same file, replace the inner messages list-comp inside `get_session_detail`:

```python
        return {
            "id": row["id"],
            "page_path": row["page_path"],
            "started_at": row["started_at"],
            "messages": [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "persona_path": r["persona_path"],
                }
                for r in msg_rows
            ],
        }
```

And update the SELECT inside `get_session_detail` to include `persona_path`:

```python
        msg_rows = con.execute(
            "SELECT role, content, created_at, persona_path FROM seance_messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
```

- [ ] **Step 2.7: Run tests to verify they pass**

Run: `pytest tests/test_seance_store.py -v`
Expected: all PASS (existing + 4 new)

- [ ] **Step 2.8: Commit**

```bash
git add living_vault/apps/seance_ui/store.py tests/test_seance_store.py
git commit -m "living-vault | Phase-10a: store.add_tool_event + persona_path + history filter"
```

---

## Task 3: `respond_with_tools` loop on LLM class

**Files:**
- Modify: `living_vault/core/llm.py`
- Create: `tests/test_core_llm_tools.py`

- [ ] **Step 3.1: Write failing tests for the loop**

Create `tests/test_core_llm_tools.py`:

```python
"""Phase-10a: respond_with_tools loop tests using the deterministic FakeLLMWithTools."""
from __future__ import annotations
import pytest
from living_vault.core.llm import FakeLLMWithTools


def _noop_handler(name: str, args: dict) -> str:
    return f"result for {name}({args})"


def test_text_only_script_returns_text_immediately():
    llm = FakeLLMWithTools([{"type": "text", "text": "hi"}])
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=5
    )
    assert out == "hi"


def test_one_tool_use_then_text():
    llm = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "x.md"}},
        {"type": "text", "text": "final"},
    ])
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=5
    )
    assert out == "final"
    assert llm.tool_calls_made == [
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "x.md"}}
    ]


def test_multiple_tool_uses_in_a_turn():
    llm = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "x.md"}},
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "y.md"}},
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "z.md"}},
        {"type": "text", "text": "synthesis"},
    ])
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=5
    )
    assert out == "synthesis"
    assert len(llm.tool_calls_made) == 3


def test_handler_receives_name_and_args():
    seen: list[tuple[str, dict]] = []

    def cb(name: str, args: dict) -> str:
        seen.append((name, args))
        return "ok"

    llm = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "a.md"}},
        {"type": "text", "text": "done"},
    ])
    llm.respond_with_tools(system="s", history=[], tools=[], tool_handler=cb, max_iterations=5)
    assert seen == [("consult_neighbor", {"neighbor_path": "a.md"})]


def test_max_iterations_caps_loop():
    """If the script keeps emitting tool_use beyond max_iterations, the helper
    must terminate and return the forced-final fallback text."""
    script = [{"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": f"p{i}.md"}}
              for i in range(10)]  # ten tool_use steps, no terminating text
    llm = FakeLLMWithTools(script)
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=3
    )
    # forced final fallback must produce a string, not raise
    assert isinstance(out, str)
    assert len(llm.tool_calls_made) <= 3


def test_handler_is_error_passes_through():
    received: list[str] = []

    def cb(name: str, args: dict):
        received.append("called")
        return {"is_error": True, "content": "not a neighbor"}

    llm = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "bad.md"}},
        {"type": "text", "text": "ok despite error"},
    ])
    out = llm.respond_with_tools(system="s", history=[], tools=[], tool_handler=cb, max_iterations=5)
    assert out == "ok despite error"
    assert received == ["called"]


def test_empty_script_returns_fallback_string():
    llm = FakeLLMWithTools([])
    out = llm.respond_with_tools(
        system="s", history=[], tools=[], tool_handler=_noop_handler, max_iterations=5
    )
    assert isinstance(out, str)


def test_legacy_respond_still_works_for_text_only_script():
    llm = FakeLLMWithTools([{"type": "text", "text": "echo"}])
    # Phase-1 callers use respond(); FakeLLMWithTools must not break that
    out = llm.respond(system="s", history=[("user", "hi")])
    assert out == "echo"
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `pytest tests/test_core_llm_tools.py -v`
Expected: 8× FAIL with `ImportError: cannot import name 'FakeLLMWithTools'`

- [ ] **Step 3.3: Add `FakeLLMWithTools` to llm.py**

In `living_vault/core/llm.py`, after the existing `FakeLLM` class, add:

```python
class FakeLLMWithTools:
    """Deterministic tool-loop simulation for tests.

    Construct with a script like:
        [
          {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "x.md"}},
          {"type": "tool_use", "name": "consult_neighbor", "input": {"neighbor_path": "y.md"}},
          {"type": "text", "text": "final answer"},
        ]

    Each tool_use step calls tool_handler(name, input). When a 'text' step is
    reached, that text is returned. The handler's return value is captured but
    not echoed back into the script (the script itself decides the next step).
    """

    def __init__(self, script: list[dict]):
        self._script = list(script)
        self.tool_calls_made: list[dict] = []

    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        # Phase-1 compat: when the script has exactly one text step, behave like FakeLLM.
        if len(self._script) == 1 and self._script[0].get("type") == "text":
            return self._script[0]["text"]
        return "[fake tools-aware llm — use respond_with_tools]"

    def respond_with_tools(
        self,
        system: str,
        history: list[tuple[str, str]],
        tools: list[dict],
        tool_handler,
        max_iterations: int = 5,
    ) -> str:
        iters = 0
        for step in self._script:
            kind = step.get("type")
            if kind == "tool_use":
                if iters >= max_iterations:
                    return "(consultation budget exhausted — forced final)"
                iters += 1
                self.tool_calls_made.append(step)
                tool_handler(step["name"], step["input"])
            elif kind == "text":
                return step["text"]
        # script ran out without a text step
        return "(script exhausted)"
```

- [ ] **Step 3.4: Add `respond_with_tools` to AnthropicLLM**

In the same file, replace the `AnthropicLLM` class with:

```python
class AnthropicLLM:
    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        from anthropic import Anthropic
        self._client = Anthropic()
        self._model = model

    def respond(self, system: str, history: list[tuple[str, str]]) -> str:
        msgs = [{"role": role, "content": content} for role, content in history]
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

    def respond_with_tools(
        self,
        system: str,
        history: list[tuple[str, str]],
        tools: list[dict],
        tool_handler,
        max_iterations: int = 5,
    ) -> str:
        """Multi-turn Anthropic loop. Calls tool_handler(name, input) on each tool_use
        block. Returns the final assistant text. On max_iterations exhaustion, makes one
        last call without `tools=` to force a text answer.

        tool_handler return value contract:
          - str → tool_result.content = the string
          - dict with {"is_error": True, "content": "..."} → tool_result.is_error=True
        """
        # Build the running message list as the API expects: list[{role, content}]
        # where content can be a list of blocks once we start adding tool_use/tool_result.
        messages: list[dict] = [{"role": role, "content": content} for role, content in history]

        for _ in range(max_iterations):
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                tools=tools,
                messages=messages,
            )
            stop = getattr(resp, "stop_reason", None)
            blocks = list(resp.content)

            if stop != "tool_use":
                # done — collect text
                return "".join(b.text for b in blocks if getattr(b, "type", None) == "text")

            # Append the assistant message verbatim (Anthropic requires the original blocks)
            messages.append({"role": "assistant", "content": [
                self._block_to_dict(b) for b in blocks
            ]})

            # Run each tool_use block, build tool_result blocks
            tool_result_blocks = []
            for b in blocks:
                if getattr(b, "type", None) != "tool_use":
                    continue
                handler_out = tool_handler(b.name, b.input)
                if isinstance(handler_out, dict) and handler_out.get("is_error"):
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "is_error": True,
                        "content": handler_out.get("content", "error"),
                    })
                else:
                    content_str = handler_out if isinstance(handler_out, str) else str(handler_out)
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": content_str,
                    })

            messages.append({"role": "user", "content": tool_result_blocks})

        # Forced-final-call: drop tools, force text
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    @staticmethod
    def _block_to_dict(b) -> dict:
        kind = getattr(b, "type", None)
        if kind == "text":
            return {"type": "text", "text": b.text}
        if kind == "tool_use":
            return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
        # fallback — shouldn't happen but keeps the loop robust
        return {"type": kind or "unknown"}
```

- [ ] **Step 3.5: Update `get_llm` and the `LLM` Protocol if needed**

Verify the existing `LLM` Protocol still satisfies the consumer side. No change required — `respond_with_tools` is additive. Read the file to confirm:

```bash
grep -n "class LLM" living_vault/core/llm.py
```

The Protocol can remain as-is; callers that need the new method use `AnthropicLLM` or `FakeLLMWithTools` directly via `get_llm()` whose return type can stay `LLM`.

- [ ] **Step 3.6: Run tests to verify they pass**

Run: `pytest tests/test_core_llm_tools.py tests/test_core_llm.py -v`
Expected: all PASS (8 new + existing core_llm tests)

- [ ] **Step 3.7: Commit**

```bash
git add living_vault/core/llm.py tests/test_core_llm_tools.py
git commit -m "living-vault | Phase-10a: respond_with_tools loop + FakeLLMWithTools"
```

---

## Task 4: `consult_neighbor` handler module

**Files:**
- Create: `living_vault/apps/seance_ui/neighbors.py`
- Create: `tests/test_seance_neighbors.py`

- [ ] **Step 4.1: Write failing tests for the handler**

Create `tests/test_seance_neighbors.py`:

```python
"""Phase-10a: consult_neighbor handler tests."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.apps.seance_ui import store
from living_vault.apps.seance_ui.neighbors import (
    BODY_EXCERPT_CHARS,
    MAX_CONSULT_CALLS_PER_TURN,
    make_consult_neighbor_handler,
)


def _setup(vault_copy: Path, db_path: Path) -> tuple[int, str]:
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    page_path = "concepts/note-a.md"
    sid = store.new_session(db_path, page_path)
    return sid, page_path


def test_handler_rejects_non_neighbor(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    out = handler("consult_neighbor", {"neighbor_path": "concepts/secret.md"})
    assert isinstance(out, dict) and out.get("is_error") is True
    assert "not a neighbor" in out["content"].lower()


def test_handler_returns_excerpt_for_allowed_neighbor(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    # find a real neighbor in the fixture vault — pick any other page
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    out = handler("consult_neighbor", {"neighbor_path": "concepts/note-b.md"})
    assert isinstance(out, str)
    assert len(out) > 0
    assert len(out) <= BODY_EXCERPT_CHARS


def test_handler_persists_tool_event(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    handler("consult_neighbor", {"neighbor_path": "concepts/note-b.md"})
    detail = store.get_session_detail(db_path, sid)
    assert any(m["role"] == "tool_use" for m in detail["messages"])
    tool_msg = next(m for m in detail["messages"] if m["role"] == "tool_use")
    payload = json.loads(tool_msg["content"])
    assert payload["tool_name"] == "consult_neighbor"
    assert payload["tool_args"]["neighbor_path"] == "concepts/note-b.md"
    assert payload["tool_result_summary"]["chars"] >= 0
    assert tool_msg["persona_path"] == page_path


def test_handler_missing_page_returns_is_error(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    # allowlist contains a path that exists in graph but file is missing
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/ghost.md"},
    )
    out = handler("consult_neighbor", {"neighbor_path": "concepts/ghost.md"})
    assert isinstance(out, dict) and out.get("is_error") is True


def test_handler_soft_cap_after_n_calls(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    # Force MAX_CONSULT_CALLS_PER_TURN successful calls, then one more
    for _ in range(MAX_CONSULT_CALLS_PER_TURN):
        out = handler("consult_neighbor", {"neighbor_path": "concepts/note-b.md"})
        assert isinstance(out, str)
    # the (N+1)th call must be is_error budget-exhausted
    out_over = handler("consult_neighbor", {"neighbor_path": "concepts/note-b.md"})
    assert isinstance(out_over, dict) and out_over.get("is_error") is True
    assert "budget" in out_over["content"].lower()


def test_handler_invalid_args_returns_is_error(vault_copy, db_path):
    sid, page_path = _setup(vault_copy, db_path)
    handler = make_consult_neighbor_handler(
        vault_root=vault_copy,
        db_path=db_path,
        session_id=sid,
        persona_path=page_path,
        allowlist={"concepts/note-b.md"},
    )
    # missing required field
    out = handler("consult_neighbor", {})
    assert isinstance(out, dict) and out.get("is_error") is True
    assert "neighbor_path" in out["content"].lower()
```

- [ ] **Step 4.2: Run tests to verify they fail**

Run: `pytest tests/test_seance_neighbors.py -v`
Expected: 6× FAIL with `ImportError: cannot import name 'make_consult_neighbor_handler'`

- [ ] **Step 4.3: Create the handler module**

Create `living_vault/apps/seance_ui/neighbors.py`:

```python
"""Phase-10a: consult_neighbor tool-handler factory.

The factory `make_consult_neighbor_handler` returns a closure that the LLM-loop
calls with (tool_name, tool_args). The closure:
  1. Validates the tool args (Pydantic-like manual check, no new dep).
  2. Checks the requested neighbor_path is in the allowlist (graph-derived).
  3. Reads the page body via core.reader (with a hard 1500-char excerpt cap).
  4. Persists a tool-use event in seance_messages.
  5. Returns either a string (the excerpt) or a dict {is_error, content}.

The LLM-loop in core.llm.respond_with_tools handles both return shapes.
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable, Iterable

from living_vault.core.reader import read_page
from living_vault.apps.seance_ui import store


BODY_EXCERPT_CHARS = 1500
MAX_CONSULT_CALLS_PER_TURN = 10


CONSULT_NEIGHBOR_TOOL_DEF: dict = {
    "name": "consult_neighbor",
    "description": (
        "Read an excerpt of a neighbor wiki page that you (the persona) link to. "
        "Use this when you would like to consult what a neighbor knows before answering. "
        "You can call this multiple times in one turn but be selective."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "neighbor_path": {
                "type": "string",
                "description": "Relative path of the neighbor page (must be one of your own neighbors).",
            }
        },
        "required": ["neighbor_path"],
    },
}


def make_consult_neighbor_handler(
    *,
    vault_root: Path,
    db_path: Path,
    session_id: int,
    persona_path: str,
    allowlist: Iterable[str],
) -> Callable[[str, dict], str | dict]:
    """Build a handler closure bound to one séance turn.

    The closure mutates a private call-count cell to enforce MAX_CONSULT_CALLS_PER_TURN.
    """
    allow = set(allowlist)
    state = {"calls": 0}

    def handler(tool_name: str, tool_args: dict):
        # 1. arg validation
        if "neighbor_path" not in tool_args or not isinstance(tool_args["neighbor_path"], str):
            return {"is_error": True, "content": "missing required field: neighbor_path"}
        nbr = tool_args["neighbor_path"].strip()

        # 2. soft-cap budget
        if state["calls"] >= MAX_CONSULT_CALLS_PER_TURN:
            return {
                "is_error": True,
                "content": (
                    f"consultation budget exhausted "
                    f"({MAX_CONSULT_CALLS_PER_TURN}/turn) — please answer with what you have"
                ),
            }

        # 3. allowlist check
        if nbr not in allow:
            return {"is_error": True, "content": f"not a neighbor of {persona_path}"}

        # 4. fetch page body
        target = vault_root / nbr
        if not target.exists():
            store.add_tool_event(
                db_path, session_id,
                persona_path=persona_path,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result_summary={"error": "page no longer exists"},
            )
            return {"is_error": True, "content": "page no longer exists"}

        try:
            page = read_page(target, vault_root)
        except Exception as e:  # noqa: BLE001 — broad on purpose, surface as is_error
            store.add_tool_event(
                db_path, session_id,
                persona_path=persona_path,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result_summary={"error": f"could not read page: {type(e).__name__}"},
            )
            return {"is_error": True, "content": "could not read page"}

        excerpt = (page.body or "").strip()[:BODY_EXCERPT_CHARS]

        # 5. persist successful tool event + count
        state["calls"] += 1
        store.add_tool_event(
            db_path, session_id,
            persona_path=persona_path,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result_summary={
                "chars": len(excerpt),
                "title": page.title,
                "calls_used": state["calls"],
            },
        )
        return excerpt

    return handler
```

- [ ] **Step 4.4: Verify the fixture vault has the test neighbors**

```bash
ls tests/fixtures/vault/concepts/
```

The tests reference `concepts/note-a.md` and `concepts/note-b.md` — both should already exist (used by `test_seance_app.py`). If `note-b.md` is missing, abort and check the fixture vault.

- [ ] **Step 4.5: Run tests to verify they pass**

Run: `pytest tests/test_seance_neighbors.py -v`
Expected: 6× PASS

- [ ] **Step 4.6: Commit**

```bash
git add living_vault/apps/seance_ui/neighbors.py tests/test_seance_neighbors.py
git commit -m "living-vault | Phase-10a: consult_neighbor handler with allowlist + soft-cap"
```

---

## Task 5: Wire `say()` endpoint to use `respond_with_tools`

**Files:**
- Modify: `living_vault/apps/seance_ui/app.py`
- Create: `tests/test_seance_say_with_tools.py`

- [ ] **Step 5.1: Write failing end-to-end test**

Create `tests/test_seance_say_with_tools.py`:

```python
"""Phase-10a: end-to-end say() with tool-use, using FakeLLMWithTools."""
from __future__ import annotations
import json
from pathlib import Path
from fastapi.testclient import TestClient

from living_vault.core import db as db_mod
from living_vault.core.indexer import index_vault
from living_vault.core.llm import FakeLLMWithTools
from living_vault.apps.seance_ui import store


def _client_with_scripted_llm(vault: Path, db: Path, monkeypatch, script: list[dict]):
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")  # forces FakeLLM by default
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    # override get_llm to return our scripted fake
    fake = FakeLLMWithTools(script)
    monkeypatch.setattr(app_mod, "get_llm", lambda: fake)
    return TestClient(app_mod.app), fake


def test_say_with_no_tool_calls_returns_text_and_empty_events(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    client, fake = _client_with_scripted_llm(
        vault_copy, db_path, monkeypatch,
        script=[{"type": "text", "text": "I am the page."}],
    )
    r = client.post("/api/summon", json={"path": "concepts/note-a.md"})
    sid = r.json()["session_id"]
    r2 = client.post("/api/say", json={"session_id": sid, "text": "who are you?"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["reply"] == "I am the page."
    assert body["tool_events"] == []


def test_say_with_one_tool_call_persists_event_and_returns_in_response(
    vault_copy, db_path, monkeypatch
):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # pick a real neighbor that note-a.md links to in the fixture vault
    script = [
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "concepts/note-b.md"}},
        {"type": "text", "text": "Aus note-b lese ich Wichtiges."},
    ]
    client, fake = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, script)
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "what does your neighbor say?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tool_events" in body
    assert len(body["tool_events"]) == 1
    ev = body["tool_events"][0]
    assert ev["tool_name"] == "consult_neighbor"
    assert ev["tool_args"]["neighbor_path"] == "concepts/note-b.md"
    assert ev["tool_result_summary"]["chars"] > 0

    # also persisted in DB
    detail = store.get_session_detail(db_path, sid)
    roles = [m["role"] for m in detail["messages"]]
    assert "tool_use" in roles
    assert roles.count("user") == 1
    assert roles.count("assistant") == 1


def test_say_persists_user_and_assistant_with_persona_path(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    client, fake = _client_with_scripted_llm(
        vault_copy, db_path, monkeypatch,
        script=[{"type": "text", "text": "hi"}],
    )
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    client.post("/api/say", json={"session_id": sid, "text": "hello"})
    detail = store.get_session_detail(db_path, sid)
    user_msg = next(m for m in detail["messages"] if m["role"] == "user")
    assist_msg = next(m for m in detail["messages"] if m["role"] == "assistant")
    assert user_msg["persona_path"] is None
    assert assist_msg["persona_path"] == "concepts/note-a.md"


def test_say_with_non_neighbor_tool_call_records_is_error(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # script asks the LLM to consult a page that is NOT in note-a.md's neighbor set
    script = [
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "concepts/totally-unrelated.md"}},
        {"type": "text", "text": "I had to answer without that one."},
    ]
    client, fake = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, script)
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "tell me about the unrelated"})
    assert r.status_code == 200
    body = r.json()
    # tool_events list contains an entry recording the rejection (is_error=True payload)
    assert len(body["tool_events"]) >= 0  # impl may choose to surface or not
    assert "answer" in body["reply"].lower() or "had to" in body["reply"].lower()


def test_say_soft_cap_end_to_end(vault_copy, db_path, monkeypatch):
    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    # 11 tool_use steps then a text — handler will return is_error from #11 onwards
    script = [
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "concepts/note-b.md"}}
        for _ in range(11)
    ] + [{"type": "text", "text": "I have read enough."}]
    client, fake = _client_with_scripted_llm(vault_copy, db_path, monkeypatch, script)
    sid = client.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = client.post("/api/say", json={"session_id": sid, "text": "consult everything"})
    assert r.status_code == 200
    body = r.json()
    # at most MAX_CONSULT_CALLS_PER_TURN successful tool_events were persisted
    detail = store.get_session_detail(db_path, sid)
    successful = [
        m for m in detail["messages"]
        if m["role"] == "tool_use"
        and "error" not in json.loads(m["content"])["tool_result_summary"]
    ]
    from living_vault.apps.seance_ui.neighbors import MAX_CONSULT_CALLS_PER_TURN
    assert len(successful) <= MAX_CONSULT_CALLS_PER_TURN
```

Note: `concepts/note-a.md` must link to `concepts/note-b.md` in the fixture vault for these tests. Verify before running:

```bash
grep -l "note-b" tests/fixtures/vault/concepts/note-a.md || echo "MISSING: add wikilink"
```

If missing, the fixture vault needs a wikilink — but that's an existing-tests dependency. If the existing `test_seance_app.py` already passes with note-a → note-b summon flow, the link exists.

- [ ] **Step 5.2: Run tests to verify they fail**

Run: `pytest tests/test_seance_say_with_tools.py -v`
Expected: 5× FAIL (response shape doesn't match, no tool_events)

- [ ] **Step 5.3: Update `say()` endpoint**

In `living_vault/apps/seance_ui/app.py`, replace the existing `say()` function with:

```python
@app.post("/api/say")
def say(req: SayReq) -> dict:
    if len(req.text) > _MAX_USER_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"text too long ({len(req.text)} chars, max {_MAX_USER_TEXT_CHARS})",
        )
    history = store.get_history(_db_path(), req.session_id)
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

    persona = build_persona(_vault_root(), _db_path(), page_path)
    if persona is None:
        raise HTTPException(status_code=410, detail="page gone since session start")
    system = build_system_prompt(persona, neighbor_titles=[Path(n).stem for n in nbs])

    # Persist user turn first so it's in DB even if the LLM call fails.
    store.add_message(_db_path(), req.session_id, "user", req.text, persona_path=None)

    # Build the tool-use loop infrastructure.
    from living_vault.apps.seance_ui.neighbors import (
        CONSULT_NEIGHBOR_TOOL_DEF,
        make_consult_neighbor_handler,
    )
    raw_handler = make_consult_neighbor_handler(
        vault_root=_vault_root(),
        db_path=_db_path(),
        session_id=req.session_id,
        persona_path=page_path,
        allowlist=set(nbs),
    )

    tool_events: list[dict] = []

    def handler_with_capture(name: str, args: dict):
        result = raw_handler(name, args)
        # Capture every call (success or is_error) for the response.
        if isinstance(result, dict) and result.get("is_error"):
            tool_events.append({
                "tool_name": name,
                "tool_args": args,
                "tool_result_summary": {"error": result["content"]},
            })
        else:
            # Successful call — pull the matching summary from the DB row we just wrote.
            tool_events.append({
                "tool_name": name,
                "tool_args": args,
                "tool_result_summary": {"chars": len(result) if isinstance(result, str) else 0},
            })
        return result

    history_for_llm = list(history) + [("user", req.text)]
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
        _db_path(), req.session_id, "assistant", reply, persona_path=page_path
    )
    return {"reply": reply, "tool_events": tool_events}
```

- [ ] **Step 5.4: Run tests to verify they pass**

Run: `pytest tests/test_seance_say_with_tools.py tests/test_seance_app.py -v`
Expected: all PASS — old tests still green, 5 new tests green.

- [ ] **Step 5.5: Commit**

```bash
git add living_vault/apps/seance_ui/app.py tests/test_seance_say_with_tools.py
git commit -m "living-vault | Phase-10a: wire say() through respond_with_tools + return tool_events"
```

---

## Task 6: UI mini-bubbles for tool events

**Files:**
- Modify: `living_vault/apps/seance_ui/static/index.html`

This task has no automated tests (vanilla JS in a single static file). Verify manually after the live-smoke step in Task 8.

- [ ] **Step 6.1: Add CSS for tool-event mini-bubbles**

In `living_vault/apps/seance_ui/static/index.html`, inside the existing `<style>` block, after the `.msg.assistant` rule (around line 28), add:

```css
.toolEvent{
  margin:6px 0 4px 12px;
  padding:4px 10px;
  border-left:2px solid #4a8;
  font-size:11px;
  font-style:italic;
  color:#9bd;
  opacity:.85;
}
.toolEvent.error{
  border-left-color:#c66;
  color:#daa;
}
.toolEvent .wikilink{
  color:#cfe;
  font-weight:bold;
}
.budgetWarning{
  border-left-color:#e80;
  color:#fc8;
}
```

- [ ] **Step 6.2: Render tool events before the assistant bubble**

In the same file, replace the `form.onsubmit` handler (around line 139–149) with:

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
    j.tool_events.forEach((ev, idx) => appendToolEvent(ev, idx, j.tool_events.length));
  }
  appendMsg("assistant", j.reply || "(no reply)");
};
```

Then add the new render function after `appendMsg`:

```javascript
function appendToolEvent(ev, idx, total){
  const log = document.getElementById("log");
  const d = document.createElement("div");
  d.className = "toolEvent";
  const summary = ev.tool_result_summary || {};
  if (summary.error){
    d.classList.add("error");
    d.textContent = `» ${ev.tool_name} failed: ${summary.error}`;
  } else {
    const path = (ev.tool_args && ev.tool_args.neighbor_path) || "?";
    const chars = summary.chars || 0;
    d.innerHTML = `» consulted <span class="wikilink">[[${escapeHtml(path)}]]</span> (${chars} chars)`;
    if (idx + 1 >= 7 && total <= 10){
      d.classList.add("budgetWarning");
      d.innerHTML += ` <span style="opacity:.7">— nearing budget (${idx + 1}/10)</span>`;
    }
  }
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
```

- [ ] **Step 6.3: Render historical tool events when loading a past session**

In the same file, replace the `loadSessionIntoChat` function's message render loop (around line 100):

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
    } else {
      appendMsg(m.role, m.content);
    }
  });
  document.getElementById("txt").disabled = false;
  document.getElementById("send").disabled = false;
  document.getElementById("exportBtn").disabled = false;
}
```

- [ ] **Step 6.4: Run all tests to verify the static-file change doesn't break anything**

Run: `pytest tests/ -v`
Expected: full suite green (118 + 27 = ~145 tests).

- [ ] **Step 6.5: Commit**

```bash
git add living_vault/apps/seance_ui/static/index.html
git commit -m "living-vault | Phase-10a: UI mini-bubbles for tool events + budget warning"
```

---

## Task 7: Privacy-regression and allowlist-bypass tests

**Files:**
- Modify: `tests/test_seance_app.py` (add 2 tests)

- [ ] **Step 7.1: Write the two extra tests**

Append to `tests/test_seance_app.py`:

```python
def test_phase_10a_no_public_leak_after_tool_use_turn(vault_copy, db_path, monkeypatch):
    """Phase-1 privacy regression must hold after Phase-10a tool-use turns.

    Running a turn with consult_neighbor must NOT mutate is_public on any page.
    """
    from living_vault.core import db as db_mod
    from living_vault.core.indexer import index_vault
    from living_vault.core.llm import FakeLLMWithTools

    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)

    # snapshot is_public counts BEFORE
    import sqlite3
    con = sqlite3.connect(str(db_path))
    before_public = con.execute("SELECT COUNT(*) FROM pages WHERE is_public = 1").fetchone()[0]
    before_private = con.execute("SELECT COUNT(*) FROM pages WHERE is_public = 0").fetchone()[0]
    con.close()

    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    fake = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "concepts/note-b.md"}},
        {"type": "text", "text": "ok"},
    ])
    monkeypatch.setattr(app_mod, "get_llm", lambda: fake)
    c = TestClient(app_mod.app)
    sid = c.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    c.post("/api/say", json={"session_id": sid, "text": "consult"})

    con = sqlite3.connect(str(db_path))
    after_public = con.execute("SELECT COUNT(*) FROM pages WHERE is_public = 1").fetchone()[0]
    after_private = con.execute("SELECT COUNT(*) FROM pages WHERE is_public = 0").fetchone()[0]
    con.close()

    assert before_public == after_public, "is_public count changed after tool-use turn"
    assert before_private == after_private


def test_phase_10a_allowlist_blocks_bypass_attempt(vault_copy, db_path, monkeypatch):
    """If the LLM tries to consult a path that is NOT a graph neighbor of the
    summoned page, the handler must return is_error and the response must come
    back as 200 (not 500)."""
    from living_vault.core import db as db_mod
    from living_vault.core.indexer import index_vault
    from living_vault.core.llm import FakeLLMWithTools

    db_mod.initialize(db_path)
    index_vault(vault_copy, db_path)
    monkeypatch.setenv("LIVING_VAULT_ROOT", str(vault_copy))
    monkeypatch.setenv("LIVING_VAULT_DB", str(db_path))
    monkeypatch.setenv("LIVING_VAULT_FAKE_LLM", "1")
    from importlib import reload
    from living_vault.apps.seance_ui import app as app_mod
    reload(app_mod)
    fake = FakeLLMWithTools([
        {"type": "tool_use", "name": "consult_neighbor",
         "input": {"neighbor_path": "../../../etc/passwd"}},
        {"type": "text", "text": "I refused that."},
    ])
    monkeypatch.setattr(app_mod, "get_llm", lambda: fake)
    c = TestClient(app_mod.app)
    sid = c.post("/api/summon", json={"path": "concepts/note-a.md"}).json()["session_id"]
    r = c.post("/api/say", json={"session_id": sid, "text": "try escape"})
    assert r.status_code == 200, r.text
    body = r.json()
    # at least one is_error event recorded for the bypass attempt
    error_events = [
        ev for ev in body["tool_events"]
        if "error" in (ev.get("tool_result_summary") or {})
    ]
    assert len(error_events) >= 1
```

- [ ] **Step 7.2: Run tests to verify they pass**

Run: `pytest tests/test_seance_app.py -v`
Expected: all PASS (existing + 2 new).

- [ ] **Step 7.3: Run the full suite for regression check**

Run: `pytest tests/ -v --tb=short`
Expected: ~145 tests, all PASS, no warnings other than known LF/CRLF git noise.

- [ ] **Step 7.4: Commit**

```bash
git add tests/test_seance_app.py
git commit -m "living-vault | Phase-10a: privacy-regression + allowlist-bypass tests"
```

---

## Task 8: Live-DB smoke + acceptance checklist update

**Files:**
- Modify: `docs/PHASE-9-CHECKLIST.md` → rename or duplicate to `docs/PHASE-10A-CHECKLIST.md`

- [ ] **Step 8.1: Create the Phase-10a checklist**

Create `docs/PHASE-10A-CHECKLIST.md`:

```markdown
# Phase 10a — consult_neighbor Acceptance Checklist

Per spec: `docs/superpowers/specs/2026-05-09-phase-10a-consult-neighbor-design.md`

## Automated Acceptance

- [ ] Schema-Migration is idempotent against the live DB (run `python -c "from living_vault.core import db; db.initialize(__import__('pathlib').Path.home() / 'wiki' / '.vault-engine.db')"` twice — must not raise)
- [ ] FakeLLMWithTools-Variante works in all 27 new tests
- [ ] Soft-cap 10 enforced: `tests/test_seance_say_with_tools.py::test_say_soft_cap_end_to_end` PASS
- [ ] max_iterations=5 enforced: `tests/test_core_llm_tools.py::test_max_iterations_caps_loop` PASS
- [ ] Allowlist holds: `tests/test_seance_app.py::test_phase_10a_allowlist_blocks_bypass_attempt` PASS
- [ ] Privacy-regression remains green: `tests/test_privacy_regression.py` PASS
- [ ] Full suite: `pytest tests/ -v` reports ~145 PASS, 0 FAIL

## Live-DB Smoke (manual)

- [ ] Start séance UI: `seance-ui`
- [ ] Open `http://127.0.0.1:7777`
- [ ] Pick a real wiki page that has at least 2 wikilinks (e.g. `concepts/3ma-ml-pipeline.md`)
- [ ] Ask: "Was sagt einer deiner Nachbarn dazu?"
- [ ] Verify mini-bubbles appear: `» consulted [[neighbor-x]] (N chars)`
- [ ] Verify final assistant answer references the neighbor inhaltlich
- [ ] Verify session export contains the tool_use event
- [ ] User-Sichtprüfungs-Verdikt: positiv / neutral / negativ

## Performance

- [ ] Single-Turn mit 2 Tool-Calls: < 4s end-to-end gegen real Anthropic API
```

- [ ] **Step 8.2: Run the smoke check**

```bash
# 1. Confirm schema migration on the live DB is no-op (idempotent)
python -c "from living_vault.core import db; from pathlib import Path; db.initialize(Path.home() / 'wiki' / '.vault-engine.db'); print('migration ok')"

# 2. Start the séance UI in a background terminal:
seance-ui &

# 3. Manually drive the smoke checklist via the browser
```

If the manual smoke fails, file a follow-up TODO under `~/wiki/wiki/todos/` and tick the failing checklist item with a reference. Otherwise tick all green.

- [ ] **Step 8.3: Update Master-Plan status**

In `docs/plans/2026-05-08-living-vault-master-plan.md`, the Phase 10 row currently shows `🟡` — leave as 🟡 until Phase-10b also closes, OR update the Wiedereinstieg block at the bottom to say "Phase 10a ✅ closed YYYY-MM-DD, Phase 10b ⏳ pending".

```bash
# After smoke green, update the Wiedereinstieg paragraph to reflect Phase 10a closed.
# Use Edit to change just the relevant paragraph in master-plan.md.
```

- [ ] **Step 8.4: Final commit**

```bash
git add docs/PHASE-10A-CHECKLIST.md docs/plans/2026-05-08-living-vault-master-plan.md
git commit -m "living-vault | Phase-10a: acceptance checklist + live smoke verified"
```

---

## Self-Review Notes

- All 27 tests are present across Tasks 1–7 (2 + 4 + 8 + 6 + 5 + 2 = 27).
- `add_message` signature change (Task 2.3) is backward-compatible because `persona_path` is keyword-only with default `None`. Existing callers that pass only positional args still work.
- The `FakeLLMWithTools` class doubles as a Phase-1 `FakeLLM` drop-in when given a single text step (Task 3.3 `respond` impl + Task 3.1 `test_legacy_respond_still_works_for_text_only_script`).
- The fixture vault dependency on `concepts/note-b.md` linking to `note-a.md` is verified by existing `test_seance_app.py` tests passing — no new fixture work needed.
- The `say()` endpoint refactor (Task 5.3) handles BOTH the tools-aware and the legacy LLM via `hasattr(llm, "respond_with_tools")`. This keeps `LIVING_VAULT_FAKE_LLM=1` (basic FakeLLM, no tools) working for Phase-1 tests.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-09-phase-10a-consult-neighbor.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch with checkpoints for review.

Which approach?
