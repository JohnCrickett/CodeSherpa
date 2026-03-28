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
