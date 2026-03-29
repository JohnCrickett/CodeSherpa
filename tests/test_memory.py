"""Tests for the agent memory module (episodic + semantic memory)."""

import json
from unittest.mock import MagicMock

from codesherpa.memory import (
    bulk_delete_all_memory,
    bulk_delete_episodic_memory,
    bulk_delete_semantic_memory,
    delete_episodic_memory,
    delete_semantic_memory,
    ensure_memory_schema,
    get_exploration_summary,
    list_episodic_memories,
    list_semantic_memories,
    search_episodic_memory,
    search_memory,
    search_semantic_memory,
    store_episodic_memory,
    store_semantic_memory,
)


def _mock_cursor():
    """Create a mock cursor that works as a context manager."""
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _mock_conn(cursor=None):
    """Create a mock connection returning the given cursor."""
    conn = MagicMock()
    if cursor is None:
        cursor = _mock_cursor()
    conn.cursor.return_value = cursor
    return conn


def _mock_embedder(embedding=None):
    """Create a mock embedder returning a fixed vector."""
    embedder = MagicMock()
    if embedding is None:
        embedding = [0.1] * 768
    embedder.embed.return_value = embedding
    return embedder


class TestEnsureMemorySchema:
    """Tests for ensure_memory_schema table creation."""

    def test_creates_tables_when_missing(self):
        """Both memory tables are created when they don't exist."""
        cursor = _mock_cursor()
        cursor.fetchone.return_value = [0]  # table does not exist
        conn = _mock_conn(cursor)

        ensure_memory_schema(conn)

        # Should have executed CREATE TABLE statements
        executed_sqls = [
            str(c[0][0]) for c in cursor.execute.call_args_list
        ]
        create_stmts = [s for s in executed_sqls if "CREATE TABLE" in s]
        assert len(create_stmts) == 2
        conn.commit.assert_called()

    def test_skips_creation_when_tables_exist(self):
        """No CREATE TABLE when tables already exist."""
        cursor = _mock_cursor()
        cursor.fetchone.return_value = [1]  # table exists
        conn = _mock_conn(cursor)

        ensure_memory_schema(conn)

        executed_sqls = [
            str(c[0][0]) for c in cursor.execute.call_args_list
        ]
        create_stmts = [s for s in executed_sqls if "CREATE TABLE" in s]
        assert len(create_stmts) == 0


class TestStoreEpisodicMemory:
    """Tests for storing episodic memory entries."""

    def test_stores_entry_with_embedding(self):
        """Episodic memory is stored with query embedding and file paths."""
        cursor = _mock_cursor()
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        store_episodic_memory(
            conn, embedder, project_id=1,
            query="What does calculate_total do?",
            file_paths=["billing.py", "utils.py"],
            summary="Explored billing logic",
        )

        embedder.embed.assert_called_once_with(
            "What does calculate_total do?", input_type="query"
        )
        # Should have inserted into EPISODIC_MEMORY
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT" in str(c[0][0]) and "EPISODIC" in str(c[0][0])
        ]
        assert len(insert_calls) == 1
        conn.commit.assert_called()

    def test_file_paths_stored_as_json(self):
        """File paths are serialized as JSON array."""
        cursor = _mock_cursor()
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        store_episodic_memory(
            conn, embedder, project_id=1,
            query="test",
            file_paths=["a.py", "b.py"],
            summary="test summary",
        )

        insert_call = [
            c for c in cursor.execute.call_args_list
            if "INSERT" in str(c[0][0]) and "EPISODIC" in str(c[0][0])
        ][0]
        params = insert_call[0][1]
        # The file_paths param should be a JSON string
        file_paths_json = params[3]  # positional: project_id, embedding, query, file_paths, summary
        parsed = json.loads(file_paths_json)
        assert parsed == ["a.py", "b.py"]


class TestStoreSemanticMemory:
    """Tests for storing semantic memory entries."""

    def test_stores_context_with_embedding(self):
        """Semantic memory is stored with content embedding."""
        cursor = _mock_cursor()
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        store_semantic_memory(
            conn, embedder, project_id=1,
            content="This service owns all payment logic",
        )

        embedder.embed.assert_called_once_with(
            "This service owns all payment logic", input_type="document"
        )
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if "INSERT" in str(c[0][0]) and "SEMANTIC" in str(c[0][0])
        ]
        assert len(insert_calls) == 1
        conn.commit.assert_called()


