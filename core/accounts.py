"""
Multi-account Square API client.

Provides unified access to multiple Square accounts (PA, TFC, FWM).
"""

import requests
from typing import Optional, List, Dict, Any, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from .config import AccountConfig, Config

logger = logging.getLogger(__name__)


@dataclass
class Payment:
    """Normalized payment record."""
    id: str
    account_code: str
    amount_cents: int
    currency: str
    status: str
    created_at: datetime
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    raw: Dict[str, Any] = None


@dataclass
class Invoice:
    """Normalized invoice record."""
    id: str
    account_code: str
    customer_id: Optional[str]
    amount_cents: int
    currency: str
    status: str
    due_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    raw: Dict[str, Any] = None


@dataclass
class Customer:
    """Normalized customer record."""
    id: str
    account_code: str
    given_name: Optional[str]
    family_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    created_at: Optional[datetime] = None
    raw: Dict[str, Any] = None

    @property
    def full_name(self) -> str:
        parts = [self.given_name or "", self.family_name or ""]
        return " ".join(p for p in parts if p).strip() or "Unknown"


@dataclass
class Booking:
    """Normalized booking/appointment record."""
    id: str
    account_code: str
    customer_id: Optional[str]
    start_at: datetime
    end_at: Optional[datetime]
    status: str  # PENDING, ACCEPTED, CANCELLED_BY_CUSTOMER, etc.
    location_id: Optional[str] = None
    staff_member_id: Optional[str] = None
    service_name: Optional[str] = None
    is_recurring: bool = False
    recurring_booking_id: Optional[str] = None
    is_tandem: bool = False
    raw: Dict[str, Any] = None

    @property
    def is_completed(self) -> bool:
        """Check if booking is confirmed and checked out."""
        return self.status in ("ACCEPTED", "CHECKED_OUT", "COMPLETED")

    @property
    def date(self) -> str:
        """Return date string for tandem detection."""
        return self.start_at.strftime("%Y-%m-%d")

    @property
    def time(self) -> str:
        """Return time string."""
        return self.start_at.strftime("%H:%M")


@dataclass
class Order:
    """Normalized order record."""
    id: str
    account_code: str
    customer_id: Optional[str]
    total_cents: int
    currency: str
    status: str
    created_at: datetime
    line_items: List[Dict[str, Any]] = None
    raw: Dict[str, Any] = None


