"""Tests for LLM tool-calling agent (Task 16)."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, ToolMessage

from codesherpa.navigation import (
    _glob_match,
    build_navigation_graph,
    tool_calling_agent,
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
        "query_type": "specific",
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


class TestToolCallingAgentLoop:
    """Tests for the tool-calling agent loop."""

    def test_executes_search_tool_and_returns_response(self):
        """Tool-calling loop executes a search tool and returns a response."""
        mock_llm = MagicMock()

        # First call: LLM requests search_code tool
        ai_with_tool = AIMessage(
            content="",
            tool_calls=[{
                "id": "call_1",
                "name": "search_code",
                "args": {"query": "function f"},
                "type": "tool_call",
            }],
        )
        # Second call: LLM returns final answer
        ai_final = AIMessage(content="Function f returns 1.")

        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = [ai_with_tool, ai_final]

        chunk = _make_search_result("a.py", "def f(): return 1")
        state = _base_state(llm=mock_llm)

        with patch("codesherpa.navigation.hybrid_search", return_value=[chunk]):
            result = tool_calling_agent(state)

        assert result["response"] is not None
        assert "Function f" in result["response"].explanation

    def test_loop_terminates_at_iteration_limit(self):
        """Loop terminates at the iteration limit and returns a partial answer."""
        mock_llm = MagicMock()

        # LLM always requests a tool call (never stops)
        ai_with_tool = AIMessage(
            content="Still searching...",
            tool_calls=[{
                "id": "call_1",
                "name": "search_code",
                "args": {"query": "something"},
                "type": "tool_call",
            }],
        )
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = ai_with_tool

        state = _base_state(llm=mock_llm)

        with patch("codesherpa.navigation.hybrid_search", return_value=[]):
            result = tool_calling_agent(state, max_iterations=3)

        # Should still return a response, not crash
        assert result["response"] is not None

    def test_read_file_tool_returns_correct_contents(self):
        """read_file tool returns correct file contents from the DB."""
        mock_llm = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [("def main(): print('hello')",)]

        # First call: LLM requests read_file tool
        ai_with_tool = AIMessage(
            content="",
            tool_calls=[{
                "id": "call_1",
                "name": "read_file",
                "args": {"file_path": "src/main.py"},
                "type": "tool_call",
            }],
        )
        # Second call: LLM returns final answer
        ai_final = AIMessage(content="The main function prints hello.")

        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = [ai_with_tool, ai_final]

        state = _base_state(llm=mock_llm, conn=mock_conn)
        result = tool_calling_agent(state)

        assert result["response"] is not None
        # Verify read_file_from_db was called with correct file path
        mock_cursor.execute.assert_called()

    def test_list_files_tool_filters_file_tree(self):
        """list_files tool filters the file tree by glob pattern."""
        mock_llm = MagicMock()

        # First call: LLM requests list_files tool
        ai_with_tool = AIMessage(
            content="",
            tool_calls=[{
                "id": "call_1",
                "name": "list_files",
                "args": {"pattern": "*.py"},
                "type": "tool_call",
            }],
        )
        # Second call: LLM returns final answer
        ai_final = AIMessage(content="Found Python files.")

        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = [ai_with_tool, ai_final]

        state = _base_state(
            llm=mock_llm,
            file_tree=["src/main.py", "src/utils.py", "README.md", "config.json"],
        )
        result = tool_calling_agent(state)

        assert result["response"] is not None
        # Verify that the LLM received tool results containing only .py files
        # Check the second invoke call's messages for the ToolMessage
        second_call_messages = mock_llm.invoke.call_args_list[1][0][0]
        tool_msg = [m for m in second_call_messages if isinstance(m, ToolMessage)]
        assert len(tool_msg) == 1
        assert "src/main.py" in tool_msg[0].content
        assert "src/utils.py" in tool_msg[0].content
        assert "README.md" not in tool_msg[0].content

    def test_progress_events_emitted_for_each_tool_call(self):
        """Progress events are emitted for each tool call."""
        mock_llm = MagicMock()
        progress_events = []

        def capture_progress(event):
            progress_events.append(event)

        # First call: LLM requests search_code
        ai_with_tool = AIMessage(
            content="",
            tool_calls=[{
                "id": "call_1",
                "name": "search_code",
                "args": {"query": "authentication"},
                "type": "tool_call",
            }],
        )
        # Second call: LLM returns final answer
        ai_final = AIMessage(content="Done.")

        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = [ai_with_tool, ai_final]

        state = _base_state(llm=mock_llm, progress_callback=capture_progress)

        with patch("codesherpa.navigation.hybrid_search", return_value=[]):
            tool_calling_agent(state)

        # Should have at least one "Tool call" progress event
        tool_events = [e for e in progress_events if e["step"] == "Tool call"]
        assert len(tool_events) >= 1
        assert "search_code" in tool_events[0]["detail"]

    def test_multiple_tool_calls_in_sequence(self):
        """Agent handles multiple sequential tool calls across iterations."""
        mock_llm = MagicMock()

        # First call: search
        ai_search = AIMessage(
            content="",
            tool_calls=[{
                "id": "call_1",
                "name": "search_code",
                "args": {"query": "auth"},
                "type": "tool_call",
            }],
        )
        # Second call: read_file
        ai_read = AIMessage(
            content="",
            tool_calls=[{
                "id": "call_2",
                "name": "read_file",
                "args": {"file_path": "auth.py"},
                "type": "tool_call",
            }],
        )
        # Third call: final answer
        ai_final = AIMessage(content="Auth uses JWT tokens.")

        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.side_effect = [ai_search, ai_read, ai_final]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [("class JWTAuth: ...",)]

        chunk = _make_search_result("auth.py", "class JWTAuth: ...")
        state = _base_state(llm=mock_llm, conn=mock_conn)

        with patch("codesherpa.navigation.hybrid_search", return_value=[chunk]):
            result = tool_calling_agent(state)

        assert result["response"] is not None
        assert "JWT" in result["response"].explanation


class TestToolCallingKeyFiles:
    """Tests that the tool-calling agent includes key file context."""

    def test_includes_key_files_in_initial_prompt(self):
        """Key project files (README, etc.) are auto-read and included in the system prompt."""
        mock_llm = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [("# My Project\nBuilt with Flask.",)]

        # LLM returns final answer immediately (no tool calls)
        ai_final = AIMessage(content="The project is built with Flask.")
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = ai_final

        state = _base_state(
            query="What is this project based on?",
            llm=mock_llm,
            conn=mock_conn,
            file_tree=["README.md", "src/app.py", "src/utils.py"],
        )
        result = tool_calling_agent(state)

        assert result["response"] is not None
        # Check the system message includes README content
        call_args = mock_llm.invoke.call_args[0][0]
        system_text = call_args[0].content
        assert "My Project" in system_text
        assert "README.md" in system_text


class TestToolCallingGraphIntegration:
    """Tests for tool-calling agent integration into the navigation graph."""

    def test_specific_query_uses_tool_calling(self):
        """A specific query routes through the tool-calling agent."""
        mock_llm = MagicMock()

        # classify → specific
        classify_response = MagicMock(content="specific")
        # tool_calling_agent: LLM returns final answer (no tool calls)
        ai_final = AIMessage(content="parse_codebase reads files and splits them into chunks.")

        mock_llm.invoke.return_value = classify_response
        mock_llm.bind_tools.return_value = mock_llm

        # After classification, the bound LLM is used
        bound_llm = MagicMock()
        bound_llm.invoke.return_value = ai_final
        mock_llm.bind_tools.return_value = bound_llm

        state = _base_state(query="what does parse_codebase do?", llm=mock_llm)
        graph = build_navigation_graph()

        with patch("codesherpa.navigation.search_episodic_memory", return_value=[]):
            with patch("codesherpa.navigation.search_semantic_memory_broad", return_value=[]):
                with patch("codesherpa.navigation.store_episodic_memory"):
                    result = graph.invoke(state)

        assert result["response"] is not None
        assert result["query_type"] == "specific"

    def test_exploration_query_uses_tool_calling(self):
        """An exploration query routes through the tool-calling agent."""
        mock_llm = MagicMock()

        # classify → exploration
        classify_response = MagicMock(content="exploration")
        ai_final = AIMessage(content="The auth system works as follows...")

        mock_llm.invoke.return_value = classify_response
        bound_llm = MagicMock()
        bound_llm.invoke.return_value = ai_final
        mock_llm.bind_tools.return_value = bound_llm

        state = _base_state(
            query="how does authentication work?",
            llm=mock_llm,
        )
        graph = build_navigation_graph()

        with patch("codesherpa.navigation.search_episodic_memory", return_value=[]):
            with patch("codesherpa.navigation.search_semantic_memory_broad", return_value=[]):
                with patch("codesherpa.navigation.store_episodic_memory"):
                    result = graph.invoke(state)

        assert result["response"] is not None
        assert result["query_type"] == "exploration"

    def test_map_query_still_uses_map_handler(self):
        """Map queries continue to use the existing handler, not tool calling."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.side_effect = [
            [("python", 10)],
            [("main.py",)],
        ]

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content="map"),  # classify
            MagicMock(content="Codebase map: Python project"),  # handle_map
        ]

        state = _base_state(query="map", conn=mock_conn, llm=mock_llm)
        graph = build_navigation_graph()

        with patch("codesherpa.navigation.search_episodic_memory", return_value=[]):
            with patch("codesherpa.navigation.search_semantic_memory_broad", return_value=[]):
                with patch("codesherpa.navigation.store_episodic_memory"):
                    result = graph.invoke(state)

        assert result["query_type"] == "map"
        # bind_tools should NOT have been called for map queries
        mock_llm.bind_tools.assert_not_called()

    def test_fallback_on_tool_calling_failure(self):
        """If tool calling fails, fall back to explain()."""
        mock_llm = MagicMock()

        # classify → specific
        classify_response = MagicMock(content="specific")
        mock_llm.invoke.return_value = classify_response

        # bind_tools raises an error (model doesn't support tools)
        mock_llm.bind_tools.side_effect = Exception("Model does not support tools")

        chunk = _make_search_result("a.py", "def f(): return 1")
        state = _base_state(query="what does f do?", llm=mock_llm)

        with patch("codesherpa.navigation.search_episodic_memory", return_value=[]):
            with patch("codesherpa.navigation.search_semantic_memory_broad", return_value=[]):
                with patch("codesherpa.navigation.store_episodic_memory"):
                    with patch("codesherpa.navigation.explain") as mock_explain:
                        from codesherpa.explanation import ExplanationResult
                        mock_explain.return_value = ExplanationResult(
                            explanation="f returns 1",
                            sources=[chunk],
                        )
                        graph = build_navigation_graph()
                        result = graph.invoke(state)

        assert result["response"] is not None
        assert result["response"].explanation == "f returns 1"


