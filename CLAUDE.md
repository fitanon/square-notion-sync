# CLAUDE.md

Project guide for AI assistants working on this codebase.

## Project Overview

**square-notion-sync** is a multi-account Square data synchronization system for The Fit Clinic businesses. It aggregates customer data, transactions, invoices, and orders from three Square accounts into unified dashboards via Notion and Zapier.

### Supported Square Accounts

| Business | Email | Env Prefix |
|----------|-------|------------|
| THE FIT CLINIC LLC | mike@thefitclinicsj.com | `ACCOUNT__FITCLINIC_LLC__` |
| FITCLINIC.IO | mike@fitclinic.io | `ACCOUNT__FITCLINIC__` |
| FITNESS WITH MIKE | shmockeyfit@gmail.com | `ACCOUNT__FITNESSWITHMIKE__` |

## Repository Structure

```
square-notion-sync/
├── cli.py                      # CLI entry point (argparse): status, customers, transactions, invoices, export, server
├── Makefile                    # Dev commands: install, status, customers, transactions, server, test, clean
├── requirements.txt            # Main deps: requests, python-dotenv, perplexityai, comet-ml
├── .env.example                # Template for all environment variables
├── install-perplexity.sh       # Venv creation + pip install script
│
├── src/
│   ├── multi_account.py        # Core engine: SquareAccount + SquareMultiAccount classes
│   └── callouts.py             # Example integrations: Square API, Perplexity AI, Comet ML
│
├── fastapi/
│   ├── app.py                  # FastAPI REST server (endpoints below)
│   ├── accounts.py             # Square API helper functions (single-customer operations)
│   ├── oauth.py                # Square OAuth 2.0 flow (start, callback, token listing)
│   ├── token_store.py          # File-based token persistence (fastapi/tokens.json)
│   ├── notion_helper.py        # Notion API integration (upsert pages to database)
│   ├── requirements.txt        # FastAPI deps: fastapi, uvicorn, cryptography
│   └── README.md               # FastAPI-specific setup docs
│
├── scripts/
│   ├── create_notion_page.py   # Creates Notion database with schema + sample row
│   └── square_examples.py      # Direct Square API CLI (payments, orders, customers, invoices, bookings)
│
├── README.md                   # Main project documentation
├── README-DEPLOY.md            # Deployment checklist and security notes
├── NOTION_SETUP.md             # Notion integration guide with curl examples
├── ZAPIER_SETUP_INSTRUCTIONS.md  # Zapier table + Zap setup (15 Zaps total)
└── ZAPIER_DASHBOARD_STRUCTURE.md # Zapier table schemas and dashboard layout
```

## Architecture & Data Flow

```
Square Accounts (3)
       │
       ▼
SquareMultiAccount (src/multi_account.py)
  - Loads accounts from ACCOUNT__*__ env vars
  - Aggregates data across all accounts
  - Tags every record with _source field
       │
       ├──► CLI (cli.py) ──► Terminal output / JSON export
       ├──► FastAPI (fastapi/app.py) ──► REST API / Notion sync
       └──► Zapier (manual setup) ──► Dashboard tables
```

### Core Classes

**`SquareAccount`** (`src/multi_account.py`) - Single account connection:
- Methods: `get_locations()`, `get_all_customers()`, `get_payments()`, `get_orders()`, `get_invoices()`
- Uses Square API version `2024-01-18`

**`SquareMultiAccount`** (`src/multi_account.py`) - Aggregator across accounts:
- Auto-discovers accounts from `ACCOUNT__{NAME}__TOKEN` env vars
- Falls back to single `SQUARE_ACCESS_TOKEN` if no multi-account vars present
- Methods: `get_all_customers()`, `get_all_transactions(days_back)`, `get_all_invoices()`, `get_summary()`
- All returned data includes `_source` field for traceability

## FastAPI Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check (env + account count) |
| GET | `/accounts` | List all accounts with status |
| GET | `/customers` | All customers across accounts |
| GET | `/customers/{source}` | Customers from specific account |
| GET | `/transactions` | Transactions (query: `days`, default 30) |
| GET | `/invoices` | All invoices |
| GET | `/summary` | Account summary |
| POST | `/sync/customer/{customer_id}` | Sync customer to Notion (query: `account_name`) |
| GET | `/connect/oauth/start` | Start Square OAuth flow (query: `account_name`) |
| GET | `/connect/oauth/callback` | OAuth callback handler |
| GET | `/connect/tokens` | List stored tokens (no secrets) |

