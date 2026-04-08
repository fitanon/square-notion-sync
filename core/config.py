"""
Configuration management for multi-account Square sync.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AccountConfig:
    """Configuration for a single Square account."""
    code: str  # PA, TFC, FWM
    name: str  # Physiques Anonymous, The Fit Clinic LLC, etc.
    access_token: str
    location_id: Optional[str] = None
    environment: str = "production"

    @property
    def base_url(self) -> str:
        if self.environment == "sandbox":
            return "https://connect.squareupsandbox.com"
        return "https://connect.squareup.com"


@dataclass
class NotionConfig:
    """Configuration for Notion integration."""
    token: str
    version: str = "2022-06-28"

    # Database IDs for each table
    db_transactions: Optional[str] = None
    db_invoices: Optional[str] = None
    db_clients: Optional[str] = None
    db_appointments: Optional[str] = None
    db_sessions: Optional[str] = None


@dataclass
class SyncConfig:
    """Configuration for sync scheduling."""
    timezone: str = "America/New_York"
    schedule_hour: int = 2
    schedule_minute: int = 0
    session_item_name: str = "One-on-One 60"  # Item name to track as sessions


@dataclass
class Config:
    """Main configuration container."""
    accounts: Dict[str, AccountConfig] = field(default_factory=dict)
    notion: Optional[NotionConfig] = None
    sync: SyncConfig = field(default_factory=SyncConfig)
    square_api_version: str = "2025-06-16"
    database_url: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_prices: Optional[Dict[str, str]] = None

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Load Square accounts
        # Format: SQUARE_{CODE}_ACCESS_TOKEN, SQUARE_{CODE}_LOCATION_ID
        account_codes = ["PA", "TFC", "FWM"]
        account_names = {
            "PA": "Physiques Anonymous",
            "TFC": "The Fit Clinic LLC",
            "FWM": "Fitness With Mike"
        }

        env = os.getenv("SQUARE_ENV", "production")

        for code in account_codes:
            token = os.getenv(f"SQUARE_{code}_ACCESS_TOKEN")
            if token:
                config.accounts[code] = AccountConfig(
                    code=code,
                    name=account_names.get(code, code),
                    access_token=token,
                    location_id=os.getenv(f"SQUARE_{code}_LOCATION_ID"),
                    environment=env,
                )

        # Fallback: check for single SQUARE_ACCESS_TOKEN (legacy)
        if not config.accounts:
            legacy_token = os.getenv("SQUARE_ACCESS_TOKEN")
            if legacy_token:
                config.accounts["DEFAULT"] = AccountConfig(
                    code="DEFAULT",
                    name="Default Account",
                    access_token=legacy_token,
                    location_id=os.getenv("SQUARE_LOCATION_ID"),
                    environment=env,
                )

        # Load Notion config
        notion_token = os.getenv("NOTION_TOKEN")
        if notion_token:
            config.notion = NotionConfig(
                token=notion_token,
                version=os.getenv("NOTION_VERSION", "2022-06-28"),
                db_transactions=os.getenv("NOTION_DB_TRANSACTIONS"),
                db_invoices=os.getenv("NOTION_DB_INVOICES"),
                db_clients=os.getenv("NOTION_DB_CLIENTS"),
                db_appointments=os.getenv("NOTION_DB_APPOINTMENTS"),
                db_sessions=os.getenv("NOTION_DB_SESSIONS"),
            )

        # Load sync config
        config.sync = SyncConfig(
            timezone=os.getenv("SYNC_TIMEZONE", "America/New_York"),
            schedule_hour=int(os.getenv("SYNC_SCHEDULE_HOUR", "2")),
            schedule_minute=int(os.getenv("SYNC_SCHEDULE_MINUTE", "0")),
            session_item_name=os.getenv("SESSION_ITEM_NAME", "One-on-One 60"),
        )

        config.square_api_version = os.getenv("SQUARE_API_VERSION", "2025-06-16")

        # Load Database config
        config.database_url = os.getenv("DATABASE_URL")

        # Load Stripe config
        config.stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        config.stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        config.stripe_prices = {
            "single": os.getenv("STRIPE_PRICE_1_SESSION"),
            "5pack": os.getenv("STRIPE_PRICE_5_SESSIONS"),
            "10pack": os.getenv("STRIPE_PRICE_10_SESSIONS"),
            "monthly": os.getenv("STRIPE_PRICE_MONTHLY"),
        }

        return config

    def get_account(self, code: str) -> Optional[AccountConfig]:
        """Get account config by code."""
        return self.accounts.get(code.upper())

    def get_all_accounts(self) -> List[AccountConfig]:
        """Get all configured accounts."""
        return list(self.accounts.values())

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.accounts:
            errors.append("No Square accounts configured")

        if not self.notion:
            errors.append("Notion not configured (NOTION_TOKEN missing)")
        elif not self.notion.token:
            errors.append("NOTION_TOKEN is empty")

        if not self.database_url:
            errors.append("DATABASE_URL not set (Postgres features disabled)")

        return errors
