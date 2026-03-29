"""FastAPI web interface for CodeSherpa."""

import json
import logging
import threading
import webbrowser
from collections.abc import Callable
from pathlib import Path

import oracledb
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from codesherpa.explanation import explain
from codesherpa.ingestion import ingest
from codesherpa.parser import walk_directory
from codesherpa.project import (
    ProjectExistsError,
    ProjectNotFoundError,
    create_project,
    get_project_by_id,
    list_projects,
    update_project_stats,
)
from codesherpa.repo import RepoError, resolve_source
from codesherpa.retrieval import hybrid_search

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


def _lob_output_handler(cursor, metadata):
    """Convert CLOB columns to strings so they're JSON-serializable."""
    if metadata.type_code is oracledb.DB_TYPE_CLOB:
        return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)


class QuestionRequest(BaseModel):
    question: str
    active_file: str | None = None


class CreateProjectRequest(BaseModel):
    name: str
    source: str


# Tracks project IDs currently being ingested to prevent concurrent runs.
_active_ingestions: set[int] = set()


class _LazyLoader:
    """Loads the embedding model and LLM in a background thread on first access."""

    def __init__(self, embedder_factory: Callable, llm_factory: Callable) -> None:
        self._embedder_factory = embedder_factory
        self._llm_factory = llm_factory
        self._embedder = None
        self._llm = None
        self._ready = threading.Event()

    def _load(self) -> None:
        self._embedder = self._embedder_factory()
        self._llm = self._llm_factory()
        self._ready.set()

    def start(self) -> None:
        """Start loading models in a background thread."""
        threading.Thread(target=self._load, daemon=True).start()

    def _ensure_loaded(self) -> None:
        """Block until models are loaded."""
        self._ready.wait()

    @property
    def embedder(self):
        self._ensure_loaded()
        return self._embedder

    @property
    def llm(self):
        self._ensure_loaded()
        return self._llm

    @property
    def ready(self) -> bool:
        return self._ready.is_set()


