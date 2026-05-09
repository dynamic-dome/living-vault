from pathlib import Path
from living_vault.core import db as db_mod
from living_vault.apps.seance_ui.store import (
    new_session, add_message, get_history, list_sessions,
)
import json


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
    msgs = detail["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "wer bist du?"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "ich bin note-a"


def test_get_session_detail_unknown_returns_none(db_path: Path):
    from living_vault.apps.seance_ui.store import get_session_detail
    db_mod.initialize(db_path)
    assert get_session_detail(db_path, 9999) is None


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


def test_new_session_persists_mode(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md", mode="freeforall")
    # mode is persisted in seance_sessions, also reachable via the helper
    assert store.get_session_mode(db_path, sid) == "freeforall"


def test_new_session_default_mode_is_single(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/x.md")  # no mode kwarg
    assert store.get_session_mode(db_path, sid) == "single"


def test_get_session_mode_returns_none_for_unknown_session(db_path):
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    assert store.get_session_mode(db_path, 9999) is None


def test_add_and_get_session_personas_orders_by_seat_idx(db_path):
    """Insert in non-monotonic order to actually exercise ORDER BY."""
    from living_vault.core import db as db_mod
    from living_vault.apps.seance_ui import store
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/a.md", mode="roundrobin")
    # Insert seat_idx 2 first, then 0, then 1 — SELECT must still return 0,1,2
    store.add_session_persona(db_path, sid, "concepts/c.md", color="#c9b3ff", seat_idx=2)
    store.add_session_persona(db_path, sid, "concepts/a.md", color="#7adfd5", seat_idx=0)
    store.add_session_persona(db_path, sid, "concepts/b.md", color="#a8e6cf", seat_idx=1)

    rows = store.get_session_personas(db_path, sid)
    assert len(rows) == 3
    # ordered by seat_idx, NOT by insertion order
    assert rows[0]["seat_idx"] == 0
    assert rows[0]["persona_path"] == "concepts/a.md"
    assert rows[0]["color"] == "#7adfd5"
    assert rows[1]["seat_idx"] == 1
    assert rows[1]["persona_path"] == "concepts/b.md"
    assert rows[2]["seat_idx"] == 2
    assert rows[2]["persona_path"] == "concepts/c.md"


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
