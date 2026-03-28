"""Code parsing pipeline: file walking, chunking at function/class/module boundaries."""

import ast
import logging
import os
import re
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".zig": "zig",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".scala": "scala",
    ".sc": "scala",
    ".php": "php",
    ".lua": "lua",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "venv",
    ".venv",
    "dist",
    "build",
    ".eggs",
}

ProgressCallback = Callable[[int, int, int], None]


@dataclass
class CodeChunk:
    """A parsed chunk of source code with metadata."""

    content: str
    file_path: str
    chunk_type: str  # "function", "class", "module"
    language: str
    start_char: int
    end_char: int


def walk_directory(root: str) -> list[str]:
    """Recursively walk a directory and return paths to supported source files."""
    source_files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out hidden and skip directories in-place
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
        ]
        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                source_files.append(os.path.join(dirpath, filename))
    return source_files


def _parse_python(source: str, rel_path: str) -> list[CodeChunk]:
    """Parse a Python file using the ast module."""
    tree = ast.parse(source)
    chunks: list[CodeChunk] = []
    # Track which line ranges are covered by functions/classes
    covered_lines: set[int] = set()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_char = _line_col_to_offset(source, node.lineno, node.col_offset)
            end_char = _line_col_to_offset(source, node.end_lineno, node.end_col_offset)
            chunks.append(
                CodeChunk(
                    content=source[start_char:end_char],
                    file_path=rel_path,
                    chunk_type="function",
                    language="python",
                    start_char=start_char,
                    end_char=end_char,
                )
            )
            for line in range(node.lineno, node.end_lineno + 1):
                covered_lines.add(line)
        elif isinstance(node, ast.ClassDef):
            start_char = _line_col_to_offset(source, node.lineno, node.col_offset)
            end_char = _line_col_to_offset(source, node.end_lineno, node.end_col_offset)
            chunks.append(
                CodeChunk(
                    content=source[start_char:end_char],
                    file_path=rel_path,
                    chunk_type="class",
                    language="python",
                    start_char=start_char,
                    end_char=end_char,
                )
            )
            for line in range(node.lineno, node.end_lineno + 1):
                covered_lines.add(line)

    # Collect top-level module code (imports, assignments, etc.)
    lines = source.split("\n")
    module_parts: list[str] = []
    module_start: int | None = None
    module_end: int | None = None

    for i, line in enumerate(lines, start=1):
        if i not in covered_lines and line.strip():
            char_offset = _line_col_to_offset(source, i, 0)
            if module_start is None:
                module_start = char_offset
            module_end = char_offset + len(line)
            module_parts.append(line)

    if module_parts and module_start is not None:
        module_content = "\n".join(module_parts)
        chunks.append(
            CodeChunk(
                content=module_content,
                file_path=rel_path,
                chunk_type="module",
                language="python",
                start_char=module_start,
                end_char=module_end,
            )
        )

    return chunks


def _line_col_to_offset(source: str, lineno: int, col_offset: int) -> int:
    """Convert a 1-based line number and 0-based column offset to a character offset."""
    lines = source.split("\n")
    offset = sum(len(lines[i]) + 1 for i in range(lineno - 1))
    return offset + col_offset


