# FitAnon Square Multi-Account Sync

Centralized data sync for multiple Square accounts. Built for The Fit Clinic businesses.

## Supported Accounts

| Business | Email | Env Variable Prefix |
|----------|-------|---------------------|
| THE FIT CLINIC LLC | mike@thefitclinicsj.com | `ACCOUNT__FITCLINIC_LLC__` |
| FITCLINIC.IO | mike@fitclinic.io | `ACCOUNT__FITCLINIC__` |
| FITNESS WITH MIKE | shmockeyfit@gmail.com | `ACCOUNT__FITNESSWITHMIKE__` |

## Quick Start

```bash
# 1. Clone and enter directory
git clone https://github.com/fitanon/square-notion-sync.git
cd square-notion-sync

# 2. Install dependencies
make install

# 3. Configure your accounts (edit .env)
cp .env.example .env
# Add your Square API tokens to .env

# 4. Check connection status
make status

# 5. View your data
make customers
make transactions
```

## Commands

| Command | Description |
|---------|-------------|
| `make install` | Set up Python environment and dependencies |
| `make status` | Check connection status for all accounts |
| `make customers` | List customers from all accounts |
| `make transactions` | List recent transactions (last 30 days) |
| `make invoices` | List invoices from all accounts |
| `make export` | Export all data to JSON files |
| `make server` | Start the API server |
| `python scripts/mirror_questionnaires_to_notion.py ...` | Mirror questionnaire rows from Google Sheets into a brand-new Notion database |

## Configuration

Edit `.env` with your Square API tokens:

```bash
# Environment (sandbox or production)
SQUARE_ENV=production

# Account 1: THE FIT CLINIC LLC
ACCOUNT__FITCLINIC_LLC__TOKEN=your_token_here
ACCOUNT__FITCLINIC_LLC__EMAIL=mike@thefitclinicsj.com

# Account 2: FITCLINIC.IO
ACCOUNT__FITCLINIC__TOKEN=your_token_here
ACCOUNT__FITCLINIC__EMAIL=mike@fitclinic.io

# Account 3: FITNESS WITH MIKE
ACCOUNT__FITNESSWITHMIKE__TOKEN=your_token_here
ACCOUNT__FITNESSWITHMIKE__EMAIL=shmockeyfit@gmail.com
```

## API Server

Start the server:
```bash
make server
# or
python cli.py server --port 8000
```

### Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /accounts` | List all configured accounts |
| `GET /customers` | Get customers from all accounts |
| `GET /customers/{source}` | Get customers from specific account |
| `GET /transactions?days=30` | Get recent transactions |
| `GET /invoices` | Get invoices from all accounts |
| `GET /summary` | Get account summary |

API docs available at: `http://localhost:8000/docs`

## CLI Usage

```bash
# Activate environment first
source venv/bin/activate

# Check status
python cli.py status

# List customers (verbose)
python cli.py customers -v

# Get transactions from last 7 days
python cli.py transactions --days 7 -v

# Export all data
python cli.py export --output ./my-exports

# Start server on custom port
python cli.py server --port 3000
```

## Project Structure

```
square-notion-sync/
├── .env                    # Your API tokens (not in git)
├── .env.example            # Template for .env
├── cli.py                  # Command-line interface
├── Makefile                # Quick commands
├── requirements.txt        # Python dependencies
├── src/
│   ├── callouts.py         # Original Square API examples
│   └── multi_account.py    # Multi-account sync module
├── fastapi/
│   ├── app.py              # API server
│   ├── accounts.py         # Account helpers
│   ├── oauth.py            # OAuth flow
│   └── token_store.py      # Token storage
└── exports/                # Exported JSON data
```

## Getting Square API Tokens

1. Go to [Square Developer Dashboard](https://developer.squareup.com/apps)
2. Log in with each Square account
3. Create an app (or use existing)
4. Go to Credentials → Production Access Token
5. Copy the token to your `.env` file

## Zapier Integration

See [ZAPIER_SETUP_INSTRUCTIONS.md](ZAPIER_SETUP_INSTRUCTIONS.md) for setting up automated sync with Zapier Tables.

## Google Sheets Questionnaire → Notion Mirror

Use this script to copy selected questionnaire responses from Google Sheets into a **new**
Notion database:

```bash
source venv/bin/activate
python scripts/mirror_questionnaires_to_notion.py \
  --spreadsheet-id "$GOOGLE_SHEETS_SPREADSHEET_ID" \
  --worksheet "Questionnaire Responses" \
  --database-title "TFC Questionnaire Mirror" \
  --limit 25
```

Required environment variables:

- `NOTION_TOKEN`
- `NOTION_PARENT_PAGE_ID` (or `PARENT_PAGE_ID`)
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_FILE` **or** `GOOGLE_SERVICE_ACCOUNT_JSON`

Optional filters so you can mirror only "some" responses:

- `--row-numbers 2,7,12` mirror specific sheet rows
- `--contains completed` mirror rows containing a keyword
- `--columns "Timestamp,Name,Email,Goals"` include only chosen columns
- `--use-questionnaire-default-fields` include: first/last name, goals, phone, email, AI medical summary, training history, nutrition history, other details, submission date
- `--limit 10` cap total mirrored rows
- `--dry-run` preview selection without writing to Notion

Field set command matching the Fit Clinic questionnaire:

```bash
python scripts/mirror_questionnaires_to_notion.py \
  --worksheet "Questionnaire Responses" \
  --database-title "TFC Questionnaire Intake Mirror" \
  --use-questionnaire-default-fields
```

## Google Forms → Email → Notion automation

For real-time automation when a Google Form is submitted, use the Apps Script
template in `google-apps-script/form_to_notion.gs`.

Setup guide: [GOOGLE_FORMS_TO_NOTION_AUTOMATION.md](GOOGLE_FORMS_TO_NOTION_AUTOMATION.md)

## Security

- **Never commit `.env`** - it contains secrets
- Use environment variables in production
- Tokens are scoped - request only needed permissions
- Rotate tokens if exposed

## Support

Built for Mike @ The Fit Clinic by Claude.

---
*Last updated: January 2026*
