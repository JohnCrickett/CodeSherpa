# Task 09: Intelligent Navigation

## Objective
Add multi-step retrieval, follow-up questions, exploration planning, dependency linking, and codebase mapping using LangGraph.

## Requirements Covered
- REQ-6: Navigation (multi-step retrieval, follow-ups, dependency linking, exploration planning, map query)

## Acceptance Criteria

### Multi-Step Retrieval (LangGraph)
- Model multi-step retrieval as a LangGraph state graph
- Each step (retrieve, identify references, retrieve again, explain) is a node with state passed between them
- Example flow for "what calls this?": retrieve function -> find references -> retrieve callers -> explain connections

### Follow-Up Questions
- Support follow-up questions that drill deeper without re-stating context
- LangGraph state carries conversation context forward
- "What calls this?" or "where is the return value used?" work after a prior explanation

### Dependency Linking
- When the system identifies a dependency or reference (import, function call, inherited class), offer to retrieve and explain the linked code
- In the web interface, render dependencies as clickable elements that trigger follow-up retrieval

### Exploration Planning
- For broad questions (e.g., "how does the authentication system work?"), plan a multi-step exploration
- Trace flows through the codebase: find entry points, follow the flow, retrieve each step
- Produce a coherent walkthrough, not just a single set of search results

### Map Query
- "map" query returns a high-level summary of codebase structure
- Breakdown of languages used, top-level modules, and entry points where identifiable
- Based on ingested metadata

## Tests
- Ask about a function, then follow up with "what calls this?" without re-stating context: relevant results returned
- Dependency links appear in responses; system offers to explain linked code
- In web interface, clicking a dependency link triggers follow-up retrieval
- "map" query returns useful high-level summary: languages, modules, entry points
- Broad question triggers multi-step exploration with coherent walkthrough
