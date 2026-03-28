## Commands
- Setup: `uv sync --dev` (create venv and install all deps)
- Test: `uv run pytest tests/ -v` (runs the tests. Tests must pass before a task is consider complete)
- Lint: `uv run ruff check codesherpa/ tests/` (check for possible issues)
- Lint fix: `uv run ruff check --fix codesherpa/ tests/` (auto-fix lint issues)

## Project Structure
- `codesherpa/` – Main Python package (config, db, embeddings, llm, cli modules)
- `tests/` – Test suite (pytest)
- `db/` – Database initialization scripts
- `specs/` – Task specifications
- `plans/` – Implementation plan
- `design/` – Design documents

## Process
 - Always write tests before implemeting functionality.
 - Always ask before adding dependencies.
 - Always ask before modifying existing tests.
 - Never change a test to make it pass.