# Regex patterns for detecting functions and classes in non-Python languages
_FUNCTION_PATTERNS: dict[str, re.Pattern] = {
    "javascript": re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+\w+", re.MULTILINE
    ),
    "typescript": re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+\w+", re.MULTILINE
    ),
    "java": re.compile(
        r"^\s*(?:public|private|protected|static|\s)*\s+\w+\s+\w+\s*\(", re.MULTILINE
    ),
    "go": re.compile(r"^func\s+", re.MULTILINE),
    "rust": re.compile(r"^(?:pub\s+)?(?:async\s+)?fn\s+\w+", re.MULTILINE),
    "c": re.compile(r"^\w[\w\s\*]+\s+\w+\s*\(", re.MULTILINE),
    "cpp": re.compile(r"^\w[\w\s\*:]+\s+\w+\s*\(", re.MULTILINE),
    "ruby": re.compile(r"^\s*def\s+\w+", re.MULTILINE),
    "zig": re.compile(r"^(?:pub\s+)?fn\s+\w+", re.MULTILINE),
    "csharp": re.compile(
        r"^\s*(?:public|private|protected|internal|static|async|override|virtual|\s)*\s+\w+\s+\w+\s*\(",
        re.MULTILINE,
    ),
    "kotlin": re.compile(
        r"^\s*(?:(?:private|public|internal|protected|override)\s+)*fun\s+\w+", re.MULTILINE
    ),
    "swift": re.compile(
        r"^\s*(?:(?:private|public|internal|open|override|static)\s+)*func\s+\w+", re.MULTILINE
    ),
    "scala": re.compile(r"^\s*(?:(?:private|protected|override)\s+)*def\s+\w+", re.MULTILINE),
    "php": re.compile(
        r"^\s*(?:(?:public|private|protected|static)\s+)*function\s+\w+", re.MULTILINE
    ),
    "lua": re.compile(r"^(?:local\s+)?function\s+\w+", re.MULTILINE),
}

_CLASS_PATTERNS: dict[str, re.Pattern] = {
    "javascript": re.compile(r"^(?:export\s+)?class\s+\w+", re.MULTILINE),
    "typescript": re.compile(r"^(?:export\s+)?(?:abstract\s+)?class\s+\w+", re.MULTILINE),
    "java": re.compile(r"^(?:public|private|protected)?\s*class\s+\w+", re.MULTILINE),
    "rust": re.compile(r"^(?:pub\s+)?(?:struct|enum|impl)\s+\w+", re.MULTILINE),
    "cpp": re.compile(r"^(?:class|struct)\s+\w+", re.MULTILINE),
    "ruby": re.compile(r"^\s*class\s+\w+", re.MULTILINE),
    "zig": re.compile(r"^(?:pub\s+)?const\s+\w+\s*=\s*(?:struct|enum|union)", re.MULTILINE),
    "csharp": re.compile(
        r"^\s*(?:public|private|protected|internal|static|abstract|sealed|\s)*\s*class\s+\w+",
        re.MULTILINE,
    ),
    "kotlin": re.compile(
        r"^\s*(?:(?:data|sealed|abstract|open|private|internal)\s+)*class\s+\w+", re.MULTILINE
    ),
    "swift": re.compile(
        r"^\s*(?:(?:public|private|internal|open)\s+)?(?:class|struct|enum)\s+\w+", re.MULTILINE
    ),
    "scala": re.compile(
        r"^\s*(?:(?:case|abstract|sealed)\s+)*(?:class|object|trait)\s+\w+", re.MULTILINE
    ),
    "php": re.compile(
        r"^\s*(?:(?:abstract|final)\s+)?class\s+\w+", re.MULTILINE
    ),
}


def _find_block_end(source: str, start: int, language: str) -> int:
    """Find the end of a code block starting at the given position.

    For brace-delimited languages, finds the matching closing brace.
    For Ruby, finds the matching 'end' keyword.
    """
    if language in ("ruby", "lua"):
        return _find_end_keyword_block_end(source, start, language)
    return _find_brace_block_end(source, start)


def _find_brace_block_end(source: str, start: int) -> int:
    """Find the end of a brace-delimited block."""
    brace_pos = source.find("{", start)
    if brace_pos == -1:
        # No brace found; take until next blank line or end of file
        newline = source.find("\n\n", start)
        return newline if newline != -1 else len(source)

    depth = 0
    in_string = False
    string_char = ""
    i = brace_pos
    while i < len(source):
        ch = source[i]
        if in_string:
            if ch == "\\" and i + 1 < len(source):
                i += 2
                continue
            if ch == string_char:
                in_string = False
        else:
            if ch in ('"', "'", "`"):
                in_string = True
                string_char = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return len(source)


_END_BLOCK_OPENERS = {
    "ruby": r"(def|class|module|do|if|unless|while|until|for|begin|case)\b",
    "lua": r"(function|if|for|while|do|repeat)\b",
}