def create_app(
    conn,
    embedder=None,
    llm=None,
    embedder_factory: Callable | None = None,
    llm_factory: Callable | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Accepts either pre-loaded instances (embedder, llm) or factory functions
    (embedder_factory, llm_factory) for lazy loading.

    Args:
        conn: Oracle Database connection.
        embedder: CodeRankEmbedder instance (eager).
        llm: LangChain LLM instance (eager).
        embedder_factory: Callable that returns an embedder (lazy).
        llm_factory: Callable that returns an LLM (lazy).

    Returns:
        Configured FastAPI application.
    """
    if embedder is not None and llm is not None:
        # Eager mode: wrap in a loader that's already done
        loader = _LazyLoader(lambda: embedder, lambda: llm)
        loader._embedder = embedder
        loader._llm = llm
        loader._ready.set()
    elif embedder_factory is not None and llm_factory is not None:
        loader = _LazyLoader(embedder_factory, llm_factory)
        loader.start()
    else:
        raise ValueError("Provide either (embedder, llm) or (embedder_factory, llm_factory)")

    app = FastAPI(title="CodeSherpa", version="0.1.0")

    @app.get("/api/status")
    def api_status():
        return {"models_ready": loader.ready}

    @app.get("/api/projects")
    def api_list_projects():
        projects = list_projects(conn)
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "source_path": p["source_path"],
                "created_at": str(p["created_at"]) if p["created_at"] else None,
                "last_ingested_at": str(p["last_ingested_at"]) if p["last_ingested_at"] else None,
                "file_count": p["file_count"],
                "chunk_count": p["chunk_count"],
            }
            for p in projects
        ]

    @app.get("/api/projects/{project_id}/files")
    def api_file_tree(project_id: int):
        try:
            get_project_by_id(conn, project_id)
        except ProjectNotFoundError:
            raise HTTPException(status_code=404, detail="Project not found")

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT file_path FROM CODE_CHUNKS "
                "WHERE project_id = :1 ORDER BY file_path",
                [project_id],
            )
            rows = cursor.fetchall()

        return [row[0] for row in rows]

    @app.get("/api/projects/{project_id}/files/{file_path:path}")
    def api_file_content(project_id: int, file_path: str):
        try:
            get_project_by_id(conn, project_id)
        except ProjectNotFoundError:
            raise HTTPException(status_code=404, detail="Project not found")

        with conn.cursor() as cursor:
            cursor.outputtypehandler = _lob_output_handler
            cursor.execute(
                "SELECT code_text, chunk_type, language, start_char, end_char "
                "FROM CODE_CHUNKS "
                "WHERE project_id = :1 AND file_path = :2 "
                "ORDER BY start_char",
                [project_id, file_path],
            )
            rows = cursor.fetchall()

        return [
            {
                "code_text": row[0],
                "chunk_type": row[1],
                "language": row[2],
                "start_char": row[3],
                "end_char": row[4],
            }
            for row in rows
        ]

    @app.post("/api/projects/{project_id}/ask")
    def api_ask(project_id: int, req: QuestionRequest):
        try:
            get_project_by_id(conn, project_id)
        except ProjectNotFoundError:
            raise HTTPException(status_code=404, detail="Project not found")

        question = req.question
        if req.active_file:
            # Fetch the active file's code to include as direct context
            with conn.cursor() as cursor:
                cursor.outputtypehandler = _lob_output_handler
                cursor.execute(
                    "SELECT code_text FROM CODE_CHUNKS "
                    "WHERE project_id = :1 AND file_path = :2 "
                    "ORDER BY start_char",
                    [project_id, req.active_file],
                )
                rows = cursor.fetchall()
            if rows:
                file_code = "\n".join(row[0] for row in rows)
                question = (
                    f"The user is currently viewing this file:\n"
                    f"File: {req.active_file}\n"
                    f"```\n{file_code}\n```\n\n"
                    f"Question: {question}"
                )

        result = explain(conn, loader.embedder, loader.llm, question, project_id=project_id)
        return {
            "explanation": result.explanation,
            "sources": [
                {
                    "code_text": s.code_text,
                    "file_path": s.file_path,
                    "chunk_type": s.chunk_type,
                    "language": s.language,
                    "start_char": s.start_char,
                    "end_char": s.end_char,
                    "score": s.score,
                }
                for s in result.sources
            ],
        }

    @app.post("/api/projects/{project_id}/query")
    def api_query(project_id: int, req: QuestionRequest):
        try:
            get_project_by_id(conn, project_id)
        except ProjectNotFoundError:
            raise HTTPException(status_code=404, detail="Project not found")

        results = hybrid_search(conn, loader.embedder, req.question, project_id=project_id)
        return [
            {
                "code_text": r.code_text,
                "file_path": r.file_path,
                "chunk_type": r.chunk_type,
                "language": r.language,
                "start_char": r.start_char,
                "end_char": r.end_char,
                "score": r.score,
            }
            for r in results
        ]

    @app.post("/api/projects", status_code=201)
    def api_create_project(req: CreateProjectRequest):
        name = req.name.strip()
        source = req.source.strip()

        if not name:
            raise HTTPException(status_code=400, detail="Project name must not be empty.")
        if not source:
            raise HTTPException(status_code=400, detail="Source path must not be empty.")

        try:
            resolved = resolve_source(source)
        except RepoError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        try:
            project_id = create_project(conn, name, resolved)
        except ProjectExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        return {"id": project_id, "name": name, "source_path": resolved}

    @app.post("/api/projects/{project_id}/ingest")
    def api_ingest(project_id: int):
        try:
            project = get_project_by_id(conn, project_id)
        except ProjectNotFoundError:
            raise HTTPException(status_code=404, detail="Project not found")

        if project_id in _active_ingestions:
            raise HTTPException(
                status_code=409,
                detail="Ingestion is already running for this project.",
            )

        source_path = project["source_path"]

        # Re-resolve source to pull latest for GitHub repos (REQ-WEB-15)
        try:
            resolved = resolve_source(source_path)
        except RepoError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        def event_stream():
            _active_ingestions.add(project_id)
            try:
                events: list[dict] = []

                def on_progress(event: dict) -> None:
                    events.append(event)

                # Yield progress events as they arrive
                # Run ingestion synchronously within the generator
                # and yield events after completion since ingest()
                # is CPU-bound and not async
                stats = ingest(
                    conn, loader.embedder, resolved,
                    project_id=project_id,
                    progress_callback=on_progress,
                )

                # Yield all progress events
                for event in events:
                    yield f"data: {json.dumps(event)}\n\n"

                # Update project stats
                file_count = len(walk_directory(resolved))
                chunk_count = _count_project_chunks(conn, project_id)
                update_project_stats(conn, project_id, file_count, chunk_count)

                yield f"data: {json.dumps({'phase': 'complete', 'stats': stats})}\n\n"

            except Exception as exc:
                logger.exception("Ingestion failed for project %d", project_id)
                yield f"data: {json.dumps({'phase': 'error', 'message': str(exc)})}\n\n"
            finally:
                _active_ingestions.discard(project_id)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Serve frontend static files if the build directory exists
    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


def _count_project_chunks(conn: oracledb.Connection, project_id: int) -> int:
    """Return the total number of chunks stored for a project."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM CODE_CHUNKS WHERE project_id = :1",
            [project_id],
        )
        row = cursor.fetchone()
        return row[0] if row else 0


def open_browser(url: str) -> None:
    """Open the given URL in the default web browser."""
    webbrowser.open(url)