class SquareClient:
    """Client for a single Square account."""

    def __init__(self, account: AccountConfig, api_version: str = "2025-06-16"):
        self.account = account
        self.api_version = api_version
        self._cached_location_id: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {account.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Square-Version": api_version,
        })

    def _parse_payment(self, p: Dict) -> Payment:
        """Parse a raw Square payment dict into a Payment dataclass."""
        return Payment(
            id=p["id"],
            account_code=self.account.code,
            amount_cents=p.get("amount_money", {}).get("amount", 0),
            currency=p.get("amount_money", {}).get("currency", "USD"),
            status=p.get("status", "UNKNOWN"),
            created_at=datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")),
            customer_id=p.get("customer_id"),
            order_id=p.get("order_id"),
            raw=p,
        )

    def _parse_customer(self, c: Dict) -> Customer:
        """Parse a raw Square customer dict into a Customer dataclass."""
        return Customer(
            id=c["id"],
            account_code=self.account.code,
            given_name=c.get("given_name"),
            family_name=c.get("family_name"),
            email=c.get("email_address"),
            phone=c.get("phone_number"),
            created_at=datetime.fromisoformat(c["created_at"].replace("Z", "+00:00")) if c.get("created_at") else None,
            raw=c,
        )

    def _get_location_id(self) -> Optional[str]:
        """Get location ID, with caching."""
        if self.account.location_id:
            return self.account.location_id
        if self._cached_location_id:
            return self._cached_location_id
        locations = self._get("/v2/locations").get("locations", [])
        if locations:
            self._cached_location_id = locations[0]["id"]
        return self._cached_location_id

    @property
    def base_url(self) -> str:
        return self.account.base_url

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request to Square API."""
        url = f"{self.base_url}{endpoint}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, json: Dict = None) -> Dict:
        """Make POST request to Square API."""
        url = f"{self.base_url}{endpoint}"
        resp = self.session.post(url, json=json, timeout=30)
        resp.raise_for_status()
        return resp.json()

    # ─────────────────────────────────────────────────────────────
    # PAYMENTS
    # ─────────────────────────────────────────────────────────────

    def list_payments(
        self,
        begin_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
        cursor: str = None,
    ) -> tuple[List[Payment], Optional[str]]:
        """List payments with optional date filtering."""
        params = {"limit": limit}
        if begin_time:
            params["begin_time"] = begin_time.isoformat() + "Z"
        if end_time:
            params["end_time"] = end_time.isoformat() + "Z"
        if cursor:
            params["cursor"] = cursor

        data = self._get("/v2/payments", params)
        payments = [self._parse_payment(p) for p in data.get("payments", [])]
        return payments, data.get("cursor")

    def get_all_payments(
        self,
        begin_time: datetime = None,
        end_time: datetime = None,
    ) -> Iterator[Payment]:
        """Iterate through all payments with pagination."""
        cursor = None
        while True:
            payments, cursor = self.list_payments(
                begin_time=begin_time,
                end_time=end_time,
                cursor=cursor,
            )
            yield from payments
            if not cursor:
                break

    def get_last_payment_for_customer(self, customer_id: str) -> Optional[Payment]:
        """Get most recent payment for a customer."""
        params = {"customer_id": customer_id, "sort_order": "DESC", "limit": 1}
        data = self._get("/v2/payments", params)
        payments = data.get("payments", [])
        if not payments:
            return None
        return self._parse_payment(payments[0])

    # ─────────────────────────────────────────────────────────────
    # INVOICES
    # ─────────────────────────────────────────────────────────────

    def list_invoices(self, limit: int = 100, cursor: str = None) -> tuple[List[Invoice], Optional[str]]:
        """List all invoices."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        location_id = self._get_location_id()
        if not location_id:
            logger.warning(f"No location_id for account {self.account.code}, skipping invoices")
            return [], None

        params["location_id"] = location_id
        data = self._get("/v2/invoices", params)
        invoices = []

        for inv in data.get("invoices", []):
            invoices.append(Invoice(
                id=inv["id"],
                account_code=self.account.code,
                customer_id=inv.get("primary_recipient", {}).get("customer_id"),
                amount_cents=inv.get("payment_requests", [{}])[0].get("computed_amount_money", {}).get("amount", 0),
                currency=inv.get("payment_requests", [{}])[0].get("computed_amount_money", {}).get("currency", "USD"),
                status=inv.get("status", "UNKNOWN"),
                due_date=datetime.fromisoformat(inv["payment_requests"][0]["due_date"]) if inv.get("payment_requests") and inv["payment_requests"][0].get("due_date") else None,
                created_at=datetime.fromisoformat(inv["created_at"].replace("Z", "+00:00")) if inv.get("created_at") else None,
                raw=inv,
            ))

        return invoices, data.get("cursor")

    # ─────────────────────────────────────────────────────────────
    # CUSTOMERS
    # ─────────────────────────────────────────────────────────────

    def list_customers(self, limit: int = 100, cursor: str = None) -> tuple[List[Customer], Optional[str]]:
        """List all customers."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        data = self._get("/v2/customers", params)
        customers = [self._parse_customer(c) for c in data.get("customers", [])]
        return customers, data.get("cursor")

    def get_all_customers(self) -> Iterator[Customer]:
        """Iterate through all customers with pagination."""
        cursor = None
        while True:
            customers, cursor = self.list_customers(cursor=cursor)
            yield from customers
            if not cursor:
                break

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        """Get a single customer by ID."""
        try:
            data = self._get(f"/v2/customers/{customer_id}")
            c = data.get("customer")
            if not c:
                return None
            return self._parse_customer(c)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    # ─────────────────────────────────────────────────────────────
    # BOOKINGS / APPOINTMENTS
    # ─────────────────────────────────────────────────────────────

    def list_bookings(
        self,
        start_at_min: datetime = None,
        start_at_max: datetime = None,
        limit: int = 100,
        cursor: str = None,
    ) -> tuple[List[Booking], Optional[str]]:
        """List all bookings/appointments."""
        params = {"limit": limit}
        if start_at_min:
            params["start_at_min"] = start_at_min.isoformat() + "Z"
        if start_at_max:
            params["start_at_max"] = start_at_max.isoformat() + "Z"
        if cursor:
            params["cursor"] = cursor

        try:
            data = self._get("/v2/bookings", params)
        except requests.HTTPError as e:
            # Bookings API may not be available on all accounts
            if e.response.status_code in (404, 403):
                logger.warning(f"Bookings not available for account {self.account.code}")
                return [], None
            raise

        bookings = []
        for b in data.get("bookings", []):
            bookings.append(Booking(
                id=b["id"],
                account_code=self.account.code,
                customer_id=b.get("customer_id"),
                start_at=datetime.fromisoformat(b["start_at"].replace("Z", "+00:00")),
                end_at=datetime.fromisoformat(b["end_at"].replace("Z", "+00:00")) if b.get("end_at") else None,
                status=b.get("status", "UNKNOWN"),
                location_id=b.get("location_id"),
                staff_member_id=b.get("team_member_id"),
                is_recurring=b.get("transition_time_minutes") is not None or b.get("appointment_segments", [{}])[0].get("intermission_minutes") is not None,
                recurring_booking_id=b.get("source", {}).get("name"),
                raw=b,
            ))

        return bookings, data.get("cursor")

    def get_all_bookings(
        self,
        start_at_min: datetime = None,
        start_at_max: datetime = None,
    ) -> Iterator[Booking]:
        """Iterate through all bookings with pagination."""
        cursor = None
        while True:
            bookings, cursor = self.list_bookings(
                start_at_min=start_at_min,
                start_at_max=start_at_max,
                cursor=cursor,
            )
            yield from bookings
            if not cursor:
                break

    # ─────────────────────────────────────────────────────────────
    # ORDERS
    # ─────────────────────────────────────────────────────────────

    def search_orders(
        self,
        customer_id: str = None,
        location_ids: List[str] = None,
        limit: int = 100,
        cursor: str = None,
    ) -> tuple[List[Order], Optional[str]]:
        """Search orders with filters."""
        payload = {"limit": limit}

        if location_ids:
            payload["location_ids"] = location_ids
        elif self.account.location_id:
            payload["location_ids"] = [self.account.location_id]

        if customer_id:
            payload["query"] = {
                "filter": {
                    "customer_filter": {
                        "customer_ids": [customer_id]
                    }
                }
            }

        if cursor:
            payload["cursor"] = cursor

        data = self._post("/v2/orders/search", payload)
        orders = []

        for o in data.get("orders", []):
            orders.append(Order(
                id=o["id"],
                account_code=self.account.code,
                customer_id=o.get("customer_id"),
                total_cents=o.get("total_money", {}).get("amount", 0),
                currency=o.get("total_money", {}).get("currency", "USD"),
                status=o.get("state", "UNKNOWN"),
                created_at=datetime.fromisoformat(o["created_at"].replace("Z", "+00:00")),
                line_items=o.get("line_items", []),
                raw=o,
            ))

        return orders, data.get("cursor")

    def count_session_purchases(self, customer_id: str, session_item_name: str = "One-on-One 60") -> int:
        """
        Count how many sessions a customer has purchased.
        Looks for line items matching the session item name.
        """
        total_sessions = 0
        cursor = None

        while True:
            orders, cursor = self.search_orders(customer_id=customer_id, cursor=cursor)

            for order in orders:
                for item in order.line_items or []:
                    name = item.get("name", "")
                    if session_item_name.lower() in name.lower():
                        qty = int(item.get("quantity", "1"))
                        total_sessions += qty

            if not cursor:
                break

        return total_sessions


class MultiAccountClient:
    """
    Client that aggregates data from multiple Square accounts.
    """

    def __init__(self, config: Config):
        self.config = config
        self.clients: Dict[str, SquareClient] = {}

        for code, account in config.accounts.items():
            self.clients[code] = SquareClient(account, config.square_api_version)

    def get_client(self, account_code: str) -> Optional[SquareClient]:
        """Get client for specific account."""
        return self.clients.get(account_code.upper())

    def get_all_payments(
        self,
        begin_time: datetime = None,
        end_time: datetime = None,
        account_codes: List[str] = None,
    ) -> Iterator[Payment]:
        """Get payments from all (or specified) accounts."""
        codes = account_codes or list(self.clients.keys())

        for code in codes:
            client = self.clients.get(code.upper())
            if client:
                logger.info(f"Fetching payments from {code}")
                yield from client.get_all_payments(begin_time, end_time)

    def get_all_customers(self, account_codes: List[str] = None) -> Iterator[Customer]:
        """Get customers from all (or specified) accounts."""
        codes = account_codes or list(self.clients.keys())

        for code in codes:
            client = self.clients.get(code.upper())
            if client:
                logger.info(f"Fetching customers from {code}")
                yield from client.get_all_customers()

    def get_all_bookings(
        self,
        start_at_min: datetime = None,
        start_at_max: datetime = None,
        account_codes: List[str] = None,
    ) -> Iterator[Booking]:
        """Get bookings from all (or specified) accounts."""
        codes = account_codes or list(self.clients.keys())

        for code in codes:
            client = self.clients.get(code.upper())
            if client:
                logger.info(f"Fetching bookings from {code}")
                yield from client.get_all_bookings(start_at_min, start_at_max)

    def detect_tandem_appointments(self, bookings: List[Booking], threshold_minutes: int = 15) -> List[Booking]:
        """
        Detect tandem appointments (2+ clients at same time).

        Returns bookings with tandem flag set.
        """
        from collections import defaultdict

        # Group by date
        by_date: Dict[str, List[Booking]] = defaultdict(list)
        for b in bookings:
            by_date[b.date].append(b)

        # Check each date for overlaps
        for date, day_bookings in by_date.items():
            # Sort by start time
            sorted_bookings = sorted(day_bookings, key=lambda x: x.start_at)

            for i, booking in enumerate(sorted_bookings):
                for j in range(i + 1, len(sorted_bookings)):
                    other = sorted_bookings[j]
                    if booking.customer_id == other.customer_id:
                        continue

                    time_diff = abs((booking.start_at - other.start_at).total_seconds() / 60)
                    if time_diff <= threshold_minutes:
                        booking.is_tandem = True
                        other.is_tandem = True

        return bookings
