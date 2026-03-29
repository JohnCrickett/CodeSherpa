"""Tests for the intelligent navigation module."""

from unittest.mock import MagicMock, patch

from codesherpa.navigation import (
    _auto_read_key_files,
    build_navigation_graph,
    classify_query,
    extract_dependencies,
    handle_map_query,
    multi_step_retrieve,
    plan_exploration,
    read_file_from_db,
)
from codesherpa.retrieval import SearchResult


def _make_search_result(path="a.py", code="def f(): pass", chunk_type="function"):
    return SearchResult(
        code_text=code, file_path=path, chunk_type=chunk_type,
        language="python", start_char=0, end_char=len(code), score=0.85,
    )


def _base_state(**overrides):
    """Create a minimal NavigationState dict with defaults."""
    state = {
        "query": "What does f do?",
        "project_id": 1,
        "conn": MagicMock(),
        "embedder": MagicMock(),
        "llm": MagicMock(),
        "conversation_history": [],
        "query_type": "",
        "response": None,
        "dependencies": [],
        "explored_files": [],
        "episodic_memories": [],
        "semantic_memories": [],
        "file_tree": ["src/main.py", "src/utils.py"],
        "progress_callback": None,
    }
    state.update(overrides)
    return state


class TestClassifyQuery:
    """Tests for query classification into different navigation types."""

    def test_classifies_map_query(self):
        """A 'map' query is classified as map type."""
        state = _base_state(query="map")
        result = classify_query(state)
        assert result["query_type"] == "map"

    def test_classifies_map_query_case_insensitive(self):
        """Map classification is case-insensitive."""
        state = _base_state(query="Map")
        result = classify_query(state)
        assert result["query_type"] == "map"

    def test_classifies_follow_up_with_history(self):
        """A short question with conversation history is a follow-up."""
        state = _base_state(
            query="what calls this?",
            conversation_history=[
                {"query": "explain the parse function", "summary": "parse does X"},
            ],
        )
        result = classify_query(state)
        assert result["query_type"] == "follow_up"

    def test_classifies_exploration_for_broad_question(self):
        """Broad, system-level questions are classified as exploration."""
        state = _base_state(
            query="how does the authentication system work?",
        )
        # Mock LLM to return classification
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="exploration")
        state["llm"] = mock_llm
        result = classify_query(state)
        assert result["query_type"] == "exploration"

    def test_classifies_specific_question(self):
        """A specific question with no history is classified as specific."""
        state = _base_state(query="what does the parse function do?")
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="specific")
        state["llm"] = mock_llm
        result = classify_query(state)
        assert result["query_type"] == "specific"


class TestHandleMapQuery:
    """Tests for the map query handler that returns codebase structure."""

    def test_returns_language_breakdown(self):
        """Map query returns language statistics from ingested metadata."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Language counts
        mock_cursor.fetchall.side_effect = [
            [("python", 50), ("javascript", 20)],  # language counts
            [("src/main.py",), ("src/utils.py",)],  # file paths
        ]

        state = _base_state(conn=mock_conn, query="map")

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="## Codebase Map\n- Python: 50 chunks\n- JavaScript: 20 chunks"
        )
        state["llm"] = mock_llm

        result = handle_map_query(state)
        assert result["response"] is not None
        assert result["response"].explanation != ""

    def test_returns_module_structure(self):
        """Map query includes top-level module breakdown."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.fetchall.side_effect = [
            [("python", 10)],
            [("src/auth/login.py",), ("src/auth/logout.py",), ("src/db/conn.py",)],
        ]

        state = _base_state(conn=mock_conn, query="map")
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="## Modules\n- src/auth: login, logout\n- src/db: conn"
        )
        state["llm"] = mock_llm

        result = handle_map_query(state)
        assert result["response"] is not None


