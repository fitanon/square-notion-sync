"""
Postgres database client for Neon.

Provides direct DB access to the unified client/session data store,
used as a fast path for portal lookups and as the sync target for
Square -> Postgres pipelines.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2 import pool as pg_pool
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class DatabaseClient:
    """Postgres client with connection pooling for Neon."""

    def __init__(self, database_url: Optional[str] = None):
        self._database_url = database_url or os.getenv("DATABASE_URL")
        self._pool = None

        if self._database_url and HAS_PSYCOPG2:
            try:
                self._pool = pg_pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=5,
                    dsn=self._database_url,
                )
                logger.info("Postgres connection pool created")
            except Exception as e:
                logger.warning(f"Failed to create Postgres connection pool: {e}")
                self._pool = None
        elif not HAS_PSYCOPG2 and self._database_url:
            logger.warning("psycopg2 not installed; Postgres features disabled")

    @property
    def is_configured(self) -> bool:
        """True if DATABASE_URL is set and the pool was created."""
        return self._pool is not None

    def _get_conn(self):
        """Get a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Database not configured")
        return self._pool.getconn()

    def _put_conn(self, conn):
        """Return a connection to the pool."""
        if self._pool and conn:
            self._pool.putconn(conn)

    def _execute(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a query and return rows as dicts."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
                return []
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def _execute_write(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute an INSERT/UPDATE and return the affected row (if RETURNING)."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = None
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    fetched = cur.fetchone()
                    if fetched:
                        row = dict(zip(columns, fetched))
                conn.commit()
                return row
        except Exception as e:
            logger.error(f"Database write failed: {e}")
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    # ─────────────────────────────────────────────────────────────
    # READ QUERIES
    # ─────────────────────────────────────────────────────────────

    def get_client_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Look up a client by email address."""
        rows = self._execute(
            "SELECT * FROM clients WHERE LOWER(email) = LOWER(%s) AND status = 'active' LIMIT 1",
            (email,),
        )
        return rows[0] if rows else None

    def get_client_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Look up a client by phone number.

        Normalises the phone to digits-only for comparison.
        """
        # Strip to digits for flexible matching
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) >= 10:
            digits = digits[-10:]  # last 10 digits

        rows = self._execute(
            """
            SELECT * FROM clients
            WHERE REPLACE(REPLACE(REPLACE(REPLACE(phone, '-', ''), ' ', ''), '(', ''), ')', '') LIKE %s
              AND status = 'active'
            LIMIT 1
            """,
            (f"%{digits}",),
        )
        return rows[0] if rows else None

    def get_sessions_remaining(self, client_id: int) -> Optional[int]:
        """Get sessions remaining for a client.

        Returns the sum across all active packages of
        (sessions_total - sessions_used).  Returns None if the client
        has an unlimited package (sessions_total == -1).
        """
        rows = self._execute(
            """
            SELECT sessions_total, sessions_used
            FROM client_packages
            WHERE client_id = %s AND status = 'active'
            """,
            (client_id,),
        )
        if not rows:
            return 0

        total = 0
        for row in rows:
            if row["sessions_total"] == -1:
                return None  # unlimited
            total += row["sessions_total"] - row["sessions_used"]

        return max(0, total)

    def get_all_clients_with_trainers(self) -> List[Dict[str, Any]]:
        """Return all active clients joined with their trainer info."""
        return self._execute(
            """
            SELECT c.*, t.name AS trainer_name, t.email AS trainer_email,
                   t.specialty AS trainer_specialty
            FROM clients c
            LEFT JOIN trainers t ON c.trainer_id = t.id
            WHERE c.status = 'active'
            ORDER BY c.last_name, c.first_name
            """
        )

    def get_low_session_clients(self, threshold: int = 2) -> List[Dict[str, Any]]:
        """Return clients whose remaining sessions are at or below *threshold*.

        Excludes unlimited packages (sessions_total == -1).
        """
        return self._execute(
            """
            SELECT c.id, c.first_name, c.last_name, c.email, c.phone,
                   t.name AS trainer_name,
                   SUM(cp.sessions_total - cp.sessions_used) AS sessions_remaining
            FROM clients c
            JOIN client_packages cp ON cp.client_id = c.id AND cp.status = 'active'
            LEFT JOIN trainers t ON c.trainer_id = t.id
            WHERE c.status = 'active'
              AND cp.sessions_total != -1
            GROUP BY c.id, c.first_name, c.last_name, c.email, c.phone, t.name
            HAVING SUM(cp.sessions_total - cp.sessions_used) <= %s
            ORDER BY sessions_remaining ASC
            """,
            (threshold,),
        )

    # ─────────────────────────────────────────────────────────────
    # WRITE QUERIES (upserts)
    # ─────────────────────────────────────────────────────────────

    def upsert_client(
        self,
        external_id: str,
        first_name: str,
        last_name: str,
        email: str,
        phone: Optional[str] = None,
        trainer_id: Optional[int] = None,
        status: str = "active",
    ) -> Optional[Dict[str, Any]]:
        """Insert or update a client by external_id."""
        return self._execute_write(
            """
            INSERT INTO clients (external_id, login_code, first_name, last_name, email, phone, trainer_id, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW()::text)
            ON CONFLICT (external_id) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name  = EXCLUDED.last_name,
                email      = EXCLUDED.email,
                phone      = EXCLUDED.phone,
                trainer_id = EXCLUDED.trainer_id,
                status     = EXCLUDED.status
            RETURNING *
            """,
            (external_id, external_id[:8], first_name, last_name, email, phone, trainer_id, status),
        )

    def upsert_appointment(
        self,
        external_id: str,
        client_id: int,
        trainer_id: int,
        session_type: str,
        scheduled_at: str,
        status: str = "scheduled",
    ) -> Optional[Dict[str, Any]]:
        """Insert or update an appointment by external_id."""
        return self._execute_write(
            """
            INSERT INTO appointments (external_id, client_id, trainer_id, session_type, scheduled_at, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW()::text)
            ON CONFLICT (external_id) DO UPDATE SET
                client_id    = EXCLUDED.client_id,
                trainer_id   = EXCLUDED.trainer_id,
                session_type = EXCLUDED.session_type,
                scheduled_at = EXCLUDED.scheduled_at,
                status       = EXCLUDED.status
            RETURNING *
            """,
            (external_id, client_id, trainer_id, session_type, scheduled_at, status),
        )

    def close(self):
        """Close the connection pool."""
        if self._pool:
            try:
                self._pool.closeall()
                logger.info("Postgres connection pool closed")
            except Exception as e:
                logger.warning(f"Error closing pool: {e}")
