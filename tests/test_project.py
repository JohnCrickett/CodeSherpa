"""Tests for project management: CRUD, isolation, metadata, incremental re-ingestion."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from codesherpa.project import (
    ProjectExistsError,
    ProjectNotFoundError,
    create_project,
    delete_project,
    ensure_projects_schema,
    get_project,
    list_projects,
    migrate_orphaned_chunks,
    update_project_stats,
)


def _make_mock_conn():
    """Create a mock conn/cursor pair."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


class TestEnsureProjectsSchema:
    """Tests for PROJECTS table creation."""

    def test_creates_projects_table(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = (0,)

        ensure_projects_schema(mock_conn)

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        assert "CREATE TABLE" in executed_sql
        assert "PROJECTS" in executed_sql
        mock_conn.commit.assert_called()

    def test_projects_table_has_required_columns(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = (0,)

        ensure_projects_schema(mock_conn)

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        for col in ["NAME", "SOURCE_PATH", "CREATED_AT", "LAST_INGESTED_AT",
                     "FILE_COUNT", "CHUNK_COUNT"]:
            assert col in executed_sql, f"Missing column: {col}"

    def test_skips_creation_if_table_exists(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = (1,)

        ensure_projects_schema(mock_conn)

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        assert "CREATE TABLE PROJECTS" not in executed_sql


class TestCreateProject:
    """Tests for project creation."""

    def test_creates_project_returns_id(self):
        mock_conn, mock_cursor = _make_mock_conn()
        # No existing project with same name
        mock_cursor.fetchone.side_effect = [(0,), (42,)]

        project_id = create_project(mock_conn, "my-project", "/path/to/code")

        assert project_id == 42
        mock_conn.commit.assert_called()

    def test_raises_if_project_name_already_exists(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = (1,)

        with pytest.raises(ProjectExistsError, match="my-project"):
            create_project(mock_conn, "my-project", "/path/to/code")

    def test_stores_source_path(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.side_effect = [(0,), (1,)]

        create_project(mock_conn, "proj", "/some/path")

        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT" in str(c).upper()
        ]
        assert len(insert_calls) > 0
        insert_sql = str(insert_calls[0])
        assert "SOURCE_PATH" in insert_sql.upper()


class TestGetProject:
    """Tests for retrieving a project by name."""

    def test_returns_project_dict(self):
        mock_conn, mock_cursor = _make_mock_conn()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchone.return_value = (
            1, "my-project", "/path", now, now, 10, 50,
        )

        project = get_project(mock_conn, "my-project")

        assert project["id"] == 1
        assert project["name"] == "my-project"
        assert project["source_path"] == "/path"
        assert project["file_count"] == 10
        assert project["chunk_count"] == 50

    def test_raises_if_not_found(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = None

        with pytest.raises(ProjectNotFoundError, match="no-such"):
            get_project(mock_conn, "no-such")


class TestListProjects:
    """Tests for listing all projects."""

    def test_returns_list_of_project_dicts(self):
        mock_conn, mock_cursor = _make_mock_conn()
        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            (1, "proj-a", "/a", now, now, 5, 20),
            (2, "proj-b", "/b", now, None, 0, 0),
        ]

        projects = list_projects(mock_conn)

        assert len(projects) == 2
        assert projects[0]["name"] == "proj-a"
        assert projects[1]["name"] == "proj-b"

    def test_returns_empty_list_when_no_projects(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchall.return_value = []

        projects = list_projects(mock_conn)

        assert projects == []


class TestDeleteProject:
    """Tests for project deletion."""

    def test_deletes_project_and_its_chunks(self):
        mock_conn, mock_cursor = _make_mock_conn()
        # get_project returns a valid project
        mock_cursor.fetchone.return_value = (
            1, "old-proj", "/path",
            datetime.now(timezone.utc), None, 5, 20,
        )

        delete_project(mock_conn, "old-proj")

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        assert "DELETE" in executed_sql
        mock_conn.commit.assert_called()

    def test_deletes_episodic_memory_for_project(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = (
            1, "proj", "/path",
            datetime.now(timezone.utc), None, 5, 20,
        )

        delete_project(mock_conn, "proj")

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        assert "EPISODIC_MEMORY" in executed_sql

    def test_deletes_semantic_memory_for_project(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = (
            1, "proj", "/path",
            datetime.now(timezone.utc), None, 5, 20,
        )

        delete_project(mock_conn, "proj")

        executed_sql = " ".join(
            str(c.args[0]) for c in mock_cursor.execute.call_args_list
        ).upper()
        assert "SEMANTIC_MEMORY" in executed_sql

    def test_raises_if_project_not_found(self):
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = None

        with pytest.raises(ProjectNotFoundError, match="ghost"):
            delete_project(mock_conn, "ghost")


class TestUpdateProjectStats:
    """Tests for updating project metadata after ingestion."""

    def test_updates_file_and_chunk_counts(self):
        mock_conn, mock_cursor = _make_mock_conn()

        update_project_stats(mock_conn, project_id=1, file_count=10, chunk_count=50)

        update_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "UPDATE" in str(c).upper()
        ]
        assert len(update_calls) > 0
        mock_conn.commit.assert_called()


class TestProjectIsolation:
    """Tests that queries are scoped to a single project."""

    def test_ingestion_stores_project_id_with_chunks(self, tmp_path):
        """Chunks inserted during ingestion include the project_id."""
        from codesherpa.embeddings import CodeRankEmbedder
        from codesherpa.ingestion import ingest

        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock(spec=CodeRankEmbedder)
        mock_embedder.embed_batch.return_value = [[0.1] * 768]

        test_file = tmp_path / "a.py"
        test_file.write_text("def f(): pass\n")

        ingest(mock_conn, mock_embedder, str(tmp_path), project_id=7)

        # Verify project_id appears in INSERT
        all_calls = [str(c) for c in mock_cursor.executemany.call_args_list]
        insert_sql = " ".join(all_calls).upper()
        assert "PROJECT_ID" in insert_sql

    def test_retrieval_filters_by_project_id(self):
        """Search queries include project_id filter."""
        from codesherpa.retrieval import vector_search

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [0.1] * 768

        vector_search(mock_conn, mock_embedder, "test query", project_id=3)

        executed_sql = str(mock_cursor.execute.call_args).upper()
        assert "PROJECT_ID" in executed_sql

    def test_fulltext_search_filters_by_project_id(self):
        """Full-text search queries include project_id filter."""
        from codesherpa.retrieval import fulltext_search

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        fulltext_search(mock_conn, "test query", project_id=3)

        executed_sql = str(mock_cursor.execute.call_args).upper()
        assert "PROJECT_ID" in executed_sql


class TestMigrateOrphanedChunks:
    """Tests for migrating pre-existing chunks to a default project."""

    def test_assigns_orphaned_chunks_to_askdocs_project(self):
        """Chunks with NULL project_id are assigned to the AskDocs project."""
        mock_conn, mock_cursor = _make_mock_conn()
        # First call: orphan count = 5
        # Then get_or_create_project checks: no existing project (None)
        # Then create_project: count=0, then select id=1
        # Then UPDATE, then two COUNT queries for stats, then UPDATE stats
        mock_cursor.fetchone.side_effect = [
            (5,),     # orphan count
            None,     # get_or_create_project: SELECT id WHERE name = AskDocs
            (0,),     # create_project: COUNT WHERE name = AskDocs
            (1,),     # create_project: SELECT id after INSERT
            (10,),    # file_count (DISTINCT file_path)
            (5,),     # chunk_count
        ]

        migrate_orphaned_chunks(mock_conn)

        # Should have run UPDATE to set project_id
        update_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "UPDATE" in str(c).upper() and "PROJECT_ID" in str(c).upper()
        ]
        assert len(update_calls) > 0

    def test_skips_migration_when_no_orphans(self):
        """No-op when there are no orphaned chunks."""
        mock_conn, mock_cursor = _make_mock_conn()
        mock_cursor.fetchone.return_value = (0,)

        migrate_orphaned_chunks(mock_conn)

        # Should only have the one SELECT COUNT query, no UPDATEs
        assert mock_cursor.execute.call_count == 1
