"""Tests for the embedding and vector storage ingestion pipeline."""

import hashlib
from unittest.mock import MagicMock

from codesherpa.embeddings import CodeRankEmbedder
from codesherpa.ingestion import (
    compute_file_hash,
    ensure_schema,
    ingest,
)


class TestComputeFileHash:
    """Tests for file content hashing."""

    def test_returns_sha256_hex_digest(self):
        content = "def hello(): pass"
        expected = hashlib.sha256(content.encode()).hexdigest()
        assert compute_file_hash(content) == expected

    def test_different_content_gives_different_hash(self):
        assert compute_file_hash("abc") != compute_file_hash("def")

    def test_same_content_gives_same_hash(self):
        assert compute_file_hash("abc") == compute_file_hash("abc")


class TestEnsureSchema:
    """Tests for database schema creation."""

    def _make_schema_mock(self):
        """Create a mock conn/cursor where table and indexes don't exist yet."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        # _table_exists and _index_exists both call fetchone → (0,)
        mock_cursor.fetchone.return_value = (0,)
        return mock_conn, mock_cursor

    def test_creates_table_and_indexes(self):
        mock_conn, mock_cursor = self._make_schema_mock()

        ensure_schema(mock_conn)

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        assert "CREATE TABLE" in executed_sql or "CODE_CHUNKS" in executed_sql
        mock_conn.commit.assert_called()

    def test_table_has_required_columns(self):
        mock_conn, mock_cursor = self._make_schema_mock()

        ensure_schema(mock_conn)

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        for col in ["EMBEDDING", "CODE_TEXT", "FILE_PATH", "CHUNK_TYPE",
                     "LANGUAGE", "START_CHAR", "END_CHAR", "FILE_HASH"]:
            assert col in executed_sql, f"Missing column: {col}"

    def test_creates_vector_index(self):
        mock_conn, mock_cursor = self._make_schema_mock()

        ensure_schema(mock_conn)

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        assert "VECTOR" in executed_sql
        assert "INDEX" in executed_sql

    def test_creates_fulltext_index(self):
        mock_conn, mock_cursor = self._make_schema_mock()

        ensure_schema(mock_conn)

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        # Oracle Text full-text index uses CTXSYS.CONTEXT
        assert "CTXSYS" in executed_sql or "CONTEXT" in executed_sql


    def test_migrates_existing_table_adds_project_id(self):
        """When table exists but lacks project_id, ALTER TABLE is executed."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # table exists (1), column does NOT exist (0), indexes exist (1, 1)
        mock_cursor.fetchone.side_effect = [(1,), (0,), (1,), (1,)]

        ensure_schema(mock_conn)

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        assert "ALTER TABLE" in executed_sql
        assert "PROJECT_ID" in executed_sql


class TestBatchEmbedding:
    """Tests for batch embedding support in CodeRankEmbedder."""

    def test_embed_batch_returns_list_of_vectors(self, mocker):
        mock_model_cls = mocker.patch("codesherpa.embeddings.SentenceTransformer")
        mock_model = mock_model_cls.return_value
        # encode returns a 2D array for batch input
        mock_model.encode.return_value = [[0.1] * 768, [0.2] * 768]

        embedder = CodeRankEmbedder()
        results = embedder.embed_batch(["text one", "text two"])

        assert len(results) == 2
        assert len(results[0]) == 768
        assert len(results[1]) == 768
        mock_model.encode.assert_called_once_with(
            ["text one", "text two"]
        )

    def test_embed_batch_empty_list(self, mocker):
        mocker.patch("codesherpa.embeddings.SentenceTransformer")
        embedder = CodeRankEmbedder()
        results = embedder.embed_batch([])
        assert results == []


