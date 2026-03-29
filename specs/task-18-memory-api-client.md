# Task 18: Memory Management API Client

## Objective
Add TypeScript API client functions in `frontend/src/lib/api.ts` for all memory management endpoints created in Task 17. These functions will be consumed by the Memory page component in Task 19.

## Requirements Covered
- REQ-MEM-05 through REQ-MEM-24 (all operations need frontend API access)

## Changes Required

### New types in `api.ts`

```typescript
export interface EpisodicMemory {
  id: number;
  query: string;
  file_paths: string[];
  summary: string;
  created_at: string | null;
}

export interface SemanticMemory {
  id: number;
  content: string;
  created_at: string | null;
}

export interface MemorySearchResult {
  type: "episodic" | "semantic";
  id: number;
  score: number;
  // Episodic fields (present when type === "episodic")
  query?: string;
  file_paths?: string[];
  summary?: string;
  created_at?: string | null;
  // Semantic fields (present when type === "semantic")
  content?: string;
}

export interface BulkDeleteResult {
  deleted: number;
}

export interface BulkDeleteAllResult {
  episodic_deleted: number;
  semantic_deleted: number;
}

export interface EditSemanticMemoryResult {
  status: string;
  id: number;
}
```

### New functions in `api.ts`

```typescript
// List all episodic memories for a project
listEpisodicMemories(projectId: number): Promise<EpisodicMemory[]>

// List all semantic memories for a project (already exists via list endpoint)
listSemanticMemories(projectId: number): Promise<SemanticMemory[]>

// Search across both memory types
searchMemory(projectId: number, query: string): Promise<MemorySearchResult[]>

// Delete a single episodic memory entry
deleteEpisodicMemory(projectId: number, memoryId: number): Promise<void>

// Edit a semantic memory entry (delete + re-create)
editSemanticMemory(projectId: number, memoryId: number, content: string): Promise<EditSemanticMemoryResult>

// Add a new semantic memory entry (already exists, ensure exported)
addSemanticMemory(projectId: number, content: string): Promise<{status: string}>

// Delete a single semantic memory entry (already exists, ensure exported)
deleteSemanticMemory(projectId: number, memoryId: number): Promise<void>

// Bulk delete all episodic memory for a project
bulkDeleteEpisodicMemory(projectId: number): Promise<BulkDeleteResult>

// Bulk delete all semantic memory for a project
bulkDeleteSemanticMemory(projectId: number): Promise<BulkDeleteResult>

// Bulk delete all memory for a project
bulkDeleteAllMemory(projectId: number): Promise<BulkDeleteAllResult>
```

## Tests

No dedicated frontend unit tests (consistent with existing project pattern). API client correctness is validated through the backend test suite (Task 17) and manual testing in Task 19.

## Acceptance Criteria
- All API client functions are implemented and exported from `api.ts`
- Types match the response shapes defined in Task 17
- Error responses are parsed and thrown as `Error` objects (consistent with existing `createProject`/`deleteProject` pattern)
- Existing API functions remain unchanged
