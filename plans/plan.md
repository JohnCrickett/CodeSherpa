# Implementation Plan

| Task | Description | Spec | Requirements |
|------|-------------|------|--------------|
| [x] 01 | Project setup: Python structure, Docker Oracle DB, env config, CLI entry point | [task-01-project-setup.md](../specs/task-01-project-setup.md) | REQ-1 |
| [ ] 02 | Code parsing pipeline: file walking, chunking at function/class/module boundaries | [task-02-code-parsing.md](../specs/task-02-code-parsing.md) | REQ-3 |
| [ ] 03 | Embedding and vector storage: voyage-code-3, Oracle DB schema, vector + full-text indexes | [task-03-embedding-storage.md](../specs/task-03-embedding-storage.md) | REQ-3 |
| [ ] 04 | Semantic retrieval: hybrid vector + full-text search, CLI query interface | [task-04-semantic-retrieval.md](../specs/task-04-semantic-retrieval.md) | REQ-4 |
| [ ] 05 | LLM-powered explanations: LangChain retrieval chains, plain-language answers | [task-05-llm-explanations.md](../specs/task-05-llm-explanations.md) | REQ-5 |
| [ ] 06 | Project management: named projects, isolation, metadata, incremental re-ingestion | [task-06-project-management.md](../specs/task-06-project-management.md) | REQ-1, REQ-2 |
| [ ] 07 | Web interface: auto-launch, query panel, file tree, code display, loading state | [task-07-web-interface.md](../specs/task-07-web-interface.md) | REQ-1, REQ-8 |
| [ ] 08 | Agent memory: episodic + semantic memory, LangGraph memory-aware routing | [task-08-agent-memory.md](../specs/task-08-agent-memory.md) | REQ-7 |
| [ ] 09 | Intelligent navigation: multi-step retrieval, follow-ups, exploration planning, map query | [task-09-intelligent-navigation.md](../specs/task-09-intelligent-navigation.md) | REQ-6 |

## Dependency Order

```
01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09
                          │              │
                          └──────────────┘
                       (06 can start after 04)
```

### Notes

- **Tasks 01-05** are strictly sequential: each builds directly on the previous (setup → parse → store → search → explain).
- **Task 06** (project management) can begin after Task 04 since it wraps existing ingestion and retrieval with project isolation. However, it should incorporate Task 05's explanation capability before completion.
- **Task 07** (web interface) depends on Tasks 05 and 06 being complete, as it surfaces both explanations and project switching.
- **Task 08** (agent memory) depends on Task 07 for the web integration component, and on Task 05 for the LangGraph routing that decides how to use memory.
- **Task 09** (intelligent navigation) depends on Task 08 since it extends the LangGraph state graph with multi-step retrieval and builds on the memory-aware routing.
