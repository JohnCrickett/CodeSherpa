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

        with patch("codesherpa.web.get_project_by_id", return_value={"id": 1, "name": "proj"}):
            with patch("codesherpa.web.explain", return_value=result):
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


class TestAutoLaunch:
    """The serve function opens the browser or prints the URL."""

    def test_open_browser_called(self, mock_conn, mock_embedder, mock_llm):
        from codesherpa.web import open_browser

        with patch("webbrowser.open") as mock_open:
            open_browser("http://localhost:8000")
            mock_open.assert_called_once_with("http://localhost:8000")
