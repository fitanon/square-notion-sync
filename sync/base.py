"""
Base sync class with common functionality.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

from core.config import Config
from core.accounts import MultiAccountClient
from core.notion import NotionClient


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    sync_type: str
    accounts_synced: List[str]
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    def complete(self):
        """Mark sync as complete and calculate duration."""
        self.completed_at = datetime.utcnow()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "sync_type": self.sync_type,
            "accounts_synced": self.accounts_synced,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
            "records_failed": self.records_failed,
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


class BaseSync(ABC):
    """
    Base class for all sync operations.

    Provides common functionality for multi-account syncing.
    """

    sync_type: str = "base"

    def __init__(self, config: Config):
        self.config = config
        self.square = MultiAccountClient(config)
        self.notion = NotionClient(config.notion) if config.notion else None
        self.logger = logging.getLogger(f"sync.{self.sync_type}")

    @abstractmethod
    def sync(self, account_codes: List[str] = None) -> SyncResult:
        """
        Perform the sync operation.

        Args:
            account_codes: List of account codes to sync (e.g., ["PA", "TFC"]).
                          If None, sync all configured accounts.

        Returns:
            SyncResult with details of the operation.
        """
        pass

    def get_account_codes(self, account_codes: List[str] = None) -> List[str]:
        """Get list of account codes to sync."""
        if account_codes:
            valid_codes = []
            for code in account_codes:
                if code.upper() in self.config.accounts:
                    valid_codes.append(code.upper())
                else:
                    self.logger.warning(f"Unknown account code: {code}")
            return valid_codes
        return list(self.config.accounts.keys())

    def validate_notion(self) -> bool:
        """Check if Notion is properly configured."""
        if not self.notion:
            self.logger.error("Notion client not configured")
            return False
        return True
