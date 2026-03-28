"""Tests for the LLM-powered explanation module."""

from unittest.mock import MagicMock, patch

from codesherpa.explanation import ExplanationResult, explain
from codesherpa.retrieval import SearchResult


def _make_search_results(*items):
    """Create a list of SearchResult from (code, path, chunk_type) tuples."""
    results = []
    for i, (code, path, chunk_type) in enumerate(items):
        results.append(
            SearchResult(
                code_text=code,
                file_path=path,
                chunk_type=chunk_type,
                language="python",
                start_char=i * 100,
                end_char=i * 100 + len(code),
                score=0.9 - i * 0.1,
            )
        )
    return results


class TestExplanationResult:
    """Tests for the ExplanationResult dataclass."""

    def test_has_explanation_and_sources(self):
        """ExplanationResult contains explanation text and source chunks."""
        sources = _make_search_results(("def foo(): pass", "a.py", "function"))
        result = ExplanationResult(explanation="foo is a function", sources=sources)
        assert result.explanation == "foo is a function"
        assert len(result.sources) == 1
        assert result.sources[0].file_path == "a.py"


class TestExplainFunction:
    """Tests for the explain() function that drives the retrieval chain."""

    def test_returns_explanation_with_source_citations(self):
        """Explanation cites specific files and functions from retrieved chunks."""
        chunks = _make_search_results(
            ("def calculate_total(items):\n    return sum(i.price for i in items)",
             "billing.py", "function"),
        )
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="The `calculate_total` function in `billing.py` sums the price of all items."
        )

        with patch("codesherpa.explanation.hybrid_search", return_value=chunks):
            result = explain(
                conn=MagicMock(),
                embedder=MagicMock(),
                llm=mock_llm,
                question="What does calculate_total do?",
            )

        assert isinstance(result, ExplanationResult)
        assert "billing.py" in result.explanation
        assert "calculate_total" in result.explanation
        assert len(result.sources) == 1
        assert result.sources[0].file_path == "billing.py"

    def test_retrieves_from_multiple_areas_for_relationship_query(self):
        """When asked how two parts relate, retrieves from both areas."""
        chunks = _make_search_results(
            ("def create_order(cart): ...", "orders.py", "function"),
            ("def process_payment(order): ...", "payments.py", "function"),
        )
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="create_order in orders.py creates an order from a cart, "
            "then process_payment in payments.py handles the payment for that order."
        )

        with patch("codesherpa.explanation.hybrid_search", return_value=chunks):
            result = explain(
                conn=MagicMock(),
                embedder=MagicMock(),
                llm=mock_llm,
                question="How do orders and payments relate?",
            )

        assert len(result.sources) == 2
        file_paths = {s.file_path for s in result.sources}
        assert "orders.py" in file_paths
        assert "payments.py" in file_paths

    def test_flags_when_question_cannot_be_fully_answered(self):
        """When no relevant code is found, explanation flags the limitation."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="I could not find relevant code to answer this question."
        )

        with patch("codesherpa.explanation.hybrid_search", return_value=[]):
            result = explain(
                conn=MagicMock(),
                embedder=MagicMock(),
                llm=mock_llm,
                question="How does the authentication system work?",
            )

        assert isinstance(result, ExplanationResult)
        assert len(result.sources) == 0

    def test_surfaces_multiple_implementations(self):
        """When multiple implementations exist, all are surfaced as sources."""
        chunks = _make_search_results(
            ("def sort_bubble(arr): ...", "sort_bubble.py", "function"),
            ("def sort_quick(arr): ...", "sort_quick.py", "function"),
            ("def sort_merge(arr): ...", "sort_merge.py", "function"),
        )
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="There are three sorting implementations: "
            "sort_bubble in sort_bubble.py, sort_quick in sort_quick.py, "
            "and sort_merge in sort_merge.py."
        )

        with patch("codesherpa.explanation.hybrid_search", return_value=chunks):
            result = explain(
                conn=MagicMock(),
                embedder=MagicMock(),
                llm=mock_llm,
                question="What sorting implementations exist?",
            )

        assert len(result.sources) == 3

    def test_passes_retrieved_chunks_as_context_to_llm(self):
        """The LLM receives retrieved code chunks as context in its prompt."""
        chunks = _make_search_results(
            ("def hello(): print('hi')", "greet.py", "function"),
        )
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="hello prints hi")

        with patch("codesherpa.explanation.hybrid_search", return_value=chunks):
            explain(
                conn=MagicMock(),
                embedder=MagicMock(),
                llm=mock_llm,
                question="What does hello do?",
            )

        # The LLM should have been invoked with messages containing the code chunk
        call_args = mock_llm.invoke.call_args[0][0]
        # call_args is a list of messages
        messages_text = " ".join(str(m) for m in call_args)
        assert "def hello(): print('hi')" in messages_text
        assert "greet.py" in messages_text

    def test_includes_question_in_llm_prompt(self):
        """The user's question is included in the prompt sent to the LLM."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="explanation")

        with patch("codesherpa.explanation.hybrid_search", return_value=[]):
            explain(
                conn=MagicMock(),
                embedder=MagicMock(),
                llm=mock_llm,
                question="How does caching work?",
            )

        call_args = mock_llm.invoke.call_args[0][0]
        messages_text = " ".join(str(m) for m in call_args)
        assert "How does caching work?" in messages_text
