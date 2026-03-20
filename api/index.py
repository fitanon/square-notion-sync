"""
Vercel serverless entry point for Fit Clinic Portal.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Create app for Vercel
app = FastAPI(title="Fit Clinic Portal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Brand colors - The Fit Clinic
BRAND = {
    "primary": "#C9A227",      # Gold
    "primary_dark": "#A8871F",
    "secondary": "#252525",    # Dark charcoal
    "accent": "#C9A227",       # Gold accent
    "success": "#4CAF50",
    "warning": "#C9A227",
    "danger": "#E53935",
    "light": "#F5F5F5",
    "dark": "#1A1A1A",         # Near black
}


def get_notion_client():
    """Get Notion client from environment."""
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        return None, None

    try:
        from core.config import NotionConfig
        from core.notion import NotionClient

        config = NotionConfig(
            token=token,
            db_clients=os.environ.get("NOTION_DB_CLIENTS"),
            db_sessions=os.environ.get("NOTION_DB_SESSIONS"),
            db_appointments=os.environ.get("NOTION_DB_APPOINTMENTS"),
            db_transactions=os.environ.get("NOTION_DB_TRANSACTIONS"),
            db_invoices=os.environ.get("NOTION_DB_INVOICES"),
        )
        return NotionClient(config), config
    except Exception as e:
        print(f"Notion init error: {e}")
        return None, None


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


def is_configured() -> bool:
    """Check if Notion is configured."""
    return bool(os.environ.get("NOTION_TOKEN"))


@app.get("/", response_class=HTMLResponse)
async def portal_home():
    """Serve the client portal."""
    if not is_configured():
        return get_setup_html()
    return get_portal_html()


@app.get("/portal", response_class=HTMLResponse)
async def portal_redirect():
    """Redirect /portal to /"""
    if not is_configured():
        return get_setup_html()
    return get_portal_html()


@app.get("/portal/lookup")
async def lookup_client(phone: str = None, email: str = None):
    """Look up client by phone or email."""
    if not phone and not email:
        return JSONResponse(
            status_code=400,
            content={"detail": "Please provide phone or email"}
        )

    notion, config = get_notion_client()
    if not notion:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service not configured. Please contact admin."}
        )

    db_id = config.db_sessions or config.db_clients
    if not db_id:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database not configured. Please contact admin."}
        )

    # Find client
    client_page = None

    try:
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
    except Exception as e:
        print(f"Lookup error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Error looking up client. Please try again."}
        )

    if not client_page:
        return {
            "found": False,
            "message": "No account found. Please check your phone or email."
        }

    props = client_page.properties
    return {
        "found": True,
        "client": {
            "name": extract_prop(props, "Name", "title"),
            "sessions_remaining": int(extract_prop(props, "Sessions Remaining", "number")),
            "sessions_purchased": int(extract_prop(props, "Sessions Purchased", "number")),
            "sessions_used": int(extract_prop(props, "Sessions Used", "number")),
            "status": extract_prop(props, "Status", "select") or "Active",
            "next_appointment": extract_prop(props, "Next Appointment", "date"),
            "last_synced": extract_prop(props, "Last Synced", "date"),
        },
        "message": ""
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "service": "fit-clinic-portal",
        "configured": is_configured()
    }


def get_setup_html() -> str:
    """Setup instructions page with The Fit Clinic branding."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Setup Required | The Fit Clinic</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, sans-serif;
            background: {BRAND["dark"]};
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: white;
        }}
        .container {{
            background: {BRAND["secondary"]};
            border-radius: 4px;
            padding: 50px;
            max-width: 550px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.05);
            position: relative;
        }}
        .container::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 60px;
            height: 3px;
            background: {BRAND["primary"]};
        }}
        .brand {{
            text-align: center;
            margin-bottom: 35px;
        }}
        .brand-name {{
            font-size: 20px;
            font-weight: 800;
            color: white;
            letter-spacing: 3px;
            text-transform: uppercase;
        }}
        .brand-tagline {{
            color: {BRAND["primary"]};
            font-size: 9px;
            letter-spacing: 4px;
            text-transform: uppercase;
            margin-top: 8px;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 10px;
            font-size: 18px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 35px;
            font-size: 13px;
        }}
        .step {{
            background: rgba(0,0,0,0.3);
            border-radius: 2px;
            padding: 20px;
            margin-bottom: 12px;
            border-left: 3px solid {BRAND["primary"]};
        }}
        .step-num {{
            display: inline-block;
            width: 24px;
            height: 24px;
            background: {BRAND["primary"]};
            color: {BRAND["dark"]};
            border-radius: 2px;
            text-align: center;
            line-height: 24px;
            font-weight: 700;
            font-size: 12px;
            margin-right: 12px;
        }}
        .step-title {{
            font-weight: 600;
            font-size: 13px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .step-desc {{
            color: #888;
            font-size: 13px;
            margin-left: 36px;
        }}
        code {{
            background: rgba(201,162,39,0.15);
            color: {BRAND["primary"]};
            padding: 2px 8px;
            border-radius: 2px;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 12px;
        }}
        .env-list {{
            margin-top: 10px;
            margin-left: 36px;
        }}
        .env-list li {{
            color: #777;
            font-size: 12px;
            margin-bottom: 6px;
            list-style: none;
        }}
        .env-list li::before {{
            content: "—";
            color: {BRAND["primary"]};
            margin-right: 10px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #555;
            font-size: 11px;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="brand">
            <div class="brand-name">The Fit Clinic</div>
            <div class="brand-tagline">Training & Nutrition</div>
        </div>
        <h1>Setup Required</h1>
        <p class="subtitle">Configure environment variables to activate the portal</p>

        <div class="step">
            <div class="step-title">
                <span class="step-num">1</span>
                Go to Vercel Dashboard
            </div>
            <div class="step-desc">
                Open your project settings at <code>vercel.com</code>
            </div>
        </div>

        <div class="step">
            <div class="step-title">
                <span class="step-num">2</span>
                Add Environment Variables
            </div>
            <div class="step-desc">
                Settings → Environment Variables → Add:
            </div>
            <ul class="env-list">
                <li><code>NOTION_TOKEN</code> — Your Notion integration token</li>
                <li><code>NOTION_DB_SESSIONS</code> — Sessions database ID</li>
                <li><code>NOTION_DB_CLIENTS</code> — Clients database ID (optional)</li>
            </ul>
        </div>

        <div class="step">
            <div class="step-title">
                <span class="step-num">3</span>
                Redeploy
            </div>
            <div class="step-desc">
                Deployments → Click latest → Redeploy
            </div>
        </div>

        <p class="footer">Portal will activate automatically once configured</p>
    </div>
</body>
</html>'''


def get_portal_html() -> str:
    """Main portal HTML with The Fit Clinic brand styling."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Session Balance | The Fit Clinic</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, sans-serif;
            background: {BRAND["dark"]};
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: {BRAND["secondary"]};
            border-radius: 4px;
            padding: 50px 45px;
            max-width: 420px;
            width: 100%;
            box-shadow: 0 25px 80px rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.05);
            position: relative;
        }}
        .container::before {{
            content: "";
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 60px;
            height: 3px;
            background: {BRAND["primary"]};
        }}
        .brand {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .brand-name {{
            font-size: 22px;
            font-weight: 800;
            color: white;
            letter-spacing: 3px;
            text-transform: uppercase;
        }}
        .brand-tagline {{
            color: {BRAND["primary"]};
            font-size: 10px;
            letter-spacing: 4px;
            text-transform: uppercase;
            margin-top: 8px;
        }}
        h1 {{
            text-align: center;
            color: white;
            margin-bottom: 8px;
            font-size: 20px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        .tagline {{
            text-align: center;
            color: #666;
            margin-bottom: 35px;
            font-size: 13px;
            letter-spacing: 0.5px;
        }}
        .form-group {{ margin-bottom: 18px; }}
        label {{
            display: block;
            margin-bottom: 8px;
            color: {BRAND["primary"]};
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        input {{
            width: 100%;
            padding: 16px 18px;
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 2px;
            font-size: 15px;
            color: white;
            font-family: 'Montserrat', sans-serif;
            transition: all 0.3s;
        }}
        input::placeholder {{ color: #555; }}
        input:focus {{
            outline: none;
            border-color: {BRAND["primary"]};
            background: rgba(201,162,39,0.05);
        }}
        .or-divider {{
            text-align: center;
            color: #444;
            margin: 20px 0;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 2px;
            position: relative;
        }}
        .or-divider::before,
        .or-divider::after {{
            content: "";
            position: absolute;
            top: 50%;
            width: 40%;
            height: 1px;
            background: {BRAND["primary"]};
            opacity: 0.3;
        }}
        .or-divider::before {{ left: 0; }}
        .or-divider::after {{ right: 0; }}
        button {{
            width: 100%;
            padding: 16px;
            background: {BRAND["primary"]};
            color: {BRAND["dark"]};
            border: none;
            border-radius: 2px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 10px;
            font-family: 'Montserrat', sans-serif;
        }}
        button:hover {{
            background: #D4AD2E;
            box-shadow: 0 10px 30px rgba(201,162,39,0.3);
        }}
        button:active {{ transform: translateY(0); }}
        button:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            box-shadow: none;
        }}
        .result {{ margin-top: 30px; display: none; }}
        .result.show {{ display: block; animation: fadeIn 0.4s ease; }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .result-card {{
            background: rgba(0,0,0,0.3);
            border-radius: 2px;
            padding: 35px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.05);
        }}
        .client-name {{
            font-size: 18px;
            font-weight: 700;
            color: white;
            margin-bottom: 25px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        .sessions-display {{
            margin: 0 auto 25px;
            position: relative;
        }}
        .sessions-number {{
            font-size: 72px;
            font-weight: 800;
            color: {BRAND["primary"]};
            line-height: 1;
        }}
        .sessions-label {{
            font-size: 10px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 10px;
        }}
        .gold-line {{
            width: 60px;
            height: 2px;
            background: {BRAND["primary"]};
            margin: 20px auto;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 24px;
            border-radius: 2px;
            font-size: 10px;
            font-weight: 700;
            margin-bottom: 25px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        .status-active {{ background: rgba(76,175,80,0.15); color: {BRAND["success"]}; border: 1px solid rgba(76,175,80,0.3); }}
        .status-low {{ background: rgba(201,162,39,0.15); color: {BRAND["primary"]}; border: 1px solid rgba(201,162,39,0.3); }}
        .status-needs {{ background: rgba(229,57,53,0.15); color: {BRAND["danger"]}; border: 1px solid rgba(229,57,53,0.3); }}
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}
        .stat-box {{
            background: rgba(0,0,0,0.2);
            border-radius: 2px;
            padding: 18px 15px;
            border: 1px solid rgba(255,255,255,0.05);
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: 700;
            color: white;
        }}
        .stat-label {{
            font-size: 9px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 5px;
        }}
        .error {{
            background: rgba(229,57,53,0.1);
            color: {BRAND["danger"]};
            padding: 25px;
            border-radius: 2px;
            text-align: center;
            border: 1px solid rgba(229,57,53,0.2);
            font-size: 14px;
        }}
        .last-sync {{
            text-align: center;
            font-size: 10px;
            color: #555;
            margin-top: 20px;
            letter-spacing: 1px;
        }}
        .reset-btn {{
            background: transparent;
            border: 1px solid rgba(255,255,255,0.15);
            color: #888;
            margin-top: 20px;
            font-size: 11px;
        }}
        .reset-btn:hover {{
            background: rgba(255,255,255,0.05);
            box-shadow: none;
            color: white;
            border-color: rgba(255,255,255,0.3);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="brand">
            <div class="brand-name">The Fit Clinic</div>
            <div class="brand-tagline">Training & Nutrition</div>
        </div>
        <h1>Session Balance</h1>
        <p class="tagline">Check your remaining training sessions</p>

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

        form.addEventListener('submit', async (e) => {{
            e.preventDefault();
            const phone = document.getElementById('phone').value.trim();
            const email = document.getElementById('email').value.trim();

            if (!phone && !email) {{
                showError('Please enter your phone number or email.');
                return;
            }}

            submitBtn.disabled = true;
            submitBtn.textContent = 'Looking up...';

            try {{
                const params = new URLSearchParams();
                if (phone) params.append('phone', phone);
                if (email) params.append('email', email);

                const response = await fetch(`/portal/lookup?${{params}}`);
                const data = await response.json();

                if (!response.ok) {{
                    showError(data.detail || 'Something went wrong.');
                    return;
                }}
                if (!data.found) {{
                    showError(data.message);
                    return;
                }}
                showResult(data);
            }} catch (err) {{
                showError('Connection error. Please try again.');
            }} finally {{
                submitBtn.disabled = false;
                submitBtn.textContent = 'Check Balance';
            }}
        }});

        function showError(message) {{
            result.innerHTML = `<div class="error">${{message}}</div>
                <button class="reset-btn" onclick="resetForm()">Try Again</button>`;
            result.classList.add('show');
        }}

        function showResult(data) {{
            const c = data.client;
            const remaining = c.sessions_remaining;
            let statusClass = 'status-active';
            let statusText = 'Active';

            if (remaining <= 0) {{
                statusClass = 'status-needs';
                statusText = 'Needs Sessions';
            }} else if (remaining <= 3) {{
                statusClass = 'status-low';
                statusText = 'Low Balance';
            }}

            result.innerHTML = `
                <div class="result-card">
                    <div class="client-name">${{c.name}}</div>
                    <div class="sessions-display">
                        <div class="sessions-number">${{remaining}}</div>
                        <div class="sessions-label">Sessions Remaining</div>
                    </div>
                    <div class="gold-line"></div>
                    <div class="status-badge ${{statusClass}}">${{statusText}}</div>
                    <div class="stats-grid">
                        <div class="stat-box">
                            <div class="stat-value">${{c.sessions_purchased}}</div>
                            <div class="stat-label">Purchased</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">${{c.sessions_used}}</div>
                            <div class="stat-label">Used</div>
                        </div>
                    </div>
                    ${{c.last_synced ? `<div class="last-sync">Updated ${{formatDate(c.last_synced)}}</div>` : ''}}
                </div>
                <button class="reset-btn" onclick="resetForm()">Check Another</button>
            `;
            result.classList.add('show');
        }}

        function resetForm() {{
            document.getElementById('phone').value = '';
            document.getElementById('email').value = '';
            result.classList.remove('show');
            document.getElementById('phone').focus();
        }}

        function formatDate(dateStr) {{
            if (!dateStr) return '';
            const d = new Date(dateStr);
            const now = new Date();
            const diff = Math.floor((now - d) / (1000 * 60 * 60 * 24));
            if (diff === 0) return 'today';
            if (diff === 1) return 'yesterday';
            if (diff < 7) return `${{diff}} days ago`;
            return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }});
        }}
    </script>
</body>
</html>'''
