"""Tests for the memory-aware LangGraph routing module."""

from unittest.mock import MagicMock, patch

from codesherpa.retrieval import SearchResult
from codesherpa.routing import (
    build_query_graph,
    check_memory,
    explain_fresh,
    explain_with_context,
    route_query,
    update_memory,
)


def _make_search_result(path="a.py", code="def f(): pass"):
    return SearchResult(
        code_text=code, file_path=path, chunk_type="function",
        language="python", start_char=0, end_char=len(code), score=0.85,
    )


def _base_state(**overrides):
    """Create a minimal QueryState dict with defaults."""
    state = {
        "query": "What does f do?",
        "project_id": 1,
        "conn": MagicMock(),
        "embedder": MagicMock(),
        "llm": MagicMock(),
        "episodic_memories": [],
        "semantic_memories": [],
        "response": None,
        "explored_files": [],
    }
    state.update(overrides)
    return state


class TestCheckMemory:
    """Tests for the check_memory node that retrieves prior context."""

    def test_populates_episodic_memories(self):
        """check_memory retrieves relevant episodic memories."""
        memories = [
            {"id": 1, "query": "prior q", "file_paths": ["a.py"],
             "summary": "found stuff", "score": 0.9},
        ]
        state = _base_state()

        with patch("codesherpa.routing.search_episodic_memory", return_value=memories):
            with patch("codesherpa.routing.search_semantic_memory", return_value=[]):
                result = check_memory(state)

        assert len(result["episodic_memories"]) == 1
        assert result["episodic_memories"][0]["query"] == "prior q"

    def test_populates_semantic_memories(self):
        """check_memory retrieves relevant semantic memories."""
        context = [{"id": 1, "content": "this handles payments", "score": 0.95}]
        state = _base_state()

        with patch("codesherpa.routing.search_episodic_memory", return_value=[]):
            with patch("codesherpa.routing.search_semantic_memory", return_value=context):
                result = check_memory(state)

        assert len(result["semantic_memories"]) == 1
        assert result["semantic_memories"][0]["content"] == "this handles payments"


class TestRouteQuery:
    """Tests for the routing decision based on memory presence."""

    def test_routes_to_context_when_episodic_memory_exists(self):
        """Routes to 'build on context' path when episodic memories found."""
        state = _base_state(episodic_memories=[
            {"id": 1, "query": "q", "file_paths": [], "summary": "s", "score": 0.9}
        ])

        result = route_query(state)
        assert result == "explain_with_context"

    def test_routes_to_context_when_semantic_memory_exists(self):
        """Routes to 'build on context' path when semantic memories found."""
        state = _base_state(semantic_memories=[
            {"id": 1, "content": "context", "score": 0.9}
        ])

        result = route_query(state)
        assert result == "explain_with_context"

    def test_routes_to_fresh_when_no_memory(self):
        """Routes to 'full explanation' when no memories found."""
        state = _base_state()

        result = route_query(state)
        assert result == "explain_fresh"


class TestExplainWithContext:
    """Tests for the 'build on prior context' explanation path."""

    def test_includes_memory_context_in_llm_prompt(self):
        """Prior episodic and semantic memory are included in the LLM prompt."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="Building on what we explored before..."
        )

        chunks = [_make_search_result()]
        state = _base_state(
            llm=mock_llm,
            episodic_memories=[
                {"id": 1, "query": "prior", "file_paths": ["a.py"],
                 "summary": "previously explored a.py", "score": 0.9}
            ],
            semantic_memories=[
                {"id": 1, "content": "this is the payment service", "score": 0.95}
            ],
        )

        with patch("codesherpa.routing.hybrid_search", return_value=chunks):
            result = explain_with_context(state)

        assert result["response"] is not None
        assert result["explored_files"] == ["a.py"]

        # Verify memory context was passed to LLM
        call_args = mock_llm.invoke.call_args[0][0]
        messages_text = " ".join(str(m) for m in call_args)
        assert "previously explored" in messages_text
        assert "payment service" in messages_text

    def test_returns_explanation_and_sources(self):
        """Returns a proper ExplanationResult."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Explanation")

        chunks = [_make_search_result("billing.py")]
        state = _base_state(llm=mock_llm, episodic_memories=[
            {"id": 1, "query": "q", "file_paths": ["billing.py"],
             "summary": "s", "score": 0.9}
        ])

        with patch("codesherpa.routing.hybrid_search", return_value=chunks):
            result = explain_with_context(state)

        assert result["response"].explanation == "Explanation"
        assert result["response"].sources[0].file_path == "billing.py"