def _find_end_keyword_block_end(source: str, start: int, language: str) -> int:
    """Find the matching 'end' keyword for languages that use end-delimited blocks."""
    opener_pattern = _END_BLOCK_OPENERS.get(language, _END_BLOCK_OPENERS["ruby"])
    depth = 0
    lines = source[start:].split("\n")
    offset = start
    for line in lines:
        stripped = line.strip()
        if re.match(opener_pattern, stripped):
            depth += 1
        if stripped == "end" or stripped.startswith("end ") or stripped.startswith("end;"):
            depth -= 1
            if depth <= 0:
                return offset + len(line)
        offset += len(line) + 1
    return len(source)


def _parse_generic(source: str, rel_path: str, language: str) -> list[CodeChunk]:
    """Parse a non-Python source file using regex-based detection."""
    chunks: list[CodeChunk] = []
    covered_ranges: list[tuple[int, int]] = []

    # Find classes first (they may contain functions)
    class_pattern = _CLASS_PATTERNS.get(language)
    if class_pattern:
        for match in class_pattern.finditer(source):
            start = _line_start(source, match.start())
            end = _find_block_end(source, match.start(), language)
            chunks.append(
                CodeChunk(
                    content=source[start:end],
                    file_path=rel_path,
                    chunk_type="class",
                    language=language,
                    start_char=start,
                    end_char=end,
                )
            )
            covered_ranges.append((start, end))

    # Find standalone functions (not inside a class)
    func_pattern = _FUNCTION_PATTERNS.get(language)
    if func_pattern:
        for match in func_pattern.finditer(source):
            start = _line_start(source, match.start())
            # Skip if inside a class
            if any(cs <= start < ce for cs, ce in covered_ranges):
                continue
            end = _find_block_end(source, match.start(), language)
            chunks.append(
                CodeChunk(
                    content=source[start:end],
                    file_path=rel_path,
                    chunk_type="function",
                    language=language,
                    start_char=start,
                    end_char=end,
                )
            )
            covered_ranges.append((start, end))

    # If no chunks found, treat entire file as a module chunk
    if not chunks and source.strip():
        chunks.append(
            CodeChunk(
                content=source,
                file_path=rel_path,
                chunk_type="module",
                language=language,
                start_char=0,
                end_char=len(source),
            )
        )

    return chunks


def _line_start(source: str, pos: int) -> int:
    """Find the start of the line containing the given position."""
    return source.rfind("\n", 0, pos) + 1


def parse_file(file_path: str, root: str) -> list[CodeChunk]:
    """Parse a single source file into code chunks.

    Args:
        file_path: Absolute path to the source file.
        root: Root directory of the codebase (for computing relative paths).

    Returns:
        List of CodeChunk objects extracted from the file.

    Raises:
        SyntaxError: If the file cannot be parsed (for Python files).
        UnicodeDecodeError: If the file cannot be read as text.
    """
    rel_path = os.path.relpath(file_path, root)
    ext = os.path.splitext(file_path)[1].lower()
    language = SUPPORTED_EXTENSIONS.get(ext, "unknown")

    with open(file_path, encoding="utf-8", errors="replace") as f:
        source = f.read()

    if not source.strip():
        return []

    if language == "python":
        return _parse_python(source, rel_path)
    else:
        return _parse_generic(source, rel_path, language)


def parse_codebase(
    root: str,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[CodeChunk], list[str]]:
    """Parse an entire codebase into code chunks.

    Args:
        root: Root directory of the codebase.
        progress_callback: Optional callback called after each file with
            (files_processed, chunks_created, errors_count).

    Returns:
        A tuple of (chunks, errors) where errors is a list of error messages.
    """
    files = walk_directory(root)
    all_chunks: list[CodeChunk] = []
    errors: list[str] = []
    files_processed = 0

    for file_path in files:
        try:
            chunks = parse_file(file_path, root)
            all_chunks.extend(chunks)
        except Exception as exc:
            rel_path = os.path.relpath(file_path, root)
            error_msg = f"Failed to parse {rel_path}: {exc}"
            logger.warning(error_msg)
            errors.append(error_msg)

        files_processed += 1
        if progress_callback:
            progress_callback(files_processed, len(all_chunks), len(errors))

    return all_chunks, errors