class TestExtractDependencies:
    """Tests for dependency extraction from code chunks."""

    def test_extracts_python_imports(self):
        """Extracts import statements from Python code."""
        code = "import os\nfrom pathlib import Path\ndef foo(): pass"
        chunk = _make_search_result(code=code)
        deps = extract_dependencies([chunk])
        assert any("os" in d["target"] for d in deps)
        assert any("pathlib" in d["target"] for d in deps)

    def test_extracts_function_calls(self):
        """Extracts function calls from code."""
        code = "def handler():\n    result = process_data(items)\n    save(result)"
        chunk = _make_search_result(code=code)
        deps = extract_dependencies([chunk])
        assert any("process_data" in d["target"] for d in deps)

    def test_returns_empty_for_no_dependencies(self):
        """Returns empty list when no dependencies found."""
        code = "x = 1\ny = 2"
        chunk = _make_search_result(code=code)
        deps = extract_dependencies([chunk])
        assert isinstance(deps, list)

    def test_extracts_class_inheritance(self):
        """Extracts parent classes from class definitions."""
        code = "class MyHandler(BaseHandler):\n    pass"
        chunk = _make_search_result(code=code)
        deps = extract_dependencies([chunk])
        assert any("BaseHandler" in d["target"] for d in deps)


class TestMultiStepRetrieve:
    """Tests for multi-step retrieval (retrieve → find references → retrieve again → explain)."""

    def test_performs_initial_retrieval_and_follow_up(self):
        """Multi-step retrieval does an initial search, then retrieves references."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="Function f is called by g in b.py"
        )

        initial_chunk = _make_search_result("a.py", "def f(): return 1")
        follow_up_chunk = _make_search_result("b.py", "def g(): return f()")

        state = _base_state(
            query="what calls f?",
            llm=mock_llm,
            conversation_history=[
                {"query": "explain f", "summary": "f returns 1", "files": ["a.py"]},
            ],
            query_type="follow_up",
        )

        with patch("codesherpa.navigation.hybrid_search") as mock_search:
            mock_search.side_effect = [
                [initial_chunk],
                [follow_up_chunk],
            ]
            result = multi_step_retrieve(state)

        assert result["response"] is not None
        assert "a.py" in result["explored_files"] or "b.py" in result["explored_files"]

    def test_includes_dependencies_in_result(self):
        """Multi-step retrieval extracts dependencies from retrieved chunks."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Explanation")

        chunk = _make_search_result("a.py", "from utils import helper\ndef f(): helper()")

        state = _base_state(query="explain f", llm=mock_llm, query_type="specific")

        with patch("codesherpa.navigation.hybrid_search", return_value=[chunk]):
            result = multi_step_retrieve(state)

        assert isinstance(result["dependencies"], list)


