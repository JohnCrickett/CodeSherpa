# Requirements Specification: Web UI Project Management & Ingestion

## Context

The CodeSherpa web interface currently supports selecting existing projects, browsing files, viewing code, and querying. It is missing the ability to create new projects, trigger ingestion, and re-run ingestion from the web UI. These requirements cover the new web UI features for project creation, ingestion, and re-ingestion with progress tracking.

References: PRD sections 2 (Projects), 3 (Ingestion), 8 (Web Interface).

---

## Requirements

### Project Creation

**REQ-WEB-01:** When the user navigates to the projects page, the web interface shall display a list of all existing projects with their name, source path, file count, chunk count, and last ingestion timestamp.

**REQ-WEB-02:** When the user submits the create project form with a project name and source (local path or GitHub URL), the system shall create a new project record in the database and display the project in the project list.

**REQ-WEB-03:** When a GitHub URL is provided as the source, the system shall clone the repository to a local cache directory before making it available for ingestion.

**REQ-WEB-04:** When a local path is provided as the source, the system shall validate that the path exists and is a directory.

**REQ-WEB-05:** When the user submits a project name that already exists, the system shall display an error message indicating the project name is already taken.

**REQ-WEB-06:** When the user submits invalid input (empty name, empty source, invalid path, unreachable GitHub URL), the system shall display a descriptive error message without creating a project.

### Ingestion

**REQ-WEB-07:** When the user clicks the "Ingest" button for a project, the system shall start the ingestion pipeline (parse, embed, store) for that project's source path.

**REQ-WEB-08:** While ingestion is running, the web interface shall display progress information showing the current phase and progress within that phase (e.g., "Embedding chunks: batch 3 of 10").

**REQ-WEB-09:** While ingestion is running, the web interface shall disable the ingest button for that project to prevent concurrent ingestion of the same project.

**REQ-WEB-10:** When ingestion completes successfully, the system shall display a summary showing the number of chunks stored, files skipped (unchanged), files updated, and files removed.

**REQ-WEB-11:** When ingestion completes, the system shall update the project's metadata (file count, chunk count, last ingestion timestamp) and reflect these changes in the project list.

**REQ-WEB-12:** When ingestion fails, the system shall display the error message to the user and leave the project in a consistent state.

### Re-ingestion

**REQ-WEB-13:** When the user clicks the "Re-ingest" button for a previously ingested project, the system shall re-run the ingestion pipeline, re-embedding only files whose content has changed since the last ingestion.

**REQ-WEB-14:** When re-ingestion runs, the system shall preserve existing embeddings for unchanged files and delete embeddings for files that have been removed from the source.

**REQ-WEB-15:** When re-ingestion of a GitHub-sourced project is triggered, the system shall pull the latest changes from the remote repository before running the ingestion pipeline.

**REQ-WEB-16:** When re-ingestion completes, the system shall display a summary showing the number of files updated, files unchanged (skipped), files removed, and new chunks stored.

### Navigation

**REQ-WEB-17:** The web interface shall provide a separate projects management page, distinct from the code exploration view.

**REQ-WEB-18:** The web interface shall provide navigation between the projects page and the code exploration page.

**REQ-WEB-19:** When the user selects a project from the projects page, the web interface shall navigate to the code exploration view with that project selected.

---

## Acceptance Criteria

1. A user can navigate to the projects page and see all existing projects.
2. A user can create a new project from a local path and see it appear in the list.
3. A user can create a new project from a GitHub URL and see it appear in the list.
4. A user can trigger ingestion for a project and see real-time progress updates.
5. After ingestion completes, the user sees a summary of what was processed.
6. A user can re-ingest a project and only changed files are re-processed.
7. After re-ingestion, the user sees a summary distinguishing updated, unchanged, and removed files.
8. The user can navigate between the projects page and the code exploration page.
9. Error cases (duplicate name, invalid path, network failure) display clear messages.
