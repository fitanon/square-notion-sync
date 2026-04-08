"""
Stripe → Notion sync module.

Syncs Stripe payment data into the Notion sessions/clients database.
"""

import logging
from typing import List, Optional

from .base import BaseSync, SyncResult
from core.stripe_client import StripeClient

logger = logging.getLogger(__name__)


class StripePaymentsSync(BaseSync):
    """Sync Stripe payments to Notion."""

    sync_type = "stripe_payments"

    def __init__(self, config):
        super().__init__(config)
        self.stripe = StripeClient(config)

    def sync(self, account_codes: List[str] = None, limit: int = 100) -> SyncResult:
        """
        Sync recent Stripe payments to Notion.

        Pulls completed checkout sessions from Stripe and creates/updates
        records in the Notion sessions database.
        """
        result = SyncResult(
            success=False,
            sync_type=self.sync_type,
            accounts_synced=["stripe"],
        )

        if not self.stripe.is_configured:
            result.errors.append("Stripe not configured (missing STRIPE_SECRET_KEY)")
            result.complete()
            return result

        if not self.validate_notion():
            result.errors.append("Notion not configured")
            result.complete()
            return result

        try:
            payments = self.stripe.list_recent_payments(limit=limit)
            self.logger.info(f"Found {len(payments)} Stripe payments to sync")

            for payment in payments:
                try:
                    self._sync_payment(payment)
                    result.records_created += 1
                except Exception as e:
                    self.logger.error(f"Failed to sync payment {payment.id}: {e}")
                    result.records_failed += 1
                    result.errors.append(f"Payment {payment.id}: {str(e)}")

            result.success = result.records_failed == 0

        except Exception as e:
            self.logger.error(f"Stripe sync failed: {e}")
            result.errors.append(str(e))

        result.complete()
        return result

    def _sync_payment(self, payment):
        """Sync a single Stripe payment to Notion."""
        if not self.notion:
            return

        db_id = self.config.notion.db_sessions
        if not db_id:
            raise ValueError("NOTION_DB_SESSIONS not configured")

        properties = {
            "Name": {"title": [{"text": {"content": payment.customer_email or "Unknown"}}]},
            "Source": {"select": {"name": "Stripe"}},
            "Payment ID": {"rich_text": [{"text": {"content": payment.id}}]},
            "Amount": {"number": payment.amount_cents / 100},
            "Tier": {"select": {"name": payment.tier or "single"}},
            "Sessions Purchased": {"number": payment.sessions_purchased},
            "Status": {"select": {"name": payment.status}},
            "Date": {"date": {"start": payment.created_at.isoformat()}},
        }

        if payment.subscription_id:
            properties["Subscription"] = {
                "rich_text": [{"text": {"content": payment.subscription_id}}]
            }

        # Check if record exists (by payment ID)
        pages, _ = self.notion.query_database(
            db_id,
            filter_={
                "property": "Payment ID",
                "rich_text": {"equals": payment.id},
            },
        )

        if pages:
            self.notion.update_page(pages[0].id, properties)
            self.logger.debug(f"Updated payment {payment.id}")
        else:
            self.notion.create_page(db_id, properties)
            self.logger.debug(f"Created payment {payment.id}")
