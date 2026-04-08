"""
Tests for core/stripe_client.py, covering:
- handle_webhook for checkout.session.completed with monthly tier
- handle_webhook for checkout.session.completed with 10pack tier
- get_prices returns all 4 tiers
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock
from datetime import datetime

from core.stripe_client import StripeClient, StripePayment, DEFAULT_PRICES
from core.config import Config


def _make_client() -> StripeClient:
    """Create a StripeClient with minimal config."""
    config = Config()
    config.stripe_secret_key = "sk_test_fake"
    config.stripe_webhook_secret = "whsec_test_fake"
    config.stripe_prices = {
        "single": "price_single_123",
        "5pack": "price_5pack_123",
        "10pack": "price_10pack_123",
        "monthly": "price_monthly_123",
    }
    return StripeClient(config)


def _make_checkout_event(tier: str, amount: int, subscription_id=None):
    """Build a fake checkout.session.completed event object."""
    created_ts = int(time.time())
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_test_{tier}_{created_ts}",
                "customer": "cus_test_123",
                "customer_details": {"email": f"{tier}@example.com"},
                "amount_total": amount,
                "currency": "usd",
                "created": created_ts,
                "subscription": subscription_id,
                "metadata": {
                    "tier": tier,
                    "sessions": str(DEFAULT_PRICES[tier]["sessions"] or "unlimited"),
                },
            }
        },
    }


# ---------------------------------------------------------------------------
# handle_webhook tests
# ---------------------------------------------------------------------------


class TestHandleWebhookMonthly:
    """Monthly tier webhook should produce sessions_purchased=None."""

    @patch("stripe.Webhook.construct_event")
    def test_monthly_sessions_purchased_is_none(self, mock_construct):
        """For monthly unlimited, sessions_purchased must be None, not 0."""
        client = _make_client()
        event = _make_checkout_event("monthly", 29900, subscription_id="sub_monthly_001")
        mock_construct.return_value = event

        payment = client.handle_webhook(b"fake_payload", "fake_sig")

        assert payment is not None
        assert payment.tier == "monthly"
        assert payment.sessions_purchased is None, (
            f"Expected None for monthly sessions_purchased, got {payment.sessions_purchased}"
        )
        assert payment.subscription_id == "sub_monthly_001"
        assert payment.amount_cents == 29900

    @patch("stripe.Webhook.construct_event")
    def test_monthly_customer_email(self, mock_construct):
        """Monthly webhook should extract customer email correctly."""
        client = _make_client()
        event = _make_checkout_event("monthly", 29900, subscription_id="sub_001")
        mock_construct.return_value = event

        payment = client.handle_webhook(b"payload", "sig")
        assert payment.customer_email == "monthly@example.com"


class TestHandleWebhook10Pack:
    """10-pack tier webhook should produce sessions_purchased=10."""

    @patch("stripe.Webhook.construct_event")
    def test_10pack_sessions_purchased(self, mock_construct):
        """For 10-pack, sessions_purchased must be 10."""
        client = _make_client()
        event = _make_checkout_event("10pack", 75000)
        mock_construct.return_value = event

        payment = client.handle_webhook(b"fake_payload", "fake_sig")

        assert payment is not None
        assert payment.tier == "10pack"
        assert payment.sessions_purchased == 10
        assert payment.amount_cents == 75000
        assert payment.status == "completed"

    @patch("stripe.Webhook.construct_event")
    def test_10pack_no_subscription(self, mock_construct):
        """10-pack is a one-time payment, no subscription_id."""
        client = _make_client()
        event = _make_checkout_event("10pack", 75000)
        mock_construct.return_value = event

        payment = client.handle_webhook(b"payload", "sig")
        assert payment.subscription_id is None


# ---------------------------------------------------------------------------
# get_prices tests
# ---------------------------------------------------------------------------


class TestGetPrices:
    """get_prices should return all 4 tiers with correct data."""

    def test_returns_four_tiers(self):
        """get_prices must return exactly 4 pricing tiers."""
        client = _make_client()
        prices = client.get_prices()
        assert len(prices) == 4

    def test_tier_names(self):
        """All expected tier keys must be present."""
        client = _make_client()
        prices = client.get_prices()
        tier_keys = {p["tier"] for p in prices}
        assert tier_keys == {"single", "5pack", "10pack", "monthly"}

    def test_monthly_has_no_sessions(self):
        """Monthly tier should have sessions=None (unlimited)."""
        client = _make_client()
        prices = client.get_prices()
        monthly = next(p for p in prices if p["tier"] == "monthly")
        assert monthly["sessions"] is None
        assert monthly["recurring"] is True

    def test_10pack_has_10_sessions(self):
        """10-pack tier should have sessions=10."""
        client = _make_client()
        prices = client.get_prices()
        tenpack = next(p for p in prices if p["tier"] == "10pack")
        assert tenpack["sessions"] == 10
        assert tenpack["amount"] == 75000

    def test_single_session_price(self):
        """Single session should be $85 (8500 cents)."""
        client = _make_client()
        prices = client.get_prices()
        single = next(p for p in prices if p["tier"] == "single")
        assert single["amount"] == 8500
        assert single["sessions"] == 1

    def test_price_ids_mapped(self):
        """When stripe_prices is configured, price_id should be included."""
        client = _make_client()
        prices = client.get_prices()
        single = next(p for p in prices if p["tier"] == "single")
        assert single["price_id"] == "price_single_123"
