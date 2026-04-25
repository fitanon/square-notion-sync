# Secrets and Environment Variable Registry

Purpose: single source for what must be stored in GitHub/Vercel environment config
for this project and related FitClinic automations.

---

## 1) Security Rules

- Never commit real secret values to git.
- Store secrets in platform secret stores only.
- Prefer references (IDs/URLs) in repo docs, and secret values in platform settings.
- Rotate tokens if they are ever shared in plain text.

---

## 2) Core Variables for This Repository (`square-notion-sync`)

These keys are used by the scripts and README in this repo.

### Required for Google Sheets → Notion questionnaire mirror

| Key | Secret? | Purpose |
|---|---|---|
| `GOOGLE_SHEETS_SPREADSHEET_ID` | No | Source Google Sheet ID |
| `GOOGLE_SHEETS_WORKSHEET` | No | Worksheet/tab name (e.g. `Questionnaire Responses`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes | Service account JSON blob (preferred in hosted env) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | No (path only) | Local dev file path alternative |
| `NOTION_TOKEN` | Yes | Notion integration token |
| `NOTION_PARENT_PAGE_ID` | No | Parent page where a new DB gets created |
| `NOTION_VERSION` | No | Notion API version header (default `2022-06-28`) |

### Existing Square sync keys

| Key | Secret? | Purpose |
|---|---|---|
| `SQUARE_ENV` | No | `sandbox` or `production` |
| `SQUARE_ACCESS_TOKEN` | Yes | Default Square token |
| `SQUARE_SANDBOX_ACCESS_TOKEN` | Yes | Sandbox token |
| `ACCOUNT__FITCLINIC_LLC__TOKEN` | Yes | Per-account Square token |
| `ACCOUNT__FITCLINIC__TOKEN` | Yes | Per-account Square token |
| `ACCOUNT__FITNESSWITHMIKE__TOKEN` | Yes | Per-account Square token |
| `ACCOUNT__FITCLINIC_LLC__EMAIL` | No | Metadata |
| `ACCOUNT__FITCLINIC__EMAIL` | No | Metadata |
| `ACCOUNT__FITNESSWITHMIKE__EMAIL` | No | Metadata |

### Optional existing keys in repo

| Key | Secret? | Purpose |
|---|---|---|
| `PERPLEXITY_API_KEY` | Yes | Perplexity integration |
| `COMET_API_KEY` | Yes | Comet integration |
| `DRY_RUN` | No | Safety flag for some scripts |

---

## 3) Platform Placement (GitHub + Vercel)

## GitHub (Repo Settings → Secrets and variables → Actions)

### Store as **Secrets**

- `NOTION_TOKEN`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `SQUARE_ACCESS_TOKEN`
- `SQUARE_SANDBOX_ACCESS_TOKEN`
- `ACCOUNT__FITCLINIC_LLC__TOKEN`
- `ACCOUNT__FITCLINIC__TOKEN`
- `ACCOUNT__FITNESSWITHMIKE__TOKEN`
- `PERPLEXITY_API_KEY` (if used)
- `COMET_API_KEY` (if used)

### Store as **Variables**

- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_WORKSHEET`
- `NOTION_PARENT_PAGE_ID`
- `NOTION_VERSION`
- `SQUARE_ENV`
- `DRY_RUN`
- account email metadata keys

### Optional environment-specific scopes

If you use GitHub environments (`development`, `preview`, `production`), define
environment-scoped secrets/variables with the same key names.

---

## Vercel (Project Settings → Environment Variables)

### Set in each target environment as needed

- Production
- Preview
- Development

### Recommended mapping

**Encrypted / sensitive:**

- `NOTION_TOKEN`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- all Square token keys
- optional third-party API keys

**Plain config:**

- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_WORKSHEET`
- `NOTION_PARENT_PAGE_ID`
- `NOTION_VERSION`
- `SQUARE_ENV`
- `DRY_RUN`

---

## 4) Standard Naming Convention

Use these prefixes to keep future secrets organized:

- `NOTION_*` → Notion credentials/config
- `GOOGLE_*` → Google Sheets/service account
- `SQUARE_*` and `ACCOUNT__*__TOKEN` → Square auth
- `VERCEL_*` → deployment/runtime-specific values
- `APP_*` → app-level config (non-secret)

---

## 5) Notion IDs as Config Data (Not Secrets)

Notion database/page IDs are generally not secrets; treat them as config references.
Store critical IDs in versioned docs (`SYSTEM_MAP_EXTRACT.md`) and only promote to env
variables when scripts need them.

Suggested optional config keys if automation needs stable DB pointers:

- `NOTION_DB_OFFICIAL_DATABASE_ID=28072568-b32a-802c-ac78-faac010d4577`
- `NOTION_DB_APPOINTMENTS_ID=1e272568-b32a-8010-8f94-f8bb521eeca4`
- `NOTION_DB_CLIENTS_ID=1e272568-b32a-8097-b8ae-dc5947b22f74`
- `NOTION_DB_SESSION_LOGS_ID=1e272568-b32a-805b-8fa1-f4c08fc13a9e`
- `NOTION_DB_LOW_SESSIONS_ID=1865bdbb-e2fa-4997-98d1-fc00d6382649`
- `NOTION_DB_ALL_CLIENTS_ID=846de93c-8cce-4707-a71f-ac5a9fcef37f`
- `NOTION_DB_TRANSITION_CLIENTS_ID=590dec84-411b-4403-8247-8ef40b6776ec`
- `NOTION_DB_TRANSITION_TRAINERS_ID=629864e7-d2d6-4748-827b-0cf5e571c6ea`
- `NOTION_DB_STAFF_LINKS_RESOURCES_ID=05bc8072-3d9d-4e80-9085-4e160ef20b42`
- `NOTION_DB_CLIENT_INTAKE_FORM_ID=1e272568-b32a-8062-a9a6-f8a71dfd0efa`
- `NOTION_DB_FITCLINIC_CUSTOMER_SYNC_ID=98777021-5044-4456-ae36-d90b1ba7ae1c`
- `NOTION_DB_SQUARE_ORDERS_TFC_ID=2d13f6b4-608b-4e35-9e99-8e28f37ab27e`
- `NOTION_DB_SQUARE_SALES_TFC_ID=83ff7e37-6dea-4eb7-943a-5b159d881419`
- `NOTION_DB_SQUARE_CUSTOMERS_TFC_ID=d0da27b5-84f7-45b1-ac34-ba2c6f11940d`

Optional data-source env keys (for scripting/query layers):

- `NOTION_DS_STAFF_SESSIONS=collection://5453838d-36dc-499a-aab3-96b83ad753b3`
- `NOTION_DS_ALL_CLIENTS_LEGACY=collection://9a4d6934-951f-43a8-9e21-7daf753f8d0b`
- `NOTION_DS_CLIENT_PACKAGES=collection://f48657be-b022-4707-b1c3-7c0175657979`
- `NOTION_DS_SESSION_PAYROLL=collection://03a8eee4-0e57-48c4-9933-c3e30cd6bbe7`
- `NOTION_DS_MANAGEMENT_INTAKE=collection://33672568-b32a-804a-981e-000befdf764a`
- `NOTION_DS_TRANSITION_CLIENTS=collection://5b5e0d5f-d7c9-4edd-bac9-b7c0ddaf482c`
- `NOTION_DS_TRANSITION_TRAINERS=collection://90c0508e-aafd-4c74-8140-0ee9c0fea7c6`
- `NOTION_DS_STAFF_LINKS_RESOURCES=collection://5aa5fa58-0f61-4ed3-bb66-b1c8bccbe28d`
- `NOTION_DS_SESSION_LOGS=collection://1e272568-b32a-807c-becf-000b408d9e12`

Google Sheets IDs from saved prompts:

- `GOOGLE_SHEETS_SPREADSHEET_ID=1x5I9-qOCjEER3gIHnX2Ds-C-xhdo92hQTX0vpeohLHY` (CentralTFC live sync)
- `GOOGLE_SHEETS_CHECKINS_SPREADSHEET_ID=1-D1MCAJYb6rqZ3gmGHqB_q2FCEs74paAQ4MTsi06MhU` (check-ins recalibration)

---

## 6) Setup Checklist (Future-Proof)

1. Add/update keys in GitHub Secrets + Variables.
2. Mirror same keys into Vercel env vars.
3. Confirm branch/preview/prod scopes.
4. Run one dry-run sync command:

```bash
python3 scripts/mirror_questionnaires_to_notion.py \
  --worksheet "Questionnaire Responses" \
  --use-questionnaire-default-fields \
  --dry-run --limit 5
```

5. Run live sync after preview is correct.

