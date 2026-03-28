"""
Stripe client for payments, subscriptions, and tiered pricing.

Handles:
- One-time purchases (session packs with tiered pricing)
- Recurring subscriptions (monthly packages)
- Customer management
- Webhook events
"""

import stripe
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List

from .config import StripeConfig

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────

@dataclass
class StripeCustomer:
    """Stripe customer data."""
    id: str
    email: Optional[str]
    name: Optional[str]
    phone: Optional[str]
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_stripe(cls, obj: stripe.Customer) -> "StripeCustomer":
        return cls(
            id=obj.id,
            email=obj.email,
            name=obj.name,
            phone=obj.phone,
            metadata=dict(obj.metadata or {}),
            created_at=datetime.fromtimestamp(obj.created),
        )


@dataclass
class StripePayment:
    """Stripe payment/charge data."""
    id: str
    customer_id: Optional[str]
    amount_cents: int
    currency: str
    status: str
    description: Optional[str]
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def amount_dollars(self) -> float:
        return self.amount_cents / 100.0

    @classmethod
    def from_payment_intent(cls, pi: stripe.PaymentIntent) -> "StripePayment":
        return cls(
            id=pi.id,
            customer_id=pi.customer if isinstance(pi.customer, str) else (pi.customer.id if pi.customer else None),
            amount_cents=pi.amount,
            currency=pi.currency.upper(),
            status=pi.status,
            description=pi.description,
            metadata=dict(pi.metadata or {}),
            created_at=datetime.fromtimestamp(pi.created),
        )

    @classmethod
    def from_charge(cls, charge: stripe.Charge) -> "StripePayment":
        return cls(
            id=charge.id,
            customer_id=charge.customer if isinstance(charge.customer, str) else (charge.customer.id if charge.customer else None),
            amount_cents=charge.amount,
            currency=charge.currency.upper(),
            status=charge.status,
            description=charge.description,
            metadata=dict(charge.metadata or {}),
            created_at=datetime.fromtimestamp(charge.created),
        )


@dataclass
class StripeSubscription:
    """Stripe subscription data."""
    id: str
    customer_id: str
    status: str
    price_id: str
    product_id: Optional[str]
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "trialing")

    @classmethod
    def from_stripe(cls, sub: stripe.Subscription) -> "StripeSubscription":
        item = sub.items.data[0] if sub.items.data else None
        return cls(
            id=sub.id,
            customer_id=sub.customer if isinstance(sub.customer, str) else sub.customer.id,
            status=sub.status,
            price_id=item.price.id if item else "",
            product_id=item.price.product if item and isinstance(item.price.product, str) else None,
            current_period_start=datetime.fromtimestamp(sub.current_period_start),
            current_period_end=datetime.fromtimestamp(sub.current_period_end),
            cancel_at_period_end=sub.cancel_at_period_end,
            metadata=dict(sub.metadata or {}),
            created_at=datetime.fromtimestamp(sub.created),
        )


@dataclass
class TieredPrice:
    """Represents a tiered pricing option."""
    id: str
    name: str
    sessions: int
    amount_cents: int
    currency: str = "usd"
    is_recurring: bool = False
    interval: Optional[str] = None  # "month", "year"

    @property
    def amount_dollars(self) -> float:
        return self.amount_cents / 100.0

    @property
    def per_session_cents(self) -> int:
        if self.sessions > 0:
            return self.amount_cents // self.sessions
        return self.amount_cents

    @property
    def per_session_dollars(self) -> float:
        return self.per_session_cents / 100.0


# ─────────────────────────────────────────────────────────────
# STRIPE CLIENT
# ─────────────────────────────────────────────────────────────