class TestExplainFresh:
    """Tests for the 'full explanation' path (no prior context)."""

    def test_delegates_to_standard_explain(self):
        """Fresh explanation uses the standard explain function."""
        from codesherpa.explanation import ExplanationResult

        expected = ExplanationResult(
            explanation="Fresh explanation",
            sources=[_make_search_result()],
        )
        state = _base_state()

        with patch("codesherpa.routing.explain", return_value=expected):
            result = explain_fresh(state)

        assert result["response"].explanation == "Fresh explanation"
        assert result["explored_files"] == ["a.py"]


class TestUpdateMemory:
    """Tests for updating memory after a response is generated."""

    def test_stores_episodic_memory(self):
        """After response, episodic memory is stored with explored files."""
        from codesherpa.explanation import ExplanationResult

        response = ExplanationResult(
            explanation="The function does X",
            sources=[_make_search_result("billing.py")],
        )
        state = _base_state(
            response=response,
            explored_files=["billing.py"],
        )

        with patch("codesherpa.routing.store_episodic_memory") as mock_store:
            update_memory(state)

        mock_store.assert_called_once()
        call_kwargs = mock_store.call_args[1]
        assert call_kwargs["project_id"] == 1
        assert "billing.py" in call_kwargs["file_paths"]

    def test_skips_memory_update_when_no_response(self):
        """No memory is stored if there's no response."""
        state = _base_state(response=None)

        with patch("codesherpa.routing.store_episodic_memory") as mock_store:
            update_memory(state)

        mock_store.assert_not_called()


class TestBuildQueryGraph:
    """Tests for the complete LangGraph state graph construction."""

    def test_graph_compiles_successfully(self):
        """The state graph compiles without errors."""
        graph = build_query_graph()
        assert graph is not None

    def test_graph_processes_query_with_no_memory(self):
        """End-to-end: query with no prior memory goes through fresh path."""
        from codesherpa.explanation import ExplanationResult

        expected = ExplanationResult(
            explanation="Fresh answer", sources=[_make_search_result()],
        )
        state = _base_state()

        graph = build_query_graph()

        with patch("codesherpa.routing.search_episodic_memory", return_value=[]):
            with patch("codesherpa.routing.search_semantic_memory", return_value=[]):
                with patch("codesherpa.routing.explain", return_value=expected):
                    with patch("codesherpa.routing.store_episodic_memory"):
                        result = graph.invoke(state)

        assert result["response"].explanation == "Fresh answer"

    def test_graph_processes_query_with_prior_memory(self):
        """End-to-end: query with prior memory goes through context path."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="Contextual answer")

        episodic = [
            {"id": 1, "query": "prior", "file_paths": ["old.py"],
             "summary": "prior exploration", "score": 0.9}
        ]
        state = _base_state(llm=mock_llm)

        graph = build_query_graph()

        with patch("codesherpa.routing.search_episodic_memory", return_value=episodic):
            with patch("codesherpa.routing.search_semantic_memory", return_value=[]):
                with patch(
                    "codesherpa.routing.hybrid_search",
                    return_value=[_make_search_result()],
                ):
                    with patch("codesherpa.routing.store_episodic_memory"):
                        result = graph.invoke(state)

        assert result["response"].explanation == "Contextual answer"
