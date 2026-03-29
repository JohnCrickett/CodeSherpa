# Task 14: Language-Aware Dependency Extraction

## Objective
Replace the Python-only regex dependency extraction with a multi-language implementation that uses the `language` field on each code chunk to select the correct patterns.

## Requirements Covered
- REQ-DEP-01, REQ-DEP-02, REQ-DEP-03

## Acceptance Criteria

### Multi-Language Support
- Python: `import X`, `from X import Y` (existing behaviour preserved)
- JavaScript/TypeScript: `import ... from '...'`, `require('...')`, `import('...')`
- Go: `import "pkg"`, `import ( "pkg" )` (multi-line import blocks)
- Java: `import com.example.Foo;`
- Class inheritance extraction works for Python (`class X(Y)`) and Java (`class X extends Y implements Z`)

### Language Dispatch
- `extract_dependencies()` reads the `language` field from each chunk and applies the matching pattern set
- For chunks with an unrecognised language, a generic fallback regex detects `import`, `require`, `include`, and `use` statements

### Tests
- Unit tests with sample code for each supported language assert correct imports are extracted
- Unit test for an unsupported language (e.g. `"rust"`) asserts the generic fallback finds `use` statements
- Existing Python extraction tests continue to pass unchanged
