# Task 13: Expanded Key File Detection

## Objective
Broaden the key file detection patterns so the LLM receives context from project configuration, build, and deployment files across all supported languages — not just README and entry-point scripts.

## Requirements Covered
- REQ-KEY-01, REQ-KEY-02, REQ-KEY-03

## Acceptance Criteria

### Pattern Expansion
- `_KEY_FILE_PATTERNS` in `navigation.py` matches all of: `pyproject.toml`, `setup.py`, `setup.cfg`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `Makefile`, `CMakeLists.txt`, `Dockerfile`, `docker-compose.yml`, `docker-compose.yaml`
- Existing patterns (`readme`, `changelog`, `contributing`, `license`, `main.*`, `app.*`, `index.*`, `server.*`, `cli.*`) continue to match

### Tests
- Unit test asserts each new filename matches the updated pattern
- Unit test asserts existing filenames still match
- Unit test asserts unrelated filenames (e.g. `utils.py`, `random.txt`) do not match
