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
