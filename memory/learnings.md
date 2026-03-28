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
