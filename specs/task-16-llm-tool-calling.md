# Task 16: LLM Tool Calling

## Objective
Give the LLM the ability to iteratively explore the codebase by invoking tools (`search_code`, `read_file`, `list_files`) during response generation, replacing the single-shot context approach.

## Requirements Covered
- REQ-TOOL-01 through REQ-TOOL-07

## Acceptance Criteria

### Tool Definitions
- Three tools are defined and bound to the LLM via LangChain's `bind_tools`:
  - `search_code(query: str)` — runs `hybrid_search()` and returns formatted code chunks
  - `read_file(file_path: str)` — runs `read_file_from_db()` and returns the file contents
  - `list_files(pattern: str)` — filters the project's file tree by glob pattern and returns matching paths
- Each tool has a clear description so the LLM knows when to use it

### Agent Loop
- A new `tool_calling_agent()` function (or equivalent LangGraph node) implements the loop:
  1. Send user question + system prompt + any prior context to the LLM
  2. If the LLM response contains tool calls, execute them and append results
  3. Repeat until the LLM produces a final text response or the iteration limit is reached
- The loop replaces the current `multi_step_retrieve()` and `plan_exploration()` nodes for the main answer generation step (retrieval + explain)
- The iteration limit defaults to 10 and is configurable

### Progress Events
- Each tool invocation emits a progress event via the existing `progress_callback` (e.g. `{"step": "Tool call", "detail": "search_code: hybrid_search('authentication')"}`)
- The frontend displays these events in the existing progress UI without frontend changes

### Integration
- The LangGraph state graph is updated: after classification, `specific`, `follow_up`, and `exploration` routes go through the tool-calling agent instead of the hardcoded multi-step/plan nodes
- The `map` route continues to use the existing `handle_map_query()` handler (no tool calling needed)
- Memory check and memory update nodes remain unchanged
- The system prompt instructs the LLM to use tools to explore before answering, and to cite file paths

### Fallback
- If tool calling fails (e.g. model doesn't support it), fall back to the existing `explain()` function, preserving current behaviour
- The fallback is logged as a warning

### Tests
- Unit test: tool-calling loop executes a search tool and returns a response
- Unit test: loop terminates at the iteration limit and returns a partial answer
- Unit test: `read_file` tool returns correct file contents
- Unit test: `list_files` tool filters file tree correctly
- Unit test: progress events are emitted for each tool call
- Integration test: end-to-end question via `api_ask` uses tool calling and returns an answer with sources