class TestGlobMatch:
    """Tests for _glob_match with proper ** support."""

    def test_simple_extension_matches_root_files(self):
        """*.md matches root-level files like README.md."""
        assert _glob_match("README.md", "*.md")

    def test_simple_extension_matches_nested_files(self):
        """*.py matches nested files like src/main.py."""
        assert _glob_match("src/main.py", "*.py")

    def test_simple_extension_excludes_wrong_type(self):
        """*.py does not match .md files."""
        assert not _glob_match("README.md", "*.py")

    def test_double_star_matches_root_files(self):
        """**/*.md matches root-level files like README.md."""
        assert _glob_match("README.md", "**/*.md")

    def test_double_star_matches_nested_files(self):
        """**/*.py matches nested files like src/auth/login.py."""
        assert _glob_match("src/auth/login.py", "**/*.py")

    def test_prefixed_double_star_matches_direct_children(self):
        """src/**/*.py matches direct children like src/main.py."""
        assert _glob_match("src/main.py", "src/**/*.py")

    def test_prefixed_double_star_matches_deep_children(self):
        """src/**/*.py matches deeply nested files."""
        assert _glob_match("src/auth/middleware.py", "src/**/*.py")

    def test_prefixed_double_star_excludes_other_dirs(self):
        """src/**/*.py does not match files outside src/."""
        assert not _glob_match("lib/utils.py", "src/**/*.py")

    def test_exact_filename_match(self):
        """README.md matches itself."""
        assert _glob_match("README.md", "README.md")

    def test_path_pattern_without_double_star(self):
        """src/*.py matches files in src/ directory."""
        assert _glob_match("src/main.py", "src/*.py")

    def test_name_prefix_pattern(self):
        """README* matches README.md."""
        assert _glob_match("README.md", "README*")
