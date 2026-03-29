"""FastAPI web interface for CodeSherpa."""

import webbrowser
from pathlib import Path

import oracledb
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from codesherpa.explanation import explain
from codesherpa.project import ProjectNotFoundError, get_project_by_id, list_projects
from codesherpa.retrieval import hybrid_search

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


def _lob_output_handler(cursor, metadata):
    """Convert CLOB columns to strings so they're JSON-serializable."""
    if metadata.type_code is oracledb.DB_TYPE_CLOB:
        return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)


class QuestionRequest(BaseModel):
    question: str
    active_file: str | None = None


def create_app(conn, embedder, llm) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        conn: Oracle Database connection.
        embedder: CodeRankEmbedder instance.
        llm: LangChain LLM instance.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(title="CodeSherpa", version="0.1.0")

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

        result = explain(conn, embedder, llm, question, project_id=project_id)
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

        results = hybrid_search(conn, embedder, req.question, project_id=project_id)
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

    # Serve frontend static files if the build directory exists
    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


def open_browser(url: str) -> None:
    """Open the given URL in the default web browser."""
    webbrowser.open(url)
