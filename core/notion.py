"""
Notion API client for syncing Square data.

Handles upsert logic, schema mapping, and view management.
"""

import requests
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .config import NotionConfig
from .accounts import Payment, Invoice, Customer, Booking, Order

logger = logging.getLogger(__name__)

API_BASE = "https://api.notion.com/v1"


@dataclass
class NotionPage:
    """Represents a Notion page/row."""
    id: str
    properties: Dict[str, Any]
    created_time: datetime
    last_edited_time: datetime


class NotionClient:
    """Client for Notion API operations."""

    def __init__(self, config: NotionConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Notion-Version": config.version,
            "Content-Type": "application/json",
        })

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request to Notion API."""
        url = f"{API_BASE}{endpoint}"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, json_data: Dict = None) -> Dict:
        """Make POST request to Notion API."""
        url = f"{API_BASE}{endpoint}"
        resp = self.session.post(url, json=json_data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, endpoint: str, json_data: Dict = None) -> Dict:
        """Make PATCH request to Notion API."""
        url = f"{API_BASE}{endpoint}"
        resp = self.session.patch(url, json=json_data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    # ─────────────────────────────────────────────────────────────
    # DATABASE OPERATIONS
    # ─────────────────────────────────────────────────────────────

    def get_database(self, database_id: str) -> Dict:
        """Get database schema."""
        return self._get(f"/databases/{database_id}")

    def query_database(
        self,
        database_id: str,
        filter_: Dict = None,
        sorts: List[Dict] = None,
        page_size: int = 100,
        start_cursor: str = None,
    ) -> tuple[List[NotionPage], Optional[str]]:
        """Query database with optional filter and sort."""
        payload = {"page_size": page_size}
        if filter_:
            payload["filter"] = filter_
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor

        data = self._post(f"/databases/{database_id}/query", payload)
        pages = []

        for result in data.get("results", []):
            pages.append(NotionPage(
                id=result["id"],
                properties=result.get("properties", {}),
                created_time=datetime.fromisoformat(result["created_time"].replace("Z", "+00:00")),
                last_edited_time=datetime.fromisoformat(result["last_edited_time"].replace("Z", "+00:00")),
            ))

        return pages, data.get("next_cursor")

    def find_page_by_property(
        self,
        database_id: str,
        property_name: str,
        property_value: str,
        property_type: str = "rich_text",
    ) -> Optional[NotionPage]:
        """Find a page by a specific property value."""
        if property_type == "rich_text":
            filter_ = {
                "property": property_name,
                "rich_text": {"equals": property_value}
            }
        elif property_type == "title":
            filter_ = {
                "property": property_name,
                "title": {"equals": property_value}
            }
        elif property_type == "email":
            filter_ = {
                "property": property_name,
                "email": {"equals": property_value}
            }
        else:
            filter_ = {
                "property": property_name,
                property_type: {"equals": property_value}
            }

        pages, _ = self.query_database(database_id, filter_=filter_, page_size=1)
        return pages[0] if pages else None

    # ─────────────────────────────────────────────────────────────
    # PAGE OPERATIONS
    # ─────────────────────────────────────────────────────────────

    def create_page(self, database_id: str, properties: Dict[str, Any]) -> Dict:
        """Create a new page in a database."""
        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        return self._post("/pages", payload)

    def update_page(self, page_id: str, properties: Dict[str, Any]) -> Dict:
        """Update an existing page."""
        return self._patch(f"/pages/{page_id}", {"properties": properties})

    def upsert_page(
        self,
        database_id: str,
        properties: Dict[str, Any],
        unique_property: str,
        unique_value: str,
        unique_type: str = "rich_text",
    ) -> Dict:
        """
        Create or update a page based on a unique property.

        If a page with the unique property value exists, update it.
        Otherwise, create a new page.
        """
        existing = self.find_page_by_property(
            database_id, unique_property, unique_value, unique_type
        )

        if existing:
            logger.debug(f"Updating existing page {existing.id}")
            return self.update_page(existing.id, properties)
        else:
            logger.debug(f"Creating new page with {unique_property}={unique_value}")
            return self.create_page(database_id, properties)

    # ─────────────────────────────────────────────────────────────
    # PROPERTY BUILDERS
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def title(text: str) -> Dict:
        """Build title property."""
        return {"title": [{"text": {"content": text or ""}}]}

    @staticmethod
    def rich_text(text: str) -> Dict:
        """Build rich text property."""
        # Notion has a 2000 char limit per text block
        text = str(text or "")[:2000]
        return {"rich_text": [{"text": {"content": text}}]}

    @staticmethod
    def number(value: float) -> Dict:
        """Build number property."""
        return {"number": value}

    @staticmethod
    def select(option: str) -> Dict:
        """Build select property."""
        return {"select": {"name": option}}

    @staticmethod
    def multi_select(options: List[str]) -> Dict:
        """Build multi-select property."""
        return {"multi_select": [{"name": opt} for opt in options]}

    @staticmethod
    def date(dt: datetime, include_time: bool = True) -> Dict:
        """Build date property."""
        if dt is None:
            return {"date": None}
        if include_time:
            return {"date": {"start": dt.isoformat()}}
        return {"date": {"start": dt.strftime("%Y-%m-%d")}}

    @staticmethod
    def checkbox(checked: bool) -> Dict:
        """Build checkbox property."""
        return {"checkbox": checked}

    @staticmethod
    def email(email: str) -> Dict:
        """Build email property."""
        return {"email": email}

    @staticmethod
    def phone(phone: str) -> Dict:
        """Build phone property."""
        return {"phone_number": phone}

    @staticmethod
    def url(url: str) -> Dict:
        """Build URL property."""
        return {"url": url}

    # ─────────────────────────────────────────────────────────────
    # SYNC HELPERS
    # ─────────────────────────────────────────────────────────────

    def sync_customer(self, database_id: str, customer: Customer) -> Dict:
        """Sync a customer to Notion."""
        properties = {
            "Name": self.title(customer.full_name),
            "Square ID": self.rich_text(customer.id),
            "Account": self.select(customer.account_code),
            "Email": self.email(customer.email) if customer.email else {"email": None},
            "Phone": self.phone(customer.phone) if customer.phone else {"phone_number": None},
            "Last Synced": self.date(datetime.utcnow()),
        }

        return self.upsert_page(
            database_id,
            properties,
            unique_property="Square ID",
            unique_value=customer.id,
        )

    def sync_payment(self, database_id: str, payment: Payment) -> Dict:
        """Sync a payment/transaction to Notion."""
        amount_dollars = payment.amount_cents / 100.0

        properties = {
            "Payment ID": self.title(payment.id),
            "Account": self.select(payment.account_code),
            "Amount": self.number(amount_dollars),
            "Currency": self.select(payment.currency),
            "Status": self.select(payment.status),
            "Date": self.date(payment.created_at),
            "Customer ID": self.rich_text(payment.customer_id or ""),
            "Last Synced": self.date(datetime.utcnow()),
        }

        return self.upsert_page(
            database_id,
            properties,
            unique_property="Payment ID",
            unique_value=payment.id,
            unique_type="title",
        )

    def sync_booking(self, database_id: str, booking: Booking, tandem: bool = False) -> Dict:
        """Sync a booking/appointment to Notion."""
        properties = {
            "Booking ID": self.title(booking.id),
            "Account": self.select(booking.account_code),
            "Customer ID": self.rich_text(booking.customer_id or ""),
            "Date": self.date(booking.start_at, include_time=False),
            "Time": self.rich_text(booking.time),
            "Status": self.select(booking.status),
            "Completed": self.checkbox(booking.is_completed),
            "Tandem": self.checkbox(tandem or booking.raw.get("tandem", False) if booking.raw else False),
            "Recurring": self.checkbox(booking.is_recurring),
            "Last Synced": self.date(datetime.utcnow()),
        }

        return self.upsert_page(
            database_id,
            properties,
            unique_property="Booking ID",
            unique_value=booking.id,
            unique_type="title",
        )

    def sync_client_session(
        self,
        database_id: str,
        customer: Customer,
        sessions_purchased: int,
        sessions_used: int,
        last_payment: Optional[Payment] = None,
        last_appointment: Optional[Booking] = None,
        next_appointment: Optional[Booking] = None,
        tandem: bool = False,
    ) -> Dict:
        """Sync client session tracking data to Notion."""
        sessions_remaining = sessions_purchased - sessions_used

        properties = {
            "Name": self.title(customer.full_name),
            "Square ID": self.rich_text(customer.id),
            "Account": self.select(customer.account_code),
            "Email": self.email(customer.email) if customer.email else {"email": None},
            "Phone": self.phone(customer.phone) if customer.phone else {"phone_number": None},
            "Sessions Purchased": self.number(sessions_purchased),
            "Sessions Used": self.number(sessions_used),
            "Sessions Remaining": self.number(sessions_remaining),
            "Tandem": self.checkbox(tandem),
            "Last Synced": self.date(datetime.utcnow()),
        }

        if last_payment:
            properties["Last Payment Date"] = self.date(last_payment.created_at)
            properties["Last Payment Amount"] = self.number(last_payment.amount_cents / 100.0)

        if last_appointment:
            properties["Last Appointment"] = self.date(last_appointment.start_at)

        if next_appointment:
            properties["Next Appointment"] = self.date(next_appointment.start_at)

        # Determine status based on remaining sessions
        if sessions_remaining <= 0:
            status = "Needs Package"
        elif sessions_remaining <= 2:
            status = "Low Sessions"
        else:
            status = "Active"
        properties["Status"] = self.select(status)

        return self.upsert_page(
            database_id,
            properties,
            unique_property="Square ID",
            unique_value=customer.id,
        )

    def sync_invoice(self, database_id: str, invoice: Invoice) -> Dict:
        """Sync an invoice to Notion."""
        amount_dollars = invoice.amount_cents / 100.0

        properties = {
            "Invoice ID": self.title(invoice.id),
            "Account": self.select(invoice.account_code),
            "Amount": self.number(amount_dollars),
            "Currency": self.select(invoice.currency),
            "Status": self.select(invoice.status),
            "Due Date": self.date(invoice.due_date) if invoice.due_date else {"date": None},
            "Customer ID": self.rich_text(invoice.customer_id or ""),
            "Last Synced": self.date(datetime.utcnow()),
        }

        return self.upsert_page(
            database_id,
            properties,
            unique_property="Invoice ID",
            unique_value=invoice.id,
            unique_type="title",
        )
