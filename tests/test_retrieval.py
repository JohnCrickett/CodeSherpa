"""Tests for the semantic retrieval module."""

from unittest.mock import MagicMock, patch

from codesherpa.retrieval import (
    SearchResult,
    fulltext_search,
    hybrid_search,
    vector_search,
)


def _make_mock_cursor(rows, description=None):
    """Create a mock cursor that returns given rows."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _make_mock_conn(cursor):
    """Create a mock connection whose cursor() returns the given cursor."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def _make_mock_embedder(embedding=None):
    """Create a mock embedder that returns a fixed embedding."""
    embedder = MagicMock()
    if embedding is None:
        embedding = [0.1] * 768
    embedder.embed.return_value = embedding
    return embedder


class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_has_required_fields(self):
        """SearchResult has all required fields."""
        result = SearchResult(
            code_text="def foo(): pass",
            file_path="src/main.py",
            chunk_type="function",
            language="python",
            start_char=0,
            end_char=15,
            score=0.85,
        )
        assert result.code_text == "def foo(): pass"
        assert result.file_path == "src/main.py"
        assert result.chunk_type == "function"
        assert result.language == "python"
        assert result.start_char == 0
        assert result.end_char == 15
        assert result.score == 0.85

    def test_includes_file_path_and_line_reference(self):
        """Every result includes file path and character position references."""
        result = SearchResult(
            code_text="class Bar: ...",
            file_path="lib/models.py",
            chunk_type="class",
            language="python",
            start_char=100,
            end_char=200,
            score=0.5,
        )
        assert result.file_path == "lib/models.py"
        assert result.start_char == 100
        assert result.end_char == 200


class TestVectorSearch:
    """Tests for vector similarity search."""

    def test_returns_results_ranked_by_similarity(self):
        """Vector search returns results ordered by descending similarity score."""
        rows = [
            ("def foo(): pass", "src/a.py", "function", "python", 0, 15, 0.9),
            ("def bar(): pass", "src/b.py", "function", "python", 0, 15, 0.7),
        ]
        cursor = _make_mock_cursor(rows)
        conn = _make_mock_conn(cursor)
        embedder = _make_mock_embedder()

        results = vector_search(conn, embedder, "find foo function", top_k=10)

        assert len(results) == 2
        assert results[0].score >= results[1].score
        assert results[0].file_path == "src/a.py"
        embedder.embed.assert_called_once_with("find foo function", input_type="query")

    def test_applies_similarity_threshold(self):
        """Vector search filters results below the similarity threshold."""
        # The threshold filtering happens in the SQL query, so if DB returns
        # only rows above threshold, we get only those.
        rows = [
            ("def foo(): pass", "src/a.py", "function", "python", 0, 15, 0.8),
        ]
        cursor = _make_mock_cursor(rows)
        conn = _make_mock_conn(cursor)
        embedder = _make_mock_embedder()

        results = vector_search(conn, embedder, "some query", threshold=0.3)

        assert len(results) == 1
        assert results[0].score >= 0.3

    def test_returns_empty_when_no_matches(self):
        """Vector search returns empty list when no chunks exceed threshold."""
        cursor = _make_mock_cursor([])
        conn = _make_mock_conn(cursor)
        embedder = _make_mock_embedder()

        results = vector_search(conn, embedder, "nonexistent code xyz")

        assert results == []

    def test_embeds_query_with_query_input_type(self):
        """The user query is embedded with input_type='query'."""
        cursor = _make_mock_cursor([])
        conn = _make_mock_conn(cursor)
        embedder = _make_mock_embedder()

        vector_search(conn, embedder, "my question")

        embedder.embed.assert_called_once_with("my question", input_type="query")

    def test_respects_top_k(self):
        """Vector search passes top_k to limit results."""
        rows = [
            ("def a(): ...", "a.py", "function", "python", 0, 10, 0.9),
            ("def b(): ...", "b.py", "function", "python", 0, 10, 0.8),
        ]
        cursor = _make_mock_cursor(rows)
        conn = _make_mock_conn(cursor)
        embedder = _make_mock_embedder()

        results = vector_search(conn, embedder, "query", top_k=2)

        assert len(results) == 2