class TestPlanExploration:
    """Tests for exploration planning for broad questions."""

    def test_generates_multi_step_plan(self):
        """Broad question triggers multi-step exploration with coherent walkthrough."""
        mock_llm = MagicMock()
        # First call: plan steps. Second call: final explanation.
        mock_llm.invoke.side_effect = [
            MagicMock(content="1. Find entry points\n2. Trace auth flow"),
            MagicMock(content="The auth system works as follows: ..."),
        ]

        chunks_1 = [_make_search_result("auth/login.py", "def login(): ...")]
        chunks_2 = [_make_search_result("auth/middleware.py", "class AuthMiddleware: ...")]

        state = _base_state(
            query="how does the authentication system work?",
            llm=mock_llm,
            query_type="exploration",
        )

        with patch("codesherpa.navigation.hybrid_search") as mock_search:
            mock_search.side_effect = [chunks_1, chunks_2]
            result = plan_exploration(state)

        assert result["response"] is not None
        assert len(result["explored_files"]) > 0

    def test_produces_coherent_walkthrough(self):
        """Exploration result is a coherent walkthrough, not just search results."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content="1. Check routes\n2. Check handlers"),
            MagicMock(content="The system routes requests through handlers which..."),
        ]

        state = _base_state(
            query="how does request handling work?",
            llm=mock_llm,
            query_type="exploration",
        )

        with patch("codesherpa.navigation.hybrid_search", return_value=[
            _make_search_result("routes.py", "app.get('/api')"),
        ]):
            result = plan_exploration(state)

        assert result["response"] is not None
        assert len(result["response"].explanation) > 0


class TestBuildNavigationGraph:
    """Tests for the complete navigation LangGraph state graph."""

    def test_graph_compiles(self):
        """The navigation graph compiles without errors."""
        graph = build_navigation_graph()
        assert graph is not None

    def test_map_query_routes_correctly(self):
        """A 'map' query routes through the map handler."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.side_effect = [
            [("python", 10)],
            [("main.py",)],
        ]

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Codebase map: Python project")

        state = _base_state(query="map", conn=mock_conn, llm=mock_llm)
        graph = build_navigation_graph()

        with patch("codesherpa.navigation.search_episodic_memory", return_value=[]):
            with patch("codesherpa.navigation.search_semantic_memory", return_value=[]):
                with patch("codesherpa.navigation.store_episodic_memory"):
                    result = graph.invoke(state)

        assert result["query_type"] == "map"
        assert result["response"] is not None

    def test_follow_up_routes_correctly(self):
        """A follow-up question with history routes to multi-step retrieval."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="The callers are...")

        state = _base_state(
            query="what calls this?",
            llm=mock_llm,
            conversation_history=[
                {"query": "explain parse", "summary": "parse does X", "files": ["parser.py"]},
            ],
        )

        graph = build_navigation_graph()

        with patch("codesherpa.navigation.search_episodic_memory", return_value=[]):
            with patch("codesherpa.navigation.search_semantic_memory", return_value=[]):
                with patch("codesherpa.navigation.hybrid_search", return_value=[
                    _make_search_result("cli.py", "def main(): parse()")
                ]):
                    with patch("codesherpa.navigation.store_episodic_memory"):
                        result = graph.invoke(state)

        assert result["query_type"] == "follow_up"
        assert result["response"] is not None

    def test_specific_query_routes_correctly(self):
        """A specific question with no history routes to multi-step retrieval."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content="specific"),  # classify
            MagicMock(content="The function parses code"),  # explain
        ]

        state = _base_state(query="what does parse_codebase do?", llm=mock_llm)

        graph = build_navigation_graph()

        with patch("codesherpa.navigation.search_episodic_memory", return_value=[]):
            with patch("codesherpa.navigation.search_semantic_memory", return_value=[]):
                with patch("codesherpa.navigation.hybrid_search", return_value=[
                    _make_search_result("parser.py", "def parse_codebase(): ...")
                ]):
                    with patch("codesherpa.navigation.store_episodic_memory"):
                        result = graph.invoke(state)

        assert result["response"] is not None

    def test_exploration_routes_correctly(self):
        """A broad question routes through exploration planning."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content="exploration"),  # classify
            MagicMock(content="1. Check auth module"),  # plan
            MagicMock(content="The auth system uses..."),  # synthesize
        ]

        state = _base_state(
            query="how does the authentication system work?",
            llm=mock_llm,
        )

        graph = build_navigation_graph()

        with patch("codesherpa.navigation.search_episodic_memory", return_value=[]):
            with patch("codesherpa.navigation.search_semantic_memory", return_value=[]):
                with patch("codesherpa.navigation.hybrid_search", return_value=[
                    _make_search_result("auth.py", "def authenticate(): ...")
                ]):
                    with patch("codesherpa.navigation.store_episodic_memory"):
                        result = graph.invoke(state)

        assert result["query_type"] == "exploration"
        assert result["response"] is not None


class TestReadFileFromDb:
    """Tests for reading file contents from the database."""

    def test_returns_file_contents(self):
        """read_file_from_db returns concatenated code chunks."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor,
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [
            ("def foo(): pass",),
            ("def bar(): pass",),
        ]

        result = read_file_from_db(mock_conn, 1, "src/main.py")
        assert "def foo(): pass" in result
        assert "def bar(): pass" in result

    def test_returns_not_found_message(self):
        """read_file_from_db returns a message when file not found."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor,
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []

        result = read_file_from_db(mock_conn, 1, "nonexistent.py")
        assert "not found" in result.lower()


class TestAutoReadKeyFiles:
    """Tests for proactively reading key project files."""

    def test_reads_readme(self):
        """README.md is identified and read as a key file."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor,
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [
            ("# My Project\nThis does XYZ.",),
        ]

        file_tree = ["README.md", "src/main.py", "src/utils.py"]
        result = _auto_read_key_files(mock_conn, 1, file_tree)
        assert "My Project" in result
        assert "README.md" in result

    def test_reads_entry_points(self):
        """Entry point files (main.py, app.py) are identified."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=mock_cursor,
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [("def main(): ...",)]

        file_tree = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        result = _auto_read_key_files(mock_conn, 1, file_tree)
        assert "main.py" in result

    def test_returns_empty_for_no_key_files(self):
        """Returns empty string when no key files found."""
        mock_conn = MagicMock()
        file_tree = ["src/utils.py", "src/helpers.py"]
        result = _auto_read_key_files(mock_conn, 1, file_tree)
        assert result == ""


class TestFileTreeInPrompts:
    """Tests that file tree context is included in LLM prompts."""

    def test_multi_step_retrieve_includes_file_tree(self):
        """multi_step_retrieve includes the file tree in the LLM prompt."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="Explanation of the code",
        )

        state = _base_state(
            query="what does main do?",
            llm=mock_llm,
            query_type="specific",
            file_tree=["src/main.py", "src/utils.py", "tests/test_main.py"],
        )

        with patch("codesherpa.navigation.hybrid_search", return_value=[
            _make_search_result("src/main.py", "def main(): ..."),
        ]):
            multi_step_retrieve(state)

        # Check that file tree was included in the LLM prompt
        call_args = mock_llm.invoke.call_args[0][0]
        prompt_text = " ".join(str(m.content) for m in call_args)
        assert "src/main.py" in prompt_text
        assert "src/utils.py" in prompt_text

    def test_plan_exploration_includes_file_tree(self):
        """plan_exploration includes the file tree in the LLM prompt."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content="1. Check main module"),
            MagicMock(content="The system works by..."),
        ]

        state = _base_state(
            query="how does the system work?",
            llm=mock_llm,
            query_type="exploration",
            file_tree=["app/server.py", "app/routes.py"],
        )

        with patch("codesherpa.navigation.hybrid_search", return_value=[
            _make_search_result("app/server.py", "app = Flask(__name__)"),
        ]):
            plan_exploration(state)

        # The synthesis call (second invoke) should include file tree
        synth_call = mock_llm.invoke.call_args_list[-1][0][0]
        prompt_text = " ".join(str(m.content) for m in synth_call)
        assert "app/server.py" in prompt_text
        assert "app/routes.py" in prompt_text


class TestKeyFilePatterns:
    """Tests for _KEY_FILE_PATTERNS matching project config, build, and deploy files."""

    def test_existing_patterns_still_match(self):
        """Existing patterns (readme, changelog, entry points) continue to match."""
        from codesherpa.navigation import _KEY_FILE_PATTERNS

        existing_should_match = [
            "README.md",
            "readme.txt",
            "CHANGELOG.md",
            "changelog",
            "CONTRIBUTING.md",
            "contributing.rst",
            "LICENSE",
            "license.txt",
            "main.py",
            "app.js",
            "index.html",
            "server.ts",
            "cli.py",
        ]
        for filename in existing_should_match:
            assert _KEY_FILE_PATTERNS.search(filename), (
                f"Expected '{filename}' to match _KEY_FILE_PATTERNS"
            )

    def test_project_config_build_files_match(self):
        """Project config and build files match the pattern."""
        from codesherpa.navigation import _KEY_FILE_PATTERNS

        config_files = [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
            "build.gradle",
            "Makefile",
            "CMakeLists.txt",
        ]
        for filename in config_files:
            assert _KEY_FILE_PATTERNS.search(filename), (
                f"Expected '{filename}' to match _KEY_FILE_PATTERNS"
            )

    def test_container_deploy_files_match(self):
        """Container and deployment files match the pattern."""
        from codesherpa.navigation import _KEY_FILE_PATTERNS

        deploy_files = [
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
        ]
        for filename in deploy_files:
            assert _KEY_FILE_PATTERNS.search(filename), (
                f"Expected '{filename}' to match _KEY_FILE_PATTERNS"
            )

    def test_unrelated_files_do_not_match(self):
        """Unrelated filenames should not match the pattern."""
        from codesherpa.navigation import _KEY_FILE_PATTERNS

        should_not_match = [
            "utils.py",
            "random.txt",
            "helpers.js",
            "models.py",
            "test_main.py",
            "data.csv",
            "styles.css",
        ]
        for filename in should_not_match:
            assert not _KEY_FILE_PATTERNS.search(filename), (
                f"Expected '{filename}' NOT to match _KEY_FILE_PATTERNS"
            )


def _make_search_result_lang(path, code, language, chunk_type="module"):
    """Helper to create a SearchResult with a specific language."""
    return SearchResult(
        code_text=code, file_path=path, chunk_type=chunk_type,
        language=language, start_char=0, end_char=len(code), score=0.85,
    )


class TestExtractDependenciesMultiLanguage:
    """Tests for multi-language dependency extraction."""

    # --- JavaScript / TypeScript ---

    def test_extracts_js_import_from(self):
        """Extracts ES module imports: import X from 'Y'."""
        code = "import React from 'react';\nimport { useState } from 'react';"
        chunk = _make_search_result_lang("app.js", code, "javascript")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "react" in import_targets

    def test_extracts_js_require(self):
        """Extracts CommonJS require('Y') calls."""
        code = "const fs = require('fs');\nconst path = require('path');"
        chunk = _make_search_result_lang("app.js", code, "javascript")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "fs" in import_targets
        assert "path" in import_targets

    def test_extracts_js_dynamic_import(self):
        """Extracts dynamic import('Y') calls."""
        code = "const mod = await import('lodash');"
        chunk = _make_search_result_lang("app.js", code, "javascript")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "lodash" in import_targets

    def test_extracts_ts_imports(self):
        """TypeScript uses the same patterns as JavaScript."""
        code = "import { Component } from '@angular/core';\nconst x = require('express');"
        chunk = _make_search_result_lang("app.ts", code, "typescript")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "@angular/core" in import_targets
        assert "express" in import_targets

    # --- Go ---

    def test_extracts_go_single_import(self):
        """Extracts Go single-line import statements."""
        code = 'import "fmt"\n\nfunc main() {}'
        chunk = _make_search_result_lang("main.go", code, "go")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "fmt" in import_targets

    def test_extracts_go_multi_import(self):
        """Extracts Go multi-line import blocks."""
        code = 'import (\n\t"fmt"\n\t"os"\n\t"net/http"\n)\n\nfunc main() {}'
        chunk = _make_search_result_lang("main.go", code, "go")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "fmt" in import_targets
        assert "os" in import_targets
        assert "net/http" in import_targets

    # --- Java ---

    def test_extracts_java_import(self):
        """Extracts Java import statements."""
        code = "import com.example.Foo;\nimport java.util.List;\n\npublic class Bar {}"
        chunk = _make_search_result_lang("Bar.java", code, "java")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "com.example.Foo" in import_targets
        assert "java.util.List" in import_targets

    def test_extracts_java_extends(self):
        """Extracts Java class inheritance via extends."""
        code = "public class Dog extends Animal {\n}"
        chunk = _make_search_result_lang("Dog.java", code, "java")
        deps = extract_dependencies([chunk])
        inherit_targets = [d["target"] for d in deps if d["type"] == "inherits"]
        assert "Animal" in inherit_targets

    def test_extracts_java_implements(self):
        """Extracts Java class inheritance via implements."""
        code = "public class Dog extends Animal implements Runnable, Serializable {\n}"
        chunk = _make_search_result_lang("Dog.java", code, "java")
        deps = extract_dependencies([chunk])
        inherit_targets = [d["target"] for d in deps if d["type"] == "inherits"]
        assert "Animal" in inherit_targets
        assert "Runnable" in inherit_targets
        assert "Serializable" in inherit_targets

    # --- Generic fallback ---

    def test_generic_fallback_for_rust(self):
        """Unsupported language (Rust) uses generic fallback to find 'use' statements."""
        code = "use std::io;\nuse std::collections::HashMap;\n\nfn main() {}"
        chunk = _make_search_result_lang("main.rs", code, "rust")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "std::io" in import_targets
        assert "std::collections::HashMap" in import_targets

    def test_generic_fallback_detects_include(self):
        """Generic fallback detects #include statements (e.g. C/C++)."""
        code = '#include <stdio.h>\n#include "myheader.h"\n\nint main() {}'
        chunk = _make_search_result_lang("main.c", code, "c")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        assert "stdio.h" in import_targets
        assert "myheader.h" in import_targets

    # --- Python still works ---

    def test_python_extraction_still_works(self):
        """Existing Python extraction behaviour is preserved."""
        code = "import os\nfrom pathlib import Path\nclass Foo(Bar):\n    pass"
        chunk = _make_search_result_lang("app.py", code, "python")
        deps = extract_dependencies([chunk])
        import_targets = [d["target"] for d in deps if d["type"] == "import"]
        inherit_targets = [d["target"] for d in deps if d["type"] == "inherits"]
        assert "os" in import_targets
        assert "pathlib" in import_targets
        assert "Bar" in inherit_targets

    def test_function_calls_extracted_for_all_languages(self):
        """Function call extraction works regardless of language."""
        code = "function handler() {\n  process_data(items);\n  save(result);\n}"
        chunk = _make_search_result_lang("app.js", code, "javascript")
        deps = extract_dependencies([chunk])
        call_targets = [d["target"] for d in deps if d["type"] == "calls"]
        assert "process_data" in call_targets
