# Task 04: Semantic Retrieval (CLI)

## Objective
Implement hybrid retrieval combining vector similarity search and Oracle Text full-text search, exposed via a CLI interface.

## Requirements Covered
- REQ-4: Retrieval (vector search, full-text search, similarity threshold, combined results)

## Acceptance Criteria

### Vector Search
- Embed the user's natural language query using `voyage-code-3`
- Search Oracle Database for the closest chunks by cosine similarity
- Apply a minimum cosine similarity threshold of ~0.3
- Return top-K results ranked by similarity score

### Full-Text Search
- Run the query through Oracle Text full-text search on the code text column
- Catch exact identifier names, string literals, and keywords

### Hybrid Combination
- Combine results from vector search and full-text search
- De-duplicate chunks that appear in both result sets
- Rank combined results appropriately

### Result Presentation
- Include file path and line reference with every returned chunk
- When no chunks exceed the similarity threshold and full-text returns no matches, inform the user that no relevant code was found

### CLI Interface
- Simple REPL: user types a question, system returns matching chunks with locations
- Display the code text, file path, and relevance score for each result

## Tests
- Question about known code returns genuinely relevant chunks
- Same question with different phrasing returns similar results (semantic matching)
- Exact function/variable name search is caught by full-text search
- Question about non-existent code returns "no relevant code found"
- Every returned chunk includes file path and line reference
