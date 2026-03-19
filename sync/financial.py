"""
Financial sync: Transactions, Invoices, and Sales data.

Dashboard 1: Syncs payment transactions, invoices, and order data
from all configured Square accounts to Notion.
"""

import logging
from datetime import datetime, timedelta
from typing import List

from core.config import Config
from .base import BaseSync, SyncResult

logger = logging.getLogger(__name__)


class FinancialSync(BaseSync):
    """
    Sync financial data (transactions, invoices, sales) to Notion.

    Handles:
    - Payment transactions with amount, status, date
    - Invoices with due dates and status
    - Order/sales data with line items
    """

    sync_type = "financial"

    def __init__(self, config: Config):
        super().__init__(config)
        self.transactions_db = config.notion.db_transactions if config.notion else None
        self.invoices_db = config.notion.db_invoices if config.notion else None

    def sync(
        self,
        account_codes: List[str] = None,
        days_back: int = 30,
    ) -> SyncResult:
        """
        Sync financial data from Square to Notion.

        Args:
            account_codes: Accounts to sync (default: all)
            days_back: How many days of history to sync (default: 30)
        """
        codes = self.get_account_codes(account_codes)
        result = SyncResult(
            success=True,
            sync_type=self.sync_type,
            accounts_synced=codes,
        )

        if not self.validate_notion():
            result.success = False
            result.errors.append("Notion not configured")
            result.complete()
            return result

        end_time = datetime.utcnow()
        begin_time = end_time - timedelta(days=days_back)

        self.logger.info(f"Starting financial sync for accounts: {codes}")
        self.logger.info(f"Date range: {begin_time.date()} to {end_time.date()}")

        if self.transactions_db:
            result.merge_stats(self._sync_transactions(codes, begin_time, end_time))

        if self.invoices_db:
            result.merge_stats(self._sync_invoices(codes))

        result.success = result.records_failed == 0 and len(result.errors) == 0
        result.complete()

        self.logger.info(
            f"Financial sync complete: {result.records_created} created, "
            f"{result.records_updated} updated, {result.records_failed} failed"
        )

        return result

    def _sync_transactions(
        self,
        account_codes: List[str],
        begin_time: datetime,
        end_time: datetime,
    ) -> dict:
        """Sync payment transactions to Notion."""
        stats = {"created": 0, "updated": 0, "failed": 0, "errors": []}

        for payment in self.square.get_all_payments(
            begin_time=begin_time,
            end_time=end_time,
            account_codes=account_codes,
        ):
            try:
                _, was_created = self.notion.sync_payment(self.transactions_db, payment)

                if was_created:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1

            except Exception as e:
                self.logger.error(f"Failed to sync payment {payment.id}: {e}")
                stats["failed"] += 1
                stats["errors"].append(f"Payment {payment.id}: {str(e)}")

        return stats

    def _sync_invoices(self, account_codes: List[str]) -> dict:
        """Sync invoices to Notion."""
        stats = {"created": 0, "updated": 0, "failed": 0, "errors": []}

        for code in account_codes:
            client = self.square.get_client(code)
            if not client:
                continue

            try:
                invoices, _ = client.list_invoices()

                for invoice in invoices:
                    try:
                        _, was_created = self.notion.sync_invoice(self.invoices_db, invoice)

                        if was_created:
                            stats["created"] += 1
                        else:
                            stats["updated"] += 1

                    except Exception as e:
                        self.logger.error(f"Failed to sync invoice {invoice.id}: {e}")
                        stats["failed"] += 1
                        stats["errors"].append(f"Invoice {invoice.id}: {str(e)}")

            except Exception as e:
                self.logger.error(f"Failed to fetch invoices for {code}: {e}")
                stats["errors"].append(f"Invoices for {code}: {str(e)}")

        return stats
