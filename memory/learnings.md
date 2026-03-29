# Learnings

## Environment
- Python 3.14 is installed; `voyageai` package does not support Python >=3.13 in stable releases (only 0.2.x works, 0.3.x requires <3.14).
- `uv` is installed at `/opt/homebrew/bin/uv`. Use `uv` for all dependency management and running commands.
- When mocking LangChain classes like `ChatGoogleGenerativeAI`, mock at the import location (`codesherpa.llm.ChatGoogleGenerativeAI`) not the source module, since the constructor does network-dependent initialization.

## LLM
- Project uses Google Gemini (gemini-2.5-flash) via `langchain-google-genai`, not OpenAI.

## Dependencies
- Use `uv` for dependency management, not `pip`. Run tests via `uv run pytest`, lint via `uv run ruff check`.
- The `uv` venv uses Python 3.12.12 (not the system 3.14), which avoids compatibility issues.

## Parser
- Python parsing uses `ast` module; other languages use regex-based detection. No tree-sitter dependency needed.
- `CodeChunk` dataclass has: content, file_path, chunk_type, language, start_char, end_char.

## Embeddings & Storage
- Embeddings use `CodeRankEmbedder` (768-dim, CodeRankEmbed via sentence-transformers), not Voyage AI (compatibility issue) or nomic-embed-code (too much RAM).
- `CodeRankEmbedder.embed_batch()` supports batch embedding; `embed()` for single text. Queries get a prefix prepended; documents do not.
- Oracle DB table is `CODE_CHUNKS` with columns: id, embedding (VECTOR(768, FLOAT64)), code_text (CLOB), file_path, chunk_type, language, start_char, end_char, file_hash.
- Vector index: `IDX_CHUNKS_VECTOR` (COSINE distance). Full-text index: `IDX_CHUNKS_FULLTEXT` (CTXSYS.CONTEXT).
- `codesherpa/ingestion.py` has `ensure_schema()`, `compute_file_hash()`, and `ingest()` (parse → embed → store pipeline with re-ingestion support).
- Re-ingestion uses SHA-256 file content hashes to detect changes; deletes chunks for removed files.

## Explanation
- `codesherpa/explanation.py` has `ExplanationResult` dataclass (explanation + sources) and `explain()` function.
- `explain()` uses `hybrid_search` to retrieve chunks, formats them as context, passes to LLM via LangChain `SystemMessage` + `HumanMessage`.
- CLI has `ask` subcommand: `codesherpa ask "question"` for one-shot LLM-powered explanations.
- `format_explanation()` in `cli.py` renders the explanation text followed by a sources list.

## Project Management
- `codesherpa/project.py` has PROJECTS table CRUD: `create_project()`, `get_project()`, `list_projects()`, `delete_project()`, `get_or_create_project()`, `update_project_stats()`.
- PROJECTS table columns: id (identity), name (unique), source_path, created_at, last_ingested_at, file_count, chunk_count.
- CODE_CHUNKS table now has `project_id` column (NOT NULL) for project isolation.
- All ingestion and retrieval functions accept `project_id` parameter to scope operations to a single project.
- CLI commands: `ingest` auto-creates project via `get_or_create_project()`; `query`/`ask` require `--project` flag; `project list`/`project delete` for management.
- Existing CLI tests were updated to pass `--project` and `project_id` where required by the new interface.

## Web Interface
- Backend uses FastAPI (`codesherpa/web.py`) with `create_app(conn, embedder, llm)` factory pattern.
- API endpoints: `GET /api/projects`, `GET /api/projects/{id}/files`, `POST /api/projects/{id}/ask`, `POST /api/projects/{id}/query`.
- Frontend is Svelte 5 + TypeScript in `frontend/`, built with Vite. Build output goes to `frontend/dist/` and is served as static files by FastAPI.
- CLI `serve` subcommand starts uvicorn, accepts `--host`, `--port`, `--no-browser` flags. Auto-opens browser after 1s delay.
- npm cache on this machine has root-owned files; use `--cache "$TMPDIR/npm-cache"` when running npm install to work around it.
- Frontend uses Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) and snippets (`{#snippet}` / `{@render}`).

## Retrieval
- `codesherpa/retrieval.py` has `vector_search()`, `fulltext_search()`, and `hybrid_search()` returning `SearchResult` dataclass instances.
- Vector search uses `(1 - VECTOR_DISTANCE(embedding, :vec, COSINE))` for cosine similarity (Oracle returns distance, not similarity).
- Full-text search uses `CONTAINS(code_text, :query, 1) > 0` with `SCORE(1)` for relevance ranking.
- Hybrid search deduplicates by `(file_path, start_char, end_char)` tuple, keeping the higher score.
- CLI was restructured to use subcommands: `codesherpa ingest <source>` and `codesherpa query` (interactive REPL).
- `format_results()` and `run_query_repl()` are in `cli.py` and are tested independently.
