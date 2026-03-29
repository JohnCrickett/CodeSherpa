# Task 19: Memory Management Page

## Objective
Build the Memory page frontend component (`MemoryPage.svelte`) and integrate it into `App.svelte` navigation.

## Requirements Covered
- REQ-MEM-01, REQ-MEM-02, REQ-MEM-03 (navigation and project selector)
- REQ-MEM-04, REQ-MEM-05, REQ-MEM-06, REQ-MEM-07 (memory display)
- REQ-MEM-08, REQ-MEM-09, REQ-MEM-10, REQ-MEM-11 (search)
- REQ-MEM-12, REQ-MEM-13, REQ-MEM-14 (add semantic memory)
- REQ-MEM-15, REQ-MEM-16, REQ-MEM-17 (edit semantic memory)
- REQ-MEM-18, REQ-MEM-19, REQ-MEM-20 (individual delete)
- REQ-MEM-21, REQ-MEM-22, REQ-MEM-23, REQ-MEM-24 (bulk delete with confirmation)
- REQ-MEM-25, REQ-MEM-26 (error handling)

## Changes Required

### 1. App.svelte updates

- Extend `currentPage` type to include `"memory"`: `"explorer" | "projects" | "memory"`
- Add "Memory" button to header nav (alongside Explorer and Projects)
- Render `<MemoryPage>` when `currentPage === "memory"`
- Pass the currently selected project (from Explorer) to `MemoryPage` as initial selection

### 2. New component: `MemoryPage.svelte` (`frontend/src/lib/MemoryPage.svelte`)

#### Project Selector
- Dropdown listing all projects (fetched via `listProjects`)
- Pre-selects the project passed from App.svelte (if any)
- Changing project reloads both memory lists

#### Memory Display (default view, no active search)

**Episodic Memory section:**
- Header showing "Episodic Memory" with entry count (e.g., "Episodic Memory (12)")
- List/table of entries, each showing:
  - Query text
  - Files explored (as tags/chips or comma-separated)
  - Summary
  - Timestamp
  - Delete button
- "Clear All Episodic Memory" button at section level

**Semantic Memory section:**
- Header showing "Semantic Memory" with entry count
- List/table of entries, each showing:
  - Content text
  - Timestamp
  - Edit button
  - Delete button
- "Clear All Semantic Memory" button at section level
- Add form: text input + "Add" button

**Global actions:**
- "Clear All Memory" button (deletes both types)

#### Search

- Search input at top of page (above both sections)
- On submit (or debounced input), calls `searchMemory` API
- Replaces the two-section view with a unified results list
- Each result shows:
  - Type badge ("Episodic" or "Semantic")
  - Relevant fields for the type
  - Delete button
- Clearing the search input returns to the default two-section view

#### Edit Semantic Memory

- Clicking "Edit" on a semantic entry replaces its display row with an inline edit form
- Edit form has: textarea pre-filled with current content, "Save" and "Cancel" buttons
- Save calls `editSemanticMemory` (delete + create), refreshes list
- Cancel returns to display mode

#### Bulk Delete Confirmations

- Each bulk action shows a confirmation dialog/card:
  - "Clear All Episodic Memory" → "This will permanently delete all N episodic memory entries for this project. This action cannot be undone."
  - "Clear All Semantic Memory" → similar message
  - "Clear All Memory" → "This will permanently delete all episodic and semantic memory entries for this project. This action cannot be undone."
- "Confirm" and "Cancel" buttons
- On confirm, execute the bulk delete, refresh the list, dismiss the dialog

#### Error Handling

- All API calls wrapped in try/catch
- Errors displayed inline (below the relevant section or action)
- Errors auto-clear when the user retries the operation

### UI Component Library

Use the existing shadcn-svelte components (Button, Card, etc.) consistent with `ProjectsPage.svelte`.

## Tests

Frontend tests are primarily manual/visual (consistent with existing project pattern). Backend coverage is provided by Task 17 tests.

## Acceptance Criteria
- Memory page accessible via "Memory" button in header
- Project selector works and pre-selects from Explorer context
- Episodic and semantic memories display with all fields and entry counts
- Search produces consolidated results from both types with type badges
- Add semantic memory form works with validation
- Edit semantic memory works (inline edit, save = delete + create)
- Individual delete works for both memory types
- Bulk delete works with confirmation for all three variants
- Error messages display clearly without corrupting state
- Styling consistent with existing ProjectsPage
