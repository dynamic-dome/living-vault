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


def test_list_sessions_includes_message_count(db_path: Path):
    db_mod.initialize(db_path)
    s1 = new_session(db_path, page_path="concepts/note-a.md")
    add_message(db_path, s1, "user", "hi")
    add_message(db_path, s1, "assistant", "hello")
    add_message(db_path, s1, "user", "more")
    s2 = new_session(db_path, page_path="concepts/note-b.md")
    rows = list_sessions(db_path)
    by_id = {r["id"]: r for r in rows}
    assert by_id[s1]["message_count"] == 3
    assert by_id[s2]["message_count"] == 0


def test_get_session_detail_returns_messages(db_path: Path):
    from living_vault.apps.seance_ui.store import get_session_detail
    db_mod.initialize(db_path)
    sid = new_session(db_path, page_path="concepts/note-a.md")
    add_message(db_path, sid, "user", "wer bist du?")
    add_message(db_path, sid, "assistant", "ich bin note-a")
    detail = get_session_detail(db_path, sid)
    assert detail is not None
    assert detail["page_path"] == "concepts/note-a.md"
    assert detail["messages"] == [
        {"role": "user", "content": "wer bist du?"},
        {"role": "assistant", "content": "ich bin note-a"},
    ]


def test_get_session_detail_unknown_returns_none(db_path: Path):
    from living_vault.apps.seance_ui.store import get_session_detail
    db_mod.initialize(db_path)
    assert get_session_detail(db_path, 9999) is None
