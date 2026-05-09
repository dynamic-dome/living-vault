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
