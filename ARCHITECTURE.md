# Square → Notion Sync Architecture

## Overview

This is the **core library** for syncing Square data to Notion databases. It provides reusable components that are consumed by three lightweight dashboard repositories.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REPOSITORY STRUCTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  square-notion-core (THIS REPO)                                             │
│  ├── Multi-account Square API client                                        │
│  ├── Notion API client with schema management                               │
│  ├── Scheduler infrastructure (2am daily + manual trigger)                  │
│  ├── Data transformers and validators                                       │
│  └── Shared utilities (logging, error handling, retry logic)                │
│                                                                              │
│           ▼                    ▼                    ▼                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ dashboard-      │  │ dashboard-      │  │ dashboard-      │              │
│  │ financial       │  │ appointments    │  │ sessions        │              │
│  │                 │  │                 │  │                 │              │
│  │ • Transactions  │  │ • Bookings      │  │ • Session count │              │
│  │ • Invoices      │  │ • Appointments  │  │ • Purchased qty │              │
│  │ • Sales data    │  │ • Calendar      │  │ • Used count    │              │
│  │ • Revenue       │  │ • Recurring     │  │ • Tandem detect │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Square Accounts

| Account Code | Business Name        | Status   | Environment |
|--------------|----------------------|----------|-------------|
| `PA`         | Physiques Anonymous  | Primary  | Production  |
| `TFC`        | The Fit Clinic LLC   | Active   | Production  |
| `FWM`        | Fitness With Mike    | Legacy   | Production  |

## Data Flow

### Dashboard 1: Financial (Transactions/Invoices/Sales)

```
Square APIs                          Notion Database
─────────────                        ───────────────
GET /v2/payments      ───────────►   Transactions Table
GET /v2/invoices      ───────────►   Invoices Table
GET /v2/orders        ───────────►   Sales/Orders Table

Views: [PA] [TFC] [FWM] [All]
```

**Data synced:**
- Payment ID, Amount, Currency, Status, Created At
- Invoice ID, Customer, Amount Due, Status, Due Date
- Order ID, Line Items, Total, Fulfillment Status

### Dashboard 2: Appointments/Bookings

```
Square APIs                          Notion Database
─────────────                        ───────────────
GET /v2/bookings      ───────────►   Appointments Table
GET /v2/team-members  ───────────►   (join for staff info)
Calendar integration  ───────────►   Recurring Events

Views: [PA] [TFC] [FWM] [All] [This Week] [Confirmed]
```

**Data synced:**
- Booking ID, Customer, Staff Member, Start/End Time
- Status (Pending, Confirmed, Checked Out, Cancelled)
- Recurring: Each occurrence as separate row
- Location, Service Type

### Dashboard 3: Session Tracking (Complex)

```
Square APIs                          Notion Database
─────────────                        ───────────────
GET /v2/orders        ──┐
  (item_variations)     ├─────────►   Client Sessions Table
GET /v2/bookings      ──┘
  (confirmed+checked)

Computed Fields:
- Sessions Purchased = SUM(order line items for "One-on-One 60")
- Sessions Used = COUNT(bookings where status=checked_out)
- Sessions Remaining = Purchased - Used
- Tandem = true if same day+time as another client
```

**Special handling:**
- Recurring appointments: Expand each occurrence into separate records
- Tandem detection: Flag when 2+ clients have overlapping appointment times
- Session types: Track "One-on-One 60" (or other package names)

## Sync Schedule

```
┌─────────────────────────────────────────────────────────────┐
│                    SYNC SCHEDULE                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Daily Automated Sync: 2:00 AM (local timezone)            │
│  ─────────────────────────────────────────────              │
│  • Runs all 3 dashboards sequentially                       │
│  • Fetches data from all 3 Square accounts                  │
│  • Updates Notion databases                                 │
│  • Logs results to sync history                             │
│                                                             │
│  Manual Trigger: POST /sync/trigger                         │
│  ───────────────────────────────                            │
│  • Optional: specify dashboard (financial/appointments/     │
│              sessions)                                      │
│  • Optional: specify account (PA/TFC/FWM/all)               │
│  • Returns sync status and any errors                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Environment Variables

```bash
# ─────────────────────────────────────────────────────────────
# SQUARE ACCOUNTS (3 accounts, production)
# ─────────────────────────────────────────────────────────────
SQUARE_ENV=production

# Physiques Anonymous (Primary)
SQUARE_PA_ACCESS_TOKEN=sq0atp-...
SQUARE_PA_LOCATION_ID=...

# The Fit Clinic LLC
SQUARE_TFC_ACCESS_TOKEN=sq0atp-...
SQUARE_TFC_LOCATION_ID=...

# Fitness With Mike
SQUARE_FWM_ACCESS_TOKEN=sq0atp-...
SQUARE_FWM_LOCATION_ID=...

# ─────────────────────────────────────────────────────────────
# NOTION
# ─────────────────────────────────────────────────────────────
NOTION_TOKEN=secret_...
NOTION_VERSION=2022-06-28

