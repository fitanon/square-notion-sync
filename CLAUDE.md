# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Square + Stripe → Notion Sync** — Multi-account sync for fitness business management.

Syncs data from 3 Square accounts (PA, TFC, FWM) and Stripe payments into Notion databases on a daily schedule (2am) with manual trigger support. Stripe handles tiered session pack pricing and monthly subscriptions. Also includes a client-facing session balance portal deployed on Vercel.

## Architecture

```
core/           → Core library (API clients, scheduler)
  config.py     → Dataclass configs: AccountConfig, NotionConfig, StripeConfig, Config
  accounts.py   → MultiAccountClient + dataclass models (Payment, Customer, Booking, Order, Invoice)
  notion.py     → NotionClient with upsert logic, returns tuple[Dict, bool]
  stripe_client.py → StripeClient for payments, subscriptions, tiered pricing
  scheduler.py  → APScheduler for 2am daily sync

sync/           → Sync modules (all extend BaseSync)
  base.py       → BaseSync ABC + SyncResult dataclass
  financial.py  → Dashboard 1: Transactions/Invoices
  appointments.py → Dashboard 2: Bookings with tandem detection
  sessions.py   → Dashboard 3: Session tracking (purchased vs used)
  stripe_payments.py → Stripe payment and subscription sync (NOT exported from __init__.py — import directly)

api/            → Two separate FastAPI apps
  app.py        → Main API: sync triggers, scheduler control, Stripe endpoints, reports (run via run.py)
  index.py      → Standalone Vercel serverless portal: client session balance lookup (independent from app.py)
  portal.py     → Portal routes registered with main app (separate from Vercel entry point)

scripts/        → CLI tools (import_data.py, square_examples.py)
fastapi/        → Legacy prototype — DEPRECATED, do not extend (kept for reference only)
```

## Two FastAPI Apps

The project has two independent FastAPI applications:

1. **`api/app.py`** — Full API server with scheduler, all sync endpoints, Stripe integration. Run locally via `python run.py`. Uses `core/`, `sync/`, lifespan context with scheduler.
2. **`api/index.py`** — Minimal standalone serverless app for Vercel. Only handles client session balance lookups. Has its own Notion client init, HTML rendering, and error handling. Does NOT import from `api/app.py`.

`vercel.json` routes all requests to `api/index.py`.

## Key Commands

```bash
pip install -r requirements.txt      # Install dependencies
python run.py                        # Run API server (localhost:8000)
python run.py --reload               # Dev mode with auto-reload
```

No test suite exists yet. `pytest` is in requirements.txt but no `tests/` directory has been created.

## Environment Variables

**Local development** — copy `.env.example` to `.env`:
```
SQUARE_PA_ACCESS_TOKEN=...           # Physiques Anonymous
SQUARE_TFC_ACCESS_TOKEN=...          # The Fit Clinic
SQUARE_FWM_ACCESS_TOKEN=...          # Fitness With Mike
NOTION_TOKEN=secret_...
NOTION_DB_CLIENTS=<database-id>
NOTION_DB_SESSIONS=<database-id>
NOTION_DB_TRANSACTIONS=<database-id>
```

**Stripe payments** — for tiered pricing and subscriptions:
```
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_1_SESSION=price_...
STRIPE_PRICE_5_SESSIONS=price_...
STRIPE_PRICE_10_SESSIONS=price_...
STRIPE_PRICE_MONTHLY=price_...
```

**Vercel deployment** — set in Vercel dashboard for client portal:
```
NOTION_TOKEN                         # Required
NOTION_DB_SESSIONS                   # Primary lookup database
```

## Code Conventions

- Type hints on all function signatures
- Dataclasses for data models in `core/accounts.py`
- `upsert_page()` returns `tuple[Dict, bool]` where bool = was_created
- Multi-account: always iterate all 3 accounts unless filtered via `account_codes` param
- Bulk-fetch data before processing to avoid N+1 API calls
- Status constants defined at module level, not inline strings
- Sync modules extend `BaseSync` and implement `sync(account_codes: List[str]) -> SyncResult`

## Square Account Codes

| Code | Business | Status |
|------|----------|--------|
| PA | Physiques Anonymous | Primary |
| TFC | The Fit Clinic LLC | Active |
| FWM | Fitness With Mike | Legacy |

## Notion Database IDs

- Sessions/Clients: `2cd72568b32a81e58320f515603f19d8`
- Transactions: `2cd72568b32a812387a1fbbbaa9ebd71`

## Stripe API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sync/stripe/payments` | POST | Sync Stripe payments to Notion |
| `/sync/stripe/subscriptions` | POST | Sync subscriptions to Notion |
| `/stripe/checkout` | POST | Create checkout session (returns URL) |
| `/stripe/prices` | GET | List configured price tiers |
| `/stripe/webhook` | POST | Webhook handler (auto-syncs on events) |

## Stripe Tiered Pricing

Default tiers (customizable via Stripe Dashboard):
- Single Session: $85
- 5-Pack: $400 ($80/session)
- 10-Pack: $750 ($75/session)
- Monthly Unlimited: $299/month

## Security Conventions

These patterns are enforced across the codebase (SonarCloud quality gate requires A rating):

- **No `str(e)` in user-facing output** — exception details must never leak to API responses, error messages, or CLI output. Use generic messages and log with `logger.exception()`.
- **No `Exception as e`** — use bare `except Exception:` with `logger.exception()` for stack traces in logs.
- **No env var names in error messages** — don't reveal internal config structure. Use generic `"Account not configured"`.
- **No internal state in API responses** — don't return environment values, config internals, or exception details.
- **No reflected user input** — never echo user-supplied query params or path segments back in responses.
- **URL-encode user input in paths** — use `urllib.parse.quote(value, safe='')` for any user-controlled value in URL path segments.
- **CORS restricted** — origins set via `APP_CORS_ORIGINS` env var or default to `https://square-notion-sync.vercel.app`. Never use `*`.
- **XSS prevention** — all client-side rendering uses DOM APIs (`textContent`, `createElement`). No `innerHTML` anywhere.
- **Input validation** — all `Query()` parameters with numeric ranges use `ge`/`le` bounds.
- **Per-request API keys** — Stripe uses `api_key=self._api_key` per call, not global `stripe.api_key`.
- **Server-controlled URLs** — checkout success/cancel URLs come from `APP_BASE_URL` env var, not user input.
- **Bind to localhost** — default host is `127.0.0.1`, not `0.0.0.0`.
