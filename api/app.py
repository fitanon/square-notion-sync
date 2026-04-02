"""
Main FastAPI application for Square-Notion sync.

Provides:
- Health check endpoint
- Manual sync triggers for each dashboard
- Scheduler status and control
- Multi-account support
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from fastapi.responses import HTMLResponse, JSONResponse
from starlette.requests import Request

from core.config import Config
from core.scheduler import SyncScheduler, SyncRunner
from core.stripe_client import StripeClient
from sync import FinancialSync, AppointmentsSync, SessionsSync
from sync.stripe_payments import StripePaymentsSync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
config: Config = None
scheduler: SyncScheduler = None
financial_sync: FinancialSync = None
appointments_sync: AppointmentsSync = None
sessions_sync: SessionsSync = None
stripe_client: StripeClient = None
stripe_sync: StripePaymentsSync = None


def setup_sync_jobs():
    """Configure daily sync jobs."""
    global scheduler, financial_sync, appointments_sync, sessions_sync

    # Add daily jobs for each sync type
    scheduler.add_daily_sync(
        "financial",
        lambda: SyncRunner("financial").run(financial_sync.sync)
    )

    scheduler.add_daily_sync(
        "appointments",
        lambda: SyncRunner("appointments").run(appointments_sync.sync)
    )

    scheduler.add_daily_sync(
        "sessions",
        lambda: SyncRunner("sessions").run(sessions_sync.sync)
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global config, scheduler, financial_sync, appointments_sync, sessions_sync, stripe_client, stripe_sync

    # Startup
    logger.info("Starting Square-Notion Sync API...")

    config = Config.from_env()
    errors = config.validate()
    if errors:
        logger.warning(f"Configuration warnings: {errors}")

    scheduler = SyncScheduler(config.sync)
    financial_sync = FinancialSync(config)
    appointments_sync = AppointmentsSync(config)
    sessions_sync = SessionsSync(config)
    stripe_client = StripeClient(config)
    stripe_sync = StripePaymentsSync(config)

    if stripe_client.is_configured:
        logger.info("Stripe integration active")
    else:
        logger.info("Stripe not configured (set STRIPE_SECRET_KEY to enable)")

    setup_sync_jobs()
    scheduler.start()

    logger.info("API started successfully")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Square-Notion Sync API",
        description="Sync Square data to Notion databases with multi-account support",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    register_routes(app)

    return app


# Response models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    accounts: List[str]
    scheduler_running: bool


class SyncResponse(BaseModel):
    success: bool
    sync_type: str
    accounts_synced: List[str]
    records_created: int
    records_updated: int
    records_failed: int
    duration_seconds: float
    errors: List[str]


class SchedulerStatus(BaseModel):
    running: bool
    jobs: dict
    timezone: str
    next_sync_time: Optional[str]


def register_routes(app: FastAPI):
    """Register all API routes."""

    @app.get("/health", response_model=HealthResponse)
    def health_check():
        """Check API health and configuration status."""
        return HealthResponse(
            status="ok",
            timestamp=datetime.utcnow().isoformat(),
            accounts=list(config.accounts.keys()) if config else [],
            scheduler_running=scheduler.scheduler.running if scheduler else False,
        )

    @app.get("/config")
    def get_config():
        """Get current configuration (without secrets)."""
        if not config:
            raise HTTPException(status_code=500, detail="Configuration not loaded")

        return {
            "accounts": [
                {"code": acc.code, "name": acc.name, "environment": acc.environment}
                for acc in config.accounts.values()
            ],
            "notion_configured": config.notion is not None,
            "sync_schedule": {
                "hour": config.sync.schedule_hour,
                "minute": config.sync.schedule_minute,
                "timezone": config.sync.timezone,
            },
            "session_item_name": config.sync.session_item_name,
        }

    # ─────────────────────────────────────────────────────────────
    # MANUAL SYNC TRIGGERS
    # ─────────────────────────────────────────────────────────────

    @app.post("/sync/financial", response_model=SyncResponse)
    def trigger_financial_sync(
        accounts: Optional[List[str]] = Query(None, description="Account codes to sync (e.g., PA, TFC, FWM)"),
        days_back: int = Query(30, description="Days of history to sync"),
    ):
        """
        Manually trigger financial sync (transactions, invoices).

        Syncs payment transactions and invoices from Square to Notion.
        """
        if not financial_sync:
            raise HTTPException(status_code=500, detail="Financial sync not initialized")

        result = financial_sync.sync(account_codes=accounts, days_back=days_back)
        return SyncResponse(**result.to_dict())

    @app.post("/sync/appointments", response_model=SyncResponse)
    def trigger_appointments_sync(
        accounts: Optional[List[str]] = Query(None, description="Account codes to sync"),
        days_back: int = Query(30, description="Days of past appointments"),
        days_forward: int = Query(30, description="Days of future appointments"),
    ):
        """
        Manually trigger appointments sync.

        Syncs bookings/appointments from Square to Notion with tandem detection.
        """
        if not appointments_sync:
            raise HTTPException(status_code=500, detail="Appointments sync not initialized")

        result = appointments_sync.sync(
            account_codes=accounts,
            days_back=days_back,
            days_forward=days_forward,
        )
        return SyncResponse(**result.to_dict())

    @app.post("/sync/sessions", response_model=SyncResponse)
    def trigger_sessions_sync(
        accounts: Optional[List[str]] = Query(None, description="Account codes to sync"),
    ):
        """
        Manually trigger session tracking sync.

        Calculates sessions purchased vs used for each client.
        """
        if not sessions_sync:
            raise HTTPException(status_code=500, detail="Sessions sync not initialized")

        result = sessions_sync.sync(account_codes=accounts)
        return SyncResponse(**result.to_dict())

    @app.post("/sync/all", response_model=List[SyncResponse])
    def trigger_all_syncs(
        accounts: Optional[List[str]] = Query(None, description="Account codes to sync"),
    ):
        """
        Manually trigger all syncs (financial, appointments, sessions).
        """
        results = []

        if financial_sync:
            results.append(SyncResponse(**financial_sync.sync(account_codes=accounts).to_dict()))

        if appointments_sync:
            results.append(SyncResponse(**appointments_sync.sync(account_codes=accounts).to_dict()))

        if sessions_sync:
            results.append(SyncResponse(**sessions_sync.sync(account_codes=accounts).to_dict()))

        return results

    # ─────────────────────────────────────────────────────────────
    # SCHEDULER CONTROL
    # ─────────────────────────────────────────────────────────────

    @app.get("/scheduler/status", response_model=SchedulerStatus)
    def get_scheduler_status():
        """Get scheduler status and next run times."""
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        status = scheduler.get_status()
        next_run = None

        for job_status in status.values():
            if job_status.get("next_run"):
                if not next_run or job_status["next_run"] < next_run:
                    next_run = job_status["next_run"]

        return SchedulerStatus(
            running=scheduler.scheduler.running,
            jobs=status,
            timezone=config.sync.timezone,
            next_sync_time=next_run,
        )

    @app.post("/scheduler/trigger")
    def trigger_scheduled_sync(
        job_name: Optional[str] = Query(None, description="Specific job to trigger (financial/appointments/sessions)"),
    ):
        """Trigger scheduled sync immediately."""
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        triggered = scheduler.trigger_now(job_name)
        return {"triggered": triggered, "message": f"Triggered {len(triggered)} job(s)"}

    @app.post("/scheduler/pause/{job_name}")
    def pause_job(job_name: str):
        """Pause a specific sync job."""
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        scheduler.pause_job(job_name)
        return {"status": "paused", "job": job_name}

    @app.post("/scheduler/resume/{job_name}")
    def resume_job(job_name: str):
        """Resume a paused sync job."""
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        scheduler.resume_job(job_name)
        return {"status": "resumed", "job": job_name}

    # ─────────────────────────────────────────────────────────────
    # REPORTS / VIEWS
    # ─────────────────────────────────────────────────────────────

    @app.get("/reports/tandem")
    def get_tandem_report(
        accounts: Optional[List[str]] = Query(None),
        days_back: int = Query(7),
        days_forward: int = Query(14),
    ):
        """Get tandem appointments report."""
        if not appointments_sync:
            raise HTTPException(status_code=500, detail="Appointments sync not initialized")

        return appointments_sync.get_tandem_summary(
            account_codes=accounts,
            days_back=days_back,
            days_forward=days_forward,
        )

    @app.get("/reports/low-sessions")
    def get_low_sessions_report(
        accounts: Optional[List[str]] = Query(None),
        threshold: int = Query(2, description="Sessions remaining threshold"),
    ):
        """Get clients with low remaining sessions (trainer view)."""
        if not sessions_sync:
            raise HTTPException(status_code=500, detail="Sessions sync not initialized")

        return sessions_sync.get_low_session_clients(
            account_codes=accounts,
            threshold=threshold,
        )

    # ─────────────────────────────────────────────────────────────
    # STRIPE ENDPOINTS
    # ─────────────────────────────────────────────────────────────

    @app.get("/stripe/prices")
    def get_stripe_prices():
        """List available pricing tiers."""
        if not stripe_client:
            raise HTTPException(status_code=500, detail="Stripe not initialized")
        return {"prices": stripe_client.get_prices()}

    @app.post("/stripe/checkout")
    def create_checkout(
        tier: str = Query(..., description="Pricing tier: single, 5pack, 10pack, monthly"),
        email: Optional[str] = Query(None, description="Customer email"),
        success_url: Optional[str] = Query(None),
        cancel_url: Optional[str] = Query(None),
    ):
        """Create a Stripe Checkout session and return the payment URL."""
        if not stripe_client or not stripe_client.is_configured:
            raise HTTPException(status_code=500, detail="Stripe not configured")

        try:
            result = stripe_client.create_checkout_session(
                tier=tier,
                customer_email=email,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/stripe/webhook")
    async def stripe_webhook(request: Request):
        """Handle Stripe webhook events."""
        if not stripe_client:
            raise HTTPException(status_code=500, detail="Stripe not initialized")

        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")

        try:
            payment = stripe_client.handle_webhook(payload, sig_header)
            if payment and stripe_sync:
                stripe_sync._sync_payment(payment)
                return {"status": "synced", "payment_id": payment.id}
            return {"status": "ignored"}
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/sync/stripe/payments")
    def trigger_stripe_sync(
        limit: int = Query(100, description="Number of recent payments to sync"),
    ):
        """Manually trigger Stripe → Notion payment sync."""
        if not stripe_sync:
            raise HTTPException(status_code=500, detail="Stripe sync not initialized")

        result = stripe_sync.sync(limit=limit)
        return SyncResponse(**result.to_dict())

    # ─────────────────────────────────────────────────────────────
    # CLIENT PORTAL
    # ─────────────────────────────────────────────────────────────

    @app.get("/portal/lookup")
    def portal_lookup(
        email: Optional[str] = Query(None),
        phone: Optional[str] = Query(None),
    ):
        """Look up a client's session balance by email or phone."""
        if not email and not phone:
            raise HTTPException(status_code=400, detail="Provide email or phone")

        if not config or not config.accounts:
            raise HTTPException(status_code=500, detail="No accounts configured")

        from core.accounts import MultiAccountClient
        multi = MultiAccountClient(config)

        # Search across all accounts
        for code, client in multi.clients.items():
            for customer in client.get_all_customers():
                match = False
                if email and customer.email and customer.email.lower() == email.lower():
                    match = True
                if phone and customer.phone:
                    # Normalize phone for comparison
                    clean_input = ''.join(c for c in (phone or '') if c.isdigit())
                    clean_stored = ''.join(c for c in customer.phone if c.isdigit())
                    if clean_input and clean_stored and clean_input[-10:] == clean_stored[-10:]:
                        match = True

                if match:
                    # Count sessions
                    purchased = client.count_session_purchases(
                        customer.id,
                        config.sync.session_item_name,
                    )

                    # Count completed bookings as sessions used
                    used = 0
                    for booking in client.get_all_bookings():
                        if booking.customer_id == customer.id and booking.is_completed:
                            used += 1

                    return {
                        "name": customer.full_name,
                        "email": customer.email,
                        "phone": customer.phone,
                        "account": code,
                        "sessions_purchased": purchased,
                        "sessions_used": used,
                        "sessions_remaining": max(0, purchased - used),
                    }

        raise HTTPException(status_code=404, detail="Client not found. Check your phone number or email.")

    @app.get("/", response_class=HTMLResponse)
    def portal():
        """Serve the client portal."""
        import os
        portal_path = os.path.join(os.path.dirname(__file__), "..", "portal", "index.html")
        try:
            with open(portal_path) as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return HTMLResponse(content="<h1>Portal not found</h1>", status_code=404)


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
