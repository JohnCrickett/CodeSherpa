# Product Requirements Document

## Code Sherpa

---

## Overview

Code Sherpa is a developer tool that helps engineers explore and make sense of large, unfamiliar codebases using natural language. Rather than reading files top to bottom, a developer asks questions and the agent retrieves semantically relevant code, explains what it does, and builds up a shared understanding of the project over time.

The agent is built on Oracle Database 26ai, which stores both vector embeddings and full-text indexes for every function, class, and module in the codebase. Queries are matched by semantic similarity using `voyage-code-3` embeddings, supplemented by full-text search for exact identifier and keyword matches. The agentic behaviour - memory-aware routing, multi-step retrieval, and exploration planning - is orchestrated using LangGraph, while LangChain handles the retrieval chains and LLM integration.

The system supports multiple named projects, so a developer can maintain separate knowledge bases for different codebases. All project data, including embeddings and agent memory, is persisted between runs. The agent remembers what has already been explored, what the developer has told it about the project, and the connections it has discovered, so each session builds on the last.

The developer starts the system from the command line, pointing it at a local folder or a GitHub repository. The system ingests the codebase and launches a web interface for browsing and querying. Oracle Database provides vector storage, running in a local Docker container by default, with cloud configuration available as an option.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python |
| Retrieval chains and LLM integration | LangChain |
| Agent orchestration and state management | LangGraph |
| Vector and full-text database | Oracle Database 26ai |
| Database deployment | Docker (default) or Oracle Cloud |
| Embedding model | Voyage AI `voyage-code-3` (1024 dimensions) |
| Web interface | Served locally on startup |

---

## Requirements

### 1. Startup and Invocation

- The system shall be started from the command line, accepting a project name and either a local folder path or a GitHub repository URL as arguments.
- When a GitHub URL is provided, the system shall clone the repository to a temporary local directory before ingestion begins.
- When started, the system shall ingest or update the target codebase, then launch the web interface automatically.
- The system shall open the web interface in the default browser on startup, or display the local URL clearly in the terminal.
- The system shall connect to Oracle Database running in a local Docker container by default.
- Where a cloud Oracle Database connection string is provided via configuration, the system shall use that instead of the local Docker container.
- The system shall read all database configuration and credentials from an environment file so that no credentials are hardcoded.
- If the Docker container is not running and no cloud connection is configured, the system shall display a clear error message and instructions for starting the container before exiting.

---

### 2. Projects

- The system shall organise all ingested codebases into named projects.
- The system shall store project metadata (name, source path, creation date, last ingestion timestamp, file count, chunk count) in Oracle Database.
- The system shall store each project's embeddings, agent memory, and metadata in isolation so that queries against one project do not affect another.
- The system shall allow the user to create, list, and select projects from both the CLI and the web interface.
- When a codebase is re-ingested into an existing project, the system shall update embeddings for changed files and preserve embeddings for unchanged files.
- The system shall persist all project data between runs in Oracle Database, including embeddings, agent memory, conversation history, and project metadata.

---

### 3. Ingestion

- The system shall parse a target codebase and split it into logical chunks at function, class, and module boundaries.
- The system shall embed each chunk using Voyage AI's `voyage-code-3` model.
- The system shall store each embedding in Oracle Database with metadata including file path, chunk type, programming language, and character range.
- The system shall create an Oracle Text full-text index on the code text column to support keyword and identifier search alongside vector similarity.
- When a file in the codebase changes, the system shall re-embed and update only the affected chunks.
- If a file cannot be parsed, the system shall log the failure and continue processing the remaining files.
- The system shall display ingestion progress in the terminal, including the number of files processed, chunks created, and any failures encountered.

---

### 4. Retrieval

- The system shall accept natural language questions and return the most relevant code chunks using both vector similarity search and Oracle Text full-text search, combining results from both.
- The system shall include file path and line reference with every retrieved chunk.
- While a query is being processed, LangGraph shall orchestrate the retrieval flow: first checking agent memory for relevant prior context, then querying the vector and full-text indexes, then generating the response.
- The system shall use a minimum cosine similarity threshold of approximately 0.3 for `voyage-code-3` embeddings. When no chunks exceed this threshold and full-text search returns no matches, the system shall inform the user that no relevant code was found rather than returning low-confidence results.

---

### 5. Explanation

- When a user asks what a piece of code does, the system shall explain it in plain language, citing the specific functions and files involved.
- When a user asks how two parts of the codebase relate, the system shall retrieve both and explain the connection between them.
- Where multiple implementations of the same concept exist, the system shall surface all of them and explain the differences.
- The system shall not speculate beyond what the retrieved code supports, and shall explicitly say so when a question cannot be fully answered from the ingested codebase.

---

### 6. Navigation

- The system shall use LangGraph to model multi-step retrieval as a state graph, where each step (retrieve, identify references, retrieve again, explain) is a node with state passed between them.
- The system shall support follow-up questions that drill deeper into a retrieved result without the user needing to re-state context, using LangGraph's state to carry conversation context forward.
- When the system identifies a dependency or reference in retrieved code, it shall offer to retrieve and explain the linked code.
- The system shall support exploration planning: when given a broad question (e.g. "how does the authentication system work?"), LangGraph shall plan and execute a multi-step retrieval sequence, tracing flows through the codebase and producing a coherent walkthrough.
- The system shall support a "map" query that returns a high-level summary of the codebase structure based on ingested metadata, including a breakdown of languages, top-level modules, and entry points where identifiable.

---

### 7. Agent Memory

- The system shall persist episodic memory across sessions in Oracle Database, tracking which areas of the codebase the developer has already explored.
- When the user provides project-level context (e.g. "this service owns all payment logic"), the system shall store it as semantic memory in Oracle Database and apply it to future responses within that project.
- LangGraph shall implement memory-aware routing: when a query arrives, the graph shall check memory first and route to a "build on prior context" path for previously explored areas, or a "full explanation" path for new territory.
- The system shall provide a summary of what has been explored so far and what remains unvisited, when requested by the user.

---

### 8. Web Interface

- The system shall serve a web interface automatically on startup, accessible via a local browser.
- The web interface shall allow the user to select and switch between projects.
- The web interface shall provide a conversational query panel for asking questions about the currently selected project.
- The web interface shall display retrieved code chunks alongside the agent's explanation, with file path and line references shown for each chunk.
- The web interface shall display a browsable file tree of the ingested codebase structure, derived from stored metadata.
- The web interface shall show a summary of what has been explored in the current session, and allow the user to review memory from previous sessions.
- Where the agent identifies a linked dependency in a response, the web interface shall render it as a clickable element that triggers a follow-up retrieval for that dependency.
- If the agent is processing a query, the web interface shall display a loading state so the user knows a response is in progress.
