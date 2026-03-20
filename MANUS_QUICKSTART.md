# Manus Quick Start Guide
## The Fit Clinic Portal - Setup Instructions

---

## Summary
The portal is 95% complete. Just needs Notion credentials configured in Vercel.

**Live URL:** https://square-notion-sync.vercel.app
**Repo:** github.com/fitanon/square-notion-sync
**Branch:** claude/analyze-repository-uJMcr

---

## 4 Steps to Complete

### Step 1: Create New Notion Token
> Previous token was accidentally exposed - must regenerate

1. Go to: **https://www.notion.so/my-integrations**
2. Click existing integration OR create new one named "Fit Clinic Portal"
3. Copy the **Internal Integration Secret** (starts with `ntn_`)
4. Save this - you'll need it in Step 3

---

### Step 2: Connect Integration to Database
> The integration needs permission to read the database

1. Open Notion
2. Go to the Sessions/Clients database
3. Click **⋯** (three dots, top right)
4. Click **Connections**
5. Click **Add connections**
6. Select your integration ("Fit Clinic Portal")

---

### Step 3: Add Environment Variables in Vercel

1. Go to: **https://vercel.com/dashboard**
2. Click project: **square-notion-sync**
3. Click **Settings** tab
4. Click **Environment Variables** in sidebar
5. Add these two variables:

```
Name:  NOTION_TOKEN
Value: [paste the token from Step 1]

Name:  NOTION_DB_SESSIONS
Value: 2cd72568b32a81e58320f515603f19d8
```

6. Check all environment boxes: ✅ Production, ✅ Preview, ✅ Development
7. Click **Save**

---

### Step 4: Redeploy

1. Go to **Deployments** tab in Vercel
2. Find the top/latest deployment
3. Click the **⋯** (three dots) on the right
4. Click **Redeploy**
5. Wait 30-60 seconds

---

## Test It

1. Go to: **https://square-notion-sync.vercel.app**
2. Enter a client's phone number or email
3. Should display their session balance with gold/dark branding

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Service not configured" | NOTION_TOKEN missing or invalid |
| "Database not configured" | NOTION_DB_SESSIONS missing |
| "No account found" | Client not in database OR integration not connected (Step 2) |
| Blank page / errors | Check Vercel logs: Deployments → click deployment → Logs |

---

## Database ID Reference
```
Sessions/Clients: 2cd72568b32a81e58320f515603f19d8
Transactions:     2cd72568b32a812387a1fbbbaa9ebd71
```

---

## Expected Database Properties
The Notion database should have these columns:

- **Name** (Title) - Client name
- **Email** (Email) - For lookup
- **Phone** (Phone) - For lookup
- **Sessions Remaining** (Number)
- **Sessions Purchased** (Number)
- **Sessions Used** (Number)
- **Status** (Select) - Active, Low Sessions, etc.

---

## Files Changed
- `/api/index.py` - Main portal (FastAPI + HTML/CSS)
- `/vercel.json` - Deployment config
- `/HANDOFF.md` - Detailed documentation

---

## Owner Info
- **Vercel Account:** fitanon
- **GitHub:** fitanon/square-notion-sync
- **Brand:** The Fit Clinic (Campbell & San Jose, CA)
