# TFC Ecosystem Consolidation — Design Spec
**Date:** 2026-04-02
**Status:** Approved
**Author:** Claude + Mike

---

## Problem Statement

The Fit Clinic has 10+ Vercel deployments, 4 data sources (Google Sheets, Notion, MySQL, Square), and massive overlap between projects. Most custom-domain deployments return 504. The operational system (Google Sheets + QR check-in) is disconnected from the web portals. There is no single source of truth.

## Goals

1. **One database** (Neon Postgres) as the unified data store
2. **Two portals** — tfc-c (client) and tfc-s (staff) — replacing 10+ broken deployments
3. **Keep Google Sheets working** — it's the live operational system
4. **Fix critical bugs** in square-notion-sync before adding features
5. **Wire everything together** — Sheets ↔ Postgres ↔ Square ↔ Stripe ↔ Notion

## Architecture

### Data Flow

```
Google Sheets (Members, Check-Ins, Session Logs)
    ↕ (Google Sheets API — SA key exists in tfc-dashboard/.env.local)
Neon Postgres (unified store)
    ↕ (sync jobs)
Square API (payments, invoices, customers, bookings — 3 accounts)
    ↕
Stripe (checkout sessions, subscriptions, webhooks)
    ↕
Notion (Session Logs DB, All Clients DB — dashboard layer, optional)
```

### Postgres Schemas

```sql
-- Maps to project sections and audience
CREATE SCHEMA clients;    -- Client-facing data (tfc-c reads from here)
CREATE SCHEMA staff;      -- Staff-facing data (tfc-s reads from here)
CREATE SCHEMA square;     -- Raw Square API data (3 accounts)
CREATE SCHEMA stripe;     -- Raw Stripe data
CREATE SCHEMA sessions;   -- Session tracking, check-ins, QR logs
```

#### Key Tables

**clients schema:**
- `clients.profiles` — name, email, phone, square_id, status (Active/Inactive/Lead)
- `clients.session_balance` — VIEW joining purchases + completed bookings
- `clients.purchases` — Stripe checkout records (migrated from tfc-pay MySQL)

**staff schema:**
- `staff.users` — staff logins, roles (migrated from tfc-pay MySQL users table)
- `staff.pay_rates` — trainer × session type → pay rate
- `staff.payroll_periods` — bi-weekly periods

**square schema:**
- `square.customers` — all customers from 3 accounts
- `square.payments` — all transactions
- `square.invoices` — all invoices
- `square.bookings` — all appointments
- `square.orders` — all orders with line items

**stripe schema:**
- `stripe.checkout_sessions` — all checkout records
- `stripe.subscriptions` — active subscriptions
- `stripe.webhook_events` — raw event log for debugging

**sessions schema:**
- `sessions.check_ins` — QR check-in log (synced from Google Sheets)
- `sessions.trainer_logs` — per-trainer session data (from 10 trainer sheets)
- `sessions.packages` — purchased packages and remaining count

### Portals

**tfc-c (Client Home)** — `clients.fitclinic.io`
- Session balance lookup (phone/email)
- Purchase sessions (Stripe Checkout — existing 4 tiers)
- QR check-in status
- View upcoming appointments
- No login required for balance lookup; Stripe handles payment auth

**tfc-s (Staff Home)** — `staff.fitclinic.io`
- All clients overview (By Trainer board view)
- Session alerts (low sessions, overdue visits)
- Payroll dashboard (date-range interactive, mirrors Google Sheets)
- Tandem detection report
- Requires authentication (API key or staff login)

**tfc (Landing Hub)** — `fitclinic.io`
- Simple page with two buttons: "I'm a Client" → tfc-c, "I'm Staff" → tfc-s
- Marketing content, contact info

### Backend

**square-notion-sync** remains the single API backend, enhanced with:
- Neon Postgres connection (via `DATABASE_URL`)
- Google Sheets sync endpoints (using existing SA credentials)
- Authentication middleware on admin endpoints
- Fixed CORS, fixed Stripe webhook handling, fixed portal lookup

### What Gets Killed

| Deployment | Action | Reason |
|---|---|---|
| tfc-dashboard-coral.vercel.app | KILL | Empty project, returns 504 |
| fitclinic-session-history.vercel.app | KILL | Replaced by tfc-s |
| chat.fitclinic.io | KILL | Returns 504, no backend |
| vibe-coding-platform | KILL | Experiment, returns 401 |
| All 9 Manus deployments | KEEP as archive | They're on Manus, not costing Vercel resources |
| Dead package calculator files | DELETE | `package-calc.tsx`, `package-calculator.tsx`, empty `prices/` |

### What Gets Fixed (Critical Bugs)

1. `sync/stripe_payments.py:96` — wrong param name `filter_props` → `filter_`
2. `sync/stripe_payments.py:104` — tuple destructuring `existing[0]["id"]` → `pages[0].id`
3. `core/stripe_client.py:177` — monthly unlimited `sessions_purchased=0` → `None` for unlimited
4. `api/app.py:113-119` — CORS `*` with credentials → whitelist origins
5. `api/app.py` — add API key auth on admin endpoints
6. `api/app.py:395-403` — webhook error handling (separate signature verification from sync)
7. `api/app.py:436-471` — portal lookup O(n) → use Square SearchCustomers API

### Package Calculator Status

| Item | Action |
|---|---|
| `fitclinic-package-calculator.vercel.app` | KEEP (listed as Active) |
| `v1 - fullpricelist/` (has index.html) | KEEP if it works, otherwise delete |
| `package-calc.tsx` (standalone, no build) | DELETE |
| `package-calculator.tsx` (standalone, no build) | DELETE |
| `prices/` (empty) | DELETE |
| `All Prices/allpriceproject/` | CHECK then decide |
| Price Book PDF/XLSX/DOCX | KEEP as reference |

## Implementation Order

1. Fix 7 critical bugs (TDD — write test, watch fail, fix, watch pass)
2. Provision Neon Postgres via Vercel Marketplace
3. Create schemas + tables with Drizzle migrations
4. Add Google Sheets sync to square-notion-sync
5. Build tfc-c portal (client-facing, pulls from Postgres)
6. Build tfc-s portal (staff-facing, pulls from Postgres)
7. Build tfc landing hub
8. Wire custom domains
9. Kill broken deployments
10. Delete dead package calculator files

## Success Criteria

- Client can look up session balance in < 2 seconds (not O(n) API calls)
- Staff can see all-clients dashboard with real-time data
- QR check-ins sync to Postgres within 5 minutes
- Monthly unlimited subscribers see "Unlimited" not "0 remaining"
- All admin endpoints require authentication
- Zero 504 errors on active custom domains
