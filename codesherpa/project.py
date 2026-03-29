"""Project management: named projects with isolation and metadata."""

import logging

import oracledb

logger = logging.getLogger(__name__)

PROJECTS_TABLE = "PROJECTS"

_CREATE_PROJECTS_TABLE_SQL = f"""
CREATE TABLE {PROJECTS_TABLE} (
    id               NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name             VARCHAR2(200) NOT NULL UNIQUE,
    source_path      VARCHAR2(1000) NOT NULL,
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_ingested_at TIMESTAMP WITH TIME ZONE,
    file_count       NUMBER DEFAULT 0,
    chunk_count      NUMBER DEFAULT 0
)
"""


class ProjectExistsError(Exception):
    """Raised when creating a project with a name that already exists."""


class ProjectNotFoundError(Exception):
    """Raised when a project with the given name does not exist."""


def _projects_table_exists(cursor: oracledb.Cursor) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM user_tables WHERE table_name = :1",
        [PROJECTS_TABLE],
    )
    row = cursor.fetchone()
    return row is not None and row[0] > 0


def ensure_projects_schema(conn: oracledb.Connection) -> None:
    """Create the PROJECTS table if it does not exist."""
    with conn.cursor() as cursor:
        if not _projects_table_exists(cursor):
            cursor.execute(_CREATE_PROJECTS_TABLE_SQL)
    conn.commit()


def _row_to_dict(row) -> dict:
    """Convert a project row tuple to a dict."""
    return {
        "id": row[0],
        "name": row[1],
        "source_path": row[2],
        "created_at": row[3],
        "last_ingested_at": row[4],
        "file_count": row[5],
        "chunk_count": row[6],
    }


def create_project(
    conn: oracledb.Connection, name: str, source_path: str
) -> int:
    """Create a new project and return its ID.

    Raises ProjectExistsError if a project with the same name exists.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {PROJECTS_TABLE} WHERE name = :1",
            [name],
        )
        if cursor.fetchone()[0] > 0:
            raise ProjectExistsError(
                f"Project already exists: {name}"
            )

        cursor.execute(
            f"""INSERT INTO {PROJECTS_TABLE} (name, source_path)
                VALUES (:1, :2)""",
            [name, source_path],
        )
        cursor.execute(
            f"SELECT id FROM {PROJECTS_TABLE} WHERE name = :1",
            [name],
        )
        project_id = cursor.fetchone()[0]

    conn.commit()
    return project_id


def get_project(conn: oracledb.Connection, name: str) -> dict:
    """Retrieve a project by name.

    Raises ProjectNotFoundError if the project does not exist.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            f"""SELECT id, name, source_path, created_at, last_ingested_at,
                       file_count, chunk_count
                FROM {PROJECTS_TABLE} WHERE name = :1""",
            [name],
        )
        row = cursor.fetchone()

    if row is None:
        raise ProjectNotFoundError(f"Project not found: {name}")

    return _row_to_dict(row)


def get_project_by_id(conn: oracledb.Connection, project_id: int) -> dict:
    """Retrieve a project by ID.

    Raises ProjectNotFoundError if the project does not exist.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            f"""SELECT id, name, source_path, created_at, last_ingested_at,
                       file_count, chunk_count
                FROM {PROJECTS_TABLE} WHERE id = :1""",
            [project_id],
        )
        row = cursor.fetchone()

    if row is None:
        raise ProjectNotFoundError(f"Project not found: id={project_id}")

    return _row_to_dict(row)


def list_projects(conn: oracledb.Connection) -> list[dict]:
    """Return a list of all projects with their metadata."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"""SELECT id, name, source_path, created_at, last_ingested_at,
                       file_count, chunk_count
                FROM {PROJECTS_TABLE} ORDER BY name"""
        )
        rows = cursor.fetchall()

    return [_row_to_dict(row) for row in rows]


def _delete_project_data(conn: oracledb.Connection, project_id: int) -> None:
    """Delete all data associated with a project ID and the project itself."""
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM EPISODIC_MEMORY WHERE project_id = :1",
            [project_id],
        )
        cursor.execute(
            "DELETE FROM SEMANTIC_MEMORY WHERE project_id = :1",
            [project_id],
        )
        cursor.execute(
            "DELETE FROM CODE_CHUNKS WHERE project_id = :1",
            [project_id],
        )
        cursor.execute(
            f"DELETE FROM {PROJECTS_TABLE} WHERE id = :1",
            [project_id],
        )
    conn.commit()


def delete_project(conn: oracledb.Connection, name: str) -> None:
    """Delete a project and all its associated data.

    Removes code chunks, episodic memory, semantic memory, and the project.
    Raises ProjectNotFoundError if the project does not exist.
    """
    project = get_project(conn, name)
    _delete_project_data(conn, project["id"])


def delete_project_by_id(conn: oracledb.Connection, project_id: int) -> None:
    """Delete a project by ID and all its associated data.

    Removes code chunks, episodic memory, semantic memory, and the project.
    Raises ProjectNotFoundError if the project does not exist.
    """
    get_project_by_id(conn, project_id)  # raises if not found
    _delete_project_data(conn, project_id)


def update_project_stats(
    conn: oracledb.Connection,
    project_id: int,
    file_count: int,
    chunk_count: int,
) -> None:
    """Update a project's metadata after ingestion."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"""UPDATE {PROJECTS_TABLE}
                SET last_ingested_at = CURRENT_TIMESTAMP,
                    file_count = :1,
                    chunk_count = :2
                WHERE id = :3""",
            [file_count, chunk_count, project_id],
        )
    conn.commit()


def get_or_create_project(
    conn: oracledb.Connection, name: str, source_path: str
) -> int:
    """Get an existing project's ID or create a new one."""
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT id FROM {PROJECTS_TABLE} WHERE name = :1",
            [name],
        )
        row = cursor.fetchone()

    if row is not None:
        return row[0]

    return create_project(conn, name, source_path)


DEFAULT_PROJECT_NAME = "AskDocs"


def migrate_orphaned_chunks(conn: oracledb.Connection) -> None:
    """Assign any chunks with NULL project_id to the default AskDocs project.

    Creates the AskDocs project if it doesn't exist, then updates all
    orphaned chunks and refreshes the project stats.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM CODE_CHUNKS WHERE project_id IS NULL"
        )
        orphan_count = cursor.fetchone()[0]

    if orphan_count == 0:
        return

    project_id = get_or_create_project(conn, DEFAULT_PROJECT_NAME, "migrated")

    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE CODE_CHUNKS SET project_id = :1 WHERE project_id IS NULL",
            [project_id],
        )
        cursor.execute(
            "SELECT COUNT(DISTINCT file_path) FROM CODE_CHUNKS WHERE project_id = :1",
            [project_id],
        )
        file_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM CODE_CHUNKS WHERE project_id = :1",
            [project_id],
        )
        chunk_count = cursor.fetchone()[0]

    conn.commit()
    update_project_stats(conn, project_id, file_count, chunk_count)
    logger.info(
        "Migrated %d orphaned chunks to project '%s'",
        orphan_count, DEFAULT_PROJECT_NAME,
    )
