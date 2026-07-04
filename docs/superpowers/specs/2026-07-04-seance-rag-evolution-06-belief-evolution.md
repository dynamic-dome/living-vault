# Séance RAG Evolution 06: Belief Evolution

## Goal

Make the conversation inspectable as an evolving set of page-perspectives. The
feature should help the user see how each summoned persona's visible stance
changed during a session, without inventing hidden memory.

## User Contract

- A running or loaded séance session exposes a `trace` action.
- The trace shows:
  - participants
  - user-turn count
  - a compact timeline
  - for each persona: first visible stance, latest visible stance, response count
- The trace is derived only from persisted `seance_messages`.

## Non-Goals

- No LLM summarization call.
- No persistence of inferred beliefs.
- No mutation of page files, insights, or personas.
- No claim that a page has permanently changed its beliefs.

## Backend Shape

New module:

`living_vault/apps/seance_ui/belief_evolution.py`

Public function:

```python
summarize_belief_evolution(db_path: Path, session_id: int) -> dict | None
```

Response shape:

```json
{
  "session_id": 1,
  "page_path": "concepts/note-a.md",
  "mode": "roundrobin",
  "participants": ["concepts/note-a.md", "concepts/note-b.md"],
  "turn_count": 2,
  "timeline": [
    {"turn": 1, "role": "user", "text": "..."},
    {"turn": 1, "role": "assistant", "persona_path": "concepts/note-a.md", "stance": "..."}
  ],
  "persona_arcs": [
    {
      "persona_path": "concepts/note-a.md",
      "response_count": 2,
      "first_stance": "...",
      "latest_stance": "...",
      "changed": true
    }
  ]
}
```

## HTTP API

`GET /api/sessions/{session_id}/belief-evolution`

- `200` with trace if session exists
- `404` if session does not exist

## Frontend

Add a small `trace` button next to `seal record`.

On click:

- Fetch the trace endpoint.
- Append a compact assistant-style bubble into the current log.
- Do not alter the session or write messages to the DB.

## Compatibility

- Existing export format stays unchanged.
- Existing session detail endpoint stays unchanged.
- Existing MCP insight tools stay unchanged.

## Tests

1. Unit: single-mode trace extracts first/latest stance.
2. Unit: roundtable trace separates persona arcs.
3. Endpoint: unknown session returns 404.
4. UI/browser smoke: after one turn, `trace` appends a visible Belief Evolution
   bubble without console errors.

## Self-Review

- Honesty: PASS. It reports persisted transcript facts, not hidden cognition.
- Safety: PASS. Read-only endpoint; no page or insight writes.
- Compatibility: PASS. Existing session/export APIs are additive.
- UI scope: PASS. One small action button and one rendered bubble.
