# CLAUDE.md

## Project Overview

**Square → Notion Sync** — Multi-account Square to Notion sync for fitness business management.

Syncs data from 3 Square accounts (Physiques Anonymous, The Fit Clinic, Fitness With Mike) into Notion databases on a daily schedule (2am) with manual trigger support.

## Architecture

```
core/           → Core library (Square API client, Notion client, scheduler)
sync/           → Sync modules (financial, appointments, sessions)
api/            → FastAPI application with endpoints
scripts/        → CLI tools (data import, Square API examples)
fastapi/        → Legacy prototype (being replaced by core/ + api/)
```

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API server
python run.py

# Run with auto-reload (development)
python run.py --reload

# Import data from CSV files
python scripts/import_data.py --file data.csv --type customers --account PA

# Run tests
pytest
```

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `SQUARE_PA_ACCESS_TOKEN`, `SQUARE_TFC_ACCESS_TOKEN`, `SQUARE_FWM_ACCESS_TOKEN` — Square API tokens
- `NOTION_TOKEN` — Notion integration token
- `NOTION_DB_CLIENTS`, `NOTION_DB_TRANSACTIONS` — Notion database IDs

## API Endpoints

- `POST /sync/financial` — Sync transactions & invoices
- `POST /sync/appointments` — Sync bookings with tandem detection
- `POST /sync/sessions` — Sync session tracking (purchased vs used)
- `POST /sync/all` — Run all syncs
- `POST /scheduler/trigger` — Trigger immediate sync
- `GET /scheduler/status` — View next run times
- `GET /reports/low-sessions` — Clients with low sessions
- `GET /reports/tandem` — Tandem appointments

## Code Conventions

- Python 3.10+
- Type hints on all function signatures
- Dataclasses for data models (Payment, Customer, Booking, Order, Invoice)
- `upsert_page()` returns `tuple[Dict, bool]` where bool = was_created
- Multi-account: always iterate all 3 accounts unless filtered
- Bulk-fetch data before processing to avoid N+1 API calls
- Status constants defined at module level, not inline strings

## Square Account Codes

| Code | Business | Status |
|------|----------|--------|
| PA | Physiques Anonymous | Primary |
| TFC | The Fit Clinic LLC | Active |
| FWM | Fitness With Mike | Legacy |

## Notion Database IDs (from URLs)

- Clients: `2cd72568b32a81e58320f515603f19d8`
- Transactions: `2cd72568b32a812387a1fbbbaa9ebd71`
