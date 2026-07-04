# Séance RAG Evolution 05: Persona Constellations

## Goal

Let the user ask the RAG for ready-made discussion circles, not just single
personas. A constellation is a small set of existing pages that can be summoned
through the existing roundtable UI.

## User Contract

- The user enters a query in the existing RAG-summon search box.
- The UI can request constellation candidates for that query.
- Each constellation contains only metadata: label, reason, relative paths, and
  titles.
- Clicking a constellation selects all its pages in the existing page picker.
- The user still chooses the mode and can still enable Semantic Archive before
  summoning.

## Non-Goals

- No new séance session mode.
- No new prompt memory or hidden injected context.
- No page bodies, excerpts, or absolute filesystem paths in the candidate API.
- No persistence of constellations.

## Backend Shape

New module:

`living_vault/apps/seance_ui/constellations.py`

Public function:

```python
suggest_constellations(db_path: Path, query: str, *, limit: int = 3, size: int = 3) -> dict
```

Response shape:

```json
{
  "query": "...",
  "constellations": [
    {
      "label": "note-a + 2",
      "reason": "semantic seed with graph and archive complements",
      "paths": ["concepts/note-a.md", "concepts/note-b.md"],
      "titles": ["Note A", "Note B"]
    }
  ]
}
```

Selection algorithm:

1. Validate query with the same empty/length behavior as RAG-Summon.
2. Use semantic search to find seed pages.
3. For each seed, add graph neighbors first.
4. Fill remaining seats from semantic candidates that are not already in the
   group.
5. Keep each group between 2 and `size` pages.
6. Deduplicate groups by sorted path set.
7. Cap output to `limit`.

## HTTP API

`POST /api/constellations`

Request:

```json
{"query": "memory atlas", "limit": 3, "size": 3}
```

Errors mirror RAG-Summon:

- `400` empty query
- `413` query too long

## Frontend

Add a second button in the existing RAG search row:

- `seek` keeps returning individual persona candidates.
- `circles` returns constellation candidates.

Render constellation items below single candidates. A click selects all paths;
double-click selects all paths and immediately summons the existing circle.

## Compatibility

- Existing `/api/summon-candidates` stays unchanged.
- Existing `/api/summon` stays unchanged.
- Existing mode selector and Semantic Archive checkbox remain the only controls
  that affect session behavior.

## Tests

1. Unit: constellations include seed plus graph/semantic complements and no
   duplicate paths.
2. Unit: empty query is rejected.
3. Endpoint: `/api/constellations` returns metadata-only constellation objects.
4. UI/browser smoke: request circles, select one, existing mode row appears and
   summon still works.

## Self-Review

- Privacy: PASS. API returns relative paths and titles only.
- Backward compatibility: PASS. No existing endpoint changes.
- Failure mode: PASS. Missing embeddings simply yields empty constellations via
  semantic search, not a broken session.
- Scope: PASS. The feature only improves selection before session creation.
