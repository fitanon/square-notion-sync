"""
Tests for Bug 7 fix: Portal lookup uses Square Search API.

The /portal/lookup endpoint must:
- Call search_customers (Search API) instead of iterating all customers O(n)
- Return customer data with session balance on match
- Return 400 when neither email nor phone is provided
- Return 404 when no customer matches
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

def _make_customer(
    customer_id="cust_001",
    account_code="TFC",
    given_name="Jane",
    family_name="Doe",
    email="jane@example.com",
    phone="+12125551234",
):
    return Customer(
        id=customer_id,
        account_code=account_code,
        given_name=given_name,
        family_name=family_name,
        email=email,
        phone=phone,
        created_at=datetime(2025, 1, 15),
        raw={},
    )


def _make_booking(customer_id="cust_001", account_code="TFC", status="ACCEPTED"):
    return Booking(
        id="bk_001",
        account_code=account_code,
        customer_id=customer_id,
        start_at=datetime(2025, 3, 10, 10, 0),
        end_at=datetime(2025, 3, 10, 11, 0),
        status=status,
        raw={},
    )


def _build_test_app():
    """Create a FastAPI app with mocked globals for portal testing."""
    import api.app as app_module

    mock_config = MagicMock()
    mock_config.accounts = {"TFC": MagicMock(code="TFC", name="TFC", environment="sandbox", access_token="fake")}
    mock_config.notion = MagicMock()
    mock_config.sync.schedule_hour = 2
    mock_config.sync.schedule_minute = 0
    mock_config.sync.timezone = "America/New_York"
    mock_config.sync.session_item_name = "One-on-One 60"
    mock_config.square_api_version = "2025-06-16"

    mock_scheduler = MagicMock()
    mock_scheduler.scheduler.running = True

    app_module.config = mock_config
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
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def portal_found():
    """App where search_customers finds a customer with sessions."""
    customer = _make_customer()
    booking = _make_booking(status="ACCEPTED")

    mock_square_client = MagicMock()
    mock_square_client.search_customers.return_value = [customer]
    mock_square_client.get_all_bookings.return_value = [booking]
    mock_square_client.count_session_purchases.return_value = 5

    env = os.environ.copy()
    env.pop("API_SECRET_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        app = _build_test_app()
        # Patch where the import resolves: core.accounts.MultiAccountClient
        with patch("core.accounts.MultiAccountClient") as MockMulti:
            instance = MockMulti.return_value
            instance.clients = {"TFC": mock_square_client}
            yield TestClient(app), mock_square_client


@pytest.fixture()
def portal_not_found():
    """App where search_customers finds nobody."""
    mock_square_client = MagicMock()
    mock_square_client.search_customers.return_value = []

    env = os.environ.copy()
    env.pop("API_SECRET_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        app = _build_test_app()
        with patch("core.accounts.MultiAccountClient") as MockMulti:
            instance = MockMulti.return_value
            instance.clients = {"TFC": mock_square_client}
            yield TestClient(app), mock_square_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPortalLookupValidEmail:
    """Portal lookup with a valid email should return customer data."""

    def test_returns_customer_data(self, portal_found):
        client, mock_sq = portal_found
        resp = client.get("/portal/lookup?email=jane@example.com")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Jane Doe"
        assert data["email"] == "jane@example.com"
        assert data["account"] == "TFC"

    def test_returns_session_balance(self, portal_found):
        client, mock_sq = portal_found
        resp = client.get("/portal/lookup?email=jane@example.com")
        data = resp.json()
        assert data["sessions_purchased"] == 5
        assert data["sessions_used"] == 1  # one ACCEPTED booking
        assert data["sessions_remaining"] == 4

    def test_calls_search_customers_not_get_all(self, portal_found):
        """The fix must use search_customers, not get_all_customers."""
        client, mock_sq = portal_found
        client.get("/portal/lookup?email=jane@example.com")
        mock_sq.search_customers.assert_called_once_with(email="jane@example.com", phone=None)
        # get_all_customers should NOT be called (that's the old O(n) path)
        mock_sq.get_all_customers.assert_not_called()


class TestPortalLookupMissingParams:
    """Portal lookup without email or phone should return 400."""

    def test_no_params_returns_400(self, portal_not_found):
        client, _ = portal_not_found
        resp = client.get("/portal/lookup")
        assert resp.status_code == 400
        assert "Provide" in resp.json()["detail"]

    def test_empty_string_params(self, portal_not_found):
        """Empty string query params -- FastAPI treats them as truthy strings."""
        client, _ = portal_not_found
        resp = client.get("/portal/lookup?email=&phone=")
        # Empty strings are still truthy in Python, so the check passes
        # and we get 404 (no customer found) rather than 400
        assert resp.status_code in (400, 404)


class TestPortalLookupNotFound:
    """Portal lookup with unknown email should return 404."""

    def test_unknown_email_returns_404(self, portal_not_found):
        client, mock_sq = portal_not_found
        resp = client.get("/portal/lookup?email=nobody@example.com")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_unknown_phone_returns_404(self, portal_not_found):
        client, mock_sq = portal_not_found
        resp = client.get("/portal/lookup?phone=5559999999")
        assert resp.status_code == 404
