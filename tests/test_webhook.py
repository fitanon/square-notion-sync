"""
Tests for Bug 6 fix: Stripe webhook error handling.

The webhook endpoint must:
- Return 400 when signature verification fails (ValueError from handle_webhook)
- Return 200 with status "received_sync_failed" when Notion sync fails
- Return 200 with status "synced" on successful sync
- Never return 400 for internal sync failures (which would cause Stripe retries)
"""

import os
import time
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.stripe_client import StripePayment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_test_app():
    """Create a FastAPI app with mocked globals for webhook testing."""
    import api.app as app_module

    mock_config = MagicMock()
    mock_config.accounts = {"PA": MagicMock(code="PA", name="PA", environment="sandbox")}
    mock_config.notion = MagicMock()
    mock_config.sync.schedule_hour = 2
    mock_config.sync.schedule_minute = 0
    mock_config.sync.timezone = "America/New_York"
    mock_config.sync.session_item_name = "One-on-One 60"

    mock_scheduler = MagicMock()
    mock_scheduler.scheduler.running = True

    mock_stripe_client = MagicMock()
    mock_stripe_client.is_configured = True
    mock_stripe_sync = MagicMock()

    app_module.config = mock_config
    app_module.scheduler = mock_scheduler
    app_module.financial_sync = MagicMock()
    app_module.appointments_sync = MagicMock()
    app_module.sessions_sync = MagicMock()
    app_module.stripe_client = mock_stripe_client
    app_module.stripe_sync = mock_stripe_sync

    from api.app import register_routes

    test_app = FastAPI()
    register_routes(test_app)
    return test_app, mock_stripe_client, mock_stripe_sync


def _make_payment(tier="single", amount=8500):
    """Build a fake StripePayment for testing."""
    return StripePayment(
        id=f"cs_test_{tier}_{int(time.time())}",
        customer_id="cus_test_123",
        customer_email="test@example.com",
        amount_cents=amount,
        currency="usd",
        status="completed",
        tier=tier,
        sessions_purchased=1,
        created_at=datetime.utcnow(),
        subscription_id=None,
        raw={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def webhook_app():
    """Return test client plus mocked stripe_client and stripe_sync."""
    env = os.environ.copy()
    env.pop("API_SECRET_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        app, stripe_client, stripe_sync = _build_test_app()
        client = TestClient(app)
        yield client, stripe_client, stripe_sync


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWebhookReturns400OnInvalidSignature:
    """Signature verification failures must return 400."""

    def test_missing_signature_header(self, webhook_app):
        client, stripe_client, stripe_sync = webhook_app
        resp = client.post(
            "/stripe/webhook",
            content=b'{"fake": "payload"}',
        )
        assert resp.status_code == 400
        assert "stripe-signature" in resp.json()["detail"].lower() or "Missing" in resp.json()["detail"]

    def test_invalid_signature_returns_400(self, webhook_app):
        client, stripe_client, stripe_sync = webhook_app
        # handle_webhook raises ValueError for bad signature / missing secret
        stripe_client.handle_webhook.side_effect = ValueError("Webhook secret not configured")

        resp = client.post(
            "/stripe/webhook",
            content=b'{"fake": "payload"}',
            headers={"stripe-signature": "bad_sig"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid webhook"

    def test_value_error_from_stripe_returns_400(self, webhook_app):
        client, stripe_client, stripe_sync = webhook_app
        stripe_client.handle_webhook.side_effect = ValueError(
            "No signatures found matching the expected signature for payload"
        )

        resp = client.post(
            "/stripe/webhook",
            content=b'{"data": {}}',
            headers={"stripe-signature": "t=123,v1=abc"},
        )
        assert resp.status_code == 400


class TestWebhookReturns200OnSyncFailure:
    """Notion sync failures must still return 200 to avoid Stripe retries."""

    def test_sync_failure_returns_200(self, webhook_app):
        client, stripe_client, stripe_sync = webhook_app
        payment = _make_payment()
        stripe_client.handle_webhook.return_value = payment
        stripe_sync._sync_payment.side_effect = Exception("Notion API timeout")

        resp = client.post(
            "/stripe/webhook",
            content=b'{"data": {}}',
            headers={"stripe-signature": "valid_sig"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "received_sync_failed"
        assert data["payment_id"] == payment.id

    def test_sync_failure_does_not_return_400(self, webhook_app):
        """The old code returned 400 on ANY exception. Verify that's fixed."""
        client, stripe_client, stripe_sync = webhook_app
        payment = _make_payment(tier="10pack", amount=75000)
        stripe_client.handle_webhook.return_value = payment
        stripe_sync._sync_payment.side_effect = ConnectionError("Notion unreachable")

        resp = client.post(
            "/stripe/webhook",
            content=b'{"data": {}}',
            headers={"stripe-signature": "valid_sig"},
        )
        # Must NOT be 400 -- that would cause Stripe to retry
        assert resp.status_code != 400
        assert resp.status_code == 200


class TestWebhookSuccessfulSync:
    """Successful webhook + sync should return 200 with synced status."""

    def test_synced_status(self, webhook_app):
        client, stripe_client, stripe_sync = webhook_app
        payment = _make_payment()
        stripe_client.handle_webhook.return_value = payment
        stripe_sync._sync_payment.return_value = None  # no error

        resp = client.post(
            "/stripe/webhook",
            content=b'{"data": {}}',
            headers={"stripe-signature": "valid_sig"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "synced"
        assert data["payment_id"] == payment.id

    def test_ignored_event_returns_200(self, webhook_app):
        """Events that don't produce a payment should return 'ignored'."""
        client, stripe_client, stripe_sync = webhook_app
        stripe_client.handle_webhook.return_value = None  # unrecognized event type

        resp = client.post(
            "/stripe/webhook",
            content=b'{"type": "charge.refunded"}',
            headers={"stripe-signature": "valid_sig"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
