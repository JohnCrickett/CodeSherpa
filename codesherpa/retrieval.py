"""Semantic retrieval: hybrid vector + full-text search over code chunks."""

import logging
from dataclasses import dataclass

import oracledb

from codesherpa.embeddings import CodeRankEmbedder
from codesherpa.ingestion import TABLE_NAME

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result from the retrieval pipeline."""

    code_text: str
    file_path: str
    chunk_type: str
    language: str
    start_char: int
    end_char: int
    score: float


def vector_search(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    query: str,
    top_k: int = 10,
    threshold: float = 0.3,
    project_id: int | None = None,
) -> list[SearchResult]:
    """Search for code chunks by vector cosine similarity.

    Args:
        conn: Oracle Database connection.
        embedder: Embedding client to encode the query.
        query: Natural language query string.
        top_k: Maximum number of results to return.
        threshold: Minimum cosine similarity (0-1). Results below this are excluded.
        project_id: If provided, restrict results to this project.

    Returns:
        List of SearchResult ordered by similarity descending.
    """
    query_embedding = embedder.embed(query, input_type="query")

    project_filter = "AND project_id = :5" if project_id is not None else ""
    sql = f"""
        SELECT code_text, file_path, chunk_type, language, start_char, end_char,
               (1 - VECTOR_DISTANCE(embedding, :1, COSINE)) AS similarity
        FROM {TABLE_NAME}
        WHERE (1 - VECTOR_DISTANCE(embedding, :2, COSINE)) >= :3
        {project_filter}
        ORDER BY similarity DESC
        FETCH FIRST :4 ROWS ONLY
    """

    params = [query_embedding, query_embedding, threshold, top_k]
    if project_id is not None:
        params.append(project_id)

    with conn.cursor() as cursor:
        cursor.setinputsizes(oracledb.DB_TYPE_VECTOR, oracledb.DB_TYPE_VECTOR)
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    return [
        SearchResult(
            code_text=row[0],
            file_path=row[1],
            chunk_type=row[2],
            language=row[3],
            start_char=row[4],
            end_char=row[5],
            score=row[6],
        )
        for row in rows
    ]


def fulltext_search(
    conn: oracledb.Connection,
    query: str,
    top_k: int = 10,
    project_id: int | None = None,
) -> list[SearchResult]:
    """Search for code chunks using Oracle Text full-text search.

    Args:
        conn: Oracle Database connection.
        query: Search query (identifiers, keywords, string literals).
        top_k: Maximum number of results to return.
        project_id: If provided, restrict results to this project.

    Returns:
        List of SearchResult ordered by Oracle Text relevance score.
    """
    project_filter = "AND project_id = :3" if project_id is not None else ""
    sql = f"""
        SELECT code_text, file_path, chunk_type, language, start_char, end_char,
               SCORE(1) AS relevance
        FROM {TABLE_NAME}
        WHERE CONTAINS(code_text, :1, 1) > 0
        {project_filter}
        ORDER BY relevance DESC
        FETCH FIRST :2 ROWS ONLY
    """

    # Wrap in {} to escape Oracle Text special characters (?, &, -, etc.)
    escaped_query = "{" + query + "}"

    params = [escaped_query, top_k]
    if project_id is not None:
        params.append(project_id)

    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    return [
        SearchResult(
            code_text=row[0],
            file_path=row[1],
            chunk_type=row[2],
            language=row[3],
            start_char=row[4],
            end_char=row[5],
            score=row[6],
        )
        for row in rows
    ]


def hybrid_search(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    query: str,
    top_k: int = 10,
    threshold: float = 0.3,
    project_id: int | None = None,
) -> list[SearchResult]:
    """Combine vector similarity and full-text search, deduplicate, and rank.

    Args:
        conn: Oracle Database connection.
        embedder: Embedding client to encode the query.
        query: Natural language or keyword query.
        top_k: Maximum results per search method before merging.
        threshold: Minimum cosine similarity for vector search.
        project_id: If provided, restrict results to this project.

    Returns:
        Deduplicated list of SearchResult ordered by score descending.
    """
    vec_results = vector_search(
        conn, embedder, query, top_k=top_k, threshold=threshold,
        project_id=project_id,
    )
    ft_results = fulltext_search(conn, query, top_k=top_k, project_id=project_id)

    # Deduplicate by (file_path, start_char, end_char), keeping higher score
    seen: dict[tuple[str, int, int], SearchResult] = {}
    for result in vec_results + ft_results:
        key = (result.file_path, result.start_char, result.end_char)
        existing = seen.get(key)
        if existing is None or result.score > existing.score:
            seen[key] = result

    combined = sorted(seen.values(), key=lambda r: r.score, reverse=True)
    return combined