class TestSearchEpisodicMemory:
    """Tests for searching episodic memory by semantic similarity."""

    def test_returns_relevant_memories(self):
        """Searching returns memories ordered by similarity."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = [
            (1, "What does billing do?", '["billing.py"]', "Explored billing", 0.92),
            (2, "How does payment work?", '["pay.py"]', "Explored payments", 0.85),
        ]
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        results = search_episodic_memory(conn, embedder, "billing logic", project_id=1)

        assert len(results) == 2
        assert results[0]["query"] == "What does billing do?"
        assert results[0]["file_paths"] == ["billing.py"]
        assert results[0]["summary"] == "Explored billing"
        assert results[0]["score"] == 0.92

    def test_returns_empty_list_for_no_matches(self):
        """Returns empty list when no relevant memories exist."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = []
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        results = search_episodic_memory(conn, embedder, "unrelated", project_id=1)
        assert results == []

    def test_respects_top_k_limit(self):
        """Only top_k results are returned."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = [(1, "q", "[]", "s", 0.9)]
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        search_episodic_memory(conn, embedder, "test", project_id=1, top_k=3)

        # Verify top_k was passed to query
        sql_call = cursor.execute.call_args
        params = sql_call[0][1]
        assert 3 in params


class TestSearchSemanticMemory:
    """Tests for searching semantic memory by similarity."""

    def test_returns_relevant_context(self):
        """Searching returns stored context ordered by similarity."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = [
            (1, "This service owns payment logic", 0.95),
        ]
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        results = search_semantic_memory(conn, embedder, "payments", project_id=1)

        assert len(results) == 1
        assert results[0]["content"] == "This service owns payment logic"
        assert results[0]["score"] == 0.95


class TestGetExplorationSummary:
    """Tests for the exploration summary."""

    def test_returns_explored_files_and_queries(self):
        """Summary includes all explored file paths and queries."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = [
            ("What does billing do?", '["billing.py", "utils.py"]'),
            ("How does auth work?", '["auth.py"]'),
        ]
        conn = _mock_conn(cursor)

        summary = get_exploration_summary(conn, project_id=1)

        assert "billing.py" in summary["explored_files"]
        assert "utils.py" in summary["explored_files"]
        assert "auth.py" in summary["explored_files"]
        assert len(summary["queries"]) == 2
        assert summary["queries"][0] == "What does billing do?"

    def test_returns_empty_summary_when_nothing_explored(self):
        """Summary is empty when no episodic memories exist."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = []
        conn = _mock_conn(cursor)

        summary = get_exploration_summary(conn, project_id=1)

        assert summary["explored_files"] == []
        assert summary["queries"] == []

    def test_deduplicates_explored_files(self):
        """Files explored multiple times appear only once."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = [
            ("Query 1", '["billing.py", "utils.py"]'),
            ("Query 2", '["billing.py", "auth.py"]'),
        ]
        conn = _mock_conn(cursor)

        summary = get_exploration_summary(conn, project_id=1)

        assert len(summary["explored_files"]) == 3  # billing, utils, auth


class TestListSemanticMemories:
    """Tests for listing all semantic memories."""

    def test_returns_all_memories_for_project(self):
        """All semantic memories for a project are returned."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = [
            (1, "Context about payments", "2025-01-01 00:00:00"),
            (2, "Auth uses JWT tokens", "2025-01-02 00:00:00"),
        ]
        conn = _mock_conn(cursor)

        memories = list_semantic_memories(conn, project_id=1)

        assert len(memories) == 2
        assert memories[0]["id"] == 1
        assert memories[0]["content"] == "Context about payments"
        assert memories[1]["content"] == "Auth uses JWT tokens"

    def test_returns_empty_list_when_no_memories(self):
        """Returns empty list for project with no semantic memories."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = []
        conn = _mock_conn(cursor)

        memories = list_semantic_memories(conn, project_id=1)
        assert memories == []


class TestDeleteSemanticMemory:
    """Tests for deleting semantic memory entries."""

    def test_deletes_memory_by_id(self):
        """Memory is deleted by ID."""
        cursor = _mock_cursor()
        cursor.rowcount = 1
        conn = _mock_conn(cursor)

        delete_semantic_memory(conn, memory_id=5)

        delete_calls = [
            c for c in cursor.execute.call_args_list
            if "DELETE" in str(c[0][0])
        ]
        assert len(delete_calls) == 1
        conn.commit.assert_called()


class TestListEpisodicMemories:
    """Tests for listing all episodic memories."""

    def test_list_episodic_memories_returns_entries(self):
        """Returns entries with all fields."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = [
            (1, "What does billing do?", '["billing.py"]',
             "Explored billing", "2025-01-01 00:00:00"),
            (2, "How does auth work?", '["auth.py"]',
             "Explored auth", "2025-01-02 00:00:00"),
        ]
        conn = _mock_conn(cursor)

        memories = list_episodic_memories(conn, project_id=1)

        assert len(memories) == 2
        assert memories[0]["id"] == 1
        assert memories[0]["query"] == "What does billing do?"
        assert memories[0]["file_paths"] == ["billing.py"]
        assert memories[0]["summary"] == "Explored billing"
        assert memories[0]["created_at"] == "2025-01-01 00:00:00"
        assert memories[1]["id"] == 2

    def test_list_episodic_memories_empty(self):
        """Returns empty list when none exist."""
        cursor = _mock_cursor()
        cursor.fetchall.return_value = []
        conn = _mock_conn(cursor)

        memories = list_episodic_memories(conn, project_id=1)
        assert memories == []


