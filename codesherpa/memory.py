"""Agent memory: episodic and semantic memory stored in Oracle Database.

Episodic memory tracks which areas of the codebase have been explored.
Semantic memory stores project-level context provided by the developer.
Both types are stored as vectors for semantic retrieval and isolated per project.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import oracledb

if TYPE_CHECKING:
    from codesherpa.embeddings import CodeRankEmbedder

logger = logging.getLogger(__name__)


def _lob_output_handler(cursor, metadata):
    """Convert CLOB columns to strings so they're JSON-serializable."""
    if metadata.type_code is oracledb.DB_TYPE_CLOB:
        return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)

EPISODIC_TABLE = "EPISODIC_MEMORY"
SEMANTIC_TABLE = "SEMANTIC_MEMORY"

_CREATE_EPISODIC_TABLE_SQL = f"""
CREATE TABLE {EPISODIC_TABLE} (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id  NUMBER         NOT NULL,
    embedding   VECTOR(768, FLOAT64),
    query       CLOB           NOT NULL,
    file_paths  CLOB           NOT NULL,
    summary     CLOB           NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_SEMANTIC_TABLE_SQL = f"""
CREATE TABLE {SEMANTIC_TABLE} (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id  NUMBER         NOT NULL,
    embedding   VECTOR(768, FLOAT64),
    content     CLOB           NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
)
"""


def _table_exists(cursor: oracledb.Cursor, table_name: str) -> bool:
    """Check whether a table already exists."""
    cursor.execute(
        "SELECT COUNT(*) FROM user_tables WHERE table_name = :1",
        [table_name],
    )
    row = cursor.fetchone()
    return row is not None and row[0] > 0


def ensure_memory_schema(conn: oracledb.Connection) -> None:
    """Create the EPISODIC_MEMORY and SEMANTIC_MEMORY tables if they don't exist."""
    with conn.cursor() as cursor:
        if not _table_exists(cursor, EPISODIC_TABLE):
            cursor.execute(_CREATE_EPISODIC_TABLE_SQL)

        if not _table_exists(cursor, SEMANTIC_TABLE):
            cursor.execute(_CREATE_SEMANTIC_TABLE_SQL)

    conn.commit()


def store_episodic_memory(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    project_id: int,
    query: str,
    file_paths: list[str],
    summary: str,
) -> None:
    """Store an episodic memory entry for explored areas.

    Args:
        conn: Oracle Database connection.
        embedder: Embedding client to encode the query.
        project_id: The project this memory belongs to.
        query: The question that was asked.
        file_paths: List of file paths explored during the query.
        summary: Brief summary of what was explored/found.
    """
    embedding = embedder.embed(query, input_type="query")
    file_paths_json = json.dumps(file_paths)

    try:
        with conn.cursor() as cursor:
            cursor.setinputsizes(None, oracledb.DB_TYPE_VECTOR)
            cursor.execute(
                f"""INSERT INTO {EPISODIC_TABLE}
                    (project_id, embedding, query, file_paths, summary)
                VALUES (:1, :2, :3, :4, :5)""",
                [project_id, embedding, query, file_paths_json, summary],
            )
        conn.commit()
    except oracledb.DatabaseError:
        logger.warning("Failed to store episodic memory", exc_info=True)


def store_semantic_memory(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    project_id: int,
    content: str,
) -> None:
    """Store a semantic memory entry (developer-provided project context).

    Args:
        conn: Oracle Database connection.
        embedder: Embedding client to encode the content.
        project_id: The project this memory belongs to.
        content: The context to store (e.g., "this service owns all payment logic").
    """
    embedding = embedder.embed(content, input_type="document")

    with conn.cursor() as cursor:
        cursor.setinputsizes(None, oracledb.DB_TYPE_VECTOR)
        cursor.execute(
            f"""INSERT INTO {SEMANTIC_TABLE}
                (project_id, embedding, content)
            VALUES (:1, :2, :3)""",
            [project_id, embedding, content],
        )

    conn.commit()


