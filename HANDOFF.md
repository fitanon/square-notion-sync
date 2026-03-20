# Project Handoff: The Fit Clinic Portal

## Project Overview
A client-facing portal where fitness clients can check their remaining training sessions by entering their phone or email. Data syncs from Square → Notion, and the portal reads from Notion.

## Current Status

### What's DONE
1. **Full sync system** - Python backend that syncs Square data (payments, appointments, invoices) to Notion databases
2. **Vercel deployment config** - `vercel.json` and `api/index.py` ready for serverless deployment
3. **Client portal UI** - Beautiful branded page matching The Fit Clinic brand guidelines (dark charcoal + gold)
4. **Session lookup endpoint** - `/portal/lookup?phone=XXX` or `?email=XXX` API endpoint

### What's NOT WORKING
1. **Vercel environment variables** - Need to be configured in Vercel dashboard
2. **Notion integration connection** - The Notion integration needs to be connected to the database

### What Manus Needs to Do

#### Step 1: Create New Notion Integration Token
The previous token was exposed and needs to be regenerated:
1. Go to https://www.notion.so/my-integrations
2. Click the existing integration (or create new one called "Fit Clinic Portal")
3. Copy the "Internal Integration Secret" (starts with `ntn_`)

#### Step 2: Connect Integration to Notion Database
1. Open the Sessions/Clients database in Notion
2. Database URL: https://www.notion.so/2cd72568b32a81e58320f515603f19d8
3. Click the **...** menu (top right corner)
4. Click **Connections** → **Add connections**
5. Select the "Fit Clinic Portal" integration

#### Step 3: Add Environment Variables in Vercel
1. Go to https://vercel.com/dashboard
2. Click "square-notion-sync" project
3. Go to **Settings** → **Environment Variables**
4. Add these variables:

| Name | Value |
|------|-------|
| `NOTION_TOKEN` | (the new token from Step 1) |
| `NOTION_DB_SESSIONS` | `2cd72568b32a81e58320f515603f19d8` |

5. Make sure to select "Production", "Preview", and "Development" checkboxes

#### Step 4: Redeploy
1. Go to **Deployments** tab
2. Click **...** next to the latest deployment
3. Click **Redeploy**
4. Wait for it to complete

#### Step 5: Test
1. Visit https://square-notion-sync.vercel.app
2. Enter a client's phone number or email
3. Should show their session balance

---

## Key Files

### `/api/index.py`
The main serverless function. Contains:
- FastAPI app with The Fit Clinic branding
- `/` - Main portal page (HTML/CSS/JS)
- `/portal/lookup` - API endpoint to look up client by phone/email
- `/health` - Health check endpoint

### `/vercel.json`
Vercel deployment configuration - routes all requests to the API.

### `/core/notion.py`
Notion API client with methods for querying databases.

### `/core/config.py`
Configuration classes for Notion and Square credentials.

---

## Notion Database Schema Expected
The portal expects these properties in the Sessions database:

| Property | Type | Purpose |
|----------|------|---------|
| Name | Title | Client name |
| Email | Email | For lookup |
| Phone | Phone | For lookup |
| Sessions Remaining | Number | Current balance |
| Sessions Purchased | Number | Total purchased |
| Sessions Used | Number | Total used |
| Status | Select | Active/Low Sessions/etc |
| Last Synced | Date | When last updated |

---

## GitHub Repository
- **Repo**: fitanon/square-notion-sync
- **Branch with latest code**: `claude/analyze-repository-uJMcr`
- **Main branch**: `main` (may need to merge the claude branch)

---

## Credentials Needed
1. **Notion Integration Token** - Generate new one (old one was exposed)
2. **Notion Database ID** - `2cd72568b32a81e58320f515603f19d8`
3. **Vercel Account** - Owner: fitanon

---

## If Portal Still Doesn't Work After Setup

Check these common issues:

1. **"Service not configured"** - NOTION_TOKEN not set or invalid
2. **"Database not configured"** - NOTION_DB_SESSIONS not set
3. **"No account found"** - Client doesn't exist in database OR integration doesn't have access to database
4. **500 errors** - Check Vercel logs (Deployments → Click deployment → Logs)

---

## Contact/Resources
- Vercel Dashboard: https://vercel.com/dashboard
- Notion Integrations: https://www.notion.so/my-integrations
- Deployed URL: https://square-notion-sync.vercel.app
