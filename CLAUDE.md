# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
make install            # Create venv + install all deps
make server             # Start FastAPI on port 8000 (Swagger at /docs)
make status             # Verify Square account connections
make test               # pytest tests/ or fallback to python -m src.multi_account
make clean              # Remove exports/*.json and __pycache__
```

All make targets activate `venv/` automatically. For direct use: `source venv/bin/activate`.

CLI usage: `python cli.py {status,customers,transactions,invoices,export,server}` with optional `-v` (verbose) and `-d DAYS` (transactions).

## Architecture

**Two-layer design**: `SquareAccount` wraps a single Square API connection; `SquareMultiAccount` aggregates three accounts and tags every record with `_source` for traceability.

```
Square Accounts (3) → SquareMultiAccount (src/multi_account.py)
                            ├── CLI (cli.py)
                            └── FastAPI (fastapi/app.py) → Notion sync (fastapi/notion_helper.py)
```

- **src/multi_account.py** — Core engine. `SquareMultiAccount` auto-discovers accounts from `ACCOUNT__{NAME}__TOKEN` env vars (hardcoded list: FITCLINIC_LLC, FITCLINIC, FITNESSWITHMIKE). Falls back to single `SQUARE_ACCESS_TOKEN`.
- **fastapi/app.py** — REST API. Instantiates one global `SquareMultiAccount`, exposes `/customers`, `/transactions`, `/invoices`, `/summary`. POST `/sync/customer/{id}` fetches from Square and upserts to Notion.
- **fastapi/accounts.py** — Single-customer Square API helpers (get_customer, find_by_email, last_payment, orders, bookings). Uses a **different** API version (`2025-06-16`) than core (`2024-01-18`).
- **fastapi/oauth.py** — OAuth 2.0 flow mounted as FastAPI router at `/connect/oauth/*`.
- **fastapi/notion_helper.py** — Creates Notion pages. Silently skips if `NOTION_TOKEN`/`NOTION_DATABASE_ID` not set.

## Key Conventions

- **Source tagging**: All aggregated data must include `_source` (account display name) and `_source_email`. Preserve these when transforming data.
- **Error isolation**: Account-level errors are caught and returned inline (as error entries in the list), never halt the full aggregation loop.
- **Graceful degradation**: Optional integrations (Notion, Perplexity, Comet ML) check env vars at runtime and skip silently. Follow this pattern for new integrations.
- **Pagination**: Only `get_all_customers()` handles cursor-based pagination. Other endpoints use simple `limit` params.

## Environment Variables

Config lives in `.env` (copy `.env.example`). Required: `SQUARE_ENV` (sandbox/production). Per-account: `ACCOUNT__{NAME}__TOKEN`, `ACCOUNT__{NAME}__EMAIL`, `ACCOUNT__{NAME}__LOCATION_ID`. Optional: `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `SQUARE_APPLICATION_ID`/`SECRET` (OAuth), `PERPLEXITY_API_KEY`, `COMET_API_KEY`, `DRY_RUN`.

## Known Issues

- **API version mismatch**: `src/multi_account.py` uses `2024-01-18`, `fastapi/accounts.py` uses `2025-06-16` — keep in mind when adding endpoints.
- **No real test suite**: `make test` falls back to running the module directly if no `tests/` directory exists.
- **Notion creates only**: `upsert_connection_row` always creates new pages — no duplicate detection or update logic.
- **Token store is plaintext**: `fastapi/tokens.json` via `token_store.py`.
