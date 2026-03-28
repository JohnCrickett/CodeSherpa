# CodeSherpa

An AI-powered tool that helps software engineers explore and understand unfamiliar codebases using natural language. Point it at a local directory or GitHub repository, and it ingests the code into a searchable vector database so you can ask questions about what the code does and how it fits together.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker (for running Oracle Database 26ai locally)
- Git (for cloning GitHub repositories)

## Setup

1. **Clone the repository:**

   ```sh
   git clone https://github.com/your-org/CodeSherpa.git
   cd CodeSherpa
   ```

2. **Install dependencies:**

   ```sh
   uv sync --dev
   ```

3. **Start Oracle Database 26ai in Docker:**

   CodeSherpa uses Oracle Database for vector and full-text storage. Start a local instance using Docker before running the tool.

4. **Create a `.env` file** in the project root with the following variables:

   ```
   ORACLE_DSN=localhost:1521/FREEPDB1
   ORACLE_USER=codesherpa
   ORACLE_PASSWORD=your_password
   LLM_API_KEY=your_api_key
   LLM_MODEL=gemini-2.0-flash
   ```

   Values can reference environment variables using `${VAR_NAME}` syntax, e.g. `LLM_API_KEY=${GOOGLE_API_KEY}`.

## Usage

### Ingesting a codebase

Index a local codebase:

```sh
uv run codesherpa ingest /path/to/your/project
```

Index a GitHub repository (cloned automatically):

```sh
uv run codesherpa ingest https://github.com/owner/repo
```

Specify a custom project name:

```sh
uv run codesherpa ingest /path/to/project --project my-project
```

If `--project` is not provided, the directory name is used as the project name.

### Querying the codebase

After ingesting, start an interactive search session:

```sh
uv run codesherpa query
```

This opens a REPL where you can type natural language questions or exact identifiers:

```
query> how does ingestion work?
query> compute_file_hash
query> class that handles database connections
```

Each result shows the matching code, its file path and character range, chunk type, language, and a relevance score. The search combines vector similarity (semantic meaning) with full-text matching (exact identifiers and keywords), deduplicating and ranking the merged results.

Type `quit` or `exit` (or press Ctrl+D) to leave the REPL.

## Verifying the Database

You can connect to the Oracle database with `sqlplus` to inspect ingested data:

```sh
sqlplus codesherpa/<your_password>@localhost:1521/FREEPDB1
```

Replace `<your_password>` with the value of `ORACLE_PASSWORD` from your `.env` file.

Useful queries:

```sql
-- Count total ingested chunks
SELECT COUNT(*) FROM CODE_CHUNKS;

-- List all indexed files
SELECT DISTINCT file_path FROM CODE_CHUNKS;

-- Clear all ingested data (keeps the schema)
TRUNCATE TABLE CODE_CHUNKS;

-- Drop everything and start fresh
DROP INDEX idx_chunks_fulltext;
DROP INDEX idx_chunks_vector;
DROP TABLE CODE_CHUNKS;
```

## Development

Run tests:

```sh
uv run pytest tests/ -v
```

Lint:

```sh
uv run ruff check codesherpa/ tests/
```

Auto-fix lint issues:

```sh
uv run ruff check --fix codesherpa/ tests/
```

## Project Structure

```
codesherpa/       Main Python package
  cli.py          CLI entry point
  config.py       Environment configuration loading
  db.py           Oracle Database connection
  embeddings.py   Embedding model integration
  ingestion.py    Codebase ingestion pipeline
  retrieval.py    Hybrid vector + full-text search
  parser.py       Code parsing and chunking
  repo.py         Local path and GitHub URL resolution
  llm.py          LLM integration
tests/            Test suite (pytest)
specs/            Task specifications
plans/            Implementation plan
```

## License

See [LICENSE](LICENSE) for details.
