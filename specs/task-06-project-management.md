# Task 06: Project Management

## Objective
Add named project support so developers can maintain separate knowledge bases for different codebases.

## Requirements Covered
- REQ-2: Projects (named projects, metadata, isolation, CRUD, incremental re-ingestion, persistence)
- REQ-1: Startup (project selection via CLI)

## Acceptance Criteria

### Project Metadata
- Store project metadata in Oracle Database: name, source path, creation date, last ingestion timestamp, file count, chunk count
- Each project's embeddings, metadata, and agent memory are isolated (queries against one project never return results from another)

### Project Operations
- Create a new project (from CLI, specifying name + source path or GitHub URL)
- List existing projects with metadata
- Select a project to query
- When a GitHub URL is provided, clone the repository to a temporary local directory before ingestion

### Incremental Re-ingestion
- When re-ingesting into an existing project, only re-embed changed files
- Unchanged files keep their existing embeddings
- Update project metadata (last ingestion timestamp, file count, chunk count) after re-ingestion

### Persistence
- All project data persists between runs in Oracle Database
- Restart the system and verify all data is intact and queryable

## Tests
- Create two projects from different codebases; queries return results only from the correct project
- List projects: both appear with correct names and metadata
- Query project metadata directly in Oracle Database; matches system output
- Modify a file, re-ingest: only changed file's chunks are re-embedded
- Stop and restart the system: all project data is intact and queryable
