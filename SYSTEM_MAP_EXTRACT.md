# TFC System Map (Extracted from saved prompt)

This file captures the highest-value architecture details and IDs from prior prompts so future agents and automations use the same canonical map.

## 1) Core rule for Notion IDs

- A Notion "database ID" (UUID) is not always the same identifier used by scripting/query layers.
- For automation/query tooling in this project, prefer **data source URLs** when available (`collection://...`).
- Store both when possible:
  - `NOTION_DB_*` for UUIDs
  - `NOTION_DS_*` for `collection://...`

## 2) Canonical pipeline (current model)

1. Square (3 business accounts) feeds operational/sales data.
2. Google Sheets is the transformation layer and near-live sync source.
3. Notion is the staff-facing operations surface and selected ledger layer.
4. Vercel dashboards read from synchronized data surfaces (especially sheets-derived views).

## 3) Canonical Google Sheets

- Central live-sync sheet (Dashboard - CentralTFC):
  - `1x5I9-qOCjEER3gIHnX2Ds-C-xhdo92hQTX0vpeohLHY`
  - URL: `https://docs.google.com/spreadsheets/d/1x5I9-qOCjEER3gIHnX2Ds-C-xhdo92hQTX0vpeohLHY/edit?gid=528169965#gid=528169965`
- Check-ins recalibration sheet:
  - `1-D1MCAJYb6rqZ3gmGHqB_q2FCEs74paAQ4MTsi06MhU`
  - URL: `https://docs.google.com/spreadsheets/d/1-D1MCAJYb6rqZ3gmGHqB_q2FCEs74paAQ4MTsi06MhU/edit?gid=353068323#gid=353068323`

## 4) Appointments hub model

Preferred top-level structure under Appointments:

1. Packages
2. Sessions
3. Clients
4. Bookings
5. Sales

Supporting sections:

- Token and API Keys
- README
- Fundamental Files
- Historical Data and Logs
- Square-related Files
- Google Sheets

## 5) High-priority Notion entities to keep canonical

The following IDs were repeatedly referenced and are the highest-value for pipeline config:

| Purpose | Name | Notion DB ID | Data Source URL (if known) |
|---|---|---|---|
| Main hub | Official Database | `28072568-b32a-802c-ac78-faac010d4577` | unresolved |
| Hub page/db | Appointments | `1e272568-b32a-8010-8f94-f8bb521eeca4` | unresolved |
| Client ops (newer naming) | Low Sessions | `1865bdbb-e2fa-4997-98d1-fc00d6382649` | `collection://5453838d-36dc-499a-aab3-96b83ad753b3` |
| Legacy clients | All Clients | `846de93c-8cce-4707-a71f-ac5a9fcef37f` | `collection://9a4d6934-951f-43a8-9e21-7daf753f8d0b` |
| Package ledger | Client Packages | unresolved in DB UUID list | `collection://f48657be-b022-4707-b1c3-7c0175657979` |
| Session ledger/log | Session Logs | `1e272568-b32a-805b-8fa1-f4c08fc13a9e` | `collection://1e272568-b32a-807c-becf-000b408d9e12` (older map) |
| Payroll periods | Session Payroll | unresolved in DB UUID list | `collection://03a8eee4-0e57-48c4-9933-c3e30cd6bbe7` |
| Intake/accounts | Management and View of Client Intake Form | unresolved in DB UUID list | `collection://33672568-b32a-804a-981e-000befdf764a` |
| Transition clients | Transition Clients | `590dec84-411b-4403-8247-8ef40b6776ec` | `collection://5b5e0d5f-d7c9-4edd-bac9-b7c0ddaf482c` (older map) |
| Transition trainers | Transition Trainers | `629864e7-d2d6-4748-827b-0cf5e571c6ea` | `collection://90c0508e-aafd-4c74-8140-0ee9c0fea7c6` (older map) |
| Staff resources | Staff Links & Resources | `05bc8072-3d9d-4e80-9085-4e160ef20b42` | `collection://5aa5fa58-0f61-4ed3-bb66-b1c8bccbe28d` (older map) |
| Sales | Square Sales - TFC | `83ff7e37-6dea-4eb7-943a-5b159d881419` | unresolved |
| Sales orders | Square Orders - TFC | `2d13f6b4-608b-4e35-9e99-8e28f37ab27e` | unresolved |
| Sales customers | Square Customers - TFC | `d0da27b5-84f7-45b1-ac34-ba2c6f11940d` | unresolved |
| Intake form | Client Intake Form | `1e272568-b32a-8062-a9a6-f8a71dfd0efa` | unresolved |
| Sync target | FitClinic Customer Sync Database | `98777021-5044-4456-ae36-d90b1ba7ae1c` | unresolved |

