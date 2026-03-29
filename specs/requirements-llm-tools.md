# Requirements Specification: LLM Tool Calling & Orchestration Improvements

## Context

The CodeSherpa navigation system (Task 09) uses a LangGraph state graph to classify
queries and route them to specialised handlers. The current implementation hardcodes
orchestration logic in Python — follow-up detection uses regex, dependency extraction
is Python-only, key file selection uses a fixed list, and the LLM receives a single
batch of context with no ability to request more.

These requirements replace the hardcoded orchestration with LLM-driven tool calling,
so the model can iteratively explore the codebase, and fix the brittle heuristics
that limit the system to Python codebases.

References: PRD sections 5 (Explanation), 6 (Navigation), 8 (Web Interface).

---

## Requirements

### LLM Tool Calling

**REQ-TOOL-01:** The system shall bind tool definitions to the LLM so that the model
can invoke tools during response generation, rather than receiving a single batch of
context.

**REQ-TOOL-02:** The system shall provide a `search_code(query: str)` tool that the
LLM can invoke to run a hybrid search (vector + full-text) against the current
project and receive the matching code chunks.

**REQ-TOOL-03:** The system shall provide a `read_file(file_path: str)` tool that
the LLM can invoke to retrieve the full contents of a specific file from the
database.

**REQ-TOOL-04:** The system shall provide a `list_files(pattern: str)` tool that the
LLM can invoke to list project files matching a glob-style pattern (e.g.
`"src/**/*.py"`).

**REQ-TOOL-05:** The system shall implement a tool-calling agent loop that sends
the user's question to the LLM, executes any tool calls the LLM makes, returns the
results, and repeats until the LLM produces a final text response.

**REQ-TOOL-06:** The system shall enforce a maximum number of tool-call iterations
(configurable, default 10) to prevent runaway loops, returning whatever partial
answer is available when the limit is reached.

**REQ-TOOL-07:** Each tool call and its result shall be emitted as a progress event
via the existing SSE stream so the frontend can show the user what the LLM is
exploring in real time.

### Unified Query Classification

**REQ-CLASS-01:** The system shall classify all query types (map, follow-up,
exploration, specific) in a single LLM call, replacing the current split of
exact-match, regex, and LLM classification.

**REQ-CLASS-02:** The classification prompt shall include conversation history
(when present) so the LLM can determine follow-up intent from context rather
than keyword matching.

**REQ-CLASS-03:** The system shall pass the classification result to the existing
LangGraph routing logic, preserving the current graph structure (map handler,
exploration planner, multi-step retriever).

### Language-Aware Dependency Extraction

**REQ-DEP-01:** The dependency extraction logic shall support at minimum: Python,
JavaScript/TypeScript, Go, and Java import/require/include patterns.

**REQ-DEP-02:** The dependency extraction shall use the `language` field already
stored on each code chunk to select the appropriate extraction patterns.

**REQ-DEP-03:** For languages not explicitly supported, the system shall fall back
to a generic regex that detects common import-like patterns (e.g. `import`, `require`,
`include`, `use`) rather than returning no dependencies.

### Expanded Key File Detection

**REQ-KEY-01:** The key file detection pattern shall include project configuration
and build files: `pyproject.toml`, `setup.py`, `setup.cfg`, `package.json`,
`Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `Makefile`, `CMakeLists.txt`.

**REQ-KEY-02:** The key file detection pattern shall include container and
deployment files: `Dockerfile`, `docker-compose.yml`, `docker-compose.yaml`.

**REQ-KEY-03:** The key file detection pattern shall continue to include the
existing patterns: `readme`, `changelog`, `contributing`, `license`, `main.*`,
`app.*`, `index.*`, `server.*`, `cli.*`.

---

## Acceptance Criteria

1. The LLM can invoke `search_code`, `read_file`, and `list_files` tools during a
   conversation and uses the results to build its answer.
2. A question like "what does function X do and what calls it?" triggers multiple
   tool calls (search for X, then search for callers) without hardcoded orchestration.
3. The tool-call loop terminates within the configured iteration limit.
4. Progress events for each tool call appear in the SSE stream and are visible in
   the frontend.
5. Query classification works correctly for all four types in a single LLM call,
   including follow-ups detected from conversation context.
6. Dependency extraction returns meaningful results for a JavaScript/TypeScript
   codebase (e.g. `import ... from`, `require(...)`) and a Go codebase
   (e.g. `import "fmt"`).
7. Key file detection matches `pyproject.toml`, `Dockerfile`, `package.json`, and
   `go.mod` in addition to the existing patterns.
8. All existing tests continue to pass; new tests cover tool invocation, multi-
   language dependency extraction, and unified classification.
