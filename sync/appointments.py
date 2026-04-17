"""
Appointments sync: Bookings, Calendar, and Recurring events.

Dashboard 2: Syncs appointment/booking data from all configured
Square accounts to Notion, with special handling for recurring events.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict

from core.config import Config
from core.accounts import Booking
from .base import BaseSync, SyncResult

logger = logging.getLogger(__name__)


class AppointmentsSync(BaseSync):
    """
    Sync appointments/bookings to Notion.

    Handles:
    - Regular one-time appointments
    - Recurring appointments (each occurrence as separate record)
    - Tandem detection (multiple clients at same time)
    - Status tracking (pending, confirmed, checked out)
    """

    sync_type = "appointments"

    def __init__(self, config: Config):
        super().__init__(config)
        self.appointments_db = config.notion.db_appointments if config.notion else None

    def sync(
        self,
        account_codes: List[str] = None,
        days_back: int = 30,
        days_forward: int = 30,
    ) -> SyncResult:
        """
        Sync appointments from Square to Notion.

        Args:
            account_codes: Accounts to sync (default: all)
            days_back: Days of past appointments to sync
            days_forward: Days of future appointments to sync
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

        if not self.appointments_db:
            result.success = False
            result.errors.append("Appointments database ID not configured")
            result.complete()
            return result

        now = datetime.utcnow()
        start_at_min = now - timedelta(days=days_back)
        start_at_max = now + timedelta(days=days_forward)

        self.logger.info(f"Starting appointments sync for accounts: {codes}")
        self.logger.info(f"Date range: {start_at_min.date()} to {start_at_max.date()}")

        # Collect all bookings first (for tandem detection)
        all_bookings: List[Booking] = []

        for booking in self.square.get_all_bookings(
            start_at_min=start_at_min,
            start_at_max=start_at_max,
            account_codes=codes,
        ):
            all_bookings.append(booking)

        self.logger.info(f"Found {len(all_bookings)} bookings to sync")

        # Detect tandem appointments
        all_bookings = self.square.detect_tandem_appointments(all_bookings)

        # Sync each booking to Notion
        for booking in all_bookings:
            try:
                _, was_created = self.notion.sync_booking(self.appointments_db, booking)

                if was_created:
                    result.records_created += 1
                else:
                    result.records_updated += 1

            except Exception:
                self.logger.exception(f"Failed to sync booking {booking.id}")
                result.records_failed += 1
                result.errors.append(f"Booking {booking.id}: sync failed")

        result.success = result.records_failed == 0 and len(result.errors) == 0
        result.complete()

        self.logger.info(
            f"Appointments sync complete: {result.records_created} created, "
            f"{result.records_updated} updated, {result.records_failed} failed"
        )

        return result

    def get_tandem_summary(
        self,
        account_codes: List[str] = None,
        days_back: int = 7,
        days_forward: int = 14,
    ) -> Dict[str, List[Dict]]:
        """
        Get a summary of tandem appointments.

        Returns dict mapping dates to list of tandem appointment groups.
        """
        codes = self.get_account_codes(account_codes)

        now = datetime.utcnow()
        start_at_min = now - timedelta(days=days_back)
        start_at_max = now + timedelta(days=days_forward)

        all_bookings: List[Booking] = list(
            self.square.get_all_bookings(
                start_at_min=start_at_min,
                start_at_max=start_at_max,
                account_codes=codes,
            )
        )

        all_bookings = self.square.detect_tandem_appointments(all_bookings)

        tandem_by_date: Dict[str, List[Dict]] = defaultdict(list)

        for booking in all_bookings:
            if booking.is_tandem:
                tandem_by_date[booking.date].append({
                    "booking_id": booking.id,
                    "customer_id": booking.customer_id,
                    "time": booking.time,
                    "status": booking.status,
                    "account": booking.account_code,
                })

        return dict(tandem_by_date)
