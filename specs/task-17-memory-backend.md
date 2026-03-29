# Task 17: Memory Management Backend

## Objective
Extend the backend with new `memory.py` functions and `web.py` API endpoints needed by the Memory management page. The existing backend already has some of the pieces (list semantic, delete semantic, search both types, exploration summary), but several gaps must be filled.

## Requirements Covered
- REQ-MEM-05, REQ-MEM-06, REQ-MEM-07 (listing with counts)
- REQ-MEM-08, REQ-MEM-09, REQ-MEM-10 (unified search)
- REQ-MEM-12, REQ-MEM-13, REQ-MEM-14 (add semantic memory)
- REQ-MEM-15, REQ-MEM-16 (edit = delete + create)
- REQ-MEM-18, REQ-MEM-19, REQ-MEM-20 (individual delete)
- REQ-MEM-21, REQ-MEM-22, REQ-MEM-23, REQ-MEM-24 (bulk delete)
- REQ-MEM-25, REQ-MEM-26 (error handling)

## Existing Backend Inventory

Already implemented in `memory.py`:
- `list_semantic_memories(conn, project_id)` — returns `[{id, content, created_at}]`
- `delete_semantic_memory(conn, memory_id)` — deletes by ID
- `store_semantic_memory(conn, embedder, project_id, content)` — stores with embedding
- `search_episodic_memory(conn, embedder, query, project_id)` — vector search
- `search_semantic_memory(conn, embedder, query, project_id)` — vector search
- `get_exploration_summary(conn, project_id)` — returns `{explored_files, queries}`

Already implemented in `web.py`:
- `GET /api/projects/{id}/memory/exploration` — exploration summary
- `GET /api/projects/{id}/memory/semantic` — list semantic memories
- `POST /api/projects/{id}/memory/semantic` — add semantic memory
- `DELETE /api/projects/{id}/memory/semantic/{memory_id}` — delete semantic memory

## Changes Required

### 1. New functions in `memory.py`

#### `list_episodic_memories(conn, project_id) -> list[dict]`
List all episodic memory entries for a project. Return `[{id, query, file_paths, summary, created_at}]`, ordered by `created_at`.

#### `delete_episodic_memory(conn, memory_id) -> None`
Delete a single episodic memory entry by ID.

#### `bulk_delete_episodic_memory(conn, project_id) -> int`
Delete all episodic memory for a project. Return the number of rows deleted.

#### `bulk_delete_semantic_memory(conn, project_id) -> int`
Delete all semantic memory for a project. Return the number of rows deleted.

#### `bulk_delete_all_memory(conn, project_id) -> dict`
Delete both episodic and semantic memory for a project. Return `{episodic_deleted: int, semantic_deleted: int}`.

#### `search_memory(conn, embedder, query, project_id, top_k=10) -> list[dict]`
Unified search across both memory types. Performs:
1. Semantic (vector) search on both episodic and semantic tables.
2. Text-based substring filtering on both tables (SQL `LIKE '%query%'` on `query`/`summary` for episodic, `content` for semantic).
3. Merges and deduplicates results (by type + ID).
4. Returns `[{type: "episodic"|"semantic", id, score, ...fields}]` sorted by score descending.

### 2. New/updated API endpoints in `web.py`

#### `GET /api/projects/{id}/memory/episodic`
List all episodic memories for the project.

#### `DELETE /api/projects/{id}/memory/episodic/{memory_id}`
Delete a single episodic memory entry.

#### `PUT /api/projects/{id}/memory/semantic/{memory_id}`
Edit a semantic memory entry. Accepts `{content: string}`. Deletes the old entry and creates a new one with the updated content. Returns `{status: "updated", id: <new_id>}`.

#### `POST /api/projects/{id}/memory/search`
Unified memory search. Accepts `{query: string}`. Returns consolidated results from both memory types.

#### `DELETE /api/projects/{id}/memory/episodic`
Bulk delete all episodic memory for the project. Returns `{deleted: int}`.

#### `DELETE /api/projects/{id}/memory/semantic`
Bulk delete all semantic memory for the project. Returns `{deleted: int}`.

Note: The existing `GET` and single-item `DELETE` for semantic memory use distinct URL patterns, so the new bulk `DELETE /api/projects/{id}/memory/semantic` (no `/{memory_id}` suffix) does not conflict.

#### `DELETE /api/projects/{id}/memory`
Bulk delete all memory (both types) for the project. Returns `{episodic_deleted: int, semantic_deleted: int}`.

## Tests

All tests use mocked database connections (consistent with existing `test_memory.py` and `test_web.py` patterns).

### `test_memory.py` additions

- `test_list_episodic_memories_returns_entries` — returns entries with all fields
- `test_list_episodic_memories_empty` — returns empty list when none exist
- `test_delete_episodic_memory` — executes DELETE with correct ID
- `test_bulk_delete_episodic_memory` — deletes all for project, returns count
- `test_bulk_delete_semantic_memory` — deletes all for project, returns count
- `test_bulk_delete_all_memory` — deletes both types, returns counts
- `test_search_memory_combines_results` — returns results from both types, labeled
- `test_search_memory_deduplicates` — same entry from vector + text search appears once
- `test_search_memory_empty` — returns empty list when no matches

### `test_web.py` additions

- `test_list_episodic_memories` — GET returns list
- `test_delete_episodic_memory` — DELETE returns success
- `test_edit_semantic_memory` — PUT deletes old, creates new, returns new ID
- `test_edit_semantic_memory_empty_content` — PUT with empty content returns 400
- `test_search_memory` — POST returns consolidated results
- `test_bulk_delete_episodic` — DELETE returns count
- `test_bulk_delete_semantic` — DELETE returns count
- `test_bulk_delete_all` — DELETE returns both counts
- `test_memory_endpoints_404_for_missing_project` — all new endpoints return 404 for non-existent project

## Acceptance Criteria
- All new `memory.py` functions work correctly with mocked Oracle connections
- All new API endpoints return correct status codes and response shapes
- Edit (PUT) performs delete + create, not in-place update
- Bulk delete endpoints return counts of deleted rows
- Unified search merges and deduplicates results from both memory types
- All existing tests continue to pass