class TestIngest:
    """Tests for the full ingestion pipeline."""

    def _make_mock_conn(self):
        """Create a mock Oracle connection with cursor context manager."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return mock_conn, mock_cursor

    def test_full_pipeline_stores_all_chunks(self, tmp_path, mocker):
        """Parse → embed → store pipeline stores correct number of chunks."""
        # Create a test Python file
        test_file = tmp_path / "example.py"
        test_file.write_text(
            "def greet():\n    return 'hello'\n\ndef add(a, b):\n    return a + b\n"
        )

        mock_conn, mock_cursor = self._make_mock_conn()
        # No existing chunks in DB
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock(spec=CodeRankEmbedder)
        mock_embedder.embed_batch.return_value = [[0.1] * 768, [0.2] * 768, [0.3] * 768]

        stats = ingest(mock_conn, mock_embedder, str(tmp_path))

        assert stats["chunks_stored"] > 0
        assert mock_embedder.embed_batch.called

    def test_stored_entries_contain_all_metadata(self, tmp_path, mocker):
        """Each stored chunk has embedding, code text, and all metadata fields."""
        test_file = tmp_path / "hello.py"
        test_file.write_text("def hello():\n    pass\n")

        mock_conn, mock_cursor = self._make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock(spec=CodeRankEmbedder)
        mock_embedder.embed_batch.return_value = [[0.1] * 768]

        ingest(mock_conn, mock_embedder, str(tmp_path))

        # Check that executemany or execute was called with INSERT containing all columns
        all_calls = [str(c) for c in mock_cursor.execute.call_args_list]
        all_calls += [str(c) for c in mock_cursor.executemany.call_args_list]
        insert_sql = " ".join(all_calls).upper()
        for field in ["EMBEDDING", "CODE_TEXT", "FILE_PATH", "CHUNK_TYPE",
                       "LANGUAGE", "START_CHAR", "END_CHAR", "FILE_HASH"]:
            assert field in insert_sql, f"INSERT missing field: {field}"

    def test_reingestion_skips_unchanged_files(self, tmp_path, mocker):
        """Re-running ingest skips files whose hash hasn't changed."""
        test_file = tmp_path / "stable.py"
        content = "x = 1\n"
        test_file.write_text(content)
        file_hash = compute_file_hash(content)

        mock_conn, mock_cursor = self._make_mock_conn()
        # DB already has this file with the same hash
        mock_cursor.fetchall.return_value = [("stable.py", file_hash)]
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock(spec=CodeRankEmbedder)

        stats = ingest(mock_conn, mock_embedder, str(tmp_path))

        assert stats["files_skipped"] == 1
        assert stats["chunks_stored"] == 0

    def test_reingestion_updates_changed_files(self, tmp_path, mocker):
        """Re-running ingest re-embeds files whose content changed."""
        test_file = tmp_path / "changed.py"
        test_file.write_text("def new_func():\n    return 42\n")

        mock_conn, mock_cursor = self._make_mock_conn()
        # DB has old hash for this file
        mock_cursor.fetchall.return_value = [("changed.py", "old_hash_value")]
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock(spec=CodeRankEmbedder)
        mock_embedder.embed_batch.return_value = [[0.1] * 768]

        stats = ingest(mock_conn, mock_embedder, str(tmp_path))

        assert stats["files_updated"] >= 1
        # Should delete old chunks before inserting new ones
        delete_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "DELETE" in str(c).upper() and "CHANGED" in str(c).upper()
        ]
        assert len(delete_calls) > 0

    def test_reingestion_removes_deleted_files(self, tmp_path, mocker):
        """Files no longer on disk have their chunks removed from DB."""
        # Empty directory - no files
        mock_conn, mock_cursor = self._make_mock_conn()
        # DB has chunks for a file that no longer exists
        mock_cursor.fetchall.return_value = [("gone.py", "some_hash")]
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock(spec=CodeRankEmbedder)

        stats = ingest(mock_conn, mock_embedder, str(tmp_path))

        assert stats["files_deleted"] == 1
        delete_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "DELETE" in str(c).upper() and "GONE" in str(c).upper()
        ]
        assert len(delete_calls) > 0

    def test_chunk_count_matches_parser_output(self, tmp_path, mocker):
        """Number of stored chunks matches what the parser produces."""
        # Create files that will produce known chunk counts
        (tmp_path / "a.py").write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")
        (tmp_path / "b.py").write_text("class Baz:\n    def method(self):\n        pass\n")

        mock_conn, mock_cursor = self._make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0]

        # Count how many chunks the parser produces
        from codesherpa.parser import parse_codebase
        chunks, _ = parse_codebase(str(tmp_path))
        expected_count = len(chunks)

        mock_embedder = MagicMock(spec=CodeRankEmbedder)
        mock_embedder.embed_batch.return_value = [[0.1] * 768] * expected_count

        stats = ingest(mock_conn, mock_embedder, str(tmp_path))

        assert stats["chunks_stored"] == expected_count
