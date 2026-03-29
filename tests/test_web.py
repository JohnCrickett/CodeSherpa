"""Tests for the FastAPI web interface backend."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from codesherpa.retrieval import SearchResult


def _make_search_result(code="def f(): pass", path="a.py", chunk_type="function"):
    return SearchResult(
        code_text=code,
        file_path=path,
        chunk_type=chunk_type,
        language="python",
        start_char=0,
        end_char=len(code),
        score=0.85,
    )


@pytest.fixture
def mock_conn():
    return MagicMock()


@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 768
    return embedder


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Explanation text.")
    return llm


@pytest.fixture
def client(mock_conn, mock_embedder, mock_llm):
    from codesherpa.web import create_app

    app = create_app(conn=mock_conn, embedder=mock_embedder, llm=mock_llm)
    return TestClient(app)


class TestListProjects:
    """GET /api/projects returns the list of projects."""

    def test_returns_projects(self, client, mock_conn):
        now = datetime.now(timezone.utc)
        projects = [
            {"id": 1, "name": "proj-a", "source_path": "/a",
             "created_at": now, "last_ingested_at": now,
             "file_count": 5, "chunk_count": 20},
            {"id": 2, "name": "proj-b", "source_path": "/b",
             "created_at": now, "last_ingested_at": None,
             "file_count": 0, "chunk_count": 0},
        ]
        with patch("codesherpa.web.list_projects", return_value=projects):
            resp = client.get("/api/projects")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "proj-a"
        assert data[1]["name"] == "proj-b"

    def test_returns_empty_list(self, client, mock_conn):
        with patch("codesherpa.web.list_projects", return_value=[]):
            resp = client.get("/api/projects")

        assert resp.status_code == 200
        assert resp.json() == []


class TestFileTree:
    """GET /api/projects/{id}/files returns the file tree."""

    def test_returns_file_paths(self, client, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("src/main.py",),
            ("src/utils.py",),
            ("tests/test_main.py",),
        ]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            resp = client.get("/api/projects/1/files")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert "src/main.py" in data

    def test_returns_404_for_missing_project(self, client, mock_conn):
        from codesherpa.project import ProjectNotFoundError

        with patch(
            "codesherpa.web.get_project_by_id",
            side_effect=ProjectNotFoundError("not found"),
        ):
            resp = client.get("/api/projects/999/files")

        assert resp.status_code == 404


class TestAskEndpoint:
    """POST /api/projects/{id}/ask sends a question and returns explanation + sources."""

    def test_returns_explanation_and_sources(self, client, mock_conn):
        from codesherpa.explanation import ExplanationResult

        sources = [_make_search_result()]
        result = ExplanationResult(explanation="f is a function", sources=sources)

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"response": result, "dependencies": []}

        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.build_navigation_graph", return_value=mock_graph):
                resp = client.post(
                    "/api/projects/1/ask",
                    json={"question": "What does f do?"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] == "f is a function"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["file_path"] == "a.py"
        assert data["sources"][0]["start_char"] == 0
        assert data["sources"][0]["end_char"] == 13

    def test_returns_404_for_missing_project(self, client, mock_conn):
        from codesherpa.project import ProjectNotFoundError

        with patch(
            "codesherpa.web.get_project_by_id",
            side_effect=ProjectNotFoundError("not found"),
        ):
            resp = client.post(
                "/api/projects/999/ask",
                json={"question": "anything"},
            )

        assert resp.status_code == 404

    def test_returns_422_without_question(self, client):
        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            resp = client.post("/api/projects/1/ask", json={})

        assert resp.status_code == 422

    def test_active_file_prepended_to_question(self, client, mock_conn):
        from codesherpa.explanation import ExplanationResult

        result = ExplanationResult(explanation="it does stuff", sources=[])

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"response": result, "dependencies": []}

        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.build_navigation_graph", return_value=mock_graph):
                client.post(
                    "/api/projects/1/ask",
                    json={"question": "What does this file do?", "active_file": "src/main.py"},
                )

        graph_call = mock_graph.invoke.call_args[0][0]
        query_sent = graph_call["query"]
        assert "src/main.py" in query_sent
        assert "What does this file do?" in query_sent


class TestQueryEndpoint:
    """POST /api/projects/{id}/query returns raw search results without LLM."""

    def test_returns_search_results(self, client, mock_conn, mock_embedder):
        results = [_make_search_result("class Foo: pass", "foo.py", "class")]

        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.hybrid_search", return_value=results):
                resp = client.post(
                    "/api/projects/1/query",
                    json={"question": "Foo class"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["file_path"] == "foo.py"
        assert data[0]["chunk_type"] == "class"
        assert data[0]["code_text"] == "class Foo: pass"


class TestFileContent:
    """GET /api/projects/{id}/files/{path} returns chunks for a file."""

    def test_returns_chunks_ordered_by_position(self, client, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("def foo(): pass", "function", "python", 0, 15),
            ("def bar(): pass", "function", "python", 16, 31),
        ]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            resp = client.get("/api/projects/1/files/src/main.py")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["code_text"] == "def foo(): pass"
        assert data[0]["chunk_type"] == "function"
        assert data[0]["start_char"] == 0
        assert data[1]["code_text"] == "def bar(): pass"

    def test_returns_empty_list_for_unknown_file(self, client, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            resp = client.get("/api/projects/1/files/nope.py")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_404_for_missing_project(self, client, mock_conn):
        from codesherpa.project import ProjectNotFoundError

        with patch(
            "codesherpa.web.get_project_by_id",
            side_effect=ProjectNotFoundError("not found"),
        ):
            resp = client.get("/api/projects/999/files/a.py")

        assert resp.status_code == 404


class TestCreateProject:
    """POST /api/projects creates a new project."""

    def test_creates_project_returns_201(self, client, mock_conn):
        with patch("codesherpa.web.resolve_source", return_value="/resolved/path"):
            with patch("codesherpa.web.create_project", return_value=42):
                resp = client.post(
                    "/api/projects",
                    json={"name": "my-project", "source": "/some/path"},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == 42
        assert data["name"] == "my-project"
        assert data["source_path"] == "/resolved/path"

    def test_duplicate_name_returns_409(self, client, mock_conn):
        from codesherpa.project import ProjectExistsError

        with patch("codesherpa.web.resolve_source", return_value="/resolved/path"):
            with patch(
                "codesherpa.web.create_project",
                side_effect=ProjectExistsError("exists"),
            ):
                resp = client.post(
                    "/api/projects",
                    json={"name": "dup", "source": "/some/path"},
                )

        assert resp.status_code == 409
        assert "exists" in resp.json()["detail"].lower()

    def test_empty_name_returns_400(self, client, mock_conn):
        resp = client.post(
            "/api/projects",
            json={"name": "", "source": "/some/path"},
        )
        assert resp.status_code == 400

    def test_empty_source_returns_400(self, client, mock_conn):
        resp = client.post(
            "/api/projects",
            json={"name": "proj", "source": ""},
        )
        assert resp.status_code == 400

    def test_invalid_source_returns_400(self, client, mock_conn):
        from codesherpa.repo import RepoError

        with patch(
            "codesherpa.web.resolve_source",
            side_effect=RepoError("Path does not exist"),
        ):
            resp = client.post(
                "/api/projects",
                json={"name": "proj", "source": "/nonexistent"},
            )

        assert resp.status_code == 400
        assert "path" in resp.json()["detail"].lower()

    def test_github_url_source_resolves(self, client, mock_conn):
        mock_resolve = patch("codesherpa.web.resolve_source", return_value="/cache/owner_repo")
        with mock_resolve as mock_resolve:
            with patch("codesherpa.web.create_project", return_value=1):
                resp = client.post(
                    "/api/projects",
                    json={"name": "gh-proj", "source": "https://github.com/owner/repo"},
                )

        assert resp.status_code == 201
        mock_resolve.assert_called_once_with("https://github.com/owner/repo")


class TestIngestEndpoint:
    """POST /api/projects/{id}/ingest streams ingestion progress via SSE."""

    def test_returns_404_for_missing_project(self, client, mock_conn):
        from codesherpa.project import ProjectNotFoundError

        with patch(
            "codesherpa.web.get_project_by_id",
            side_effect=ProjectNotFoundError("not found"),
        ):
            resp = client.post("/api/projects/999/ingest")

        assert resp.status_code == 404

    def test_returns_sse_content_type(self, client, mock_conn, mock_embedder):
        project = {"id": 1, "name": "proj", "source_path": "/src"}
        with patch("codesherpa.web.get_project_by_id", return_value=project):
            with patch("codesherpa.web.resolve_source", return_value="/src"):
                with patch("codesherpa.web.ingest", return_value={
                    "chunks_stored": 5, "files_skipped": 0,
                    "files_updated": 0, "files_deleted": 0,
                }):
                    with patch("codesherpa.web.update_project_stats"):
                        with patch("codesherpa.web.walk_directory", return_value=["a.py"]):
                            with patch("codesherpa.web._count_project_chunks", return_value=5):
                                resp = client.post("/api/projects/1/ingest")

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_streams_complete_event_with_stats(self, client, mock_conn, mock_embedder):
        project = {"id": 1, "name": "proj", "source_path": "/src"}
        stats = {
            "chunks_stored": 10, "files_skipped": 2,
            "files_updated": 1, "files_deleted": 0,
        }
        with patch("codesherpa.web.get_project_by_id", return_value=project):
            with patch("codesherpa.web.resolve_source", return_value="/src"):
                with patch("codesherpa.web.ingest", return_value=stats):
                    with patch("codesherpa.web.update_project_stats"):
                        with patch("codesherpa.web.walk_directory", return_value=["a.py"] * 3):
                            with patch("codesherpa.web._count_project_chunks", return_value=10):
                                resp = client.post("/api/projects/1/ingest")

        assert resp.status_code == 200
        body = resp.text
        assert "complete" in body
        assert "chunks_stored" in body

    def test_concurrent_ingestion_returns_409(self, client, mock_conn, mock_embedder):
        from codesherpa.web import _active_ingestions

        project = {"id": 1, "name": "proj", "source_path": "/src"}
        _active_ingestions.add(1)
        try:
            with patch("codesherpa.web.get_project_by_id", return_value=project):
                resp = client.post("/api/projects/1/ingest")

            assert resp.status_code == 409
            assert "already" in resp.json()["detail"].lower()
        finally:
            _active_ingestions.discard(1)

    def test_streams_error_event_on_failure(self, client, mock_conn, mock_embedder):
        project = {"id": 1, "name": "proj", "source_path": "/src"}
        with patch("codesherpa.web.get_project_by_id", return_value=project):
            with patch("codesherpa.web.resolve_source", return_value="/src"):
                with patch("codesherpa.web.ingest", side_effect=RuntimeError("Embedding failed")):
                    resp = client.post("/api/projects/1/ingest")

        assert resp.status_code == 200  # SSE stream still returns 200
        body = resp.text
        assert "error" in body
        assert "Embedding failed" in body


class TestIngestProgressCallback:
    """The ingest() function invokes the progress callback at each phase."""

    def test_callback_receives_parsing_event(self, tmp_path):
        from codesherpa.ingestion import ingest

        (tmp_path / "a.py").write_text("x = 1\n")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768]

        events = []
        ingest(mock_conn, mock_embedder, str(tmp_path), progress_callback=events.append)

        phases = [e["phase"] for e in events]
        assert "parsing" in phases

    def test_callback_receives_embedding_events(self, tmp_path):
        from codesherpa.ingestion import ingest

        (tmp_path / "a.py").write_text("def foo():\n    pass\n")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768]

        events = []
        ingest(mock_conn, mock_embedder, str(tmp_path), progress_callback=events.append)

        embedding_events = [e for e in events if e["phase"] == "embedding"]
        assert len(embedding_events) > 0
        assert "batch" in embedding_events[0]
        assert "total_batches" in embedding_events[0]

    def test_callback_receives_storing_events(self, tmp_path):
        from codesherpa.ingestion import ingest

        (tmp_path / "a.py").write_text("def foo():\n    pass\n")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768]

        events = []
        ingest(mock_conn, mock_embedder, str(tmp_path), progress_callback=events.append)

        storing_events = [e for e in events if e["phase"] == "storing"]
        assert len(storing_events) > 0
        assert "current" in storing_events[0]
        assert "total" in storing_events[0]

    def test_no_callback_still_works(self, tmp_path):
        """ingest() works without a callback (backward compat)."""
        from codesherpa.ingestion import ingest

        (tmp_path / "a.py").write_text("x = 1\n")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = [0]

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768]

        stats = ingest(mock_conn, mock_embedder, str(tmp_path))
        assert "chunks_stored" in stats


class TestAutoLaunch:
    """The serve function opens the browser or prints the URL."""

    def test_open_browser_called(self, mock_conn, mock_embedder, mock_llm):
        from codesherpa.web import open_browser

        with patch("webbrowser.open") as mock_open:
            open_browser("http://localhost:8000")
            mock_open.assert_called_once_with("http://localhost:8000")


class TestExplorationSummary:
    """GET /api/projects/{id}/memory/exploration returns explored areas."""

    def test_returns_exploration_summary(self, client, mock_conn):
        summary = {"explored_files": ["a.py", "b.py"], "queries": ["What does a do?"]}
        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.get_exploration_summary", return_value=summary):
                resp = client.get("/api/projects/1/memory/exploration")

        assert resp.status_code == 200
        data = resp.json()
        assert data["explored_files"] == ["a.py", "b.py"]
        assert data["queries"] == ["What does a do?"]

    def test_returns_empty_summary(self, client, mock_conn):
        summary = {"explored_files": [], "queries": []}
        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.get_exploration_summary", return_value=summary):
                resp = client.get("/api/projects/1/memory/exploration")

        assert resp.status_code == 200
        data = resp.json()
        assert data["explored_files"] == []

    def test_returns_404_for_missing_project(self, client, mock_conn):
        from codesherpa.project import ProjectNotFoundError

        with patch(
            "codesherpa.web.get_project_by_id",
            side_effect=ProjectNotFoundError("not found"),
        ):
            resp = client.get("/api/projects/999/memory/exploration")

        assert resp.status_code == 404


class TestListSemanticMemoriesEndpoint:
    """GET /api/projects/{id}/memory/semantic returns semantic memories."""

    def test_returns_memories(self, client, mock_conn):
        memories = [
            {"id": 1, "content": "Payment context", "created_at": "2025-01-01"},
            {"id": 2, "content": "Auth context", "created_at": "2025-01-02"},
        ]
        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.list_semantic_memories", return_value=memories):
                resp = client.get("/api/projects/1/memory/semantic")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["content"] == "Payment context"

    def test_returns_404_for_missing_project(self, client, mock_conn):
        from codesherpa.project import ProjectNotFoundError

        with patch(
            "codesherpa.web.get_project_by_id",
            side_effect=ProjectNotFoundError("not found"),
        ):
            resp = client.get("/api/projects/999/memory/semantic")

        assert resp.status_code == 404


class TestAddSemanticMemoryEndpoint:
    """POST /api/projects/{id}/memory/semantic adds a semantic memory."""

    def test_creates_memory(self, client, mock_conn):
        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.store_semantic_memory") as mock_store:
                resp = client.post(
                    "/api/projects/1/memory/semantic",
                    json={"content": "This service owns payments"},
                )

        assert resp.status_code == 201
        mock_store.assert_called_once()

    def test_empty_content_returns_400(self, client, mock_conn):
        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            resp = client.post(
                "/api/projects/1/memory/semantic",
                json={"content": "  "},
            )

        assert resp.status_code == 400

    def test_returns_404_for_missing_project(self, client, mock_conn):
        from codesherpa.project import ProjectNotFoundError

        with patch(
            "codesherpa.web.get_project_by_id",
            side_effect=ProjectNotFoundError("not found"),
        ):
            resp = client.post(
                "/api/projects/999/memory/semantic",
                json={"content": "context"},
            )

        assert resp.status_code == 404


class TestDeleteSemanticMemoryEndpoint:
    """DELETE /api/projects/{id}/memory/semantic/{memory_id} deletes a memory."""

    def test_deletes_memory(self, client, mock_conn):
        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.delete_semantic_memory") as mock_delete:
                resp = client.delete("/api/projects/1/memory/semantic/5")

        assert resp.status_code == 200
        mock_delete.assert_called_once_with(mock_conn, 5)

    def test_returns_404_for_missing_project(self, client, mock_conn):
        from codesherpa.project import ProjectNotFoundError

        with patch(
            "codesherpa.web.get_project_by_id",
            side_effect=ProjectNotFoundError("not found"),
        ):
            resp = client.delete("/api/projects/999/memory/semantic/5")

        assert resp.status_code == 404


class TestAskWithMemoryRouting:
    """POST /api/projects/{id}/ask uses memory-aware routing."""

    def test_ask_uses_graph_routing(self, client, mock_conn, mock_embedder, mock_llm):
        from codesherpa.explanation import ExplanationResult

        result = ExplanationResult(explanation="routed answer", sources=[])

        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"response": result, "dependencies": []}

        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.build_navigation_graph", return_value=mock_graph):
                resp = client.post(
                    "/api/projects/1/ask",
                    json={"question": "What does f do?"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation"] == "routed answer"
