"""Multi-Account Square Sync Module

Handles syncing data from multiple Square accounts to centralized storage.
Supports: Customers, Transactions, Invoices, Orders

Usage:
    from src.multi_account import SquareMultiAccount

    sync = SquareMultiAccount()
    all_customers = sync.get_all_customers()
    all_transactions = sync.get_all_transactions()
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
import requests

load_dotenv()


class SquareAccount:
    """Represents a single Square account connection."""

    def __init__(self, name: str, token: str, location_id: str = None, email: str = None):
        self.name = name
        self.token = token
        self.location_id = location_id
        self.email = email
        self.env = os.getenv("SQUARE_ENV", "production")
        self.base_url = (
            "https://connect.squareupsandbox.com"
            if self.env == "sandbox"
            else "https://connect.squareup.com"
        )
        self.api_version = "2024-01-18"

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Square-Version": self.api_version,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make an API request to Square."""
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_locations(self) -> List[Dict]:
        """Get all locations for this account."""
        return self._request("GET", "/v2/locations").get("locations", [])

    def get_customers(self, limit: int = 100, cursor: str = None) -> Dict:
        """Get customers with pagination."""
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/v2/customers", params=params)

    def get_all_customers(self) -> List[Dict]:
        """Get all customers (handles pagination)."""
        customers = []
        cursor = None
        while True:
            result = self.get_customers(cursor=cursor)
            customers.extend(result.get("customers", []))
            cursor = result.get("cursor")
            if not cursor:
                break
        return customers

    def get_payments(self, begin_time: str = None, end_time: str = None, limit: int = 100) -> Dict:
        """Get payments/transactions."""
        params = {"limit": limit}
        if begin_time:
            params["begin_time"] = begin_time
        if end_time:
            params["end_time"] = end_time
        return self._request("GET", "/v2/payments", params=params)

    def get_orders(self, location_ids: List[str] = None, limit: int = 100) -> Dict:
        """Search orders."""
        body = {"limit": limit}
        if location_ids:
            body["location_ids"] = location_ids
        elif self.location_id:
            body["location_ids"] = [self.location_id]
        return self._request("POST", "/v2/orders/search", json=body)

    def get_invoices(self, location_id: str = None, limit: int = 100) -> Dict:
        """Get invoices."""
        loc = location_id or self.location_id
        if not loc:
            # Get first location if not specified
            locations = self.get_locations()
            if locations:
                loc = locations[0]["id"]
        params = {"location_id": loc, "limit": limit}
        return self._request("GET", "/v2/invoices", params=params)


class SquareMultiAccount:
    """Manages multiple Square accounts and aggregates their data."""

    def __init__(self):
        self.accounts: Dict[str, SquareAccount] = {}
        self._load_accounts_from_env()

    def _load_accounts_from_env(self):
        """Load account configurations from environment variables."""
        # Pattern: ACCOUNT__{NAME}__TOKEN, ACCOUNT__{NAME}__LOCATION_ID, ACCOUNT__{NAME}__EMAIL

        # Define expected accounts
        account_configs = [
            ("FITCLINIC_LLC", "THE FIT CLINIC LLC"),
            ("FITCLINIC", "FITCLINIC.IO"),
            ("FITNESSWITHMIKE", "FITNESS WITH MIKE"),
        ]

        for env_key, display_name in account_configs:
            token = os.getenv(f"ACCOUNT__{env_key}__TOKEN")
            if token:
                self.accounts[display_name] = SquareAccount(
                    name=display_name,
                    token=token,
                    location_id=os.getenv(f"ACCOUNT__{env_key}__LOCATION_ID"),
                    email=os.getenv(f"ACCOUNT__{env_key}__EMAIL"),
                )

        # Fallback to default token if no accounts configured
        if not self.accounts:
            default_token = os.getenv("SQUARE_ACCESS_TOKEN")
            if default_token:
                self.accounts["DEFAULT"] = SquareAccount(
                    name="DEFAULT",
                    token=default_token,
                )

    def add_account(self, name: str, token: str, location_id: str = None, email: str = None):
        """Manually add an account."""
        self.accounts[name] = SquareAccount(name, token, location_id, email)

    def get_all_customers(self) -> List[Dict]:
        """Get customers from all accounts with source labels."""
        all_customers = []
        for name, account in self.accounts.items():
            try:
                customers = account.get_all_customers()
                for customer in customers:
                    customer["_source"] = name
                    customer["_source_email"] = account.email
                all_customers.append({
                    "source": name,
                    "customers": customers,
                    "count": len(customers),
                })
            except Exception as e:
                all_customers.append({
                    "source": name,
                    "error": str(e),
                    "customers": [],
                    "count": 0,
                })
        return all_customers

    def get_all_transactions(self, days_back: int = 30) -> List[Dict]:
        """Get transactions/payments from all accounts."""
        end_time = datetime.utcnow()
        begin_time = end_time - timedelta(days=days_back)

        all_transactions = []
        for name, account in self.accounts.items():
            try:
                result = account.get_payments(
                    begin_time=begin_time.isoformat() + "Z",
                    end_time=end_time.isoformat() + "Z",
                )
                payments = result.get("payments", [])
                for payment in payments:
                    payment["_source"] = name
                all_transactions.append({
                    "source": name,
                    "transactions": payments,
                    "count": len(payments),
                })
            except Exception as e:
                all_transactions.append({
                    "source": name,
                    "error": str(e),
                    "transactions": [],
                    "count": 0,
                })
        return all_transactions

    def get_all_invoices(self) -> List[Dict]:
        """Get invoices from all accounts."""
        all_invoices = []
        for name, account in self.accounts.items():
            try:
                result = account.get_invoices()
                invoices = result.get("invoices", [])
                for invoice in invoices:
                    invoice["_source"] = name
                all_invoices.append({
                    "source": name,
                    "invoices": invoices,
                    "count": len(invoices),
                })
            except Exception as e:
                all_invoices.append({
                    "source": name,
                    "error": str(e),
                    "invoices": [],
                    "count": 0,
                })
        return all_invoices

    def get_summary(self) -> Dict:
        """Get a summary of all accounts."""
        summary = {
            "accounts": [],
            "total_accounts": len(self.accounts),
            "generated_at": datetime.utcnow().isoformat(),
        }

        for name, account in self.accounts.items():
            account_summary = {
                "name": name,
                "email": account.email,
                "environment": account.env,
            }

            try:
                locations = account.get_locations()
                account_summary["locations"] = len(locations)
                account_summary["location_ids"] = [loc["id"] for loc in locations]
                account_summary["status"] = "connected"
            except Exception as e:
                account_summary["status"] = "error"
                account_summary["error"] = str(e)

            summary["accounts"].append(account_summary)

        return summary


def main():
    """Test the multi-account setup."""
    print("=" * 60)
    print("Square Multi-Account Sync Test")
    print("=" * 60)

    sync = SquareMultiAccount()

    print(f"\nLoaded {len(sync.accounts)} accounts:")
    for name in sync.accounts:
        print(f"  - {name}")

    print("\n" + "-" * 60)
    print("Account Summary:")
    print("-" * 60)

    summary = sync.get_summary()
    print(json.dumps(summary, indent=2))

    if sync.accounts:
        print("\n" + "-" * 60)
        print("Fetching customers from all accounts...")
        print("-" * 60)

        customers = sync.get_all_customers()
        for result in customers:
            print(f"\n{result['source']}: {result['count']} customers")
            if result.get("error"):
                print(f"  Error: {result['error']}")


if __name__ == "__main__":
    main()