class StripeClient:
    """Client for Stripe API operations."""

    # Default tiered pricing structure
    DEFAULT_TIERS: List[Dict[str, Any]] = [
        {"name": "Single Session", "sessions": 1, "amount_cents": 8500},
        {"name": "5 Session Pack", "sessions": 5, "amount_cents": 40000},  # $80/session
        {"name": "10 Session Pack", "sessions": 10, "amount_cents": 75000},  # $75/session
    ]

    # Default monthly subscription
    DEFAULT_MONTHLY = {"name": "Monthly Unlimited", "amount_cents": 29900, "interval": "month"}

    def __init__(self, config: StripeConfig):
        self.config = config
        stripe.api_key = config.secret_key
        self._cached_prices: Dict[str, TieredPrice] = {}

    # ─────────────────────────────────────────────────────────
    # CUSTOMER MANAGEMENT
    # ─────────────────────────────────────────────────────────

    def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeCustomer:
        """Create a new Stripe customer."""
        customer = stripe.Customer.create(
            email=email,
            name=name,
            phone=phone,
            metadata=metadata or {},
        )
        logger.info(f"Created Stripe customer {customer.id} for {email}")
        return StripeCustomer.from_stripe(customer)

    def get_customer(self, customer_id: str) -> Optional[StripeCustomer]:
        """Get customer by ID."""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            if customer.deleted:
                return None
            return StripeCustomer.from_stripe(customer)
        except stripe.error.InvalidRequestError:
            return None

    def find_customer_by_email(self, email: str) -> Optional[StripeCustomer]:
        """Find customer by email address."""
        customers = stripe.Customer.list(email=email, limit=1)
        if customers.data:
            return StripeCustomer.from_stripe(customers.data[0])
        return None

    def get_or_create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeCustomer:
        """Get existing customer or create new one."""
        existing = self.find_customer_by_email(email)
        if existing:
            return existing
        return self.create_customer(email, name, phone, metadata)

    def list_customers(self, limit: int = 100, starting_after: Optional[str] = None) -> List[StripeCustomer]:
        """List customers with pagination."""
        params = {"limit": limit}
        if starting_after:
            params["starting_after"] = starting_after
        customers = stripe.Customer.list(**params)
        return [StripeCustomer.from_stripe(c) for c in customers.data]

    # ─────────────────────────────────────────────────────────
    # PRODUCT & PRICE MANAGEMENT
    # ─────────────────────────────────────────────────────────

    def create_product(self, name: str, description: Optional[str] = None) -> str:
        """Create a Stripe product. Returns product ID."""
        product = stripe.Product.create(
            name=name,
            description=description,
        )
        logger.info(f"Created product {product.id}: {name}")
        return product.id

    def create_price(
        self,
        product_id: str,
        amount_cents: int,
        currency: str = "usd",
        recurring_interval: Optional[str] = None,  # "month", "year"
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Create a price for a product. Returns price ID."""
        params = {
            "product": product_id,
            "unit_amount": amount_cents,
            "currency": currency,
            "metadata": metadata or {},
        }
        if recurring_interval:
            params["recurring"] = {"interval": recurring_interval}

        price = stripe.Price.create(**params)
        logger.info(f"Created price {price.id}: ${amount_cents/100:.2f} {currency.upper()}")
        return price.id

    def setup_tiered_pricing(self, tiers: Optional[List[Dict[str, Any]]] = None) -> Dict[str, str]:
        """
        Create products and prices for tiered session packs.

        Returns dict mapping tier key to price ID.
        """
        tiers = tiers or self.DEFAULT_TIERS
        price_ids = {}

        # Create main product for session packs
        product_id = self.create_product(
            name="Training Sessions",
            description="Personal training session packs",
        )

        for tier in tiers:
            sessions = tier["sessions"]
            price_id = self.create_price(
                product_id=product_id,
                amount_cents=tier["amount_cents"],
                metadata={"sessions": str(sessions), "tier_name": tier["name"]},
            )
            key = f"{sessions}_SESSION" if sessions == 1 else f"{sessions}_SESSIONS"
            price_ids[key] = price_id

        return price_ids

    def setup_monthly_subscription(
        self,
        amount_cents: Optional[int] = None,
        name: str = "Monthly Unlimited",
    ) -> str:
        """Create product and price for monthly subscription. Returns price ID."""
        amount = amount_cents or self.DEFAULT_MONTHLY["amount_cents"]

        product_id = self.create_product(
            name=name,
            description="Monthly unlimited training subscription",
        )

        price_id = self.create_price(
            product_id=product_id,
            amount_cents=amount,
            recurring_interval="month",
            metadata={"type": "subscription", "tier_name": name},
        )

        return price_id

    def get_price(self, price_id: str) -> Optional[TieredPrice]:
        """Get price details."""
        if price_id in self._cached_prices:
            return self._cached_prices[price_id]

        try:
            price = stripe.Price.retrieve(price_id, expand=["product"])
            product = price.product
            product_name = product.name if hasattr(product, "name") else ""

            sessions = int(price.metadata.get("sessions", 1))
            is_recurring = price.recurring is not None

            tiered = TieredPrice(
                id=price.id,
                name=price.metadata.get("tier_name", product_name),
                sessions=sessions,
                amount_cents=price.unit_amount,
                currency=price.currency.upper(),
                is_recurring=is_recurring,
                interval=price.recurring.interval if is_recurring else None,
            )
            self._cached_prices[price_id] = tiered
            return tiered
        except stripe.error.InvalidRequestError:
            return None

    # ─────────────────────────────────────────────────────────
    # CHECKOUT & PAYMENTS
    # ─────────────────────────────────────────────────────────

    def create_checkout_session(
        self,
        price_id: str,
        customer_id: Optional[str] = None,
        customer_email: Optional[str] = None,
        success_url: str = "https://example.com/success",
        cancel_url: str = "https://example.com/cancel",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Create a Stripe Checkout session for payment.

        Returns the checkout session URL.
        """
        price = stripe.Price.retrieve(price_id)
        mode = "subscription" if price.recurring else "payment"

        params = {
            "mode": mode,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata or {},
        }

        if customer_id:
            params["customer"] = customer_id
        elif customer_email:
            params["customer_email"] = customer_email

        session = stripe.checkout.Session.create(**params)
        logger.info(f"Created checkout session {session.id} for price {price_id}")
        return session.url

    def create_payment_intent(
        self,
        amount_cents: int,
        customer_id: Optional[str] = None,
        currency: str = "usd",
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripePayment:
        """Create a PaymentIntent for custom payment flows."""
        params = {
            "amount": amount_cents,
            "currency": currency,
            "metadata": metadata or {},
        }
        if customer_id:
            params["customer"] = customer_id
        if description:
            params["description"] = description

        pi = stripe.PaymentIntent.create(**params)
        logger.info(f"Created PaymentIntent {pi.id}: ${amount_cents/100:.2f}")
        return StripePayment.from_payment_intent(pi)

    def get_payment(self, payment_intent_id: str) -> Optional[StripePayment]:
        """Get payment intent by ID."""
        try:
            pi = stripe.PaymentIntent.retrieve(payment_intent_id)
            return StripePayment.from_payment_intent(pi)
        except stripe.error.InvalidRequestError:
            return None

    def list_payments(
        self,
        customer_id: Optional[str] = None,
        limit: int = 100,
        created_after: Optional[datetime] = None,
    ) -> List[StripePayment]:
        """List payment intents with optional filters."""
        params = {"limit": limit}
        if customer_id:
            params["customer"] = customer_id
        if created_after:
            params["created"] = {"gte": int(created_after.timestamp())}

        intents = stripe.PaymentIntent.list(**params)
        return [StripePayment.from_payment_intent(pi) for pi in intents.data]

    def list_charges(
        self,
        customer_id: Optional[str] = None,
        limit: int = 100,
        created_after: Optional[datetime] = None,
    ) -> List[StripePayment]:
        """List charges with optional filters."""
        params = {"limit": limit}
        if customer_id:
            params["customer"] = customer_id
        if created_after:
            params["created"] = {"gte": int(created_after.timestamp())}

        charges = stripe.Charge.list(**params)
        return [StripePayment.from_charge(c) for c in charges.data]

    # ─────────────────────────────────────────────────────────
    # SUBSCRIPTIONS
    # ─────────────────────────────────────────────────────────

    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeSubscription:
        """Create a subscription for a customer."""
        sub = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            metadata=metadata or {},
        )
        logger.info(f"Created subscription {sub.id} for customer {customer_id}")
        return StripeSubscription.from_stripe(sub)

    def get_subscription(self, subscription_id: str) -> Optional[StripeSubscription]:
        """Get subscription by ID."""
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            return StripeSubscription.from_stripe(sub)
        except stripe.error.InvalidRequestError:
            return None

    def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> StripeSubscription:
        """Cancel a subscription."""
        if at_period_end:
            sub = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
        else:
            sub = stripe.Subscription.delete(subscription_id)
        logger.info(f"Cancelled subscription {subscription_id} (at_period_end={at_period_end})")
        return StripeSubscription.from_stripe(sub)

    def list_subscriptions(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[StripeSubscription]:
        """List subscriptions with optional filters."""
        params = {"limit": limit}
        if customer_id:
            params["customer"] = customer_id
        if status:
            params["status"] = status

        subs = stripe.Subscription.list(**params)
        return [StripeSubscription.from_stripe(s) for s in subs.data]

    def get_customer_subscriptions(self, customer_id: str) -> List[StripeSubscription]:
        """Get all active subscriptions for a customer."""
        return self.list_subscriptions(customer_id=customer_id, status="active")

    # ─────────────────────────────────────────────────────────
    # WEBHOOKS
    # ─────────────────────────────────────────────────────────

    def construct_webhook_event(self, payload: bytes, signature: str) -> stripe.Event:
        """Verify and construct webhook event."""
        if not self.config.webhook_secret:
            raise ValueError("Webhook secret not configured")

        return stripe.Webhook.construct_event(
            payload,
            signature,
            self.config.webhook_secret,
        )

    def handle_webhook_event(self, event: stripe.Event) -> Dict[str, Any]:
        """
        Process webhook event and return relevant data.

        Returns dict with event type and parsed data.
        """
        event_type = event.type
        data = event.data.object

        result = {"event_type": event_type, "handled": True}

        if event_type == "checkout.session.completed":
            result["checkout_session_id"] = data.id
            result["customer_id"] = data.customer
            result["mode"] = data.mode
            result["payment_status"] = data.payment_status
            result["metadata"] = dict(data.metadata or {})

        elif event_type == "payment_intent.succeeded":
            result["payment"] = StripePayment.from_payment_intent(data)

        elif event_type == "customer.subscription.created":
            result["subscription"] = StripeSubscription.from_stripe(data)

        elif event_type == "customer.subscription.updated":
            result["subscription"] = StripeSubscription.from_stripe(data)

        elif event_type == "customer.subscription.deleted":
            result["subscription_id"] = data.id
            result["customer_id"] = data.customer

        elif event_type == "invoice.paid":
            result["invoice_id"] = data.id
            result["customer_id"] = data.customer
            result["amount_paid"] = data.amount_paid
            result["subscription_id"] = data.subscription

        elif event_type == "invoice.payment_failed":
            result["invoice_id"] = data.id
            result["customer_id"] = data.customer
            result["subscription_id"] = data.subscription

        else:
            result["handled"] = False

        return result
