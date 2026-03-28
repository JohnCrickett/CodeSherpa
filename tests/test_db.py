"""Tests for Oracle Database connection utility."""

import pytest

from codesherpa.db import DatabaseConnectionError, get_connection


class TestGetConnection:
    """Tests for the database connection utility."""

    def test_returns_connection_with_valid_config(self, mocker):
        """get_connection returns a connection object when DB is reachable."""
        mock_connect = mocker.patch("oracledb.connect")
        mock_connect.return_value.is_healthy.return_value = True

        conn = get_connection(
            dsn="localhost:1521/FREEPDB1",
            user="codesherpa",
            password="codesherpa",
        )
        assert conn is not None
        mock_connect.assert_called_once_with(
            dsn="localhost:1521/FREEPDB1",
            user="codesherpa",
            password="codesherpa",
        )

    def test_raises_clear_error_when_db_unreachable(self, mocker):
        """get_connection raises DatabaseConnectionError with a helpful message."""
        import oracledb

        mock_connect = mocker.patch("oracledb.connect")
        mock_connect.side_effect = oracledb.DatabaseError("connection refused")

        with pytest.raises(DatabaseConnectionError, match="Could not connect"):
            get_connection(
                dsn="localhost:1521/FREEPDB1",
                user="codesherpa",
                password="codesherpa",
            )
