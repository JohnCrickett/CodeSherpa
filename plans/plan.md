# Implementation Plan

| Task | Description | Spec | Requirements |
|------|-------------|------|--------------|
| [x] 01 | Project setup: Python structure, Docker Oracle DB, env config, CLI entry point | [task-01-project-setup.md](../specs/task-01-project-setup.md) | REQ-1 |
| [x] 02 | Code parsing pipeline: file walking, chunking at function/class/module boundaries | [task-02-code-parsing.md](../specs/task-02-code-parsing.md) | REQ-3 |
| [x] 03 | Embedding and vector storage: CodeRankEmbed, Oracle DB schema, vector + full-text indexes | [task-03-embedding-storage.md](../specs/task-03-embedding-storage.md) | REQ-3 |
| [x] 04 | Semantic retrieval: hybrid vector + full-text search, CLI query interface | [task-04-semantic-retrieval.md](../specs/task-04-semantic-retrieval.md) | REQ-4 |
| [x] 05 | LLM-powered explanations: LangChain retrieval chains, plain-language answers | [task-05-llm-explanations.md](../specs/task-05-llm-explanations.md) | REQ-5 |
| [x] 06 | Project management: named projects, isolation, metadata, incremental re-ingestion | [task-06-project-management.md](../specs/task-06-project-management.md) | REQ-1, REQ-2 |
| [x] 07 | Web interface: auto-launch, query panel, file tree, code display, loading state | [task-07-web-interface.md](../specs/task-07-web-interface.md) | REQ-1, REQ-8 |
| [x] 08 | Agent memory: episodic + semantic memory, LangGraph memory-aware routing | [task-08-agent-memory.md](../specs/task-08-agent-memory.md) | REQ-7 |
| [x] 09 | Intelligent navigation: multi-step retrieval, follow-ups, exploration planning, map query | [task-09-intelligent-navigation.md](../specs/task-09-intelligent-navigation.md) | REQ-6 |
| [x] 10 | Ingestion progress API: project creation endpoint, SSE ingestion streaming, progress callback | [task-10-ingestion-progress-api.md](../specs/task-10-ingestion-progress-api.md) | REQ-WEB-02 to 16 |
| [x] 11 | Projects page: project list, create form, ingest/re-ingest with progress, navigation | [task-11-projects-page.md](../specs/task-11-projects-page.md) | REQ-WEB-01 to 19 |
| [x] 12 | Chat UI: ChatGPT-style conversation, follow-up mode, clickable sources, new layout | [task-12-chat-ui.md](../specs/task-12-chat-ui.md) | REQ-CHAT-01 to 08 |
| [ ] 13 | Expanded key file detection: broaden patterns for build, config, and deployment files | [task-13-expanded-key-files.md](../specs/task-13-expanded-key-files.md) | REQ-KEY-01 to 03 |
| [ ] 14 | Language-aware dependency extraction: multi-language import/inheritance patterns | [task-14-language-aware-deps.md](../specs/task-14-language-aware-deps.md) | REQ-DEP-01 to 03 |
| [ ] 15 | Unified query classification: single LLM call for all four query types | [task-15-unified-classification.md](../specs/task-15-unified-classification.md) | REQ-CLASS-01 to 03 |
| [ ] 16 | LLM tool calling: iterative codebase exploration via search, read, and list tools | [task-16-llm-tool-calling.md](../specs/task-16-llm-tool-calling.md) | REQ-TOOL-01 to 07 |

## Dependency Order

```
01 → 02 → 03 → 04 → 05 → 06 → 07 → 10 → 11
                          │              │
                          └──────────────┘
                       (06 can start after 04)

07 → 08 → 09
     │
     └→ 12

09 → 13 (no dependencies between 13, 14, 15)
09 → 14
09 → 15 → 16
```

### Phase 2 Notes (Tasks 13–16)

- **Tasks 13, 14** are independent leaf tasks that can be done in any order or in parallel. Both modify `navigation.py` but touch different functions.
- **Task 15** (unified classification) should be done before Task 16 because the tool-calling agent replaces the handler nodes that classification routes to; having clean classification first simplifies integration.
- **Task 16** (LLM tool calling) is the largest task and depends on 15 being complete. It replaces `multi_step_retrieve()` and `plan_exploration()` with a tool-calling agent loop, so those handlers must not be in flux.

```
Recommended order: 13 → 14 → 15 → 16
(13 and 14 can be parallelised)
```

### Phase 1 Notes

- **Tasks 01-05** are strictly sequential: each builds directly on the previous (setup → parse → store → search → explain).
- **Task 06** (project management) can begin after Task 04 since it wraps existing ingestion and retrieval with project isolation. However, it should incorporate Task 05's explanation capability before completion.
- **Task 07** (web interface) depends on Tasks 05 and 06 being complete, as it surfaces both explanations and project switching.
- **Task 08** (agent memory) depends on Task 07 for the web integration component, and on Task 05 for the LangGraph routing that decides how to use memory.
- **Task 09** (intelligent navigation) depends on Task 08 since it extends the LangGraph state graph with multi-step retrieval and builds on the memory-aware routing.
- **Task 10** (ingestion progress API) depends on Task 07, adding new backend endpoints for project creation and SSE-streamed ingestion progress. Refactors `ingest()` with a progress callback.
- **Task 11** (projects page) depends on Task 10, building the frontend projects management page that consumes the new API endpoints.
