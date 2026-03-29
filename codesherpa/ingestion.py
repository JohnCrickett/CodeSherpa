"""Embedding and vector storage ingestion pipeline.

Wires the code parser into the embedding client and Oracle Database storage,
with support for re-ingestion of changed files.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

import oracledb
from tqdm import tqdm

from codesherpa.parser import CodeChunk, parse_codebase, walk_directory

if TYPE_CHECKING:
    from codesherpa.embeddings import CodeRankEmbedder

logger = logging.getLogger(__name__)

TABLE_NAME = "CODE_CHUNKS"

_CREATE_TABLE_SQL = f"""
CREATE TABLE {TABLE_NAME} (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id  NUMBER         NOT NULL,
    embedding   VECTOR(768, FLOAT64),
    code_text   CLOB,
    file_path   VARCHAR2(1000) NOT NULL,
    chunk_type  VARCHAR2(50)   NOT NULL,
    language    VARCHAR2(50)   NOT NULL,
    start_char  NUMBER         NOT NULL,
    end_char    NUMBER         NOT NULL,
    file_hash   VARCHAR2(64)   NOT NULL
)
"""

_CREATE_VECTOR_INDEX_SQL = f"""
CREATE VECTOR INDEX idx_chunks_vector
ON {TABLE_NAME} (embedding)
ORGANIZATION NEIGHBOR PARTITIONS
DISTANCE COSINE
WITH TARGET ACCURACY 95
"""

_CREATE_FULLTEXT_INDEX_SQL = f"""
CREATE INDEX idx_chunks_fulltext
ON {TABLE_NAME} (code_text)
INDEXTYPE IS CTXSYS.CONTEXT
"""


def compute_file_hash(content: str) -> str:
    """Compute a SHA-256 hash of file content for change detection."""
    return hashlib.sha256(content.encode()).hexdigest()


def _table_exists(cursor: oracledb.Cursor) -> bool:
    """Check whether the CODE_CHUNKS table already exists."""
    cursor.execute(
        "SELECT COUNT(*) FROM user_tables WHERE table_name = :1",
        [TABLE_NAME],
    )
    row = cursor.fetchone()
    return row is not None and row[0] > 0


def _index_exists(cursor: oracledb.Cursor, index_name: str) -> bool:
    """Check whether an index already exists."""
    cursor.execute(
        "SELECT COUNT(*) FROM user_indexes WHERE index_name = :1",
        [index_name.upper()],
    )
    row = cursor.fetchone()
    return row is not None and row[0] > 0


def _column_exists(cursor: oracledb.Cursor, column_name: str) -> bool:
    """Check whether a column exists on the CODE_CHUNKS table."""
    cursor.execute(
        "SELECT COUNT(*) FROM user_tab_columns "
        "WHERE table_name = :1 AND column_name = :2",
        [TABLE_NAME, column_name.upper()],
    )
    row = cursor.fetchone()
    return row is not None and row[0] > 0


def _migrate_add_project_id(cursor: oracledb.Cursor) -> None:
    """Add project_id column to an existing CODE_CHUNKS table if missing."""
    if not _column_exists(cursor, "PROJECT_ID"):
        cursor.execute(
            f"ALTER TABLE {TABLE_NAME} ADD project_id NUMBER"
        )


def ensure_schema(conn: oracledb.Connection) -> None:
    """Create the CODE_CHUNKS table and indexes if they do not exist."""
    with conn.cursor() as cursor:
        if not _table_exists(cursor):
            cursor.execute(_CREATE_TABLE_SQL)
        else:
            _migrate_add_project_id(cursor)

        if not _index_exists(cursor, "IDX_CHUNKS_VECTOR"):
            cursor.execute(_CREATE_VECTOR_INDEX_SQL)

        if not _index_exists(cursor, "IDX_CHUNKS_FULLTEXT"):
            cursor.execute(_CREATE_FULLTEXT_INDEX_SQL)

    conn.commit()


def _get_existing_file_hashes(
    cursor: oracledb.Cursor, project_id: int
) -> dict[str, str]:
    """Return a mapping of file_path → file_hash for a project's stored files."""
    cursor.execute(
        f"SELECT DISTINCT file_path, file_hash FROM {TABLE_NAME} WHERE project_id = :1",
        [project_id],
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def _delete_chunks_for_file(
    cursor: oracledb.Cursor, file_path: str, project_id: int
) -> None:
    """Remove all stored chunks for a given file path within a project."""
    cursor.execute(
        f"DELETE FROM {TABLE_NAME} WHERE file_path = :1 AND project_id = :2",
        [file_path, project_id],
    )


def _insert_chunks(
    cursor: oracledb.Cursor,
    chunks: list[CodeChunk],
    embeddings: list[list[float]],
    file_hash: str,
    project_id: int,
) -> None:
    """Insert embedded chunks into the database."""
    rows = []
    for chunk, embedding in zip(chunks, embeddings):
        rows.append({
            "project_id": project_id,
            "embedding": embedding,
            "code_text": chunk.content,
            "file_path": chunk.file_path,
            "chunk_type": chunk.chunk_type,
            "language": chunk.language,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "file_hash": file_hash,
        })

    cursor.setinputsizes(embedding=oracledb.DB_TYPE_VECTOR)
    cursor.executemany(
        f"""INSERT INTO {TABLE_NAME}
            (project_id, embedding, code_text, file_path, chunk_type, language,
             start_char, end_char, file_hash)
        VALUES
            (:project_id, :embedding, :code_text, :file_path, :chunk_type, :language,
             :start_char, :end_char, :file_hash)""",
        rows,
    )


def ingest(
    conn: oracledb.Connection,
    embedder: CodeRankEmbedder,
    root: str,
    project_id: int = 1,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict[str, int]:
    """Run the full parse → embed → store pipeline.

    On re-ingestion, only changed files are re-embedded. Chunks from
    deleted files are removed.

    Args:
        conn: An active Oracle Database connection.
        embedder: The embedding client.
        root: Root directory of the codebase to ingest.
        project_id: The project to associate chunks with.
        progress_callback: Optional callback receiving progress dicts with
            a ``phase`` key (``parsing``, ``embedding``, ``storing``,
            ``complete``).

    Returns:
        A dict with keys: chunks_stored, files_skipped, files_updated,
        files_deleted.
    """
    def _emit(event: dict) -> None:
        if progress_callback is not None:
            progress_callback(event)

    stats = {
        "chunks_stored": 0,
        "files_skipped": 0,
        "files_updated": 0,
        "files_deleted": 0,
    }

    with conn.cursor() as cursor:
        existing_hashes = _get_existing_file_hashes(cursor, project_id)

        # Parse the codebase
        _emit({"phase": "parsing", "detail": "Parsing codebase..."})
        all_chunks, errors = parse_codebase(root)
        if errors:
            for err in errors:
                logger.warning(err)

        # Group chunks by file path
        chunks_by_file: dict[str, list[CodeChunk]] = {}
        for chunk in all_chunks:
            chunks_by_file.setdefault(chunk.file_path, []).append(chunk)

        # Compute current file hashes by reading files
        current_hashes: dict[str, str] = {}
        source_files = walk_directory(root)
        for file_path in source_files:
            rel_path = os.path.relpath(file_path, root)
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
            current_hashes[rel_path] = compute_file_hash(content)

        # Determine which files need processing
        files_to_embed: dict[str, list[CodeChunk]] = {}
        for rel_path, chunks in chunks_by_file.items():
            current_hash = current_hashes.get(rel_path, "")
            old_hash = existing_hashes.get(rel_path)

            if old_hash == current_hash:
                stats["files_skipped"] += 1
                continue

            # File is new or changed — delete old chunks if any
            if old_hash is not None:
                _delete_chunks_for_file(cursor, rel_path, project_id)
                stats["files_updated"] += 1
            files_to_embed[rel_path] = chunks

        # Remove chunks for deleted files
        current_rel_paths = set(current_hashes.keys())
        for old_path in existing_hashes:
            if old_path not in current_rel_paths:
                _delete_chunks_for_file(cursor, old_path, project_id)
                stats["files_deleted"] += 1

        # Embed and store new/changed chunks in batches
        all_new_chunks: list[CodeChunk] = []
        file_hash_for_chunk: list[str] = []
        for rel_path, chunks in files_to_embed.items():
            file_hash = current_hashes[rel_path]
            all_new_chunks.extend(chunks)
            file_hash_for_chunk.extend([file_hash] * len(chunks))

        if all_new_chunks:
            texts = [chunk.content for chunk in all_new_chunks]

            # Embed in batches with progress
            batch_size = 32
            total_batches = (len(texts) + batch_size - 1) // batch_size
            embeddings: list[list[float]] = []
            for i in tqdm(range(0, len(texts), batch_size),
                          desc="Embedding chunks",
                          unit="batch"):
                batch_num = i // batch_size + 1
                _emit({
                    "phase": "embedding",
                    "batch": batch_num,
                    "total_batches": total_batches,
                })
                batch = texts[i : i + batch_size]
                embeddings.extend(embedder.embed_batch(batch))

            # Insert in per-file groups for correct hash association
            idx = 0
            total_files = len(files_to_embed)
            for file_num, (rel_path, chunks) in enumerate(
                tqdm(files_to_embed.items(), desc="Storing chunks", unit="file"),
                start=1,
            ):
                _emit({
                    "phase": "storing",
                    "current": file_num,
                    "total": total_files,
                })
                n = len(chunks)
                chunk_embeddings = embeddings[idx : idx + n]
                _insert_chunks(
                    cursor, chunks, chunk_embeddings, current_hashes[rel_path],
                    project_id,
                )
                idx += n

            stats["chunks_stored"] = len(all_new_chunks)

    conn.commit()
    return stats
