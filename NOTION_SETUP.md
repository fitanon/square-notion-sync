v# Notion setup & Square → Notion integration

This document explains how to create a Notion database for Square account syncs, how to run a helper script to create the DB + sample entry, and includes copy-paste terminal commands to fetch Square data (payments, orders, invoices, customers, bookings).

---

## What this contains

- A ready-to-run Python script `scripts/create_notion_page.py` that:
  - Creates a Notion database under a `PARENT_PAGE_ID` (if provided).
  - Inserts a sample page/row representing a connection for one Square account.
  - Prints created `database_id` and `page_id` for you to wire into automation.

- A helper script `scripts/square_examples.py` with short functions and example usage to fetch data from Square's APIs.

- Exact `curl` commands you can copy/paste to fetch data for each Square account (sandbox and production variants shown).

---

## Notion: quick background & required permissions

1. Create an integration in Notion (https://www.notion.so/my-integrations). Copy the Integration Token (secret). Set it as `NOTION_TOKEN` in your environment. Keep it secret.
2. Create or choose a parent page in your Notion workspace where the DB will be created. Open that page in a browser and copy the page id from the URL; set it as `PARENT_PAGE_ID`.
3. Invite the integration to the parent page (Share → Invite → select your integration). This is required so that the integration can create a database under the page.

Required Notion permission for the integration: write access to the parent page / database.

---

## Notion database schema (what `create_notion_page.py` will create)

Properties:
- Name (Title) — the human-friendly label (e.g., "ShmockeyFit - Main Location")
- Square Account ID (rich_text)
- Square Environment (select) — options: sandbox, production
- Data Type (multi-select) — e.g., Payments, Orders, Invoices, Bookings, Customers
- Last Synced (date)
- Connection URL (url) — optional link to management console
- Notes (rich_text)

This schema is intentionally minimal and useful for automated sync status and manual inspection.

---

## Setup local env (example)

Run these in your terminal (zsh):

```bash
cd /Users/mike/my-react-app/square-callouts-starter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables (example placeholders):

```bash
export NOTION_TOKEN="secret_notion_token_here"
export PARENT_PAGE_ID="your_parent_page_id_here"
# For Square examples below (only if you want to run the Python fetch examples):
export SQUARE_ACCESS_TOKEN="sq0atp-REPLACE-WITH-YOUR-TOKEN"
export SQUARE_ENV="sandbox" # or production
export SQUARE_API_VERSION="2025-06-16" # optional override
export SQUARE_LOCATION_ID="replace_location_id_if_needed"
```

---

## How to create the Notion DB and a sample connection row (one-shot)

1. Ensure `NOTION_TOKEN` and `PARENT_PAGE_ID` are set in env.
2. Run the helper script:

```bash
python3 scripts/create_notion_page.py
```

The script prints the `database_id` and `sample_page_id` on success. Save those for your automation.

---

## Example Notion REST call (curl) — create a page in an existing DB

Replace `DATABASE_ID` and `NOTION_TOKEN`:

```bash
curl -X POST 'https://api.notion.com/v1/pages' \
  -H 'Authorization: Bearer $NOTION_TOKEN' \
  -H 'Content-Type: application/json' \
  -H 'Notion-Version: 2022-06-28' \
  -d '{
    "parent": {"database_id": "DATABASE_ID"},
    "properties": {
      "Name": {"title":[{"text":{"content":"Sample Account"}}]},
      "Square Account ID": {"rich_text":[{"text":{"content":"sq-account-123"}}]},
      "Square Environment": {"select":{"name":"sandbox"}},
      "Data Type": {"multi_select":[{"name":"Payments"}]},
      "Last Synced": {"date":{"start":"2025-12-08T00:00:00Z"}}
    }
  }'
```

---

## Square quick reference: auth models & recommended scopes

Two common ways to access a Square account:

A) Developer / Server Personal Token (quickest when you control the account):
- Obtain a personal access token from the Developer Dashboard (or use a sandbox token).
- Use the Bearer token in Authorization headers.
- Token example env var name: `SQUARE_ACCESS_TOKEN`.

B) OAuth (recommended for multiple external business accounts you do not own):
- Build an OAuth flow using Square's OAuth endpoints.
- Required OAuth scopes (examples):
  - PAYMENTS_READ, PAYMENTS_WRITE (if writing),
  - ORDERS_READ, ORDERS_WRITE,
  - INVOICES_READ, INVOICES_WRITE,
  - CUSTOMERS_READ, BOOKINGS_READ
- Store the returned access token securely and refresh as recommended.

---

## Copy-paste curl commands to fetch data (replace tokens and ids)

Note: use `https://connect.squareupsandbox.com` for sandbox and `https://connect.squareup.com` for production.

Payments (last 7 days):

```bash
BEGIN=$(date -v-7d -u +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

curl -s -X GET "https://connect.squareupsandbox.com/v2/payments?begin_time=$BEGIN&end_time=$END&sort_order=DESC" \
  -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
  -H "Accept: application/json" \
  -H "Square-Version: 2025-06-16"
```

Orders (search example — list orders for a location):

```bash
curl -s -X POST "https://connect.squareupsandbox.com/v2/orders/search" \
  -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Square-Version: 2025-06-16" \
  -d '{"query":{"filter":{"location_id":{"location_ids":["'$SQUARE_LOCATION_ID'"]}}},"limit":20}'
```

Customers (list):

```bash
curl -s -X GET "https://connect.squareupsandbox.com/v2/customers" \
  -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
  -H "Square-Version: 2025-06-16"
```

Invoices (list/search):

```bash
curl -s -X GET "https://connect.squareupsandbox.com/v2/invoices" \
  -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
  -H "Square-Version: 2025-06-16"
```

Bookings/Appointments (if using Bookings API — may be `appointments` or `bookings` depending on your Square product):

```bash
curl -s -X GET "https://connect.squareupsandbox.com/v2/bookings" \
  -H "Authorization: Bearer $SQUARE_ACCESS_TOKEN" \
  -H "Square-Version: 2025-06-16"
```

(If your account uses a different endpoint or a later API version, replace accordingly.)

---

## Next steps after creating the Notion DB

1. Copy `database_id` from the script output into your automation config.
2. Implement a scheduled job (cron / serverless scheduler / APscheduler) to:
   - For each configured Square account, call the Square endpoints above (payments/orders/invoices/customers/bookings) since `last_synced`.
   - Upsert results into Notion pages (or a normalized data store + Notion summary pages).
3. Optionally add webhooks in Square to trigger near-real-time syncs (verify and validate Square webhook signatures).

---

If you want, I can run the Notion creation step for you — but I need a live `NOTION_TOKEN` and `PARENT_PAGE_ID` (or you can run the script locally and paste the `database_id`). I will NOT accept tokens in chat; run locally or paste the IDs afterwards.

