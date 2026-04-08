"""
Tests for Stripe -> Notion sync, covering:
- Bug 1: query_database called with correct `filter_` param (not `filter_props`)
- Bug 2: Correct tuple destructuring of query_database result
- Bug 3: Monthly unlimited returns sessions_purchased=None, portal returns "unlimited"
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from core.notion import NotionPage
from core.stripe_client import StripePayment


# ---------------------------------------------------------------------------
# Bug 1: _sync_payment must call query_database with `filter_=` not `filter_props=`
# ---------------------------------------------------------------------------


class TestSyncPaymentFilterParam:
    """Verify _sync_payment calls query_database with the correct keyword argument."""

    def _make_sync(self):
        """Create a StripePaymentsSync with mocked dependencies."""
        from core.config import Config, NotionConfig

        config = Config()
        config.notion = NotionConfig(token="fake-token", db_sessions="db-123")
        config.stripe_secret_key = "sk_test_fake"

        with patch("sync.stripe_payments.StripeClient"):
            from sync.stripe_payments import StripePaymentsSync
            sync = StripePaymentsSync(config)

        # Mock the notion client
        mock_notion = MagicMock()
        mock_notion.query_database.return_value = ([], None)
        sync.notion = mock_notion

        return sync, mock_notion

    def test_filter_param_name(self):
        """query_database must be called with filter_= keyword, not filter_props=."""
        sync, mock_notion = self._make_sync()

        payment = StripePayment(
            id="cs_test_123",
            customer_id="cus_123",
            customer_email="test@example.com",
            amount_cents=8500,
            currency="usd",
            status="completed",
            tier="single",
            sessions_purchased=1,
            created_at=datetime(2026, 1, 15),
        )

        sync._sync_payment(payment)

        mock_notion.query_database.assert_called_once()
        call_kwargs = mock_notion.query_database.call_args
        # filter_ must be passed as a keyword arg, not filter_props
        assert "filter_" in call_kwargs.kwargs, (
            "query_database was not called with filter_= keyword argument"
        )
        assert "filter_props" not in call_kwargs.kwargs, (
            "query_database was incorrectly called with filter_props="
        )


# ---------------------------------------------------------------------------
# Bug 2: Correct tuple destructuring of query_database return value
# ---------------------------------------------------------------------------


class TestSyncPaymentDestructuring:
    """Verify _sync_payment correctly destructures (pages, cursor) tuple."""

    def _make_sync(self):
        from core.config import Config, NotionConfig

        config = Config()
        config.notion = NotionConfig(token="fake-token", db_sessions="db-123")
        config.stripe_secret_key = "sk_test_fake"

        with patch("sync.stripe_payments.StripeClient"):
            from sync.stripe_payments import StripePaymentsSync
            sync = StripePaymentsSync(config)

        mock_notion = MagicMock()
        sync.notion = mock_notion
        return sync, mock_notion

    def test_update_existing_page_uses_dot_id(self):
        """When a matching page exists, update_page should be called with page.id (attribute)."""
        sync, mock_notion = self._make_sync()

        existing_page = NotionPage(
            id="page-abc-123",
            properties={},
            created_time=datetime(2026, 1, 1),
            last_edited_time=datetime(2026, 1, 1),
        )
        mock_notion.query_database.return_value = ([existing_page], None)

        payment = StripePayment(
            id="cs_test_456",
            customer_id="cus_456",
            customer_email="client@example.com",
            amount_cents=40000,
            currency="usd",
            status="completed",
            tier="5pack",
            sessions_purchased=5,
            created_at=datetime(2026, 2, 1),
        )

        sync._sync_payment(payment)

        # update_page must be called with the page's .id string
        mock_notion.update_page.assert_called_once()
        first_arg = mock_notion.update_page.call_args[0][0]
        assert first_arg == "page-abc-123", (
            f"Expected update_page called with 'page-abc-123', got '{first_arg}'"
        )

    def test_create_new_page_when_no_match(self):
        """When no matching page exists, create_page should be called."""
        sync, mock_notion = self._make_sync()

        mock_notion.query_database.return_value = ([], None)

        payment = StripePayment(
            id="cs_test_789",
            customer_id="cus_789",
            customer_email="new@example.com",
            amount_cents=8500,
            currency="usd",
            status="completed",
            tier="single",
            sessions_purchased=1,
            created_at=datetime(2026, 3, 1),
        )

        sync._sync_payment(payment)

        mock_notion.create_page.assert_called_once()
        mock_notion.update_page.assert_not_called()


# ---------------------------------------------------------------------------
# Bug 3: Monthly tier → sessions_purchased=None, portal returns "unlimited"
# ---------------------------------------------------------------------------


class TestMonthlySessionsPurchased:
    """Monthly unlimited tier should have sessions_purchased=None, not 0."""

    def test_sync_payment_none_sessions_for_monthly(self):
        """When monthly subscriber pays, sessions_purchased in Notion should be None."""
        from core.config import Config, NotionConfig

        config = Config()
        config.notion = NotionConfig(token="fake-token", db_sessions="db-123")
        config.stripe_secret_key = "sk_test_fake"

        with patch("sync.stripe_payments.StripeClient"):
            from sync.stripe_payments import StripePaymentsSync
            sync = StripePaymentsSync(config)

        mock_notion = MagicMock()
        mock_notion.query_database.return_value = ([], None)
        sync.notion = mock_notion

        payment = StripePayment(
            id="cs_monthly_001",
            customer_id="cus_monthly",
            customer_email="monthly@example.com",
            amount_cents=29900,
            currency="usd",
            status="completed",
            tier="monthly",
            sessions_purchased=None,  # Bug 3 fix: None means unlimited
            created_at=datetime(2026, 4, 1),
            subscription_id="sub_monthly_001",
        )

        sync._sync_payment(payment)

        mock_notion.create_page.assert_called_once()
        props = mock_notion.create_page.call_args[0][1]
        # sessions_purchased=None means unlimited, should NOT be 0
        assert props["Sessions Purchased"]["number"] is None, (
            f"Expected Sessions Purchased to be None for monthly, got {props['Sessions Purchased']}"
        )


class TestPortalUnlimited:
    """Portal lookup should return 'unlimited' for monthly subscribers."""

    def test_portal_returns_unlimited_for_none_purchased(self):
        """
        When sessions_purchased is None (monthly unlimited), portal should
        return 'unlimited' instead of computing a numeric remainder.
        """
        from fastapi.testclient import TestClient
        from unittest.mock import patch

        import api.app as app_module

        # Set up config
        mock_config = MagicMock()
        mock_config.accounts = {"TFC": MagicMock(code="TFC")}
        mock_config.notion = MagicMock()
        mock_config.sync = MagicMock()
        mock_config.sync.session_item_name = "One-on-One 60"
        app_module.config = mock_config
        app_module.scheduler = MagicMock()
        app_module.scheduler.scheduler.running = True
        app_module.financial_sync = MagicMock()
        app_module.appointments_sync = MagicMock()
        app_module.sessions_sync = MagicMock()
        app_module.stripe_client = MagicMock()
        app_module.stripe_client.is_configured = True
        app_module.stripe_sync = MagicMock()

        # Create a mock customer
        mock_customer = MagicMock()
        mock_customer.email = "monthly@example.com"
        mock_customer.phone = "555-0100"
        mock_customer.full_name = "Monthly Client"
        mock_customer.id = "cust_monthly"

        # Mock SquareClient with search_customers (Bug 7 fix uses search, not iteration)
        mock_client = MagicMock()
        mock_client.search_customers.return_value = [mock_customer]
        # Return None for purchased (monthly unlimited)
        mock_client.count_session_purchases.return_value = None
        mock_client.get_all_bookings.return_value = []

        mock_multi_instance = MagicMock()
        mock_multi_instance.clients = {"TFC": mock_client}

        # Patch where portal_lookup imports MultiAccountClient from
        with patch("core.accounts.MultiAccountClient", return_value=mock_multi_instance):
            from fastapi import FastAPI
            from api.app import register_routes
            test_app = FastAPI()
            register_routes(test_app)
            client = TestClient(test_app, raise_server_exceptions=False)

            response = client.get("/portal/lookup?email=monthly@example.com")

            assert response.status_code == 200
            data = response.json()
            assert data["sessions_remaining"] == "unlimited", (
                f"Expected 'unlimited', got {data['sessions_remaining']}"
            )
