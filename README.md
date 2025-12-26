# Square → Notion Sync

Multi-account Square to Notion synchronization for fitness business management.

## Features

- **Multi-Account Support**: Sync data from 3 Square accounts (PA, TFC, FWM)
- **Daily Automated Sync**: Runs at 2am with configurable timezone
- **Manual Sync Trigger**: On-demand sync via API endpoints
- **3 Dashboard Types**:
  - **Financial**: Transactions, invoices, sales data
  - **Appointments**: Bookings, calendar, recurring events
  - **Sessions**: Client session tracking (purchased vs used)
- **Tandem Detection**: Highlights when 2+ clients have overlapping appointments
- **Trainer View**: Identifies clients with low remaining sessions

## Quick Start

### 1. Setup Environment

```bash
# Clone and navigate to repo
cd square-notion-sync

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API credentials
```

### 2. Configure Credentials

Edit `.env` with your credentials:

```bash
# Square Accounts
SQUARE_PA_ACCESS_TOKEN=sq0atp-...   # Physiques Anonymous
SQUARE_TFC_ACCESS_TOKEN=sq0atp-...  # The Fit Clinic
SQUARE_FWM_ACCESS_TOKEN=sq0atp-...  # Fitness With Mike

# Notion
NOTION_TOKEN=secret_...
NOTION_DB_CLIENTS=your-database-id
NOTION_DB_TRANSACTIONS=your-database-id
```

### 3. Run the API

```bash
python run.py
```

Server starts at `http://localhost:8000` with interactive docs at `/docs`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/sync/financial` | POST | Sync transactions & invoices |
| `/sync/appointments` | POST | Sync bookings with tandem detection |
| `/sync/sessions` | POST | Sync session tracking |
| `/sync/all` | POST | Run all syncs |
| `/scheduler/status` | GET | View scheduler status |
| `/scheduler/trigger` | POST | Trigger immediate sync |
| `/reports/low-sessions` | GET | Clients with low sessions |
| `/reports/tandem` | GET | Tandem appointments |

### Manual Sync Examples

```bash
# Sync all accounts
curl -X POST http://localhost:8000/sync/all

# Sync specific account
curl -X POST "http://localhost:8000/sync/financial?accounts=PA"

# Sync with date range
curl -X POST "http://localhost:8000/sync/financial?days_back=60"

# Trigger scheduled sync now
curl -X POST http://localhost:8000/scheduler/trigger
```

## Project Structure

```
square-notion-sync/
├── core/                    # Core library
│   ├── config.py           # Multi-account configuration
│   ├── accounts.py         # Square API client
│   ├── notion.py           # Notion API client
│   └── scheduler.py        # APScheduler for daily sync
│
├── sync/                    # Sync modules
│   ├── financial.py        # Dashboard 1: Transactions/Invoices
│   ├── appointments.py     # Dashboard 2: Bookings/Calendar
│   └── sessions.py         # Dashboard 3: Session tracking
│
├── api/                     # FastAPI application
│   └── app.py              # API routes and lifecycle
│
├── scripts/
│   ├── import_data.py      # Import CSV/JSON data files
│   └── square_examples.py  # Square API examples
│
├── run.py                   # Run the API server
├── requirements.txt
├── .env.example
└── ARCHITECTURE.md          # Detailed architecture docs
```

## Data Import

Import existing data from CSV files:

```bash
# Import customers
python scripts/import_data.py --file customers.csv --type customers --account PA

# Import transactions
python scripts/import_data.py --file transactions.csv --type transactions --account PA

# Dry run (preview without changes)
python scripts/import_data.py --file data.csv --dry-run
```

## Square Accounts

| Code | Business | Status |
|------|----------|--------|
| PA | Physiques Anonymous | Primary |
| TFC | The Fit Clinic LLC | Active |
| FWM | Fitness With Mike | Legacy |

## Notion Database Structure

### Client Tracker (Main Database)

| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Client full name |
| Square ID | Text | Square customer ID |
| Account | Select | PA / TFC / FWM |
| Email | Email | Contact email |
| Phone | Phone | Contact phone |
| Sessions Purchased | Number | Total sessions bought |
| Sessions Used | Number | Completed appointments |
| Sessions Remaining | Formula | Purchased - Used |
| Last Payment Date | Date | Most recent payment |
| Last Payment Amount | Number | Amount of last payment |
| Tandem | Checkbox | Has overlapping sessions |
| Status | Select | Active / Low Sessions / Needs Package |

## Sync Schedule

- **Daily Sync**: 2:00 AM (configurable via `SYNC_SCHEDULE_HOUR`)
- **Timezone**: America/New_York (configurable via `SYNC_TIMEZONE`)
- **Manual Override**: POST to `/scheduler/trigger` anytime

## Development

```bash
# Run with auto-reload
python run.py --reload

# Run tests
pytest

# Check API docs
open http://localhost:8000/docs
```

## Security

- Never commit `.env` to git
- Store production secrets in environment variables or secrets manager
- OAuth tokens are stored encrypted when using production deployment

## License

Private - Physiques Anonymous
