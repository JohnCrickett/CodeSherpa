# Task 08: Agent Memory

## Objective
Add episodic and semantic memory stored in Oracle Database, with LangGraph memory-aware routing.

## Requirements Covered
- REQ-7: Agent Memory (episodic memory, semantic memory, memory-aware routing, exploration summary)

## Acceptance Criteria

### Episodic Memory
- Track which areas of the codebase the developer has explored across sessions
- Store episodic memory entries as vectors in Oracle Database for semantic retrieval
- Isolated per project

### Semantic Memory
- Store project-level context provided by the developer (e.g., "this service owns all payment logic")
- Apply stored context to future responses within that project
- Stored as vectors in Oracle Database for semantic retrieval
- Isolated per project

### Memory-Aware Routing (LangGraph)
- Build a LangGraph state graph for query processing:
  1. Check memory for relevant prior context
  2. Route to "build on prior context" path for previously explored areas
  3. Route to "full explanation" path for new territory
  4. After response, update memory with what was explored
- Each node handles one concern; edges encode routing decisions

### Exploration Summary
- When requested, provide a summary of what has been explored and what remains unvisited

### Persistence
- Both memory types persist across sessions in Oracle Database
- Returning to a project picks up where the user left off

### Web Interface Integration
- Show a summary of what has been explored in the current session
- Allow the user to review memory from previous sessions

## Tests
- Explore areas across a session, restart, ask what was explored: accurate summary returned
- Tell the system project context; subsequent queries use that context
- Ask about previously explored area: system builds on prior understanding, not from scratch
- Ask for explored vs. unvisited summary: reasonable breakdown returned
