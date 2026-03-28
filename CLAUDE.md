# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (creates venv, installs requirements)
make install

# Check Square account connection status
make status

# Start FastAPI server (port 8000, auto-reload)
make server

# Run tests
make test

# CLI commands
python cli.py status
python cli.py customers -v
python cli.py transactions --days 7 -v
python cli.py export --output ./my-exports
python cli.py server --port 3000
```

## Architecture

This project syncs data from multiple Square accounts to Notion databases.

### Core Components

- **`cli.py`** - Main CLI entry point, delegates to `SquareMultiAccount` from `src/multi_account.py`
- **`src/multi_account.py`** - Core sync logic:
  - `SquareAccount` - Single account connection (handles auth, API calls)
  - `SquareMultiAccount` - Aggregates multiple accounts, loads config from env vars
- **`fastapi/app.py`** - REST API server wrapping the sync functionality
- **`fastapi/accounts.py`** - Square API helpers for customer/payment/order lookups
- **`fastapi/notion_helper.py`** - Notion API integration for upserting data

### Configuration

Environment variables loaded from `.env` (gitignored). Two patterns supported:

```bash
# Multi-account pattern (preferred)
ACCOUNT__{NAME}__TOKEN=...
ACCOUNT__{NAME}__LOCATION_ID=...
ACCOUNT__{NAME}__EMAIL=...

# Fallback single-account
SQUARE_ACCESS_TOKEN=...
```

Account names: `FITCLINIC_LLC`, `FITCLINIC`, `FITNESSWITHMIKE`

### Data Flow

1. `SquareMultiAccount._load_accounts_from_env()` reads env vars at init
2. Each account gets a `SquareAccount` instance with its own token/headers
3. Aggregation methods (`get_all_customers`, etc.) iterate accounts and merge results
4. Results tagged with `_source` field to identify originating account
5. Optional Notion sync via `notion_helper.upsert_connection_row()`

### API Endpoints

- `GET /health` - Health check with account count
- `GET /accounts` - List configured accounts and status
- `GET /customers` - All customers from all accounts
- `GET /transactions?days=30` - Recent transactions
- `POST /sync/customer/{id}` - Sync single customer to Notion
