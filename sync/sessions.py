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
from core.accounts import Customer, Booking, Payment, Order
from .base import BaseSync, SyncResult

logger = logging.getLogger(__name__)

# Session status constants
STATUS_ACTIVE = "Active"
STATUS_LOW_SESSIONS = "Low Sessions"
STATUS_NEEDS_PACKAGE = "Needs Package"


def determine_status(sessions_remaining: int) -> str:
    """Determine client status based on remaining sessions."""
    if sessions_remaining <= 0:
        return STATUS_NEEDS_PACKAGE
    elif sessions_remaining <= 2:
        return STATUS_LOW_SESSIONS
    return STATUS_ACTIVE


class SessionsSync(BaseSync):
    """
    Sync client session tracking data to Notion.

    Calculates:
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
        """Sync session tracking data for all clients."""
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

        for code in codes:
            client = self.square.get_client(code)
            if not client:
                continue

            self.logger.info(f"Processing account: {code}")

            try:
                # Bulk fetch all data upfront (avoids N+1)
                customers = list(client.get_all_customers())
                self.logger.info(f"Found {len(customers)} customers in {code}")

                all_bookings = list(client.get_all_bookings(
                    start_at_min=appt_start,
                    start_at_max=appt_end,
                ))
                all_bookings = self.square.detect_tandem_appointments(all_bookings)

                # Bulk fetch all orders to count sessions (avoids per-customer N+1)
                all_orders = []
                cursor = None
                while True:
                    orders, cursor = client.search_orders(cursor=cursor)
                    all_orders.extend(orders)
                    if not cursor:
                        break

                # Bulk fetch recent payments (avoids per-customer N+1)
                all_payments = list(client.get_all_payments())

                # Group by customer
                bookings_by_customer: Dict[str, List[Booking]] = defaultdict(list)
                for booking in all_bookings:
                    if booking.customer_id:
                        bookings_by_customer[booking.customer_id].append(booking)

                orders_by_customer: Dict[str, List[Order]] = defaultdict(list)
                for order in all_orders:
                    if order.customer_id:
                        orders_by_customer[order.customer_id].append(order)

                payments_by_customer: Dict[str, List[Payment]] = defaultdict(list)
                for payment in all_payments:
                    if payment.customer_id:
                        payments_by_customer[payment.customer_id].append(payment)

                # Process each customer using pre-fetched data
                for customer in customers:
                    try:
                        sync_data = self._calculate_session_data(
                            customer, bookings_by_customer,
                            orders_by_customer, payments_by_customer, now
                        )

                        _, was_created = self.notion.sync_client_session(
                            db_id, customer, sync_data
                        )
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
        customer: Customer,
        bookings_by_customer: Dict[str, List[Booking]],
        orders_by_customer: Dict[str, List[Order]],
        payments_by_customer: Dict[str, List[Payment]],
        now: datetime,
    ) -> Dict:
        """Calculate all session tracking data for a customer using pre-fetched data."""

        # Count sessions purchased from orders
        sessions_purchased = 0
        for order in orders_by_customer.get(customer.id, []):
            for item in order.line_items or []:
                name = item.get("name", "")
                if self.session_item_name.lower() in name.lower():
                    sessions_purchased += int(item.get("quantity", "1"))

        # Count completed sessions from bookings
        customer_bookings = bookings_by_customer.get(customer.id, [])
        sessions_used = sum(
            1 for b in customer_bookings
            if b.is_completed and b.start_at < now
        )

        sessions_remaining = sessions_purchased - sessions_used

        # Check for tandem
        has_tandem = any(b.is_tandem for b in customer_bookings)

        # Find last completed appointment
        past_bookings = [b for b in customer_bookings if b.start_at < now and b.is_completed]
        last_appointment = max(past_bookings, key=lambda b: b.start_at) if past_bookings else None

        # Find next upcoming appointment
        future_bookings = [b for b in customer_bookings if b.start_at >= now]
        next_appointment = min(future_bookings, key=lambda b: b.start_at) if future_bookings else None

        # Get last payment from pre-fetched data
        customer_payments = payments_by_customer.get(customer.id, [])
        last_payment = max(customer_payments, key=lambda p: p.created_at) if customer_payments else None

        return {
            "sessions_purchased": sessions_purchased,
            "sessions_used": sessions_used,
            "sessions_remaining": sessions_remaining,
            "has_tandem": has_tandem,
            "status": determine_status(sessions_remaining),
            "last_appointment": last_appointment,
            "next_appointment": next_appointment,
            "last_payment": last_payment,
        }

    def get_low_session_clients(
        self,
        account_codes: List[str] = None,
        threshold: int = 2,
    ) -> List[Dict]:
        """Get clients with low remaining sessions (for trainer view)."""
        codes = self.get_account_codes(account_codes)
        low_session_clients = []

        now = datetime.utcnow()

        for code in codes:
            client = self.square.get_client(code)
            if not client:
                continue

            # Bulk fetch once per account (NOT per customer)
            customers = list(client.get_all_customers())
            all_bookings = list(client.get_all_bookings())
            all_orders = []
            cursor = None
            while True:
                orders, cursor = client.search_orders(cursor=cursor)
                all_orders.extend(orders)
                if not cursor:
                    break

            # Group by customer
            bookings_by_customer: Dict[str, List[Booking]] = defaultdict(list)
            for b in all_bookings:
                if b.customer_id:
                    bookings_by_customer[b.customer_id].append(b)

            orders_by_customer: Dict[str, List] = defaultdict(list)
            for o in all_orders:
                if o.customer_id:
                    orders_by_customer[o.customer_id].append(o)

            for customer in customers:
                # Count sessions from pre-fetched orders
                sessions_purchased = 0
                for order in orders_by_customer.get(customer.id, []):
                    for item in order.line_items or []:
                        if self.session_item_name.lower() in item.get("name", "").lower():
                            sessions_purchased += int(item.get("quantity", "1"))

                customer_bookings = bookings_by_customer.get(customer.id, [])
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