def search_episodic_memory(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    query: str,
    project_id: int,
    top_k: int = 5,
    threshold: float = 0.3,
) -> list[dict]:
    """Search episodic memory for relevant prior explorations.

    Args:
        conn: Oracle Database connection.
        embedder: Embedding client to encode the query.
        query: The current question to find related past explorations.
        project_id: Restrict to this project's memories.
        top_k: Maximum number of results.
        threshold: Minimum cosine similarity.

    Returns:
        List of dicts with id, query, file_paths, summary, score.
    """
    query_embedding = embedder.embed(query, input_type="query")

    sql = f"""
        SELECT id, query, file_paths, summary,
               (1 - VECTOR_DISTANCE(embedding, :1, COSINE)) AS similarity
        FROM {EPISODIC_TABLE}
        WHERE project_id = :2
          AND (1 - VECTOR_DISTANCE(embedding, :3, COSINE)) >= :4
        ORDER BY similarity DESC
        FETCH FIRST :5 ROWS ONLY
    """

    try:
        with conn.cursor() as cursor:
            cursor.outputtypehandler = _lob_output_handler
            cursor.setinputsizes(
                oracledb.DB_TYPE_VECTOR, None, oracledb.DB_TYPE_VECTOR,
            )
            cursor.execute(
                sql, [query_embedding, project_id, query_embedding, threshold, top_k],
            )
            rows = cursor.fetchall()
    except oracledb.DatabaseError:
        logger.debug("Episodic memory search failed, returning empty", exc_info=True)
        return []

    return [
        {
            "id": row[0],
            "query": row[1],
            "file_paths": json.loads(row[2]) if isinstance(row[2], str) else [],
            "summary": row[3],
            "score": row[4],
        }
        for row in rows
    ]


def search_semantic_memory(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    query: str,
    project_id: int,
    top_k: int = 5,
    threshold: float = 0.3,
) -> list[dict]:
    """Search semantic memory for relevant project context.

    Args:
        conn: Oracle Database connection.
        embedder: Embedding client to encode the query.
        query: The current question to find related context.
        project_id: Restrict to this project's memories.
        top_k: Maximum number of results.
        threshold: Minimum cosine similarity.

    Returns:
        List of dicts with id, content, score.
    """
    query_embedding = embedder.embed(query, input_type="query")

    sql = f"""
        SELECT id, content,
               (1 - VECTOR_DISTANCE(embedding, :1, COSINE)) AS similarity
        FROM {SEMANTIC_TABLE}
        WHERE project_id = :2
          AND (1 - VECTOR_DISTANCE(embedding, :3, COSINE)) >= :4
        ORDER BY similarity DESC
        FETCH FIRST :5 ROWS ONLY
    """

    try:
        with conn.cursor() as cursor:
            cursor.outputtypehandler = _lob_output_handler
            cursor.setinputsizes(
                oracledb.DB_TYPE_VECTOR, None, oracledb.DB_TYPE_VECTOR,
            )
            cursor.execute(
                sql, [query_embedding, project_id, query_embedding, threshold, top_k],
            )
            rows = cursor.fetchall()
    except oracledb.DatabaseError:
        logger.debug("Semantic memory search failed, returning empty", exc_info=True)
        return []

    return [
        {
            "id": row[0],
            "content": row[1],
            "score": row[2],
        }
        for row in rows
    ]


def search_semantic_memory_broad(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    query: str,
    project_id: int,
    top_k: int = 10,
    threshold: float = 0.1,
) -> list[dict]:
    """Search semantic memory using both vector similarity and keyword matching.

    The code embedding model has low sensitivity to natural-language queries,
    so we combine vector search with keyword-based matching to ensure
    developer-provided context is found even when the embedding model
    produces low similarity scores.

    Returns:
        List of dicts with id, content, score — deduplicated, sorted by score.
    """
    results: dict[int, dict] = {}

    # 1. Vector search
    try:
        for mem in search_semantic_memory(
            conn, embedder, query, project_id, top_k=top_k, threshold=threshold,
        ):
            results[mem["id"]] = mem
    except Exception:
        logger.warning("Semantic vector search failed", exc_info=True)

    # 2. Keyword search — use same positional-param pattern as search_memory
    words = [w for w in query.lower().split() if len(w) >= 3]
    for word in words[:5]:
        like_pattern = f"%{word}%"
        try:
            with conn.cursor() as cursor:
                cursor.outputtypehandler = _lob_output_handler
                cursor.execute(
                    f"SELECT id, content FROM {SEMANTIC_TABLE} "
                    f"WHERE project_id = :1 AND LOWER(content) LIKE :2 "
                    f"FETCH FIRST :3 ROWS ONLY",
                    [project_id, like_pattern, top_k],
                )
                for row in cursor.fetchall():
                    if row[0] not in results:
                        results[row[0]] = {
                            "id": row[0],
                            "content": row[1],
                            "score": 0.0,
                        }
        except Exception:
            logger.warning(
                "Semantic keyword search failed for word=%s", word,
                exc_info=True,
            )

    return sorted(results.values(), key=lambda r: r["score"], reverse=True)[:top_k]


