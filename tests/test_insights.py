"""Tests for core.insights — Phase 12."""
from __future__ import annotations
from pathlib import Path
import time

import pytest

from living_vault.core import db as db_mod
from living_vault.core import insights as insights_mod


def _seed_session(db_path: Path, page_path: str = "x.md") -> int:
    """Create a real seance_sessions row so session_id FK validates."""
    con = db_mod.connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO seance_sessions(page_path, started_at, mode) VALUES (?, ?, ?)",
            (page_path, "2026-05-10T00:00:00Z", "single"),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def test_insert_and_get_roundtrip(db_path: Path):
    db_mod.initialize(db_path)
    sid = _seed_session(db_path)
    iid = insights_mod.insert_insight(
        db_path,
        page_path="concepts/foo.md",
        persona_path="concepts/foo.md",
        question="What is foo?",
        insight="Foo is the prelude to bar.",
        session_id=sid,
    )
    row = insights_mod.get_insight(db_path, iid)
    assert row is not None
    assert row["page_path"] == "concepts/foo.md"
    assert row["persona_path"] == "concepts/foo.md"
    assert row["question"] == "What is foo?"
    assert row["insight"] == "Foo is the prelude to bar."
    assert row["session_id"] == sid
    assert row["created_at"]  # non-empty ISO


def test_session_id_none_allowed(db_path: Path):
    db_mod.initialize(db_path)
    iid = insights_mod.insert_insight(
        db_path,
        page_path="x.md",
        persona_path="x.md",
        question="q",
        insight="standalone insight without session",
    )
    row = insights_mod.get_insight(db_path, iid)
    assert row["session_id"] is None


def test_invalid_session_id_raises(db_path: Path):
    db_mod.initialize(db_path)
    with pytest.raises(ValueError, match="does not exist"):
        insights_mod.insert_insight(
            db_path,
            page_path="x.md",
            persona_path="x.md",
            question="q",
            insight="i",
            session_id=99999,
        )


def test_empty_fields_raise(db_path: Path):
    db_mod.initialize(db_path)
    with pytest.raises(ValueError):
        insights_mod.insert_insight(
            db_path, page_path="", persona_path="x.md",
            question="q", insight="i",
        )
    with pytest.raises(ValueError):
        insights_mod.insert_insight(
            db_path, page_path="x.md", persona_path="x.md",
            question="   ", insight="i",
        )
    with pytest.raises(ValueError):
        insights_mod.insert_insight(
            db_path, page_path="x.md", persona_path="x.md",
            question="q", insight="",
        )


def test_list_insights_filters_by_page(db_path: Path):
    db_mod.initialize(db_path)
    insights_mod.insert_insight(
        db_path, page_path="a.md", persona_path="a.md",
        question="q1", insight="ai",
    )
    insights_mod.insert_insight(
        db_path, page_path="b.md", persona_path="b.md",
        question="q2", insight="bi",
    )
    rows_a = insights_mod.list_insights(db_path, page_path="a.md")
    rows_b = insights_mod.list_insights(db_path, page_path="b.md")
    assert {r["page_path"] for r in rows_a} == {"a.md"}
    assert {r["page_path"] for r in rows_b} == {"b.md"}


def test_list_insights_filters_by_persona(db_path: Path):
    db_mod.initialize(db_path)
    insights_mod.insert_insight(
        db_path, page_path="a.md", persona_path="persona-x.md",
        question="q", insight="i",
    )
    insights_mod.insert_insight(
        db_path, page_path="a.md", persona_path="persona-y.md",
        question="q", insight="i",
    )
    rows = insights_mod.list_insights(db_path, persona_path="persona-x.md")
    assert len(rows) == 1
    assert rows[0]["persona_path"] == "persona-x.md"


def test_list_insights_limit_capped(db_path: Path):
    db_mod.initialize(db_path)
    for i in range(5):
        insights_mod.insert_insight(
            db_path, page_path=f"p{i}.md", persona_path="x.md",
            question="q", insight=f"insight {i}",
        )
    # Cap at 100, but request 200 — should not raise, just clamp.
    rows = insights_mod.list_insights(db_path, limit=200)
    assert len(rows) == 5  # only 5 were inserted, cap is 100
    rows_small = insights_mod.list_insights(db_path, limit=2)
    assert len(rows_small) == 2


def test_list_insights_orders_newest_first(db_path: Path):
    db_mod.initialize(db_path)
    iid_a = insights_mod.insert_insight(
        db_path, page_path="x.md", persona_path="x.md",
        question="q", insight="first",
    )
    time.sleep(0.01)  # ensure created_at differs
    iid_b = insights_mod.insert_insight(
        db_path, page_path="x.md", persona_path="x.md",
        question="q", insight="second",
    )
    rows = insights_mod.list_insights(db_path, page_path="x.md")
    assert [r["id"] for r in rows] == [iid_b, iid_a]


def test_migration_idempotent(db_path: Path):
    db_mod.initialize(db_path)
    db_mod.initialize(db_path)  # second call: no-op for additive Phase-12 table
    # Insertion still works after second initialize.
    iid = insights_mod.insert_insight(
        db_path, page_path="x.md", persona_path="x.md",
        question="q", insight="i",
    )
    assert iid > 0
