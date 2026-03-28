"""Oracle Database connection utility."""

import oracledb


class DatabaseConnectionError(Exception):
    """Raised when the database cannot be reached."""


def get_connection(dsn: str, user: str, password: str) -> oracledb.Connection:
    """Create a connection to the Oracle Database.

    Args:
        dsn: Oracle connection string (e.g. localhost:1521/FREEPDB1).
        user: Database username.
        password: Database password.

    Returns:
        An active oracledb.Connection.

    Raises:
        DatabaseConnectionError: If the database is unreachable.
    """
    try:
        return oracledb.connect(dsn=dsn, user=user, password=password)
    except oracledb.DatabaseError as exc:
        raise DatabaseConnectionError(
            f"Could not connect to Oracle Database at {dsn}. "
            "Ensure the Docker container is running or a cloud connection is configured. "
            f"Details: {exc}"
        ) from exc
