"""
Client Portal: Simple session lookup for clients.

Provides:
- Client lookup by phone or email
- Session balance display
- Upcoming appointments
- Staff sync trigger
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal", tags=["portal"])


class ClientInfo(BaseModel):
    """Client session information."""
    name: str
    sessions_remaining: int
    sessions_purchased: int
    sessions_used: int
    status: str
    next_appointment: Optional[str] = None
    last_synced: Optional[str] = None


class AppointmentInfo(BaseModel):
    """Upcoming appointment."""
    date: str
    time: str
    status: str


class PortalResponse(BaseModel):
    """Full portal response for a client."""
    found: bool
    client: Optional[ClientInfo] = None
    upcoming_appointments: List[AppointmentInfo] = []
    message: str = ""


def extract_property_value(properties: dict, name: str, prop_type: str = "number") -> any:
    """Extract a value from Notion properties."""
    prop = properties.get(name, {})
    if prop_type == "number":
        return prop.get("number", 0) or 0
    elif prop_type == "title":
        title_arr = prop.get("title", [])
        return title_arr[0]["plain_text"] if title_arr else ""
    elif prop_type == "rich_text":
        text_arr = prop.get("rich_text", [])
        return text_arr[0]["plain_text"] if text_arr else ""
    elif prop_type == "select":
        select = prop.get("select")
        return select["name"] if select else ""
    elif prop_type == "date":
        date_obj = prop.get("date")
        return date_obj["start"] if date_obj else None
    elif prop_type == "phone_number":
        return prop.get("phone_number", "")
    elif prop_type == "email":
        return prop.get("email", "")
    return None


def normalize_phone(phone: str) -> str:
    """Normalize phone number to digits only for comparison."""
    if not phone:
        return ""
    return "".join(c for c in phone if c.isdigit())


def register_portal_routes(app):
    """Register portal routes with the app."""

    @router.get("/", response_class=HTMLResponse)
    async def portal_home():
        """Serve the client portal HTML page."""
        return get_portal_html()

    @router.get("/lookup", response_model=PortalResponse)
    async def lookup_client(
        request: Request,
        phone: Optional[str] = Query(None, description="Client phone number"),
        email: Optional[str] = Query(None, description="Client email address"),
    ):
        """
        Look up a client by phone or email.

        Returns session balance and upcoming appointments from Notion.
        """
        if not phone and not email:
            raise HTTPException(
                status_code=400,
                detail="Please provide either phone or email"
            )

        config = request.app.state.config
        if not config.notion:
            raise HTTPException(
                status_code=503,
                detail="Notion not configured"
            )

        from core.notion import NotionClient
        notion = NotionClient(config.notion)

        # Try sessions DB first, fall back to clients DB
        db_id = config.notion.db_sessions or config.notion.db_clients
        if not db_id:
            raise HTTPException(
                status_code=503,
                detail="Client database not configured"
            )

        # Query Notion for the client
        client_page = None

        if email:
            client_page = notion.find_page_by_property(
                db_id, "Email", email, property_type="email"
            )

        if not client_page and phone:
            # Phone lookup requires scanning (Notion doesn't filter phone well)
            normalized_input = normalize_phone(phone)
            if len(normalized_input) >= 10:
                # Get all pages and filter by phone
                pages, cursor = notion.query_database(db_id, page_size=100)
                all_pages = list(pages)
                while cursor:
                    more_pages, cursor = notion.query_database(
                        db_id, page_size=100, start_cursor=cursor
                    )
                    all_pages.extend(more_pages)

                for page in all_pages:
                    page_phone = extract_property_value(
                        page.properties, "Phone", "phone_number"
                    )
                    if normalize_phone(page_phone) == normalized_input:
                        client_page = page
                        break

        if not client_page:
            return PortalResponse(
                found=False,
                message="No client found with that phone or email. Please check and try again."
            )

        # Extract client data
        props = client_page.properties
        client_info = ClientInfo(
            name=extract_property_value(props, "Name", "title"),
            sessions_remaining=int(extract_property_value(props, "Sessions Remaining", "number")),
            sessions_purchased=int(extract_property_value(props, "Sessions Purchased", "number")),
            sessions_used=int(extract_property_value(props, "Sessions Used", "number")),
            status=extract_property_value(props, "Status", "select") or "Unknown",
            next_appointment=extract_property_value(props, "Next Appointment", "date"),
            last_synced=extract_property_value(props, "Last Synced", "date"),
        )

        # Get upcoming appointments if appointments DB is configured
        upcoming = []
        if config.notion.db_appointments:
            customer_id = extract_property_value(props, "Square ID", "rich_text")
            if customer_id:
                try:
                    # Query appointments for this customer, future dates
                    today = datetime.utcnow().strftime("%Y-%m-%d")
                    filter_ = {
                        "and": [
                            {"property": "Customer ID", "rich_text": {"equals": customer_id}},
                            {"property": "Date", "date": {"on_or_after": today}},
                        ]
                    }
                    sorts = [{"property": "Date", "direction": "ascending"}]
                    appt_pages, _ = notion.query_database(
                        config.notion.db_appointments,
                        filter_=filter_,
                        sorts=sorts,
                        page_size=5,
                    )
                    for appt in appt_pages:
                        appt_props = appt.properties
                        upcoming.append(AppointmentInfo(
                            date=extract_property_value(appt_props, "Date", "date") or "",
                            time=extract_property_value(appt_props, "Time", "rich_text") or "",
                            status=extract_property_value(appt_props, "Status", "select") or "",
                        ))
                except Exception:
                    logger.warning("Failed to fetch appointments")

        return PortalResponse(
            found=True,
            client=client_info,
            upcoming_appointments=upcoming,
            message="",
        )

    @router.post("/sync-now")
    async def trigger_sync(request: Request):
        """Trigger an immediate sync (staff use)."""
        triggered = request.app.state.scheduler.trigger_now()
        return {
            "success": True,
            "triggered": triggered,
            "message": f"Sync started for {len(triggered)} job(s). Data will update shortly."
        }

    app.include_router(router)


def get_portal_html() -> str:
    """Return the client portal HTML."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Session Balance</title>
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
        .form-group {
            margin-bottom: 20px;
        }
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
        .result {
            margin-top: 30px;
            display: none;
        }
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
        .appointments {
            margin-top: 20px;
            text-align: left;
        }
        .appointments h3 {
            font-size: 16px;
            color: #333;
            margin-bottom: 10px;
        }
        .appt-item {
            background: white;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .appt-date { font-weight: 500; }
        .appt-time { color: #666; font-size: 14px; }
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
        .staff-section {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e1e1e1;
        }
        .staff-btn {
            background: #6c757d;
            padding: 10px;
            font-size: 14px;
        }
        .staff-btn:hover {
            box-shadow: 0 5px 20px rgba(108, 117, 125, 0.4);
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

        <div class="staff-section">
            <button class="staff-btn" id="syncBtn" onclick="triggerSync()">
                Staff: Sync Now
            </button>
        </div>
    </div>

    <script>
        const form = document.getElementById('lookupForm');
        const result = document.getElementById('result');
        const submitBtn = document.getElementById('submitBtn');

        // Escape HTML to prevent XSS
        function escapeHtml(str) {
            if (str == null) return '';
            const div = document.createElement('div');
            div.textContent = String(str);
            return div.innerHTML;
        }

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
            result.textContent = '';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = message;
            result.appendChild(errorDiv);
            result.classList.add('show');
        }

        function showResult(data) {
            const client = data.client;
            const statusClass = client.status === 'Active' ? 'status-active'
                : client.status === 'Low Sessions' ? 'status-low'
                : 'status-needs';

            result.textContent = '';
            const card = document.createElement('div');
            card.className = 'result-card';

            const nameDiv = document.createElement('div');
            nameDiv.className = 'client-name';
            nameDiv.textContent = client.name;
            card.appendChild(nameDiv);

            const circleDiv = document.createElement('div');
            circleDiv.className = 'sessions-circle';
            const numDiv = document.createElement('div');
            numDiv.className = 'sessions-number';
            numDiv.textContent = parseInt(client.sessions_remaining) || 0;
            const lblDiv = document.createElement('div');
            lblDiv.className = 'sessions-label';
            lblDiv.textContent = 'sessions left';
            circleDiv.appendChild(numDiv);
            circleDiv.appendChild(lblDiv);
            card.appendChild(circleDiv);

            const statusDiv = document.createElement('div');
            statusDiv.className = 'status-badge ' + statusClass;
            statusDiv.textContent = client.status;
            card.appendChild(statusDiv);

            const row1 = document.createElement('div');
            row1.className = 'detail-row';
            const lbl1 = document.createElement('span');
            lbl1.className = 'detail-label';
            lbl1.textContent = 'Purchased';
            const val1 = document.createElement('span');
            val1.className = 'detail-value';
            val1.textContent = parseInt(client.sessions_purchased) || 0;
            row1.appendChild(lbl1);
            row1.appendChild(val1);
            card.appendChild(row1);

            const row2 = document.createElement('div');
            row2.className = 'detail-row';
            const lbl2 = document.createElement('span');
            lbl2.className = 'detail-label';
            lbl2.textContent = 'Used';
            const val2 = document.createElement('span');
            val2.className = 'detail-value';
            val2.textContent = parseInt(client.sessions_used) || 0;
            row2.appendChild(lbl2);
            row2.appendChild(val2);
            card.appendChild(row2);

            if (data.upcoming_appointments && data.upcoming_appointments.length > 0) {
                const apptsDiv = document.createElement('div');
                apptsDiv.className = 'appointments';
                const h3 = document.createElement('h3');
                h3.textContent = 'Upcoming Appointments';
                apptsDiv.appendChild(h3);
                data.upcoming_appointments.forEach(a => {
                    const item = document.createElement('div');
                    item.className = 'appt-item';
                    const dateSpan = document.createElement('span');
                    dateSpan.className = 'appt-date';
                    dateSpan.textContent = formatDate(a.date);
                    const timeSpan = document.createElement('span');
                    timeSpan.className = 'appt-time';
                    timeSpan.textContent = a.time || '';
                    item.appendChild(dateSpan);
                    item.appendChild(timeSpan);
                    apptsDiv.appendChild(item);
                });
                card.appendChild(apptsDiv);
            }

            if (client.last_synced) {
                const syncDiv = document.createElement('div');
                syncDiv.className = 'last-sync';
                syncDiv.textContent = 'Last updated: ' + formatDate(client.last_synced);
                card.appendChild(syncDiv);
            }

            result.appendChild(card);
            result.classList.add('show');
        }

        function formatDate(dateStr) {
            if (!dateStr) return '';
            const d = new Date(dateStr);
            return d.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric'
            });
        }

        async function triggerSync() {
            const btn = document.getElementById('syncBtn');
            btn.disabled = true;
            btn.textContent = 'Syncing...';

            try {
                const response = await fetch('/portal/sync-now', { method: 'POST' });
                const data = await response.json();
                btn.textContent = 'Sync Started!';
                setTimeout(() => {
                    btn.textContent = 'Staff: Sync Now';
                    btn.disabled = false;
                }, 3000);
            } catch (err) {
                btn.textContent = 'Sync Failed';
                setTimeout(() => {
                    btn.textContent = 'Staff: Sync Now';
                    btn.disabled = false;
                }, 2000);
            }
        }
    </script>
</body>
</html>'''
