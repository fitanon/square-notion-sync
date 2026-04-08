"""
Tests for API security: CORS whitelisting and API-key authentication.

These tests build a minimal FastAPI app using the same route registration
and ``verify_api_key`` dependency from ``api.app``, but mock all backend
globals so no real Square / Stripe / Notion connections are needed.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers — build a testable app with mocked globals
# ---------------------------------------------------------------------------

def _build_test_app():
    """Create a FastAPI app with all routes but mocked backends.

    Returns the app (not a TestClient) so callers can wrap it in
    whatever env-var context they need.
    """
    import api.app as app_module

    # Mock every global that route handlers reference
    mock_config = MagicMock()
    mock_config.accounts = {"PA": MagicMock(code="PA", name="PA", environment="sandbox")}
    mock_config.notion = MagicMock()
    mock_config.sync.schedule_hour = 2
    mock_config.sync.schedule_minute = 0
    mock_config.sync.timezone = "America/New_York"
    mock_config.sync.session_item_name = "One-on-One 60"
    mock_config.validate.return_value = []

    mock_scheduler = MagicMock()
    mock_scheduler.scheduler.running = True
    mock_scheduler.get_status.return_value = {}

    _sync_result = MagicMock()
    _sync_result.to_dict.return_value = {
        "success": True, "sync_type": "test", "accounts_synced": ["PA"],
        "records_created": 0, "records_updated": 0, "records_failed": 0,
        "duration_seconds": 0.1, "errors": [],
    }
    mock_financial = MagicMock()
    mock_financial.sync.return_value = _sync_result
    mock_appointments = MagicMock()
    mock_appointments.sync.return_value = _sync_result
    mock_sessions = MagicMock()
    mock_sessions.sync.return_value = _sync_result
    mock_stripe_client = MagicMock()
    mock_stripe_client.is_configured = True
    mock_stripe_client.get_prices.return_value = []
    mock_stripe_sync = MagicMock()

    app_module.config = mock_config
    app_module.scheduler = mock_scheduler
    app_module.financial_sync = mock_financial
    app_module.appointments_sync = mock_appointments
    app_module.sessions_sync = mock_sessions
    app_module.stripe_client = mock_stripe_client
    app_module.stripe_sync = mock_stripe_sync

    # Build a fresh app with the same CORS config and routes
    from api.app import register_routes

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://square-notion-sync.vercel.app",
            "https://fitclinic.io",
            "https://clients.fitclinic.io",
            "https://staff.fitclinic.io",
            "http://localhost:3000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    register_routes(test_app)
    return test_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_no_auth():
    """App with API_SECRET_KEY unset (dev mode -- no auth enforced).

    We ensure the env var is absent for the full lifetime of the client.
    """
    test_app = _build_test_app()
    env = os.environ.copy()
    env.pop("API_SECRET_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        yield TestClient(test_app)


@pytest.fixture()
def client_with_auth():
    """App with API_SECRET_KEY set -- admin endpoints require the key."""
    test_app = _build_test_app()
    with patch.dict(os.environ, {"API_SECRET_KEY": "test-secret-key-12345"}):
        yield TestClient(test_app)


# ===================================================================
# Bug 4 -- CORS only allows whitelisted origins
# ===================================================================

class TestCORS:
    """Verify CORS headers only appear for whitelisted origins."""

    def test_whitelisted_origin_gets_cors_headers(self, client_no_auth):
        resp = client_no_auth.get(
            "/health",
            headers={"Origin": "https://fitclinic.io"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://fitclinic.io"

    def test_non_whitelisted_origin_no_cors_header(self, client_no_auth):
        resp = client_no_auth.get(
            "/health",
            headers={"Origin": "https://evil-site.com"},
        )
        assert resp.status_code == 200
        # The response must NOT echo back the attacker origin
        acao = resp.headers.get("access-control-allow-origin")
        assert acao != "https://evil-site.com"
        assert acao != "*"

    def test_localhost_origin_allowed(self, client_no_auth):
        resp = client_no_auth.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_preflight_only_allows_get_post(self, client_no_auth):
        resp = client_no_auth.options(
            "/health",
            headers={
                "Origin": "https://fitclinic.io",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        allowed = resp.headers.get("access-control-allow-methods", "")
        assert "DELETE" not in allowed
        assert "PUT" not in allowed


# ===================================================================
# Bug 5 -- Admin endpoints require API key when configured
# ===================================================================

class TestAuthPublicEndpoints:
    """Public endpoints must be accessible without any API key,
    regardless of whether API_SECRET_KEY is configured."""

    def test_health_no_key_required(self, client_with_auth):
        resp = client_with_auth.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_portal_lookup_no_key_required(self, client_with_auth):
        # Will get 400 (missing email/phone) -- but NOT 401
        resp = client_with_auth.get("/portal/lookup")
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Provide email or phone"

    def test_stripe_prices_no_key_required(self, client_with_auth):
        resp = client_with_auth.get("/stripe/prices")
        assert resp.status_code == 200


class TestAuthAdminEndpoints:
    """Admin endpoints must return 401 without a valid API key."""

    # --- Sync endpoints ---

    def test_sync_financial_requires_key(self, client_with_auth):
        resp = client_with_auth.post("/sync/financial")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or missing API key"

    def test_sync_financial_succeeds_with_correct_key(self, client_with_auth):
        resp = client_with_auth.post(
            "/sync/financial",
            headers={"X-Api-Key": "test-secret-key-12345"},
        )
        # Should not be 401 -- it will either be 200 or a mock-related
        # status, but definitely not an auth rejection.
        assert resp.status_code != 401

    def test_sync_financial_rejects_wrong_key(self, client_with_auth):
        resp = client_with_auth.post(
            "/sync/financial",
            headers={"X-Api-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    # --- Scheduler endpoints ---

    def test_scheduler_status_requires_key(self, client_with_auth):
        resp = client_with_auth.get("/scheduler/status")
        assert resp.status_code == 401

    def test_scheduler_status_succeeds_with_key(self, client_with_auth):
        resp = client_with_auth.get(
            "/scheduler/status",
            headers={"X-Api-Key": "test-secret-key-12345"},
        )
        assert resp.status_code != 401

    def test_scheduler_trigger_requires_key(self, client_with_auth):
        resp = client_with_auth.post("/scheduler/trigger")
        assert resp.status_code == 401

    def test_scheduler_pause_requires_key(self, client_with_auth):
        resp = client_with_auth.post("/scheduler/pause/financial")
        assert resp.status_code == 401

    def test_scheduler_resume_requires_key(self, client_with_auth):
        resp = client_with_auth.post("/scheduler/resume/financial")
        assert resp.status_code == 401

    # --- Config endpoint ---

    def test_config_requires_key(self, client_with_auth):
        resp = client_with_auth.get("/config")
        assert resp.status_code == 401

    def test_config_succeeds_with_key(self, client_with_auth):
        resp = client_with_auth.get(
            "/config",
            headers={"X-Api-Key": "test-secret-key-12345"},
        )
        assert resp.status_code != 401

    # --- Report endpoints ---

    def test_reports_tandem_requires_key(self, client_with_auth):
        resp = client_with_auth.get("/reports/tandem")
        assert resp.status_code == 401

    def test_reports_low_sessions_requires_key(self, client_with_auth):
        resp = client_with_auth.get("/reports/low-sessions")
        assert resp.status_code == 401

    # --- Stripe admin endpoints ---

    def test_stripe_checkout_requires_key(self, client_with_auth):
        resp = client_with_auth.post("/stripe/checkout?tier=single")
        assert resp.status_code == 401

    def test_sync_stripe_payments_requires_key(self, client_with_auth):
        resp = client_with_auth.post("/sync/stripe/payments")
        assert resp.status_code == 401


class TestAuthDevMode:
    """When API_SECRET_KEY is not set, admin endpoints should be open
    (dev mode behaviour)."""

    def test_sync_financial_open_without_key_configured(self, client_no_auth):
        resp = client_no_auth.post("/sync/financial")
        # Should not be 401 -- auth is bypassed in dev mode
        assert resp.status_code != 401

    def test_scheduler_status_open_without_key_configured(self, client_no_auth):
        resp = client_no_auth.get("/scheduler/status")
        assert resp.status_code != 401

    def test_config_open_without_key_configured(self, client_no_auth):
        resp = client_no_auth.get("/config")
        assert resp.status_code != 401
