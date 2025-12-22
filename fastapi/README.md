# FastAPI skeleton for Square → Notion sync

This folder contains a small FastAPI skeleton to prototype syncs and account management. It intentionally avoids making destructive calls; network calls only run when the required environment variables are present.

Quick start (zsh):

```bash
cd /Users/mike/my-react-app/square-callouts-starter/fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# set a NOTION_TOKEN and DATABASE_ID if you want to test upserts
export NOTION_TOKEN="your_notion_token"
export NOTION_DATABASE_ID="your_database_id"

# run the app locally
uvicorn app:app --reload --port 8001
```

Endpoints:
- GET /health — returns basic health info
- POST /sync/customer/{customer_id}?account_name={name} — fetches customer + last payment + orders and returns assembled payload (and attempts Notion upsert if NOTION_TOKEN + DATABASE_ID are set)
- GET /connect/oauth/start?account_name={name} — redirect to Square OAuth authorize page
- GET /connect/oauth/callback — OAuth callback, exchanges code for token and stores it in local token store
- GET /connect/tokens — list stored account keys and basic metadata (no secrets returned)

Files:
- `app.py` — FastAPI app and routes
- `accounts.py` — account helpers and Square fetch wrappers
- `notion_helper.py` — helper to upsert to Notion (safe: prints payload when token missing)
