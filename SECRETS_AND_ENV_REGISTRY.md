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

