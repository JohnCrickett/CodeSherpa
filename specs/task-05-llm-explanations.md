# Task 05: LLM-Powered Explanations

## Objective
Add LLM-powered explanations using LangChain retrieval chains so the system explains retrieved code in plain language.

## Requirements Covered
- REQ-5: Explanation (plain language, citations, relationships, multiple implementations, no speculation)

## Acceptance Criteria

### LangChain Integration
- Build a LangChain retrieval chain that passes retrieved code chunks as context alongside the user's question
- Use the configured LLM provider for generating explanations

### Explanation Quality
- Explain code in plain language, citing specific functions and files
- When asked how two parts relate, retrieve both and explain the connection
- When multiple implementations of the same concept exist, surface all and explain differences
- Never speculate beyond what the retrieved code supports; explicitly flag when a question can't be fully answered

### Response Format
- Return both the explanation text and the source code chunks with file paths
- Clearly cite which files and functions are referenced in the explanation

## Tests
- Ask what a specific function does: explanation is accurate, plain language, cites file and function
- Ask how two parts of the codebase relate: retrieves from both areas, explains relationship
- Ask a question only partially answerable: explains what it can, flags what it can't determine
- Ask about a concept with multiple implementations: surfaces all, explains differences
