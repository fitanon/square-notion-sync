"""
Session tracking sync: Purchased vs Used sessions per client.

Dashboard 3: The most complex sync - tracks:
- Sessions purchased (from item sales, e.g., "One-on-One 60")
- Sessions used (from completed/checked-out appointments)
- Sessions remaining (calculated)
- Tandem detection
- Last/Next appointment tracking
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict

from core.config import Config
from core.accounts import Customer, Booking, Payment
from .base import BaseSync, SyncResult

logger = logging.getLogger(__name__)


class SessionsSync(BaseSync):
    """
    Sync client session tracking data to Notion.

    This is the complex dashboard that calculates:
    - Sessions Purchased: Count of session packages bought
    - Sessions Used: Count of completed appointments
    - Sessions Remaining: Purchased - Used
    - Tandem: Whether client has overlapping appointments
    - Status: Active / Low Sessions / Needs Package
    """

    sync_type = "sessions"

    def __init__(self, config: Config):
        super().__init__(config)
        self.sessions_db = config.notion.db_sessions if config.notion else None
        self.clients_db = config.notion.db_clients if config.notion else None
        self.session_item_name = config.sync.session_item_name

    def sync(
        self,
        account_codes: List[str] = None,
        days_back_appointments: int = 365,
        days_forward_appointments: int = 30,
    ) -> SyncResult:
        """
        Sync session tracking data for all clients.

        Args:
            account_codes: Accounts to sync (default: all)
            days_back_appointments: Days of past appointments to count
            days_forward_appointments: Days ahead for next appointment
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

        db_id = self.sessions_db or self.clients_db
        if not db_id:
            result.success = False
            result.errors.append("Sessions/Clients database ID not configured")
            result.complete()
            return result

        self.logger.info(f"Starting sessions sync for accounts: {codes}")

        now = datetime.utcnow()
        appt_start = now - timedelta(days=days_back_appointments)
        appt_end = now + timedelta(days=days_forward_appointments)

        # Process each account
        for code in codes:
            client = self.square.get_client(code)
            if not client:
                continue

            self.logger.info(f"Processing account: {code}")

            try:
                # Get all customers for this account
                customers = list(client.get_all_customers())
                self.logger.info(f"Found {len(customers)} customers in {code}")

                # Get all bookings for this account (for tandem detection and counting)
                all_bookings = list(client.get_all_bookings(
                    start_at_min=appt_start,
                    start_at_max=appt_end,
                ))

                # Detect tandem appointments
                all_bookings = self.square.detect_tandem_appointments(all_bookings)

                # Group bookings by customer
                bookings_by_customer: Dict[str, List[Booking]] = defaultdict(list)
                for booking in all_bookings:
                    if booking.customer_id:
                        bookings_by_customer[booking.customer_id].append(booking)

                # Process each customer
                for customer in customers:
                    try:
                        sync_data = self._calculate_session_data(
                            client, customer, bookings_by_customer, now
                        )

                        self._sync_customer_sessions(db_id, customer, sync_data)
                        result.records_updated += 1

                    except Exception as e:
                        self.logger.error(f"Failed to sync customer {customer.id}: {e}")
                        result.records_failed += 1
                        result.errors.append(f"Customer {customer.id}: {str(e)}")

            except Exception as e:
                self.logger.error(f"Failed to process account {code}: {e}")
                result.errors.append(f"Account {code}: {str(e)}")

        result.success = result.records_failed == 0 and len(result.errors) == 0
        result.complete()

        self.logger.info(
            f"Sessions sync complete: {result.records_updated} updated, "
            f"{result.records_failed} failed"
        )

        return result

    def _calculate_session_data(
        self,
        square_client,
        customer: Customer,
        bookings_by_customer: Dict[str, List[Booking]],
        now: datetime,
    ) -> Dict:
        """Calculate all session tracking data for a customer."""

        # Get sessions purchased (from orders)
        sessions_purchased = square_client.count_session_purchases(
            customer.id, self.session_item_name
        )

        # Get bookings for this customer
        customer_bookings = bookings_by_customer.get(customer.id, [])

        # Count completed sessions
        sessions_used = sum(
            1 for b in customer_bookings
            if b.is_completed and b.start_at < now
        )

        # Check for tandem
        has_tandem = any(
            b.raw and b.raw.get("tandem", False)
            for b in customer_bookings
            if b.raw
        )

        # Find last completed appointment
        past_bookings = [b for b in customer_bookings if b.start_at < now and b.is_completed]
        last_appointment = max(past_bookings, key=lambda b: b.start_at) if past_bookings else None

        # Find next upcoming appointment
        future_bookings = [b for b in customer_bookings if b.start_at >= now]
        next_appointment = min(future_bookings, key=lambda b: b.start_at) if future_bookings else None

        # Get last payment
        last_payment = square_client.get_last_payment_for_customer(customer.id)

        return {
            "sessions_purchased": sessions_purchased,
            "sessions_used": sessions_used,
            "sessions_remaining": sessions_purchased - sessions_used,
            "has_tandem": has_tandem,
            "last_appointment": last_appointment,
            "next_appointment": next_appointment,
            "last_payment": last_payment,
        }

    def _sync_customer_sessions(
        self,
        database_id: str,
        customer: Customer,
        sync_data: Dict,
    ):
        """Sync calculated session data to Notion."""

        self.notion.sync_client_session(
            database_id,
            customer,
            sessions_purchased=sync_data["sessions_purchased"],
            sessions_used=sync_data["sessions_used"],
            last_payment=sync_data["last_payment"],
            last_appointment=sync_data["last_appointment"],
            next_appointment=sync_data["next_appointment"],
            tandem=sync_data["has_tandem"],
        )

    def get_low_session_clients(
        self,
        account_codes: List[str] = None,
        threshold: int = 2,
    ) -> List[Dict]:
        """
        Get clients with low remaining sessions (for trainer view).

        Args:
            threshold: Clients with <= this many sessions remaining
        """
        codes = self.get_account_codes(account_codes)
        low_session_clients = []

        for code in codes:
            client = self.square.get_client(code)
            if not client:
                continue

            for customer in client.get_all_customers():
                sessions_purchased = client.count_session_purchases(
                    customer.id, self.session_item_name
                )

                # Count used sessions (simplified - just completed bookings)
                bookings = list(client.get_all_bookings())
                customer_bookings = [b for b in bookings if b.customer_id == customer.id]
                sessions_used = sum(1 for b in customer_bookings if b.is_completed)

                remaining = sessions_purchased - sessions_used

                if remaining <= threshold:
                    low_session_clients.append({
                        "customer_id": customer.id,
                        "name": customer.full_name,
                        "email": customer.email,
                        "phone": customer.phone,
                        "account": code,
                        "sessions_purchased": sessions_purchased,
                        "sessions_used": sessions_used,
                        "sessions_remaining": remaining,
                    })

        return sorted(low_session_clients, key=lambda x: x["sessions_remaining"])
