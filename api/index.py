"""
Vercel serverless entry point for Fit Clinic Portal.
"""

import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Create app for Vercel
app = FastAPI(title="Fit Clinic Portal")

# CORS: restrict to same-origin by default
cors_origins = os.getenv("APP_CORS_ORIGINS", "").split(",")
cors_origins = [o.strip() for o in cors_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["https://square-notion-sync.vercel.app"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Minimalist design system - contrarian to Notion
THEME = {
    "bg": "#FAFAFA",           # Off-white
    "fg": "#0A0A0A",           # Near black
    "muted": "#737373",        # Gray
    "border": "#E5E5E5",       # Light border
    "accent": "#0A0A0A",       # Black accent
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
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
    except Exception:
        logger.exception("Failed to initialize Notion client")
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
    except Exception:
        logger.exception("Error during client lookup")
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
    """Setup instructions - minimalist design."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Setup</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: {THEME["bg"]};
            color: {THEME["fg"]};
            min-height: 100vh;
            padding: 80px 24px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 480px;
            margin: 0 auto;
        }}
        .logo {{
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 48px;
            color: {THEME["muted"]};
        }}
        h1 {{
            font-size: 32px;
            font-weight: 600;
            margin-bottom: 12px;
            letter-spacing: -0.5px;
        }}
        .desc {{
            color: {THEME["muted"]};
            font-size: 15px;
            margin-bottom: 48px;
        }}
        .steps {{
            border-top: 1px solid {THEME["border"]};
        }}
        .step {{
            padding: 24px 0;
            border-bottom: 1px solid {THEME["border"]};
            display: grid;
            grid-template-columns: 24px 1fr;
            gap: 16px;
        }}
        .step-num {{
            font-size: 13px;
            font-weight: 500;
            color: {THEME["muted"]};
        }}
        .step-content h3 {{
            font-size: 15px;
            font-weight: 500;
            margin-bottom: 6px;
        }}
        .step-content p {{
            font-size: 14px;
            color: {THEME["muted"]};
        }}
        code {{
            font-family: "SF Mono", Monaco, "Consolas", monospace;
            font-size: 13px;
            background: {THEME["border"]};
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .env-vars {{
            margin-top: 12px;
            padding: 16px;
            background: {THEME["fg"]};
            color: {THEME["bg"]};
            border-radius: 8px;
            font-family: "SF Mono", Monaco, monospace;
            font-size: 13px;
            line-height: 1.8;
        }}
        .env-vars .key {{ color: #A5D6FF; }}
        .env-vars .val {{ color: #7EE787; }}
        .footer {{
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid {THEME["border"]};
            font-size: 13px;
            color: {THEME["muted"]};
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">fit clinic</div>
        <h1>Setup required</h1>
        <p class="desc">Configure your environment to activate the portal.</p>

        <div class="steps">
            <div class="step">
                <span class="step-num">1</span>
                <div class="step-content">
                    <h3>Open Vercel settings</h3>
                    <p>Go to your project → Settings → Environment Variables</p>
                </div>
            </div>
            <div class="step">
                <span class="step-num">2</span>
                <div class="step-content">
                    <h3>Add variables</h3>
                    <div class="env-vars">
                        <span class="key">NOTION_TOKEN</span>=<span class="val">secret_xxx</span><br>
                        <span class="key">NOTION_DB_SESSIONS</span>=<span class="val">database_id</span>
                    </div>
                </div>
            </div>
            <div class="step">
                <span class="step-num">3</span>
                <div class="step-content">
                    <h3>Redeploy</h3>
                    <p>Deployments → Latest → Redeploy</p>
                </div>
            </div>
        </div>

        <p class="footer">Portal activates automatically after configuration.</p>
    </div>
</body>
</html>'''


def get_portal_html() -> str:
    """Main portal HTML - minimalist, contrarian design."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sessions</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: {THEME["bg"]};
            color: {THEME["fg"]};
            min-height: 100vh;
            padding: 80px 24px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 400px;
            margin: 0 auto;
        }}
        .logo {{
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
            color: {THEME["muted"]};
            margin-bottom: 48px;
        }}
        h1 {{
            font-size: 32px;
            font-weight: 600;
            letter-spacing: -0.5px;
            margin-bottom: 8px;
        }}
        .subtitle {{
            color: {THEME["muted"]};
            font-size: 15px;
            margin-bottom: 40px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
            color: {THEME["fg"]};
        }}
        input {{
            width: 100%;
            padding: 14px 16px;
            font-size: 16px;
            border: 1px solid {THEME["border"]};
            border-radius: 8px;
            background: white;
            color: {THEME["fg"]};
            font-family: inherit;
            transition: border-color 0.15s;
        }}
        input::placeholder {{
            color: {THEME["muted"]};
        }}
        input:focus {{
            outline: none;
            border-color: {THEME["fg"]};
        }}
        .divider {{
            text-align: center;
            color: {THEME["muted"]};
            font-size: 13px;
            margin: 20px 0;
            position: relative;
        }}
        .divider::before, .divider::after {{
            content: "";
            position: absolute;
            top: 50%;
            width: 45%;
            height: 1px;
            background: {THEME["border"]};
        }}
        .divider::before {{ left: 0; }}
        .divider::after {{ right: 0; }}
        button {{
            width: 100%;
            padding: 14px;
            font-size: 15px;
            font-weight: 500;
            background: {THEME["fg"]};
            color: {THEME["bg"]};
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-family: inherit;
            transition: opacity 0.15s;
            margin-top: 8px;
        }}
        button:hover {{ opacity: 0.9; }}
        button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        .result {{
            display: none;
            margin-top: 40px;
            padding-top: 40px;
            border-top: 1px solid {THEME["border"]};
            animation: fadeIn 0.3s ease;
        }}
        .result.show {{ display: block; }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .client-name {{
            font-size: 14px;
            font-weight: 500;
            color: {THEME["muted"]};
            margin-bottom: 8px;
        }}
        .sessions-count {{
            font-size: 96px;
            font-weight: 600;
            letter-spacing: -4px;
            line-height: 1;
            margin-bottom: 4px;
        }}
        .sessions-label {{
            font-size: 14px;
            color: {THEME["muted"]};
            margin-bottom: 32px;
        }}
        .status {{
            display: inline-block;
            font-size: 12px;
            font-weight: 500;
            padding: 6px 12px;
            border-radius: 100px;
            margin-bottom: 32px;
        }}
        .status-active {{
            background: rgba(34, 197, 94, 0.1);
            color: {THEME["success"]};
        }}
        .status-low {{
            background: rgba(245, 158, 11, 0.1);
            color: {THEME["warning"]};
        }}
        .status-empty {{
            background: rgba(239, 68, 68, 0.1);
            color: {THEME["danger"]};
        }}
        .stats {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1px;
            background: {THEME["border"]};
            border-radius: 8px;
            overflow: hidden;
        }}
        .stat {{
            background: white;
            padding: 20px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .stat-label {{
            font-size: 12px;
            color: {THEME["muted"]};
        }}
        .meta {{
            margin-top: 24px;
            font-size: 12px;
            color: {THEME["muted"]};
            text-align: center;
        }}
        .reset {{
            background: transparent;
            color: {THEME["muted"]};
            border: 1px solid {THEME["border"]};
            margin-top: 24px;
        }}
        .reset:hover {{
            background: {THEME["border"]};
            color: {THEME["fg"]};
            opacity: 1;
        }}
        .error-box {{
            padding: 16px;
            background: rgba(239, 68, 68, 0.05);
            border: 1px solid rgba(239, 68, 68, 0.1);
            border-radius: 8px;
            color: {THEME["danger"]};
            font-size: 14px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">fit clinic</div>
        <h1>Check sessions</h1>
        <p class="subtitle">Enter your phone or email to view your balance.</p>

        <form id="lookupForm">
            <div class="form-group">
                <label for="phone">Phone number</label>
                <input type="tel" id="phone" placeholder="(555) 123-4567" autocomplete="tel">
            </div>
            <div class="divider">or</div>
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" placeholder="you@example.com" autocomplete="email">
            </div>
            <button type="submit" id="submitBtn">Look up</button>
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
                showError('Enter your phone number or email.');
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
                showError('Connection error. Try again.');
            }} finally {{
                submitBtn.disabled = false;
                submitBtn.textContent = 'Look up';
            }}
        }});

        function showError(message) {{
            result.textContent = '';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-box';
            errorDiv.textContent = message;
            result.appendChild(errorDiv);

            const btn = document.createElement('button');
            btn.className = 'reset';
            btn.textContent = 'Try again';
            btn.addEventListener('click', resetForm);
            result.appendChild(btn);

            result.classList.add('show');
        }}

        function showResult(data) {{
            const c = data.client;
            const remaining = c.sessions_remaining;

            let statusClass = 'status-active';
            let statusText = 'Active';
            if (remaining <= 0) {{
                statusClass = 'status-empty';
                statusText = 'No sessions';
            }} else if (remaining <= 3) {{
                statusClass = 'status-low';
                statusText = 'Running low';
            }}

            result.textContent = '';

            const nameDiv = document.createElement('div');
            nameDiv.className = 'client-name';
            nameDiv.textContent = c.name;
            result.appendChild(nameDiv);

            const countDiv = document.createElement('div');
            countDiv.className = 'sessions-count';
            countDiv.textContent = parseInt(remaining) || 0;
            result.appendChild(countDiv);

            const labelDiv = document.createElement('div');
            labelDiv.className = 'sessions-label';
            labelDiv.textContent = 'sessions remaining';
            result.appendChild(labelDiv);

            const statusDiv = document.createElement('div');
            statusDiv.className = 'status ' + statusClass;
            statusDiv.textContent = statusText;
            result.appendChild(statusDiv);

            const statsDiv = document.createElement('div');
            statsDiv.className = 'stats';

            const stat1 = document.createElement('div');
            stat1.className = 'stat';
            const val1 = document.createElement('div');
            val1.className = 'stat-value';
            val1.textContent = parseInt(c.sessions_purchased) || 0;
            const lbl1 = document.createElement('div');
            lbl1.className = 'stat-label';
            lbl1.textContent = 'Purchased';
            stat1.appendChild(val1);
            stat1.appendChild(lbl1);

            const stat2 = document.createElement('div');
            stat2.className = 'stat';
            const val2 = document.createElement('div');
            val2.className = 'stat-value';
            val2.textContent = parseInt(c.sessions_used) || 0;
            const lbl2 = document.createElement('div');
            lbl2.className = 'stat-label';
            lbl2.textContent = 'Used';
            stat2.appendChild(val2);
            stat2.appendChild(lbl2);

            statsDiv.appendChild(stat1);
            statsDiv.appendChild(stat2);
            result.appendChild(statsDiv);

            if (c.last_synced) {{
                const metaDiv = document.createElement('div');
                metaDiv.className = 'meta';
                metaDiv.textContent = 'Updated ' + formatDate(c.last_synced);
                result.appendChild(metaDiv);
            }}

            const btn = document.createElement('button');
            btn.className = 'reset';
            btn.textContent = 'Check another';
            btn.addEventListener('click', resetForm);
            result.appendChild(btn);

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
            if (diff < 7) return diff + ' days ago';
            return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }});
        }}
    </script>
</body>
</html>'''
