# Square sales report and Claude package summaries

This automation lives inside a Google Sheet Apps Script project.

It does two daily jobs:

1. Pulls current-month Square payment data into a sheet tab.
2. Reads each transaction row and asks Claude to summarize the purchased
   package, including session quantity, frequency, and duration.

## Files

- `google-apps-script/square_monthly_sales_report.gs`
- `google-apps-script/claude_package_summarizer.gs`

Paste both files into the Apps Script project attached to your Google Sheet.

## What the Square import creates

By default, the Square script creates or refreshes a tab named:

`Monthly Sales Raw`

Each daily refresh pulls payments from the first day of the current month
through the time the script runs.

The sheet includes:

- Payment ID
- Order ID
- Location ID
- Customer ID
- Buyer email
- Amount and currency
- Receipt URL
- Payment note
- Order line items
- Order notes
- Package detail text
- Package summary columns populated by Claude

Existing Claude package summaries are preserved across daily Square refreshes
by matching on `Payment ID`.

## Script Properties

In Apps Script, go to **Project Settings -> Script Properties** and add these.

### Required

| Property | Purpose |
| --- | --- |
| `SQUARE_ACCESS_TOKEN` | Square access token for production or sandbox |
| `ANTHROPIC_API_KEY` | Claude API key |

### Recommended

| Property | Example | Purpose |
| --- | --- | --- |
| `SQUARE_ENV` | `production` | Use `production` or `sandbox` |
| `SQUARE_LOCATION_IDS` | `LOCATION_ID_1,LOCATION_ID_2` | Limit report to specific Square locations |
| `SQUARE_REPORT_HOUR` | `6` | Hour of day to refresh Square data |
| `CLAUDE_SUMMARY_HOUR` | `7` | Hour of day to summarize packages |
| `CLAUDE_MAX_ROWS_PER_RUN` | `50` | Limits Claude calls per run |

### Optional

| Property | Default | Purpose |
| --- | --- | --- |
| `SQUARE_VERSION` | `2025-06-16` | Square API version |
| `SQUARE_REPORT_SHEET_NAME` | `Monthly Sales Raw` | Sheet tab for Square data |
| `SQUARE_REPORT_TIMEZONE` | spreadsheet timezone | Time zone for month boundary |
| `CLAUDE_MODEL` | `claude-3-5-haiku-latest` | Claude model |
| `TRANSACTIONS_SHEET_NAME` | `Monthly Sales Raw` | Sheet tab read by Claude |

If you change `SQUARE_REPORT_SHEET_NAME`, also set
`TRANSACTIONS_SHEET_NAME` to the same value.

## Install the daily triggers

In Apps Script:

1. Paste `square_monthly_sales_report.gs`.
2. Paste `claude_package_summarizer.gs`.
3. Save the project.
4. Run `runDailySquareSalesReport` once manually and approve permissions.
5. Confirm the `Monthly Sales Raw` tab is populated.
6. Run `summarizeUnsummarizedSquarePackages` once manually and approve
   permissions.
7. Run `installDailySquareSalesReportTrigger`.
8. Run `installClaudePackageSummaryTrigger`.

The suggested schedule is:

- Square import at 6 AM
- Claude package summaries at 7 AM

This gives the Square import time to refresh before Claude reads the rows.

## Package summary behavior

Claude receives the transaction row fields, including:

- Amount
- Payment note
- Order line items
- Order notes
- Combined package detail text

It returns compact JSON with:

- `summary`
- `sessions`
- `frequency_per_week`
- `duration_weeks`
- `rationale`

Example:

If the transaction row says:

- `3 months` or `12 weeks`
- `2x/week`

Claude should infer:

- `24` sessions
- `2` sessions per week
- `12` weeks
- summary: `24 Sessions at 2x/week for 12 weeks`

The script writes these values into:

- `Package Summary`
- `Package Session Quantity`
- `Package Frequency Per Week`
- `Package Duration Weeks`
- `Package Summary Rationale`
- `Package Summary Updated At`
- `Package Summary Raw Claude Response`

## Refreshing existing rows

By default, Claude skips rows that already have `Package Summary`.

To force a row to be re-summarized:

1. Clear that row's `Package Summary` cell.
2. Run `summarizeUnsummarizedSquarePackages`.

## Common errors

### Missing required Script Property

Add the missing property under **Project Settings -> Script Properties**.

### Square API 401/403

Check that:

- `SQUARE_ACCESS_TOKEN` is valid.
- `SQUARE_ENV` matches the token type.
- The token has permission to read payments and orders.

### Claude API 401/403

Check that `ANTHROPIC_API_KEY` is valid.

### No package summary appears

Check that:

- `Monthly Sales Raw` has rows.
- `Payment ID` is present.
- `Package Summary` is blank for rows you want Claude to process.
- Apps Script **Executions** does not show an API error.
