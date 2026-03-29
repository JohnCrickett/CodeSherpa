# Task 10: Ingestion Progress API

## Objective
Add backend API endpoints for creating projects, triggering ingestion, and streaming real-time progress via Server-Sent Events (SSE).

## Requirements Covered
- REQ-WEB-02, REQ-WEB-03, REQ-WEB-04, REQ-WEB-05, REQ-WEB-06 (project creation with validation)
- REQ-WEB-07, REQ-WEB-08, REQ-WEB-09, REQ-WEB-10, REQ-WEB-11, REQ-WEB-12 (ingestion trigger and progress)
- REQ-WEB-13, REQ-WEB-14, REQ-WEB-15, REQ-WEB-16 (re-ingestion)

## Changes Required

### 1. Refactor `ingest()` to support a progress callback

File: `codesherpa/ingestion.py`

Add an optional `progress_callback` parameter to `ingest()`. The callback receives structured progress events at each phase:
- `{"phase": "parsing", "detail": "Parsing codebase..."}`
- `{"phase": "embedding", "batch": 3, "total_batches": 10}`
- `{"phase": "storing", "file": "src/main.py", "current": 5, "total": 12}`
- `{"phase": "complete", "stats": {...}}`
- `{"phase": "error", "message": "..."}`

The existing `tqdm` progress bars should still work when no callback is provided (CLI usage).

### 2. New API endpoints in `codesherpa/web.py`

**POST /api/projects** — Create a new project
- Request body: `{ "name": string, "source": string }`
- Calls `resolve_source()` to validate/clone, then `create_project()`
- Returns: `{ "id": number, "name": string, "source_path": string }` or 400/409 error

**POST /api/projects/{project_id}/ingest** — Start ingestion (returns SSE stream)
- Runs ingestion in a background thread
- Returns `text/event-stream` with progress events
- Tracks active ingestion per project to prevent concurrent runs (in-memory set)
- On completion: updates project stats and sends final summary event
- On error: sends error event

### 3. Source resolution for GitHub URLs

The `resolve_source()` function in `repo.py` already handles both local paths and GitHub URLs. The API endpoint should call this before creating the project, returning appropriate HTTP errors for invalid sources.

For re-ingestion of GitHub-sourced projects (REQ-WEB-15), `resolve_source()` already does `git pull` on existing clones, so calling it again before ingestion handles this automatically.

## Tests

### `tests/test_web.py` (additions)

- `POST /api/projects` with valid name and source returns 201 with project data
- `POST /api/projects` with duplicate name returns 409
- `POST /api/projects` with empty name returns 400
- `POST /api/projects` with invalid source path returns 400
- `POST /api/projects/{id}/ingest` returns SSE stream with progress events
- `POST /api/projects/{id}/ingest` while already ingesting returns 409
- `POST /api/projects/{id}/ingest` for non-existent project returns 404
- Progress callback in `ingest()` receives expected events during ingestion

## Acceptance Criteria
- Project creation validates input and returns clear errors
- Ingestion streams real-time progress via SSE
- Concurrent ingestion of the same project is blocked
- Project stats are updated after ingestion completes
- Re-ingestion works identically (same endpoint, change detection in `ingest()` handles it)
