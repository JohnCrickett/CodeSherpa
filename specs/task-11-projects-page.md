# Task 11: Projects Management Page

## Objective
Build a new Projects page in the frontend that lists projects, supports creating new projects, and provides ingestion/re-ingestion with real-time progress display.

## Requirements Covered
- REQ-WEB-01 (project list display)
- REQ-WEB-02 (create project form)
- REQ-WEB-05, REQ-WEB-06 (error display for invalid input / duplicate names)
- REQ-WEB-07 (ingest button)
- REQ-WEB-08 (progress display)
- REQ-WEB-09 (disable button during ingestion)
- REQ-WEB-10, REQ-WEB-16 (completion summary)
- REQ-WEB-12 (error display on failure)
- REQ-WEB-13 (re-ingest button)
- REQ-WEB-17 (separate projects page)
- REQ-WEB-18 (navigation between pages)
- REQ-WEB-19 (select project navigates to explorer)

## Changes Required

### 1. API client additions (`frontend/src/lib/api.ts`)

- `createProject(name: string, source: string): Promise<Project>` — POST to `/api/projects`
- `startIngestion(projectId: number): EventSource` — Connect to `/api/projects/{id}/ingest` SSE stream

### 2. New component: `ProjectsPage.svelte` (`frontend/src/lib/ProjectsPage.svelte`)

**Project List:**
- Table/card layout showing each project: name, source path, file count, chunk count, last ingested timestamp
- "Ingest" button for projects that have never been ingested (`last_ingested_at` is null)
- "Re-ingest" button for projects that have been ingested before
- "Explore" button that navigates to the code exploration view with that project selected

**Create Project Form:**
- Fields: project name (text input), source (text input with placeholder showing "Local path or GitHub URL")
- Submit button, disabled while submitting
- Error display for validation failures (inline, below the form)
- On success: project appears in the list, form clears

**Ingestion Progress:**
- When ingest/re-ingest is clicked, show a progress area for that project
- Display current phase and progress (e.g., "Embedding chunks: batch 3/10")
- Progress bar where applicable
- On completion: show summary card with stats (chunks stored, files skipped, updated, removed)
- On error: show error message in red
- Ingest button disabled while ingestion is active

### 3. Page routing in `App.svelte`

- Add a `currentPage` state: `"explorer"` | `"projects"`
- Header gets a "Projects" link/button to navigate to the projects page
- Projects page gets a "Back to Explorer" or similar navigation
- When "Explore" is clicked on a project in the projects page, switch to explorer with that project selected

## Tests

Frontend tests are primarily manual/visual, but the API client functions should be tested indirectly through the backend test suite (Task 10).

## Acceptance Criteria
- Projects page is accessible from the header navigation
- All existing projects are listed with metadata
- New projects can be created with clear error messages for invalid input
- Ingestion progress is displayed in real-time
- Completion summary shows accurate stats
- Navigation between projects page and explorer works smoothly
