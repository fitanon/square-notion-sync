"""
Stripe payment sync to Notion.

Syncs Stripe payments and subscriptions to Notion databases.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from core.config import Config
from core.stripe_client import StripeClient, StripePayment, StripeSubscription, StripeCustomer
from core.notion import NotionClient
from .base import BaseSync, SyncResult

logger = logging.getLogger(__name__)

# Status constants
STATUS_ACTIVE = "Active"
STATUS_CANCELLED = "Cancelled"
STATUS_PAST_DUE = "Past Due"
STATUS_SUCCEEDED = "Succeeded"
STATUS_PENDING = "Pending"
STATUS_FAILED = "Failed"


class StripePaymentSync(BaseSync):
    """Sync Stripe payments to Notion."""

    sync_type = "stripe_payments"

    def __init__(self, config: Config):
        # Don't call super().__init__ since it expects Square accounts
        self.config = config
        self.notion = NotionClient(config.notion) if config.notion else None
        self.stripe = StripeClient(config.stripe) if config.stripe else None
        self.logger = logging.getLogger(f"sync.{self.sync_type}")

    def sync(self, account_codes: List[str] = None, days_back: int = 30) -> SyncResult:
        """
        Sync Stripe payments from the last N days to Notion.

        Args:
            account_codes: Ignored for Stripe (single account).
            days_back: Number of days to look back for payments.

        Returns:
            SyncResult with details of the operation.
        """
        result = SyncResult(
            success=False,
            sync_type=self.sync_type,
            accounts_synced=["STRIPE"],
        )

        if not self.stripe:
            result.errors.append("Stripe not configured")
            result.complete()
            return result

        if not self.notion:
            result.errors.append("Notion not configured")
            result.complete()
            return result

        try:
            since = datetime.utcnow() - timedelta(days=days_back)
            payments = self.stripe.list_charges(created_after=since)

            self.logger.info(f"Found {len(payments)} payments in last {days_back} days")

            for payment in payments:
                try:
                    self._sync_payment(payment)
                    if payment.status == "succeeded":
                        result.records_created += 1
                    else:
                        result.records_updated += 1
                except Exception:
                    result.records_failed += 1
                    result.errors.append(f"Payment {payment.id}: sync failed")

            result.success = True

        except Exception:
            self.logger.exception("Stripe sync failed")
            result.errors.append("Stripe sync failed")

        result.complete()
        return result

    def _sync_payment(self, payment: StripePayment) -> None:
        """Sync a single payment to Notion."""
        db_id = self.config.notion.db_transactions
        if not db_id:
            raise ValueError("NOTION_DB_TRANSACTIONS not configured")

        # Map status
        status_map = {
            "succeeded": STATUS_SUCCEEDED,
            "pending": STATUS_PENDING,
            "failed": STATUS_FAILED,
        }
        status = status_map.get(payment.status, payment.status.title())

        properties = {
            "Payment ID": self.notion.title(payment.id),
            "Account": self.notion.select("STRIPE"),
            "Amount": self.notion.number(payment.amount_dollars),
            "Currency": self.notion.select(payment.currency),
            "Status": self.notion.select(status),
            "Date": self.notion.date(payment.created_at),
            "Customer ID": self.notion.rich_text(payment.customer_id or ""),
            "Description": self.notion.rich_text(payment.description or ""),
            "Source": self.notion.select("Stripe"),
            "Last Synced": self.notion.date(datetime.utcnow()),
        }

        # Add sessions from metadata if present
        sessions = payment.metadata.get("sessions")
        if sessions:
            properties["Sessions"] = self.notion.number(int(sessions))

        self.notion.upsert_page(
            db_id,
            properties,
            unique_property="Payment ID",
            unique_value=payment.id,
            unique_type="title",
        )


class StripeSubscriptionSync(BaseSync):
    """Sync Stripe subscriptions to Notion."""

    sync_type = "stripe_subscriptions"

    def __init__(self, config: Config):
        self.config = config
        self.notion = NotionClient(config.notion) if config.notion else None
        self.stripe = StripeClient(config.stripe) if config.stripe else None
        self.logger = logging.getLogger(f"sync.{self.sync_type}")

    def sync(self, account_codes: List[str] = None, status_filter: str = None) -> SyncResult:
        """
        Sync Stripe subscriptions to Notion.

        Args:
            account_codes: Ignored for Stripe.
            status_filter: Optional status to filter (e.g., "active").

        Returns:
            SyncResult with details of the operation.
        """
        result = SyncResult(
            success=False,
            sync_type=self.sync_type,
            accounts_synced=["STRIPE"],
        )

        if not self.stripe:
            result.errors.append("Stripe not configured")
            result.complete()
            return result

        if not self.notion:
            result.errors.append("Notion not configured")
            result.complete()
            return result

        try:
            subscriptions = self.stripe.list_subscriptions(status=status_filter)

            self.logger.info(f"Found {len(subscriptions)} subscriptions")

            for sub in subscriptions:
                try:
                    created = self._sync_subscription(sub)
                    if created:
                        result.records_created += 1
                    else:
                        result.records_updated += 1
                except Exception:
                    self.logger.exception(f"Failed to sync subscription {sub.id}")
                    result.records_failed += 1
                    result.errors.append(f"Subscription {sub.id}: sync failed")

            result.success = True

        except Exception:
            self.logger.exception("Subscription sync failed")
            result.errors.append("Subscription sync failed")

        result.complete()
        return result

    def _sync_subscription(self, sub: StripeSubscription) -> bool:
        """Sync a single subscription to Notion. Returns True if created."""
        db_id = self.config.notion.db_sessions
        if not db_id:
            raise ValueError("NOTION_DB_SESSIONS not configured")

        # Map status
        status_map = {
            "active": STATUS_ACTIVE,
            "canceled": STATUS_CANCELLED,
            "past_due": STATUS_PAST_DUE,
            "trialing": STATUS_ACTIVE,
            "unpaid": STATUS_PAST_DUE,
        }
        status = status_map.get(sub.status, sub.status.title())

        # Get customer info
        customer = self.stripe.get_customer(sub.customer_id)
        customer_name = customer.name if customer else "Unknown"
        customer_email = customer.email if customer else None

        # Get price info
        price = self.stripe.get_price(sub.price_id)
        tier_name = price.name if price else "Monthly"

        properties = {
            "Subscription ID": self.notion.title(sub.id),
            "Customer ID": self.notion.rich_text(sub.customer_id),
            "Customer Name": self.notion.rich_text(customer_name),
            "Status": self.notion.select(status),
            "Plan": self.notion.select(tier_name),
            "Period Start": self.notion.date(sub.current_period_start),
            "Period End": self.notion.date(sub.current_period_end),
            "Cancel at End": self.notion.checkbox(sub.cancel_at_period_end),
            "Source": self.notion.select("Stripe"),
            "Last Synced": self.notion.date(datetime.utcnow()),
        }

        if customer_email:
            properties["Email"] = self.notion.email(customer_email)

        _, created = self.notion.upsert_page(
            db_id,
            properties,
            unique_property="Subscription ID",
            unique_value=sub.id,
            unique_type="title",
        )
        return created


def sync_stripe_all(config: Config, days_back: int = 30) -> Dict[str, SyncResult]:
    """Run all Stripe syncs and return results."""
    results = {}

    payment_sync = StripePaymentSync(config)
    results["payments"] = payment_sync.sync(days_back=days_back)

    subscription_sync = StripeSubscriptionSync(config)
    results["subscriptions"] = subscription_sync.sync()

    return results
