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
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from core.config import Config
from core.scheduler import SyncScheduler
from core.stripe_client import StripeClient
from sync import FinancialSync, AppointmentsSync, SessionsSync
from sync.stripe_payments import StripePaymentSync, StripeSubscriptionSync
from api.portal import register_portal_routes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Square-Notion Sync API...")

    config = Config.from_env()
    errors = config.validate()
    if errors:
        logger.warning(f"Configuration warnings: {errors}")

    app.state.config = config
    app.state.scheduler = SyncScheduler(config.sync)
    app.state.financial_sync = FinancialSync(config)
    app.state.appointments_sync = AppointmentsSync(config)
    app.state.sessions_sync = SessionsSync(config)

    # Stripe sync modules (if configured)
    if config.stripe:
        app.state.stripe_client = StripeClient(config.stripe)
        app.state.stripe_payment_sync = StripePaymentSync(config)
        app.state.stripe_subscription_sync = StripeSubscriptionSync(config)
    else:
        app.state.stripe_client = None
        app.state.stripe_payment_sync = None
        app.state.stripe_subscription_sync = None

    # Register daily sync jobs (call .sync directly - SyncResult already tracks timing)
    app.state.scheduler.add_daily_sync("financial", app.state.financial_sync.sync)
    app.state.scheduler.add_daily_sync("appointments", app.state.appointments_sync.sync)
    app.state.scheduler.add_daily_sync("sessions", app.state.sessions_sync.sync)
    app.state.scheduler.start()

    logger.info("API started successfully")
    yield

    logger.info("Shutting down...")
    app.state.scheduler.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Square-Notion Sync API",
        description="Sync Square data to Notion databases with multi-account support",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_routes(app)
    register_portal_routes(app)
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
    def health_check(request: Request):
        return HealthResponse(
            status="ok",
            timestamp=datetime.utcnow().isoformat(),
            accounts=list(request.app.state.config.accounts.keys()),
            scheduler_running=request.app.state.scheduler.scheduler.running,
        )

    @app.get("/config")
    def get_config(request: Request):
        config = request.app.state.config
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
        request: Request,
        accounts: Optional[List[str]] = Query(None, description="Account codes (PA, TFC, FWM)"),
        days_back: int = Query(30, description="Days of history to sync"),
    ):
        """Sync payment transactions and invoices from Square to Notion."""
        result = request.app.state.financial_sync.sync(account_codes=accounts, days_back=days_back)
        return SyncResponse(**result.to_dict())

    @app.post("/sync/appointments", response_model=SyncResponse)
    def trigger_appointments_sync(
        request: Request,
        accounts: Optional[List[str]] = Query(None),
        days_back: int = Query(30),
        days_forward: int = Query(30),
    ):
        """Sync bookings/appointments with tandem detection."""
        result = request.app.state.appointments_sync.sync(
            account_codes=accounts, days_back=days_back, days_forward=days_forward,
        )
        return SyncResponse(**result.to_dict())

    @app.post("/sync/sessions", response_model=SyncResponse)
    def trigger_sessions_sync(
        request: Request,
        accounts: Optional[List[str]] = Query(None),
    ):
        """Calculate sessions purchased vs used for each client."""
        result = request.app.state.sessions_sync.sync(account_codes=accounts)
        return SyncResponse(**result.to_dict())

    @app.post("/sync/all", response_model=List[SyncResponse])
    def trigger_all_syncs(
        request: Request,
        accounts: Optional[List[str]] = Query(None),
    ):
        """Run all syncs (financial, appointments, sessions)."""
        state = request.app.state
        return [
            SyncResponse(**state.financial_sync.sync(account_codes=accounts).to_dict()),
            SyncResponse(**state.appointments_sync.sync(account_codes=accounts).to_dict()),
            SyncResponse(**state.sessions_sync.sync(account_codes=accounts).to_dict()),
        ]

    # ─────────────────────────────────────────────────────────────
    # SCHEDULER CONTROL
    # ─────────────────────────────────────────────────────────────

    @app.get("/scheduler/status", response_model=SchedulerStatus)
    def get_scheduler_status(request: Request):
        sched = request.app.state.scheduler
        status = sched.get_status()
        next_run = None
        for job_status in status.values():
            if job_status.get("next_run"):
                if not next_run or job_status["next_run"] < next_run:
                    next_run = job_status["next_run"]

        return SchedulerStatus(
            running=sched.scheduler.running,
            jobs=status,
            timezone=request.app.state.config.sync.timezone,
            next_sync_time=next_run,
        )

    @app.post("/scheduler/trigger")
    def trigger_scheduled_sync(
        request: Request,
        job_name: Optional[str] = Query(None),
    ):
        triggered = request.app.state.scheduler.trigger_now(job_name)
        return {"triggered": triggered, "message": f"Triggered {len(triggered)} job(s)"}

    @app.post("/scheduler/pause/{job_name}")
    def pause_job(request: Request, job_name: str):
        request.app.state.scheduler.pause_job(job_name)
        return {"status": "paused", "job": job_name}

    @app.post("/scheduler/resume/{job_name}")
    def resume_job(request: Request, job_name: str):
        request.app.state.scheduler.resume_job(job_name)
        return {"status": "resumed", "job": job_name}

    # ─────────────────────────────────────────────────────────────
    # REPORTS
    # ─────────────────────────────────────────────────────────────

    @app.get("/reports/tandem")
    def get_tandem_report(
        request: Request,
        accounts: Optional[List[str]] = Query(None),
        days_back: int = Query(7),
        days_forward: int = Query(14),
    ):
        return request.app.state.appointments_sync.get_tandem_summary(
            account_codes=accounts, days_back=days_back, days_forward=days_forward,
        )

    @app.get("/reports/low-sessions")
    def get_low_sessions_report(
        request: Request,
        accounts: Optional[List[str]] = Query(None),
        threshold: int = Query(2),
    ):
        return request.app.state.sessions_sync.get_low_session_clients(
            account_codes=accounts, threshold=threshold,
        )

    # ─────────────────────────────────────────────────────────────
    # STRIPE ENDPOINTS
    # ─────────────────────────────────────────────────────────────

    @app.post("/sync/stripe/payments", response_model=SyncResponse)
    def trigger_stripe_payment_sync(
        request: Request,
        days_back: int = Query(30, description="Days of payment history to sync"),
    ):
        """Sync Stripe payments to Notion."""
        if not request.app.state.stripe_payment_sync:
            raise HTTPException(status_code=503, detail="Stripe not configured")
        result = request.app.state.stripe_payment_sync.sync(days_back=days_back)
        return SyncResponse(**result.to_dict())

    @app.post("/sync/stripe/subscriptions", response_model=SyncResponse)
    def trigger_stripe_subscription_sync(request: Request):
        """Sync Stripe subscriptions to Notion."""
        if not request.app.state.stripe_subscription_sync:
            raise HTTPException(status_code=503, detail="Stripe not configured")
        result = request.app.state.stripe_subscription_sync.sync()
        return SyncResponse(**result.to_dict())

    @app.post("/stripe/checkout")
    def create_checkout(
        request: Request,
        price_id: str = Query(..., description="Stripe Price ID"),
        customer_email: Optional[str] = Query(None, description="Customer email"),
        success_url: str = Query("https://example.com/success"),
        cancel_url: str = Query("https://example.com/cancel"),
    ):
        """Create a Stripe Checkout session."""
        if not request.app.state.stripe_client:
            raise HTTPException(status_code=503, detail="Stripe not configured")

        try:
            url = request.app.state.stripe_client.create_checkout_session(
                price_id=price_id,
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return {"checkout_url": url}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/stripe/prices")
    def list_stripe_prices(request: Request):
        """List configured Stripe price tiers."""
        config = request.app.state.config
        if not config.stripe:
            raise HTTPException(status_code=503, detail="Stripe not configured")

        prices = []
        for key, price_id in config.stripe.prices.items():
            price = request.app.state.stripe_client.get_price(price_id)
            if price:
                prices.append({
                    "key": key,
                    "id": price.id,
                    "name": price.name,
                    "sessions": price.sessions,
                    "amount": price.amount_dollars,
                    "per_session": price.per_session_dollars,
                    "is_recurring": price.is_recurring,
                    "interval": price.interval,
                })
        return {"prices": prices}

    @app.post("/stripe/webhook")
    async def handle_stripe_webhook(request: Request):
        """Handle Stripe webhook events."""
        if not request.app.state.stripe_client:
            raise HTTPException(status_code=503, detail="Stripe not configured")

        payload = await request.body()
        signature = request.headers.get("stripe-signature", "")

        try:
            event = request.app.state.stripe_client.construct_webhook_event(
                payload, signature
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        result = request.app.state.stripe_client.handle_webhook_event(event)
        logger.info(f"Processed webhook: {event.type}")

        # Auto-sync on successful payments
        if event.type == "payment_intent.succeeded":
            request.app.state.stripe_payment_sync.sync(days_back=1)
        elif event.type in ("customer.subscription.created", "customer.subscription.updated"):
            request.app.state.stripe_subscription_sync.sync()

        return {"received": True, "event_type": event.type}


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