def get_exploration_summary(
    conn: oracledb.Connection,
    project_id: int,
) -> dict:
    """Get a summary of what has been explored for a project.

    Returns:
        Dict with 'explored_files' (deduplicated list) and 'queries' (list of past queries).
    """
    with conn.cursor() as cursor:
        cursor.outputtypehandler = _lob_output_handler
        cursor.execute(
            f"SELECT query, file_paths FROM {EPISODIC_TABLE} "
            f"WHERE project_id = :1 ORDER BY created_at",
            [project_id],
        )
        rows = cursor.fetchall()

    queries = []
    explored_files_set: set[str] = set()

    for query_text, file_paths_json in rows:
        queries.append(query_text)
        file_paths = json.loads(file_paths_json)
        explored_files_set.update(file_paths)

    return {
        "explored_files": sorted(explored_files_set),
        "queries": queries,
    }


def list_semantic_memories(
    conn: oracledb.Connection,
    project_id: int,
) -> list[dict]:
    """List all semantic memories for a project.

    Returns:
        List of dicts with id, content, created_at.
    """
    with conn.cursor() as cursor:
        cursor.outputtypehandler = _lob_output_handler
        cursor.execute(
            f"SELECT id, content, created_at FROM {SEMANTIC_TABLE} "
            f"WHERE project_id = :1 ORDER BY created_at",
            [project_id],
        )
        rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "content": row[1],
            "created_at": str(row[2]) if row[2] else None,
        }
        for row in rows
    ]


def delete_semantic_memory(
    conn: oracledb.Connection,
    memory_id: int,
) -> None:
    """Delete a semantic memory entry by ID."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {SEMANTIC_TABLE} WHERE id = :1",
            [memory_id],
        )

    conn.commit()


def list_episodic_memories(
    conn: oracledb.Connection,
    project_id: int,
) -> list[dict]:
    """List all episodic memories for a project.

    Returns:
        List of dicts with id, query, file_paths, summary, created_at.
    """
    with conn.cursor() as cursor:
        cursor.outputtypehandler = _lob_output_handler
        cursor.execute(
            f"SELECT id, query, file_paths, summary, created_at FROM {EPISODIC_TABLE} "
            f"WHERE project_id = :1 ORDER BY created_at",
            [project_id],
        )
        rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "query": row[1],
            "file_paths": json.loads(row[2]) if isinstance(row[2], str) else [],
            "summary": row[3],
            "created_at": str(row[4]) if row[4] else None,
        }
        for row in rows
    ]


def delete_episodic_memory(
    conn: oracledb.Connection,
    memory_id: int,
) -> None:
    """Delete a single episodic memory entry by ID."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {EPISODIC_TABLE} WHERE id = :1",
            [memory_id],
        )

    conn.commit()


def bulk_delete_episodic_memory(
    conn: oracledb.Connection,
    project_id: int,
) -> int:
    """Delete all episodic memory for a project. Return the number of rows deleted."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {EPISODIC_TABLE} WHERE project_id = :1",
            [project_id],
        )
        count = cursor.rowcount

    conn.commit()
    return count


def bulk_delete_semantic_memory(
    conn: oracledb.Connection,
    project_id: int,
) -> int:
    """Delete all semantic memory for a project. Return the number of rows deleted."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {SEMANTIC_TABLE} WHERE project_id = :1",
            [project_id],
        )
        count = cursor.rowcount

    conn.commit()
    return count


