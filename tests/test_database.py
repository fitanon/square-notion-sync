"""
Tests for core.database.DatabaseClient.

All tests use mocked psycopg2 — no real database connections.
"""

from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(database_url="postgresql://test:test@localhost/test"):
    """Create a DatabaseClient with a mocked connection pool."""
    with patch("core.database.pg_pool") as mock_pool_mod:
        mock_pool = MagicMock()
        mock_pool_mod.SimpleConnectionPool.return_value = mock_pool
        from core.database import DatabaseClient
        db = DatabaseClient(database_url)
        return db, mock_pool


def _mock_cursor(mock_pool, rows, columns):
    """Wire up a mock connection + cursor that returns *rows* with *columns*."""
    mock_conn = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    mock_cur = MagicMock()
    mock_cur.description = [(col,) for col in columns]
    mock_cur.fetchall.return_value = rows
    mock_cur.fetchone.return_value = rows[0] if rows else None

    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    return mock_cur


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------

class TestIsConfigured:
    def test_true_when_pool_created(self):
        db, _ = _make_db()
        assert db.is_configured is True

    def test_false_when_no_url(self):
        with patch.dict("os.environ", {}, clear=True):
            from core.database import DatabaseClient
            db = DatabaseClient(None)
        assert db.is_configured is False

    def test_false_when_pool_creation_fails(self):
        with patch("core.database.pg_pool") as mock_pool_mod:
            mock_pool_mod.SimpleConnectionPool.side_effect = Exception("connection refused")
            from core.database import DatabaseClient
            db = DatabaseClient("postgresql://bad:bad@bad/bad")
        assert db.is_configured is False


# ---------------------------------------------------------------------------
# get_client_by_email
# ---------------------------------------------------------------------------

class TestGetClientByEmail:
    def test_returns_client_dict(self):
        db, mock_pool = _make_db()
        columns = ["id", "external_id", "first_name", "last_name", "email", "phone", "status"]
        rows = [(1, "sq_123", "Jane", "Doe", "jane@example.com", "+12125551234", "active")]
        _mock_cursor(mock_pool, rows, columns)

        result = db.get_client_by_email("jane@example.com")
        assert result is not None
        assert result["first_name"] == "Jane"
        assert result["email"] == "jane@example.com"
        assert result["id"] == 1

    def test_returns_none_when_not_found(self):
        db, mock_pool = _make_db()
        columns = ["id", "external_id", "first_name", "last_name", "email", "phone", "status"]
        _mock_cursor(mock_pool, [], columns)

        result = db.get_client_by_email("nobody@example.com")
        assert result is None

    def test_uses_parameterized_query(self):
        db, mock_pool = _make_db()
        columns = ["id"]
        cur = _mock_cursor(mock_pool, [], columns)

        db.get_client_by_email("test@example.com")
        # Verify query uses %s parameter, not string interpolation
        executed_query = cur.execute.call_args[0][0]
        assert "%s" in executed_query
        assert "test@example.com" not in executed_query
        # Verify the email is passed as a parameter
        assert cur.execute.call_args[0][1] == ("test@example.com",)


# ---------------------------------------------------------------------------
# get_sessions_remaining
# ---------------------------------------------------------------------------

class TestGetSessionsRemaining:
    def test_calculates_remaining(self):
        db, mock_pool = _make_db()
        columns = ["sessions_total", "sessions_used"]
        rows = [(10, 3), (5, 2)]  # two active packages: 7 + 3 = 10 remaining
        _mock_cursor(mock_pool, rows, columns)

        result = db.get_sessions_remaining(1)
        assert result == 10

    def test_returns_zero_when_no_packages(self):
        db, mock_pool = _make_db()
        columns = ["sessions_total", "sessions_used"]
        _mock_cursor(mock_pool, [], columns)

        result = db.get_sessions_remaining(1)
        assert result == 0

    def test_returns_none_for_unlimited(self):
        db, mock_pool = _make_db()
        columns = ["sessions_total", "sessions_used"]
        rows = [(-1, 0)]  # unlimited
        _mock_cursor(mock_pool, rows, columns)

        result = db.get_sessions_remaining(1)
        assert result is None

    def test_clamps_negative_to_zero(self):
        db, mock_pool = _make_db()
        columns = ["sessions_total", "sessions_used"]
        rows = [(5, 8)]  # overused
        _mock_cursor(mock_pool, rows, columns)

        result = db.get_sessions_remaining(1)
        assert result == 0


# ---------------------------------------------------------------------------
# upsert_client
# ---------------------------------------------------------------------------

class TestUpsertClient:
    def test_generates_insert_on_conflict_sql(self):
        db, mock_pool = _make_db()
        columns = ["id", "external_id", "first_name", "last_name", "email"]
        cur = _mock_cursor(mock_pool, [(1, "sq_abc", "Jane", "Doe", "jane@test.com")], columns)

        db.upsert_client(
            external_id="sq_abc",
            first_name="Jane",
            last_name="Doe",
            email="jane@test.com",
            phone="+12125551234",
            trainer_id=None,
            status="active",
        )

        executed_query = cur.execute.call_args[0][0]
        assert "INSERT INTO clients" in executed_query
        assert "ON CONFLICT (external_id) DO UPDATE" in executed_query
        assert "RETURNING" in executed_query

    def test_passes_all_params(self):
        db, mock_pool = _make_db()
        columns = ["id"]
        cur = _mock_cursor(mock_pool, [(1,)], columns)

        db.upsert_client(
            external_id="sq_abc",
            first_name="Jane",
            last_name="Doe",
            email="jane@test.com",
            phone="+12125551234",
            trainer_id=2,
            status="active",
        )

        params = cur.execute.call_args[0][1]
        assert params == ("sq_abc", "sq_abc"[:8], "Jane", "Doe", "jane@test.com", "+12125551234", 2, "active")
