# square-notion-sync v4

The Fit Clinic's unified data sync backend. Aggregates 3 Square POS accounts, syncs to Notion dashboards, handles Stripe payments, and serves a client portal.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  CLI (cli.py)           FastAPI (api/app.py)             │
│  ─ status               ─ /health, /config               │
│  ─ customers             ─ /sync/{financial,appts,sess}   │
│  ─ transactions          ─ /stripe/{prices,checkout,wh}   │
│  ─ export                ─ /portal/lookup                 │
│  ─ sync                  ─ /scheduler/{status,trigger}    │
│  ─ server                ─ /reports/{tandem,low-sessions} │
└─────────────┬────────────────────────┬───────────────────┘
              │                        │
      ┌───────▼────────────────────────▼──────────┐
      │              core/                         │
      │  config.py      — 3-account env loading    │
      │  accounts.py    — Square API client        │
      │  notion.py      — Notion API client        │
      │  stripe_client  — Stripe checkout/webhooks │
      │  scheduler.py   — APScheduler daily sync   │
      │  database.py    — Neon Postgres (optional)  │
      └───────┬────────────┬────────────┬──────────┘
              │            │            │
      ┌───────▼──┐  ┌──────▼──┐  ┌─────▼──────┐
      │ sync/    │  │ portal/ │  │ fastapi/   │
      │ financial│  │ HTML    │  │ (legacy)   │
      │ appts    │  │ staff   │  │ OAuth flow │
      │ sessions │  │ check-in│  │ token mgmt │
      │ stripe   │  │ QR API  │  └────────────┘
      └──────────┘  └─────────┘
```

- `core/` — Config, Square client (3 accounts), Notion client, Stripe client, scheduler, Postgres
- `sync/` — Financial, appointments, sessions, stripe_payments sync → Notion
- `api/app.py` — FastAPI with 18+ endpoints, API key auth, CORS whitelist
- `portal/` — Node.js client portal (check-in, QR, staff dashboard, client lookup)
- `fastapi/` — Legacy v1 code preserved for OAuth flow (Square token management)
- `cli.py` — Local CLI: status, customers, transactions, export, sync, server
- `scripts/` — One-off utilities (Notion page creation, Square examples, data import)
- `tests/` — 7 test files covering all critical bug fixes

## Square Accounts

| Code | Business | Location |
|------|----------|----------|
| PA | Physiques Anonymous | — |
| TFC | The Fit Clinic LLC | LPWXGKNG8E2W5 |
| FWM | Fitness With Mike | LV7FY976R8GJE (+4) |

## Data Flow

1. **Square → Notion**: Sync modules pull from 3 Square accounts, normalize, upsert to 5 Notion databases
2. **Stripe → Notion**: Webhook + manual sync for payment/session tracking
3. **Square → Postgres**: Optional fast-path for portal lookups
4. **Square → JSON**: CLI export for backups/BI
5. **Zapier → Tables**: 15 Zaps documented in ZAPIER_*.md (configured externally)

## Environment Variables

See `.env.example` for full list. Critical vars:

```
# Square (3 accounts)
SQUARE_PA_ACCESS_TOKEN, SQUARE_PA_LOCATION_ID
SQUARE_TFC_ACCESS_TOKEN, SQUARE_TFC_LOCATION_ID
SQUARE_FWM_ACCESS_TOKEN, SQUARE_FWM_LOCATION_ID

# Notion (5 databases)
NOTION_TOKEN
NOTION_DB_TRANSACTIONS, NOTION_DB_INVOICES, NOTION_DB_CLIENTS
NOTION_DB_APPOINTMENTS, NOTION_DB_SESSIONS

# Stripe
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
STRIPE_PRICE_1_SESSION, STRIPE_PRICE_5_SESSIONS
STRIPE_PRICE_10_SESSIONS, STRIPE_PRICE_MONTHLY

# Postgres (optional)
DATABASE_URL

# API Auth
API_SECRET_KEY
```

## Quick Start

```bash
make install        # Create venv + install Python/Node deps
cp .env.example .env  # Fill in your tokens
make status         # Verify Square connections
make server         # Start API at localhost:8000
```

## Git

- Use noreply email: `230304362+fitanon@users.noreply.github.com`
- Vercel deploys from this repo
- GitHub: `fitanon/square-notion-sync`

## Testing

```bash
make test           # Run full test suite (pytest)
```

7 test files cover: Stripe sync, webhook handling, API security (CORS + auth), portal lookup, database client, Postgres integration.

## Related Projects

- **TFC Portal** — `~/Projects/fitclinic-app/portals/` (Stripe billing at tfc-portal-ivory.vercel.app)
- **Client App** — `~/Projects/mobile app/Fit Clinic Client App V1/` (QR check-in, Neon DB)
- **Dashboard** — `~/Projects/fitclinic-app/dashboard-central/` (CentralTFC)