# Database IDs (one per dashboard table)
NOTION_DB_TRANSACTIONS=...
NOTION_DB_INVOICES=...
NOTION_DB_CLIENTS=...
NOTION_DB_APPOINTMENTS=...
NOTION_DB_SESSIONS=...

# ─────────────────────────────────────────────────────────────
# SYNC CONFIG
# ─────────────────────────────────────────────────────────────
SYNC_TIMEZONE=America/New_York
SYNC_SCHEDULE_HOUR=2
SYNC_SCHEDULE_MINUTE=0

# Session tracking config
SESSION_ITEM_NAME="One-on-One 60"  # Item name to count as sessions
```

## Notion Database Schemas

### Client Tracker (Main Database)

Based on your existing structure, the schema should include:

| Property | Type | Description |
|----------|------|-------------|
| Name | Title | Client full name |
| Email | Email | Contact email |
| Phone | Phone | Contact phone |
| Account | Select | PA / TFC / FWM |
| Sessions Purchased | Number | Total sessions bought |
| Sessions Used | Number | Completed appointments |
| Sessions Remaining | Formula | Purchased - Used |
| Last Payment Date | Date | Most recent payment |
| Last Payment Amount | Number | Amount of last payment |
| Last Appointment | Date | Most recent appointment |
| Next Appointment | Date | Upcoming appointment |
| Tandem | Checkbox | Has overlapping sessions |
| Trainer | Relation | Link to trainers table |
| Status | Select | Active / Inactive / Paused |
| Notes | Rich Text | Additional notes |

### Views

1. **Transaction View**: Last Payment Date, Amount, Details
2. **All Clients View**: All data shown
3. **Trainer View**: Clients with low remaining sessions
4. **Contact View**: Contact info only
5. **Chart View**: Aggregated data for visualization

## File Structure (Core Library)

```
square-notion-core/
├── core/
│   ├── __init__.py
│   ├── accounts.py          # Multi-account Square API client
│   ├── notion.py             # Notion API client
│   ├── scheduler.py          # APScheduler for 2am sync
│   ├── transformers.py       # Data transformation logic
│   └── config.py             # Configuration management
│
├── sync/
│   ├── __init__.py
│   ├── base.py               # Base sync class
│   ├── financial.py          # Dashboard 1 sync logic
│   ├── appointments.py       # Dashboard 2 sync logic
│   └── sessions.py           # Dashboard 3 sync logic
│
├── api/
│   ├── __init__.py
│   ├── app.py                # FastAPI application
│   ├── routes/
│   │   ├── health.py
│   │   ├── sync.py           # Manual sync triggers
│   │   └── oauth.py          # OAuth flow
│   └── middleware.py
│
├── scripts/
│   ├── setup_notion.py       # Create/verify Notion databases
│   ├── test_connection.py    # Verify API credentials
│   └── import_data.py        # Import historical data files
│
├── tests/
│   ├── test_accounts.py
│   ├── test_notion.py
│   └── test_sync.py
│
├── requirements.txt
├── .env.example
├── docker-compose.yml        # For scheduled sync
└── README.md
```

## Recurring Appointment Handling

Square treats recurring appointments differently. Here's how we handle them:

```python
# Each occurrence is treated as a separate appointment
# Example: Weekly Monday 10am recurring appointment

Square returns:
{
    "booking_id": "abc123",
    "start_at": "2025-01-06T10:00:00Z",  # First occurrence
    "recurring_booking_id": "recurring_xyz",
    "status": "ACCEPTED"
}

We expand and track EACH occurrence:
├── 2025-01-06 10:00 → Appointment record 1
├── 2025-01-13 10:00 → Appointment record 2
├── 2025-01-20 10:00 → Appointment record 3
└── ...

Each must be "Confirmed + Checked Out" to count as completed.
```

## Tandem Detection Logic

```python
def detect_tandem(appointments: List[Appointment]) -> List[Appointment]:
    """
    Mark appointments as tandem if 2+ clients have overlapping times.

    Tandem = True when:
    - Same date
    - Overlapping time window (start_time within 15 min of another)
    - Different clients
    """
    # Group by date
    by_date = group_appointments_by_date(appointments)

    for date, appts in by_date.items():
        # Sort by start time
        sorted_appts = sorted(appts, key=lambda x: x.start_time)

        for i, appt in enumerate(sorted_appts):
            # Check if any other appointment overlaps
            for other in sorted_appts:
                if appt.client_id != other.client_id:
                    if times_overlap(appt, other, threshold_minutes=15):
                        appt.tandem = True
                        other.tandem = True

    return appointments
```

## Next Steps

1. **Share API Credentials**: Provide tokens for all 3 Square accounts + Notion
2. **Share Data Files**: Upload the zip file for historical import
3. **Confirm Schema**: Share Notion database column names for exact mapping
4. **Deploy**: Set up scheduled sync (Docker, Railway, or serverless)
