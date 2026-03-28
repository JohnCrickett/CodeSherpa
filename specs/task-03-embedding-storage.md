# Task 03: Embedding and Vector Storage

## Objective
Embed code chunks using `voyage-code-3` and store them with metadata in Oracle Database 23ai, with both vector and full-text indexes.

## Requirements Covered
- REQ-3: Ingestion (embedding, storage, indexing, re-ingestion)

## Acceptance Criteria

### Embedding
- Generate 1024-dimensional vector embeddings for each chunk using Voyage AI `voyage-code-3`
- Batch embedding calls where possible to reduce API overhead

### Oracle Database Storage
- Create a table schema with columns for:
  - Embedding vector (VECTOR type, 1024 dimensions)
  - Code text (CLOB)
  - File path, chunk type, language, start_char, end_char (metadata columns)
  - File content hash (for detecting changes on re-ingestion)
- Create a vector index on the embedding column for similarity search
- Create an Oracle Text full-text index on the code text column

### Re-ingestion
- On re-ingestion, detect changed files by comparing content hashes
- Re-embed and update only chunks from changed files
- Preserve embeddings for unchanged files
- Remove chunks for deleted files

### Pipeline Integration
- Wire the parser output (Task 02) into the embedding and storage pipeline
- Run end-to-end: parse -> embed -> store

## Tests
- Full pipeline (parse, embed, store) runs against a test codebase
- Total stored chunks in Oracle Database matches parser output count
- Stored entries contain embedding vector, code text, and all metadata fields
- Both vector index and full-text index exist on the appropriate columns
- Re-running the pipeline handles re-ingestion correctly (updates changed, skips unchanged)
