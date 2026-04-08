# square-notion-sync v4

Unified data backend for **The Fit Clinic**. Aggregates 3 Square POS accounts, syncs to Notion dashboards, handles Stripe session payments, and serves a client check-in portal.

## What's In v4

v4 is a consolidation of v1–v3. The best parts of each version, merged and cleaned:

| From | What |
|------|------|
| **v3** | Core library (config, accounts, notion, stripe, scheduler, database), sync modules, FastAPI with 18+ endpoints, tests (53), portal, architecture docs |
| **v1/v2** | CLI tool (updated for v4 core), Makefile, Zapier documentation (15 Zaps, 5 tables), OAuth flow |
| **Removed** | Duplicate worktrees, venv dirs, node_modules, Perplexity/Comet integrations, portal credentials, stale callouts.py |

All 7 critical bugs from v3 were already fixed. CLAUDE.md updated to reflect current state.

## Setup

```bash
# 1. Install dependencies
make install

# 2. Configure environment
cp .env.example .env
# Fill in Square tokens, Notion token, Stripe keys (see .env.example)

# 3. Verify connections
source venv/bin/activate
make status
```

## Usage

### CLI Commands

```bash
make status          # Check all 3 Square account connections
make customers       # List customers across all accounts
make transactions    # List recent payments with totals
make export          # Dump data to timestamped JSON files in exports/
```

### Sync to Notion

```bash
make sync            # Full sync (financial + appointments + sessions)
make sync-fin        # Financial only (transactions + invoices)
make sync-appts      # Appointments only (with tandem detection)
make sync-sessions   # Sessions only (purchased vs used tracking)
```

### API Server

```bash
make server          # Start on localhost:8000
```

Key endpoints:
- `GET /health` — status check
- `POST /sync/all` — trigger full sync
- `GET /portal/lookup?email=...` — client session balance
- `POST /stripe/checkout` — create Stripe Checkout session
- `POST /stripe/webhook` — handle Stripe events
- `GET /reports/low-sessions` — clients running low
- `GET /reports/tandem` — tandem appointment report
- `GET /docs` — interactive API documentation

All sync/report endpoints require `X-API-Key` header (set `API_SECRET_KEY` in .env).

### Portal

```bash
make portal          # Start Node.js portal on localhost:3000
```

Client-facing portal with QR check-in, staff dashboard, and session lookup. Backed by Google Sheets.

## Project Structure

```
square-notion-sync/
├── cli.py              # CLI: status, customers, transactions, export, sync, server
├── Makefile            # Quick commands (make help)
├── run.py              # Uvicorn entry point
├── vercel.json         # Vercel deployment config
├── requirements.txt    # Python dependencies (14 packages)
│
├── core/               # Shared library
│   ├── config.py       # Multi-account env loading
│   ├── accounts.py     # Square API client (SquareClient + MultiAccountClient)
│   ├── notion.py       # Notion API client
│   ├── stripe_client.py # Stripe checkout/webhooks (4 tiers)
│   ├── scheduler.py    # APScheduler for daily sync
│   └── database.py     # Neon Postgres (optional fast-path)
│
├── sync/               # Notion sync modules
│   ├── base.py         # BaseSync + SyncResult
│   ├── financial.py    # Transactions + invoices
│   ├── appointments.py # Bookings + tandem detection
│   ├── sessions.py     # Session tracking (purchased vs used)
│   └── stripe_payments.py # Stripe → Notion
│
├── api/                # FastAPI backend (18+ endpoints)
│   ├── app.py          # Main application
│   └── index.py        # Vercel entry point
│
├── portal/             # Node.js client portal
│   ├── server.js       # Express server
│   ├── api/            # Vercel serverless functions
│   ├── staff/          # Staff dashboard
│   └── client/         # Client home
│
├── fastapi/            # Legacy v1 code (OAuth flow, token management)
│   ├── oauth.py        # Square OAuth 3-legged flow
│   └── token_store.py  # Token persistence
│
├── scripts/            # One-off utilities
│   ├── create_notion_page.py
│   ├── import_data.py
│   └── square_examples.py
│
├── tests/              # 7 test files, 53 tests
│
├── docs/               # Architecture & specs
│   ├── architecture-v4.html    # Interactive visual diagram
│   └── tfc-ecosystem-map.html  # Full ecosystem overview
│
├── ZAPIER_SETUP_INSTRUCTIONS.md  # 15 Zaps setup guide
├── ZAPIER_DASHBOARD_STRUCTURE.md # 5 table schemas
├── NOTION_SETUP.md               # Notion integration guide
└── CLAUDE.md                     # Dev instructions for AI assistants
```

## Deployment

Deployed on **Vercel** (`square-notion-sync.vercel.app`):
- Python API routes → Vercel Functions
- Portal HTML → Static CDN
- Env vars managed via `vercel env`

## Square Accounts

| Code | Business | Status |
|------|----------|--------|
| PA | Physiques Anonymous | Primary |
| TFC | The Fit Clinic LLC | Active |
| FWM | Fitness With Mike | Active (5 locations) |

## Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| v1 | Jan 10, 2026 | Initial: CLI + FastAPI + 3 Square accounts + Zapier docs |
| v2 | Jan 12, 2026 | README + git init (functionally identical to v1) |
| v3 | Mar–Apr 2026 | Major rewrite: core/, sync/, Stripe, scheduler, portal, Postgres, tests |
| **v4** | **Apr 8, 2026** | **Consolidated best of v1–v3: CLI restored, Zapier docs rescued, bugs verified fixed, bloat removed** |
