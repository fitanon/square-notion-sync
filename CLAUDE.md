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
  stripe_payments.py → Stripe payment and subscription sync to Notion

api/            → FastAPI application
  app.py        → Main API routes for sync and reports
  index.py      → Vercel serverless entry point (client portal)

scripts/        → CLI tools
fastapi/        → Legacy prototype (deprecated)
```

## Key Commands

```bash
pip install -r requirements.txt      # Install dependencies
python run.py                        # Run API server (localhost:8000)
python run.py --reload               # Dev mode with auto-reload
pytest                               # Run all tests
pytest tests/test_sync.py -v         # Run specific test file
pytest -k "test_sessions"            # Run tests matching pattern
```

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
STRIPE_SECRET_KEY=sk_...             # Stripe API secret key
STRIPE_WEBHOOK_SECRET=whsec_...      # Webhook signing secret
STRIPE_PRICE_1_SESSION=price_...     # Single session price ID
STRIPE_PRICE_5_SESSIONS=price_...    # 5-pack price ID
STRIPE_PRICE_10_SESSIONS=price_...   # 10-pack price ID
STRIPE_PRICE_MONTHLY=price_...       # Monthly subscription price ID
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
