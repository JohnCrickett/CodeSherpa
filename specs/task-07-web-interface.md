# Task 07: Web Interface

## Objective
Build a web interface for browsing and querying indexed codebases, launched automatically on startup.

## Requirements Covered
- REQ-8: Web Interface (auto-launch, project selection, query panel, code display, file tree, loading state)
- REQ-1: Startup (auto-launch web interface, open browser or display URL)

## Acceptance Criteria

### Auto-Launch
- Web interface launches automatically when the system starts
- Opens in the default browser on startup, or displays the local URL clearly in the terminal

### Project Selection
- Select and switch between projects from the web interface
- Project list shows names and key metadata

### Query Panel
- Conversational query panel for asking questions about the currently selected project
- Displays retrieved code chunks alongside the agent's explanation
- File path and line references shown for each chunk

### File Tree
- Browsable file tree of the ingested codebase structure, derived from stored metadata
- Gives a visual overview of the project layout

### Loading State
- While the agent is processing a query, display a loading indicator
- Clear the loading state when the response arrives

## Tests
- System starts and web interface is accessible in the browser
- Select a project and ask a question: response shows code chunks with file paths, line references, and explanation
- Switch between projects: results update to reflect selected project
- File tree accurately reflects the ingested codebase structure
- Loading indicator appears while a query is processing
