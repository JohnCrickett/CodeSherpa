# Task 02: Code Parsing Pipeline

## Objective
Build a parser that walks a codebase and splits source files into logical chunks at function, class, and module boundaries.

## Requirements Covered
- REQ-3: Ingestion (parsing, chunking, metadata, error handling, progress display)

## Acceptance Criteria

### File Tree Walking
- Recursively walk a given directory and identify source files by extension
- Support common languages: Python, JavaScript/TypeScript, Java, Go, Rust, C/C++, Ruby
- Skip binary files, hidden directories (`.git`, `node_modules`, `__pycache__`, etc.)

### Chunk Extraction
- Parse each source file and split at function, class, and module boundaries
- Each chunk represents one coherent unit of code (a complete function, class, or top-level module block)
- Attach metadata to each chunk:
  - `file_path`: relative path within the codebase
  - `chunk_type`: one of `function`, `class`, `module`
  - `language`: detected programming language
  - `start_char` / `end_char`: character range in the original file

### Error Handling
- If a file cannot be parsed (syntax error, unsupported format), log the failure and continue
- Never abort the entire pipeline due to a single file failure

### Progress Display
- Display progress in the terminal: files processed, chunks created, failures encountered
- Update progress as processing proceeds (not only at the end)

## Tests
- Parser produces chunks at function and class boundaries, not arbitrary splits
- Each chunk contains a complete, coherent unit of code
- Metadata on each chunk is correct (file path, chunk type, language, character range)
- A file with a deliberate syntax error is logged and skipped; remaining files are processed
- Terminal output shows files processed, chunks created, and errors