## 6) Known unresolved items (from original prompt)

- Several `fitclinic.notion.site/...` links were not fully resolved to canonical `notion.so` resources.
- "Official Database" was identified by DB ID but not fully mapped to a confirmed data source URL in prior tooling.
- Bookings canonical source remains a design choice (cal.com vs Square vs Google Calendar).

## 7) Recommended source-of-truth policy

- **Square**: payments/orders/bookings truth.
- **Google Sheets**: transformations + live dashboard feed.
- **Notion**: operations-facing working datasets and controlled manual overrides.

## 8) Additional Notion DB IDs extracted from prompt inventory

These were explicitly provided in your saved prompt dump and are added here for
reference/config alignment.

| Name | Notion DB ID |
|---|---|
| Client Assessments | `[REDACTED]` |
| Official Database | `28072568-b32a-802c-ac78-faac010d4577` |
| Program Tracker | `fd5bea0b-9ca6-484b-9d39-6a4fef8d12de` |
| Captures | `911aaf1b-14d7-43ee-81a6-c8033c094854` |
| Days | `be53ccf2-d8aa-42e4-8403-0b3d7f393800` |
| Targets | `063da530-3265-4628-8c4a-b05456a7f18e` |
| Session Logs | `1e272568-b32a-805b-8fa1-f4c08fc13a9e` |
| Home | `23572568-b32a-800d-a8b4-cc5d5527c1cb` |
| Employee Onboarding Form | `2c672568-b32a-80fd-9071-d52ca28c94a9` |
| Master Organizational Directory | `ce2fbd41-3290-4e42-b7c3-650820fa04ef` |
| Links [2026] | `30d72568-b32a-813d-9942-fd359b525f04` |
| Staff Links & Resources | `05bc8072-3d9d-4e80-9085-4e160ef20b42` |
| Wells Fargo Transactions | `1ce9d672-3246-45ad-870a-e49b7376f241` |
| Appointments | `1e272568-b32a-8010-8f94-f8bb521eeca4` |
| Clients | `1e272568-b32a-8097-b8ae-dc5947b22f74` |
| Projects | `20172568-b32a-808c-a6ef-c320e6ffa2a7` |
| Meetings | `23472568-b32a-80f3-b4c5-e00c72d39e99` |
| AI-Enhanced Knowledge Base Tracker | `24572568-b32a-8005-8ebb-ddc7bbc00079` |
| Transition Clients | `590dec84-411b-4403-8247-8ef40b6776ec` |
| Developer APIs & Integrations | `7f2edba9-0fe5-4aef-b741-e5b2fa0cc1b3` |
| Square Sales - TFC | `83ff7e37-6dea-4eb7-943a-5b159d881419` |
| All Clients | `846de93c-8cce-4707-a71f-ac5a9fcef37f` |
| FitClinic Customer Sync Database | `98777021-5044-4456-ae36-d90b1ba7ae1c` |
| Square Customers - TFC | `d0da27b5-84f7-45b1-ac34-ba2c6f11940d` |
| Client Database | `1e272568-b32a-804c-bcf2-cf85f55283fa` |
| Client Intake Form | `1e272568-b32a-8062-a9a6-f8a71dfd0efa` |
| All Workflow | `28072568-b32a-804e-84bb-fd81566b4e35` |

Notes:
- Your prompt contained many duplicate "Todays Diet Table" DB entries with
  different IDs. Keep those as per-client shards unless you decide to
  consolidate.
- For automation/query scripts in this repo, still prefer resolved
  `collection://...` data source IDs when available.

