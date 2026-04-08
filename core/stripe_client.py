"""
Stripe integration client for tiered pricing and subscriptions.

Pricing tiers:
- Single session: $85
- 5-pack: $400 ($80/session)
- 10-pack: $750 ($75/session)
- Monthly unlimited: $299/mo
"""

import stripe
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

from .config import Config

logger = logging.getLogger(__name__)


# Default pricing (used when Stripe price IDs aren't configured)
DEFAULT_PRICES = {
    "single": {"amount": 8500, "sessions": 1, "label": "Single Session", "per_session": 8500},
    "5pack": {"amount": 40000, "sessions": 5, "label": "5-Session Pack", "per_session": 8000},
    "10pack": {"amount": 75000, "sessions": 10, "label": "10-Session Pack", "per_session": 7500},
    "monthly": {"amount": 29900, "sessions": None, "label": "Monthly Unlimited", "per_session": None, "recurring": True},
}


@dataclass
class StripePayment:
    """Normalized Stripe payment record."""
    id: str
    customer_id: Optional[str]
    customer_email: Optional[str]
    amount_cents: int
    currency: str
    status: str
    tier: Optional[str]  # single, 5pack, 10pack, monthly
    sessions_purchased: Optional[int]  # None means unlimited (monthly)
    created_at: datetime
    subscription_id: Optional[str] = None
    raw: Dict[str, Any] = None


class StripeClient:
    """Client for Stripe payments and subscriptions."""

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.stripe_secret_key
        self.webhook_secret = config.stripe_webhook_secret

        if self.api_key:
            stripe.api_key = self.api_key

        # Map Stripe price IDs to tiers
        self.price_map = {}
        if config.stripe_prices:
            for tier, price_id in config.stripe_prices.items():
                if price_id:
                    self.price_map[price_id] = tier

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def get_prices(self) -> List[Dict[str, Any]]:
        """Return available pricing tiers."""
        prices = []
        for tier_key, tier_info in DEFAULT_PRICES.items():
            price_id = self.config.stripe_prices.get(tier_key) if self.config.stripe_prices else None
            prices.append({
                "tier": tier_key,
                "price_id": price_id,
                "label": tier_info["label"],
                "amount": tier_info["amount"],
                "amount_display": f"${tier_info['amount'] / 100:.0f}",
                "sessions": tier_info["sessions"],
                "per_session": tier_info.get("per_session"),
                "per_session_display": f"${tier_info['per_session'] / 100:.0f}" if tier_info.get("per_session") else None,
                "recurring": tier_info.get("recurring", False),
            })
        return prices

    def create_checkout_session(
        self,
        tier: str,
        customer_email: Optional[str] = None,
        success_url: str = None,
        cancel_url: str = None,
    ) -> Dict[str, Any]:
        """Create a Stripe Checkout session for a pricing tier."""
        if not self.is_configured:
            raise ValueError("Stripe not configured")

        if tier not in DEFAULT_PRICES:
            raise ValueError(f"Unknown tier: {tier}. Options: {list(DEFAULT_PRICES.keys())}")

        tier_info = DEFAULT_PRICES[tier]
        price_id = (self.config.stripe_prices or {}).get(tier)

        params = {
            "payment_method_types": ["card"],
            "success_url": success_url or "https://square-notion-sync.vercel.app/?success=true",
            "cancel_url": cancel_url or "https://square-notion-sync.vercel.app/?cancelled=true",
        }

        if customer_email:
            params["customer_email"] = customer_email

        if price_id:
            # Use configured Stripe price
            mode = "subscription" if tier_info.get("recurring") else "payment"
            params["mode"] = mode
            params["line_items"] = [{"price": price_id, "quantity": 1}]
        else:
            # Use ad-hoc price
            if tier_info.get("recurring"):
                params["mode"] = "subscription"
                params["line_items"] = [{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": tier_info["label"]},
                        "unit_amount": tier_info["amount"],
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }]
            else:
                params["mode"] = "payment"
                params["line_items"] = [{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": tier_info["label"]},
                        "unit_amount": tier_info["amount"],
                    },
                    "quantity": 1,
                }]

        # Add metadata for webhook processing
        params["metadata"] = {
            "tier": tier,
            "sessions": str(tier_info["sessions"] or "unlimited"),
        }

        session = stripe.checkout.Session.create(**params)
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "tier": tier,
            "amount": tier_info["amount"],
        }

    def handle_webhook(self, payload: bytes, sig_header: str) -> Optional[StripePayment]:
        """Process a Stripe webhook event. Returns payment if relevant."""
        if not self.webhook_secret:
            raise ValueError("Webhook secret not configured")

        event = stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            metadata = session.get("metadata", {})
            tier = metadata.get("tier", "single")
            tier_info = DEFAULT_PRICES.get(tier, DEFAULT_PRICES["single"])

            return StripePayment(
                id=session["id"],
                customer_id=session.get("customer"),
                customer_email=session.get("customer_details", {}).get("email"),
                amount_cents=session.get("amount_total", 0),
                currency=session.get("currency", "usd"),
                status="completed",
                tier=tier,
                sessions_purchased=tier_info["sessions"],  # None for monthly (unlimited)
                created_at=datetime.utcfromtimestamp(session["created"]),
                subscription_id=session.get("subscription"),
                raw=session,
            )

        if event["type"] == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            sub_id = invoice.get("subscription")

            if sub_id:
                return StripePayment(
                    id=invoice["id"],
                    customer_id=invoice.get("customer"),
                    customer_email=invoice.get("customer_email"),
                    amount_cents=invoice.get("amount_paid", 0),
                    currency=invoice.get("currency", "usd"),
                    status="completed",
                    tier="monthly",
                    sessions_purchased=None,  # None = unlimited
                    created_at=datetime.utcfromtimestamp(invoice["created"]),
                    subscription_id=sub_id,
                    raw=invoice,
                )

        return None

    def list_recent_payments(self, limit: int = 100) -> List[StripePayment]:
        """List recent completed checkout sessions."""
        if not self.is_configured:
            return []

        sessions = stripe.checkout.Session.list(
            limit=limit,
            status="complete",
            expand=["data.customer"],
        )

        payments = []
        for s in sessions.data:
            metadata = s.get("metadata", {})
            tier = metadata.get("tier", "single")
            tier_info = DEFAULT_PRICES.get(tier, DEFAULT_PRICES["single"])

            payments.append(StripePayment(
                id=s["id"],
                customer_id=s.get("customer", {}).get("id") if isinstance(s.get("customer"), dict) else s.get("customer"),
                customer_email=s.get("customer_details", {}).get("email"),
                amount_cents=s.get("amount_total", 0),
                currency=s.get("currency", "usd"),
                status="completed",
                tier=tier,
                sessions_purchased=tier_info["sessions"],  # None for monthly (unlimited)
                created_at=datetime.utcfromtimestamp(s["created"]),
                subscription_id=s.get("subscription"),
                raw=dict(s),
            ))

        return payments