Swagger UI available at `/docs` when server is running.

## CLI Commands

```bash
python cli.py status                     # Check account connections
python cli.py customers [-v]             # List customers (-v for verbose)
python cli.py transactions [-d DAYS] [-v] # List transactions (default 30 days)
python cli.py invoices [-v]              # List invoices
python cli.py export                     # Export to exports/summary_<timestamp>.json
python cli.py server [-p PORT]           # Start FastAPI server (default port 8000)
```

## Makefile Targets

```bash
make install        # Create venv, install all deps (requirements.txt + fastapi/requirements.txt + notion-client)
make status         # Run: python cli.py status
make customers      # Run: python cli.py customers -v
make transactions   # Run: python cli.py transactions -v
make invoices       # Run: python cli.py invoices -v
make export         # Run: python cli.py export
make server         # Run: python cli.py server -p 8000
make test           # Run pytest or fallback to python -m src.multi_account
make clean          # Remove exports/*.json and __pycache__
make setup          # Alias for install + print setup instructions
make help           # Show all targets
```

## Environment Variables

All configuration lives in `.env` (copy from `.env.example`). Key variables:

### Required
- `SQUARE_ENV` - `sandbox` or `production`

### Multi-Account (per account)
- `ACCOUNT__{NAME}__TOKEN` - Square access token
- `ACCOUNT__{NAME}__EMAIL` - Account email
- `ACCOUNT__{NAME}__LOCATION_ID` - Location ID (optional)

### Single Account Fallback
- `SQUARE_ACCESS_TOKEN` - Production token
- `SQUARE_SANDBOX_ACCESS_TOKEN` - Sandbox token

### Notion Integration (optional)
- `NOTION_TOKEN` - Notion integration bearer token
- `NOTION_DATABASE_ID` - Target database ID
- `NOTION_VERSION` - API version (default: `2022-06-28`)

### Square OAuth (optional)
- `SQUARE_APPLICATION_ID` - OAuth client ID
- `SQUARE_APPLICATION_SECRET` - OAuth client secret
- `SQUARE_OAUTH_REDIRECT_URI` - Callback URL (default: `http://localhost:8000/connect/oauth/callback`)

### Optional Integrations
- `PERPLEXITY_API_KEY` - Perplexity AI
- `COMET_API_KEY` - Comet ML experiment tracking
- `DRY_RUN` - Set `true` to skip real API calls

## Key Patterns & Conventions

### Source Tagging
All data returned from `SquareMultiAccount` includes a `_source` field identifying the originating account. Always preserve this when transforming data.

### Graceful Degradation
Optional integrations (Notion, Perplexity, Comet ML) check for their env vars at runtime and silently skip if not configured. Follow this pattern for new integrations.

### Error Isolation
Account-level errors do not halt multi-account operations. Errors are returned inline as error entries so other accounts continue processing.

### Pagination
Built into `get_all_customers()` via cursor-based pagination. Other endpoints use `limit` parameters. Large datasets may need similar pagination support.

### API Versions
- `src/multi_account.py` uses Square API `2024-01-18`
- `fastapi/accounts.py` uses Square API `2025-06-16`
- Keep these consistent when adding new endpoints.

## Development Workflow

```bash
# Initial setup
make install
cp .env.example .env
# Edit .env with tokens

# Verify connections
make status

# Run the API server
make server
# Open http://localhost:8000/docs

# Run tests
make test

# Clean up
make clean
```

## Security Notes

- `.env` is in `.gitignore` - never commit secrets
- Token storage in `fastapi/token_store.py` is plaintext JSON (prototype only; encrypt for production)
- CORS is set to `allow_origins=["*"]` in FastAPI - restrict for production
- OAuth scopes: PAYMENTS_READ, PAYMENTS_WRITE, INVOICES_READ, INVOICES_WRITE, CUSTOMERS_READ, ORDERS_READ, BOOKINGS_READ
- Revoke and rotate tokens immediately if exposed

## Known Limitations

1. **No test suite** - `make test` falls back to running the module directly; real tests should be added
2. **Notion upsert creates pages only** - No duplicate detection or update logic
3. **Pull-based sync only** - No webhook support for real-time updates
4. **Token store unencrypted** - `fastapi/tokens.json` stores tokens in plaintext
5. **Single location assumption** - Code allows one `LOCATION_ID` per account
6. **API version mismatch** - `src/` and `fastapi/` use different Square API versions