def bulk_delete_all_memory(
    conn: oracledb.Connection,
    project_id: int,
) -> dict:
    """Delete both episodic and semantic memory for a project.

    Returns:
        Dict with episodic_deleted and semantic_deleted counts.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {EPISODIC_TABLE} WHERE project_id = :1",
            [project_id],
        )
        episodic_count = cursor.rowcount

        cursor.execute(
            f"DELETE FROM {SEMANTIC_TABLE} WHERE project_id = :1",
            [project_id],
        )
        semantic_count = cursor.rowcount

    conn.commit()
    return {
        "episodic_deleted": episodic_count,
        "semantic_deleted": semantic_count,
    }


def search_memory(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    query: str,
    project_id: int,
    top_k: int = 10,
) -> list[dict]:
    """Unified search across both memory types.

    Performs vector search and text-based substring filtering on both tables,
    merges and deduplicates results, returns sorted by score descending.

    Returns:
        List of dicts with type, id, score, and type-specific fields.
    """
    query_embedding = embedder.embed(query, input_type="query")
    results: dict[tuple[str, int], dict] = {}

    # 1. Episodic vector search
    try:
        with conn.cursor() as cursor:
            cursor.outputtypehandler = _lob_output_handler
            cursor.setinputsizes(
                oracledb.DB_TYPE_VECTOR, None, oracledb.DB_TYPE_VECTOR,
            )
            cursor.execute(
                f"""SELECT id, query, file_paths, summary,
                           (1 - VECTOR_DISTANCE(embedding, :1, COSINE)) AS similarity
                    FROM {EPISODIC_TABLE}
                    WHERE project_id = :2
                      AND (1 - VECTOR_DISTANCE(embedding, :3, COSINE)) >= 0.3
                    ORDER BY similarity DESC
                    FETCH FIRST :4 ROWS ONLY""",
                [query_embedding, project_id, query_embedding, top_k],
            )
            for row in cursor.fetchall():
                key = ("episodic", row[0])
                results[key] = {
                    "type": "episodic",
                    "id": row[0],
                    "query": row[1],
                    "file_paths": json.loads(row[2]) if isinstance(row[2], str) else [],
                    "summary": row[3],
                    "score": row[4],
                }
    except oracledb.DatabaseError:
        logger.debug("Episodic vector search failed", exc_info=True)

    # 2. Semantic vector search
    try:
        with conn.cursor() as cursor:
            cursor.outputtypehandler = _lob_output_handler
            cursor.setinputsizes(
                oracledb.DB_TYPE_VECTOR, None, oracledb.DB_TYPE_VECTOR,
            )
            cursor.execute(
                f"""SELECT id, content,
                           (1 - VECTOR_DISTANCE(embedding, :1, COSINE)) AS similarity
                    FROM {SEMANTIC_TABLE}
                    WHERE project_id = :2
                      AND (1 - VECTOR_DISTANCE(embedding, :3, COSINE)) >= 0.3
                    ORDER BY similarity DESC
                    FETCH FIRST :4 ROWS ONLY""",
                [query_embedding, project_id, query_embedding, top_k],
            )
            for row in cursor.fetchall():
                key = ("semantic", row[0])
                results[key] = {
                    "type": "semantic",
                    "id": row[0],
                    "content": row[1],
                    "score": row[2],
                }
    except oracledb.DatabaseError:
        logger.debug("Semantic vector search failed", exc_info=True)

    # 3. Episodic text search
    try:
        like_pattern = f"%{query}%"
        with conn.cursor() as cursor:
            cursor.outputtypehandler = _lob_output_handler
            cursor.execute(
                f"""SELECT id, query, file_paths, summary
                    FROM {EPISODIC_TABLE}
                    WHERE project_id = :1
                      AND (query LIKE :2 OR summary LIKE :3)
                    FETCH FIRST :4 ROWS ONLY""",
                [project_id, like_pattern, like_pattern, top_k],
            )
            for row in cursor.fetchall():
                key = ("episodic", row[0])
                if key not in results:
                    results[key] = {
                        "type": "episodic",
                        "id": row[0],
                        "query": row[1],
                        "file_paths": json.loads(row[2]) if isinstance(row[2], str) else [],
                        "summary": row[3],
                        "score": 0.0,
                    }
    except oracledb.DatabaseError:
        logger.debug("Episodic text search failed", exc_info=True)

    # 4. Semantic text search
    try:
        like_pattern = f"%{query}%"
        with conn.cursor() as cursor:
            cursor.outputtypehandler = _lob_output_handler
            cursor.execute(
                f"""SELECT id, content
                    FROM {SEMANTIC_TABLE}
                    WHERE project_id = :1
                      AND content LIKE :2
                    FETCH FIRST :3 ROWS ONLY""",
                [project_id, like_pattern, top_k],
            )
            for row in cursor.fetchall():
                key = ("semantic", row[0])
                if key not in results:
                    results[key] = {
                        "type": "semantic",
                        "id": row[0],
                        "content": row[1],
                        "score": 0.0,
                    }
    except oracledb.DatabaseError:
        logger.debug("Semantic text search failed", exc_info=True)

    return sorted(results.values(), key=lambda r: r["score"], reverse=True)
