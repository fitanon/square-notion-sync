"""
Tests for portal lookup Postgres integration.

Verifies:
- Portal uses Postgres when database is configured (fast path)
- Portal falls back to Square when Postgres is not configured
- Portal falls back to Square when Postgres query raises an exception
"""

import os
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.accounts import Customer, Booking


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_customer(**overrides):
    defaults = dict(
        id="cust_001",
        account_code="TFC",
        given_name="Jane",
        family_name="Doe",
        email="jane@example.com",
        phone="+12125551234",
        created_at=datetime(2025, 1, 15),
        raw={},
    )
    defaults.update(overrides)
    return Customer(**defaults)


def _build_test_app(db_mock=None):
    """Create a FastAPI test app with mocked globals."""
    import api.app as app_module

    mock_config = MagicMock()
    mock_config.accounts = {
        "TFC": MagicMock(code="TFC", name="TFC", environment="sandbox", access_token="fake")
    }
    mock_config.notion = MagicMock()
    mock_config.sync.schedule_hour = 2
    mock_config.sync.schedule_minute = 0
    mock_config.sync.timezone = "America/New_York"
    mock_config.sync.session_item_name = "One-on-One 60"
    mock_config.square_api_version = "2025-06-16"

    mock_scheduler = MagicMock()
    mock_scheduler.scheduler.running = True

    app_module.config = mock_config
    app_module.db = db_mock
    app_module.scheduler = mock_scheduler
    app_module.financial_sync = MagicMock()
    app_module.appointments_sync = MagicMock()
    app_module.sessions_sync = MagicMock()
    app_module.stripe_client = MagicMock()
    app_module.stripe_client.is_configured = True
    app_module.stripe_sync = MagicMock()

    from api.app import register_routes
    test_app = FastAPI()
    register_routes(test_app)
    return test_app


# ---------------------------------------------------------------------------
# Postgres fast-path tests
# ---------------------------------------------------------------------------

class TestPortalLookupPostgres:
    """When Postgres is configured and has the client, use the fast path."""

    def test_returns_data_from_postgres(self):
        mock_db = MagicMock()
        mock_db.is_configured = True
        mock_db.get_client_by_email.return_value = {
            "id": 1,
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "phone": "+12125551234",
        }
        mock_db.get_sessions_remaining.return_value = 7

        env = os.environ.copy()
        env.pop("API_SECRET_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            app = _build_test_app(db_mock=mock_db)
            client = TestClient(app)
            resp = client.get("/portal/lookup?email=jane@example.com")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Jane Doe"
        assert data["source"] == "postgres"
        assert data["sessions_remaining"] == 7

    def test_returns_unlimited_from_postgres(self):
        mock_db = MagicMock()
        mock_db.is_configured = True
        mock_db.get_client_by_email.return_value = {
            "id": 1,
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "phone": None,
        }
        mock_db.get_sessions_remaining.return_value = None  # unlimited

        env = os.environ.copy()
        env.pop("API_SECRET_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            app = _build_test_app(db_mock=mock_db)
            client = TestClient(app)
            resp = client.get("/portal/lookup?email=jane@example.com")

        data = resp.json()
        assert data["sessions_remaining"] == "unlimited"

    def test_postgres_phone_lookup(self):
        mock_db = MagicMock()
        mock_db.is_configured = True
        mock_db.get_client_by_email.return_value = None
        mock_db.get_client_by_phone.return_value = {
            "id": 2,
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob@example.com",
            "phone": "+12125559999",
        }
        mock_db.get_sessions_remaining.return_value = 3

        env = os.environ.copy()
        env.pop("API_SECRET_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            app = _build_test_app(db_mock=mock_db)
            client = TestClient(app)
            resp = client.get("/portal/lookup?phone=2125559999")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Bob Smith"
        assert data["source"] == "postgres"


# ---------------------------------------------------------------------------
# Fallback to Square tests
# ---------------------------------------------------------------------------

class TestPortalLookupFallback:
    """When Postgres is not configured, fall back to Square API."""

    def test_uses_square_when_db_not_configured(self):
        """db is None -> must go to Square."""
        customer = _make_customer()
        mock_square = MagicMock()
        mock_square.search_customers.return_value = [customer]
        mock_square.count_session_purchases.return_value = 5
        mock_square.get_all_bookings.return_value = []

        env = os.environ.copy()
        env.pop("API_SECRET_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            app = _build_test_app(db_mock=None)
            with patch("core.accounts.MultiAccountClient") as MockMulti:
                MockMulti.return_value.clients = {"TFC": mock_square}
                client = TestClient(app)
                resp = client.get("/portal/lookup?email=jane@example.com")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "square"
        mock_square.search_customers.assert_called_once()

    def test_falls_back_to_square_on_postgres_error(self):
        """Postgres throws -> graceful fallback to Square."""
        mock_db = MagicMock()
        mock_db.is_configured = True
        mock_db.get_client_by_email.side_effect = Exception("connection lost")

        customer = _make_customer()
        mock_square = MagicMock()
        mock_square.search_customers.return_value = [customer]
        mock_square.count_session_purchases.return_value = 10
        mock_square.get_all_bookings.return_value = []

        env = os.environ.copy()
        env.pop("API_SECRET_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            app = _build_test_app(db_mock=mock_db)
            with patch("core.accounts.MultiAccountClient") as MockMulti:
                MockMulti.return_value.clients = {"TFC": mock_square}
                client = TestClient(app)
                resp = client.get("/portal/lookup?email=jane@example.com")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "square"

    def test_falls_back_when_postgres_client_not_found(self):
        """Postgres has no match -> fall through to Square."""
        mock_db = MagicMock()
        mock_db.is_configured = True
        mock_db.get_client_by_email.return_value = None

        customer = _make_customer()
        mock_square = MagicMock()
        mock_square.search_customers.return_value = [customer]
        mock_square.count_session_purchases.return_value = 5
        mock_square.get_all_bookings.return_value = []

        env = os.environ.copy()
        env.pop("API_SECRET_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            app = _build_test_app(db_mock=mock_db)
            with patch("core.accounts.MultiAccountClient") as MockMulti:
                MockMulti.return_value.clients = {"TFC": mock_square}
                client = TestClient(app)
                resp = client.get("/portal/lookup?email=jane@example.com")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "square"
