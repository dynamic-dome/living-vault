from living_vault.apps.seance_ui import store
from living_vault.apps.seance_ui.belief_evolution import summarize_belief_evolution
from living_vault.core import db as db_mod


def test_belief_evolution_single_mode_tracks_first_and_latest(db_path):
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/note-a.md")
    store.add_message(db_path, sid, "user", "What matters first?")
    store.add_message(db_path, sid, "assistant", "Alpha is the opening stance.", persona_path="concepts/note-a.md")
    store.add_message(db_path, sid, "user", "And now?")
    store.add_message(db_path, sid, "assistant", "Alpha now includes beta.", persona_path="concepts/note-a.md")

    trace = summarize_belief_evolution(db_path, sid)

    assert trace is not None
    assert trace["mode"] == "single"
    assert trace["participants"] == ["concepts/note-a.md"]
    assert trace["turn_count"] == 2
    assert trace["timeline"][0] == {"turn": 1, "role": "user", "text": "What matters first?"}
    arc = trace["persona_arcs"][0]
    assert arc["first_stance"] == "Alpha is the opening stance."
    assert arc["latest_stance"] == "Alpha now includes beta."
    assert arc["response_count"] == 2
    assert arc["changed"] is True


def test_belief_evolution_roundtable_separates_persona_arcs(db_path):
    db_mod.initialize(db_path)
    sid = store.new_session(db_path, "concepts/note-a.md", mode="roundrobin")
    store.add_session_persona(db_path, sid, "concepts/note-a.md", color="#aaa", seat_idx=0)
    store.add_session_persona(db_path, sid, "concepts/note-b.md", color="#bbb", seat_idx=1)
    store.add_message(db_path, sid, "user", "Discuss.")
    store.add_message(db_path, sid, "assistant", "A stance.", persona_path="concepts/note-a.md")
    store.add_message(db_path, sid, "assistant", "B stance.", persona_path="concepts/note-b.md")

    trace = summarize_belief_evolution(db_path, sid)

    assert trace is not None
    assert trace["mode"] == "roundrobin"
    assert trace["participants"] == ["concepts/note-a.md", "concepts/note-b.md"]
    arcs = {arc["persona_path"]: arc for arc in trace["persona_arcs"]}
    assert arcs["concepts/note-a.md"]["latest_stance"] == "A stance."
    assert arcs["concepts/note-b.md"]["latest_stance"] == "B stance."


def test_belief_evolution_unknown_session_returns_none(db_path):
    db_mod.initialize(db_path)

    assert summarize_belief_evolution(db_path, 9999) is None