class TestDeleteEpisodicMemory:
    """Tests for deleting episodic memory entries."""

    def test_delete_episodic_memory(self):
        """Executes DELETE with correct ID."""
        cursor = _mock_cursor()
        cursor.rowcount = 1
        conn = _mock_conn(cursor)

        delete_episodic_memory(conn, memory_id=7)

        delete_calls = [
            c for c in cursor.execute.call_args_list
            if "DELETE" in str(c[0][0]) and "EPISODIC" in str(c[0][0])
        ]
        assert len(delete_calls) == 1
        conn.commit.assert_called()


class TestBulkDeleteEpisodicMemory:
    """Tests for bulk deleting episodic memory."""

    def test_bulk_delete_episodic_memory(self):
        """Deletes all for project, returns count."""
        cursor = _mock_cursor()
        cursor.rowcount = 5
        conn = _mock_conn(cursor)

        count = bulk_delete_episodic_memory(conn, project_id=1)

        assert count == 5
        delete_calls = [
            c for c in cursor.execute.call_args_list
            if "DELETE" in str(c[0][0]) and "EPISODIC" in str(c[0][0])
        ]
        assert len(delete_calls) == 1
        conn.commit.assert_called()


class TestBulkDeleteSemanticMemory:
    """Tests for bulk deleting semantic memory."""

    def test_bulk_delete_semantic_memory(self):
        """Deletes all for project, returns count."""
        cursor = _mock_cursor()
        cursor.rowcount = 3
        conn = _mock_conn(cursor)

        count = bulk_delete_semantic_memory(conn, project_id=1)

        assert count == 3
        delete_calls = [
            c for c in cursor.execute.call_args_list
            if "DELETE" in str(c[0][0]) and "SEMANTIC" in str(c[0][0])
        ]
        assert len(delete_calls) == 1
        conn.commit.assert_called()


class TestBulkDeleteAllMemory:
    """Tests for bulk deleting all memory."""

    def test_bulk_delete_all_memory(self):
        """Deletes both types, returns counts."""
        cursor = _mock_cursor()
        # rowcount changes per execute call
        cursor.rowcount = 5  # default
        conn = _mock_conn(cursor)

        # We need rowcount to return different values for each delete
        rowcounts = [4, 3]
        cursor_call_count = [0]
        original_execute = cursor.execute

        def track_execute(*args, **kwargs):
            original_execute(*args, **kwargs)
            if args and "DELETE" in str(args[0]):
                cursor.rowcount = rowcounts[cursor_call_count[0]]
                cursor_call_count[0] += 1

        cursor.execute = MagicMock(side_effect=track_execute)

        result = bulk_delete_all_memory(conn, project_id=1)

        assert result["episodic_deleted"] == 4
        assert result["semantic_deleted"] == 3
        conn.commit.assert_called()


class TestSearchMemory:
    """Tests for unified memory search."""

    def test_search_memory_combines_results(self):
        """Returns results from both types, labeled."""
        cursor = _mock_cursor()
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        # Mock fetchall to return results for 4 queries:
        # 1. episodic vector search
        # 2. semantic vector search
        # 3. episodic text search
        # 4. semantic text search
        cursor.fetchall.side_effect = [
            [(1, "billing query", '["billing.py"]', "billing summary", 0.9)],  # episodic vector
            [(10, "payment context", 0.85)],  # semantic vector
            [],  # episodic text
            [],  # semantic text
        ]

        results = search_memory(conn, embedder, "billing", project_id=1)

        assert len(results) == 2
        types = {r["type"] for r in results}
        assert "episodic" in types
        assert "semantic" in types

    def test_search_memory_deduplicates(self):
        """Same entry from vector + text search appears once."""
        cursor = _mock_cursor()
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        # Same episodic entry appears in both vector and text search
        cursor.fetchall.side_effect = [
            [(1, "billing query", '["billing.py"]', "billing summary", 0.9)],  # episodic vector
            [],  # semantic vector
            # episodic text (duplicate)
            [(1, "billing query", '["billing.py"]', "billing summary", None)],
            [],  # semantic text
        ]

        results = search_memory(conn, embedder, "billing", project_id=1)

        episodic_results = [r for r in results if r["type"] == "episodic"]
        assert len(episodic_results) == 1

    def test_search_memory_empty(self):
        """Returns empty list when no matches."""
        cursor = _mock_cursor()
        conn = _mock_conn(cursor)
        embedder = _mock_embedder()

        cursor.fetchall.side_effect = [[], [], [], []]

        results = search_memory(conn, embedder, "nonexistent", project_id=1)
        assert results == []
