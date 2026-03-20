"""
Vercel serverless entry point for FastAPI.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Create a minimal app for Vercel (scheduler doesn't work in serverless)
app = FastAPI(title="Fit Clinic Portal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_notion_client():
    """Get Notion client from environment."""
    from core.config import NotionConfig
    from core.notion import NotionClient

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        return None

    config = NotionConfig(
        token=token,
        db_clients=os.environ.get("NOTION_DB_CLIENTS"),
        db_sessions=os.environ.get("NOTION_DB_SESSIONS"),
        db_appointments=os.environ.get("NOTION_DB_APPOINTMENTS"),
        db_transactions=os.environ.get("NOTION_DB_TRANSACTIONS"),
        db_invoices=os.environ.get("NOTION_DB_INVOICES"),
    )
    return NotionClient(config), config


def normalize_phone(phone: str) -> str:
    """Normalize phone to digits only."""
    if not phone:
        return ""
    return "".join(c for c in phone if c.isdigit())


def extract_prop(properties: dict, name: str, prop_type: str = "number"):
    """Extract value from Notion properties."""
    prop = properties.get(name, {})
    if prop_type == "number":
        return prop.get("number", 0) or 0
    elif prop_type == "title":
        arr = prop.get("title", [])
        return arr[0]["plain_text"] if arr else ""
    elif prop_type == "rich_text":
        arr = prop.get("rich_text", [])
        return arr[0]["plain_text"] if arr else ""
    elif prop_type == "select":
        sel = prop.get("select")
        return sel["name"] if sel else ""
    elif prop_type == "date":
        d = prop.get("date")
        return d["start"] if d else None
    elif prop_type == "phone_number":
        return prop.get("phone_number", "")
    elif prop_type == "email":
        return prop.get("email", "")
    return None


@app.get("/", response_class=HTMLResponse)
async def portal_home():
    """Serve the client portal."""
    return get_portal_html()


@app.get("/portal", response_class=HTMLResponse)
async def portal_redirect():
    """Redirect /portal to /"""
    return get_portal_html()


@app.get("/portal/lookup")
async def lookup_client(phone: str = None, email: str = None):
    """Look up client by phone or email."""
    if not phone and not email:
        return JSONResponse(
            status_code=400,
            content={"detail": "Please provide phone or email"}
        )

    result = get_notion_client()
    if not result:
        return JSONResponse(
            status_code=503,
            content={"detail": "Notion not configured. Add NOTION_TOKEN in Vercel settings."}
        )

    notion, config = result
    db_id = config.db_sessions or config.db_clients

    if not db_id:
        return JSONResponse(
            status_code=503,
            content={"detail": "No database configured. Add NOTION_DB_SESSIONS in Vercel settings."}
        )

    # Find client
    client_page = None

    if email:
        client_page = notion.find_page_by_property(db_id, "Email", email, "email")

    if not client_page and phone:
        normalized = normalize_phone(phone)
        if len(normalized) >= 10:
            pages, cursor = notion.query_database(db_id, page_size=100)
            all_pages = list(pages)
            while cursor:
                more, cursor = notion.query_database(db_id, page_size=100, start_cursor=cursor)
                all_pages.extend(more)

            for page in all_pages:
                page_phone = extract_prop(page.properties, "Phone", "phone_number")
                if normalize_phone(page_phone) == normalized:
                    client_page = page
                    break

    if not client_page:
        return {
            "found": False,
            "message": "No client found with that phone or email."
        }

    props = client_page.properties
    return {
        "found": True,
        "client": {
            "name": extract_prop(props, "Name", "title"),
            "sessions_remaining": int(extract_prop(props, "Sessions Remaining", "number")),
            "sessions_purchased": int(extract_prop(props, "Sessions Purchased", "number")),
            "sessions_used": int(extract_prop(props, "Sessions Used", "number")),
            "status": extract_prop(props, "Status", "select") or "Unknown",
            "next_appointment": extract_prop(props, "Next Appointment", "date"),
            "last_synced": extract_prop(props, "Last Synced", "date"),
        },
        "upcoming_appointments": [],
        "message": ""
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "fit-clinic-portal"}


def get_portal_html() -> str:
    """Return portal HTML."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Check Your Sessions | Fit Clinic</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 24px;
        }
        .form-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
        }
        input {
            width: 100%;
            padding: 14px;
            border: 2px solid #e1e1e1;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        button:disabled {
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
        }
        .or-divider {
            text-align: center;
            color: #999;
            margin: 15px 0;
            font-size: 14px;
        }
        .result { margin-top: 30px; display: none; }
        .result.show { display: block; }
        .result-card {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
        }
        .client-name {
            font-size: 20px;
            font-weight: 600;
            color: #333;
            margin-bottom: 20px;
        }
        .sessions-circle {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin: 0 auto 20px;
            color: white;
        }
        .sessions-number {
            font-size: 42px;
            font-weight: 700;
            line-height: 1;
        }
        .sessions-label {
            font-size: 12px;
            opacity: 0.9;
        }
        .status-badge {
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 15px;
        }
        .status-active { background: #d4edda; color: #155724; }
        .status-low { background: #fff3cd; color: #856404; }
        .status-needs { background: #f8d7da; color: #721c24; }
        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
            font-size: 14px;
        }
        .detail-row:last-child { border-bottom: none; }
        .detail-label { color: #666; }
        .detail-value { font-weight: 500; color: #333; }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .last-sync {
            text-align: center;
            font-size: 12px;
            color: #999;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Check Your Sessions</h1>
        <form id="lookupForm">
            <div class="form-group">
                <label for="phone">Phone Number</label>
                <input type="tel" id="phone" placeholder="(555) 123-4567">
            </div>
            <div class="or-divider">or</div>
            <div class="form-group">
                <label for="email">Email Address</label>
                <input type="email" id="email" placeholder="you@example.com">
            </div>
            <button type="submit" id="submitBtn">Check Balance</button>
        </form>
        <div class="result" id="result"></div>
    </div>
    <script>
        const form = document.getElementById('lookupForm');
        const result = document.getElementById('result');
        const submitBtn = document.getElementById('submitBtn');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const phone = document.getElementById('phone').value.trim();
            const email = document.getElementById('email').value.trim();

            if (!phone && !email) {
                showError('Please enter your phone number or email.');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Looking up...';

            try {
                const params = new URLSearchParams();
                if (phone) params.append('phone', phone);
                if (email) params.append('email', email);

                const response = await fetch(`/portal/lookup?${params}`);
                const data = await response.json();

                if (!response.ok) {
                    showError(data.detail || 'Something went wrong.');
                    return;
                }
                if (!data.found) {
                    showError(data.message);
                    return;
                }
                showResult(data);
            } catch (err) {
                showError('Network error. Please try again.');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Check Balance';
            }
        });

        function showError(message) {
            result.innerHTML = `<div class="error">${message}</div>`;
            result.classList.add('show');
        }

        function showResult(data) {
            const client = data.client;
            const statusClass = client.status === 'Active' ? 'status-active'
                : client.status === 'Low Sessions' ? 'status-low' : 'status-needs';

            result.innerHTML = `
                <div class="result-card">
                    <div class="client-name">${client.name}</div>
                    <div class="sessions-circle">
                        <div class="sessions-number">${client.sessions_remaining}</div>
                        <div class="sessions-label">sessions left</div>
                    </div>
                    <div class="status-badge ${statusClass}">${client.status}</div>
                    <div class="detail-row">
                        <span class="detail-label">Purchased</span>
                        <span class="detail-value">${client.sessions_purchased}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Used</span>
                        <span class="detail-value">${client.sessions_used}</span>
                    </div>
                    ${client.last_synced ? `<div class="last-sync">Last updated: ${formatDate(client.last_synced)}</div>` : ''}
                </div>
            `;
            result.classList.add('show');
        }

        function formatDate(dateStr) {
            if (!dateStr) return '';
            return new Date(dateStr).toLocaleDateString('en-US', {
                weekday: 'short', month: 'short', day: 'numeric'
            });
        }
    </script>
</body>
</html>'''