class TestFulltextSearch:
    """Tests for Oracle Text full-text search."""

    def test_returns_matching_chunks(self):
        """Full-text search returns chunks matching exact identifiers."""
        rows = [
            ("def calculate_total(): ...", "billing.py", "function", "python", 0, 30, 1),
        ]
        cursor = _make_mock_cursor(rows)
        conn = _make_mock_conn(cursor)

        results = fulltext_search(conn, "calculate_total", top_k=10)

        assert len(results) == 1
        assert results[0].file_path == "billing.py"
        assert "calculate_total" in results[0].code_text

    def test_returns_empty_when_no_matches(self):
        """Full-text search returns empty list when nothing matches."""
        cursor = _make_mock_cursor([])
        conn = _make_mock_conn(cursor)

        results = fulltext_search(conn, "xyznonexistent123")

        assert results == []

    def test_respects_top_k(self):
        """Full-text search limits results to top_k."""
        rows = [
            ("def a(): ...", "a.py", "function", "python", 0, 10, 5),
            ("def b(): ...", "b.py", "function", "python", 0, 10, 3),
        ]
        cursor = _make_mock_cursor(rows)
        conn = _make_mock_conn(cursor)

        results = fulltext_search(conn, "def", top_k=2)

        assert len(results) == 2

    def test_handles_question_marks_in_query(self):
        """Queries with ? (Oracle Text wildcard) don't cause parser errors."""
        rows = [
            ("def do_thing(): ...", "a.py", "function", "python", 0, 20, 1),
        ]
        cursor = _make_mock_cursor(rows)
        conn = _make_mock_conn(cursor)

        results = fulltext_search(conn, "what does this do?")

        assert len(results) == 1
        # Verify the escaped query passed to Oracle has no raw ?
        sql_params = cursor.execute.call_args[0][1]
        assert "?" not in sql_params[0]

    def test_handles_special_characters_in_query(self):
        """Queries with Oracle Text operators (& | ! * %) are safely escaped."""
        cursor = _make_mock_cursor([])
        conn = _make_mock_conn(cursor)

        fulltext_search(conn, "foo & bar | baz*")

        sql_params = cursor.execute.call_args[0][1]
        query_sent = sql_params[0]
        assert "&" not in query_sent
        assert "|" not in query_sent
        assert "*" not in query_sent

    def test_returns_empty_for_query_with_only_special_chars(self):
        """A query of only special characters returns empty without querying."""
        cursor = _make_mock_cursor([])
        conn = _make_mock_conn(cursor)

        results = fulltext_search(conn, "???")

        assert results == []
        cursor.execute.assert_not_called()


class TestHybridSearch:
    """Tests for hybrid search combining vector and full-text results."""

    def test_combines_vector_and_fulltext_results(self):
        """Hybrid search returns results from both search methods."""
        embedder = _make_mock_embedder()

        with patch("codesherpa.retrieval.vector_search") as mock_vec, \
             patch("codesherpa.retrieval.fulltext_search") as mock_ft:
            mock_vec.return_value = [
                SearchResult("def foo(): ...", "a.py", "function", "python", 0, 15, 0.9),
            ]
            mock_ft.return_value = [
                SearchResult("def bar(): ...", "b.py", "function", "python", 0, 15, 0.5),
            ]
            conn = MagicMock()
            results = hybrid_search(conn, embedder, "find functions")

        assert len(results) == 2

    def test_deduplicates_chunks_in_both_sets(self):
        """Chunks appearing in both vector and full-text results are deduplicated."""
        embedder = _make_mock_embedder()

        same_result_vec = SearchResult(
            "def foo(): pass", "a.py", "function", "python", 0, 15, 0.9,
        )
        same_result_ft = SearchResult(
            "def foo(): pass", "a.py", "function", "python", 0, 15, 0.5,
        )

        with patch("codesherpa.retrieval.vector_search") as mock_vec, \
             patch("codesherpa.retrieval.fulltext_search") as mock_ft:
            mock_vec.return_value = [same_result_vec]
            mock_ft.return_value = [same_result_ft]
            conn = MagicMock()
            results = hybrid_search(conn, embedder, "foo")

        # Same chunk should appear only once, with the higher score
        assert len(results) == 1
        assert results[0].score == 0.9

    def test_ranks_combined_results_by_score(self):
        """Combined results are ranked by score descending."""
        embedder = _make_mock_embedder()

        with patch("codesherpa.retrieval.vector_search") as mock_vec, \
             patch("codesherpa.retrieval.fulltext_search") as mock_ft:
            mock_vec.return_value = [
                SearchResult("def a(): ...", "a.py", "function", "python", 0, 10, 0.7),
            ]
            mock_ft.return_value = [
                SearchResult("def b(): ...", "b.py", "function", "python", 0, 10, 0.8),
            ]
            conn = MagicMock()
            results = hybrid_search(conn, embedder, "query")

        assert results[0].score >= results[1].score

    def test_returns_no_results_message_info(self):
        """When no results found, hybrid_search returns empty list."""
        embedder = _make_mock_embedder()

        with patch("codesherpa.retrieval.vector_search") as mock_vec, \
             patch("codesherpa.retrieval.fulltext_search") as mock_ft:
            mock_vec.return_value = []
            mock_ft.return_value = []
            conn = MagicMock()
            results = hybrid_search(conn, embedder, "nonexistent xyz")

        assert results == []

    def test_every_result_includes_file_path_and_location(self):
        """Every returned result includes file_path, start_char, and end_char."""
        embedder = _make_mock_embedder()

        with patch("codesherpa.retrieval.vector_search") as mock_vec, \
             patch("codesherpa.retrieval.fulltext_search") as mock_ft:
            mock_vec.return_value = [
                SearchResult("code1", "src/x.py", "function", "python", 10, 50, 0.9),
                SearchResult("code2", "src/y.py", "class", "python", 100, 300, 0.6),
            ]
            mock_ft.return_value = []
            conn = MagicMock()
            results = hybrid_search(conn, embedder, "query")

        for r in results:
            assert r.file_path is not None
            assert r.start_char is not None
            assert r.end_char is not None
