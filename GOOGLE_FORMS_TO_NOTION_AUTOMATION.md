# Google Forms -> Email -> Notion automation

This automation runs when someone submits a Google Form. It sends an email
notification and creates or updates a page in your Notion data source.

Default Notion target:

- Official Notion page/database link: `https://fitclinic.notion.site/34d72568b32a8181832be8eb6a9f0822?v=34d72568b32a8129a7c2000c5aa773e3&source=copy_link`
- Data source ID: `34d72568-b32a-814e-9e2b-000b7b75a88a`

Notion's browser page URL and API data source ID are different identifiers. Use
the page link above for manual review, and use the data source ID above for
`NOTION_DATA_SOURCE_ID`.

## How it works

1. Google Forms writes each submission to its response Google Sheet.
2. A Google Apps Script installable trigger runs on every new row.
3. The script reads the submitted answers.
4. The script creates or updates a Notion page in the configured data source.
5. The script emails the configured notification address.

## Setup

### 1. Connect your Form to a Google Sheet

In Google Forms:

1. Open the form.
2. Go to **Responses**.
3. Click **Link to Sheets**.
4. Create or select the response spreadsheet.

### 2. Create and share a Notion integration

1. Go to <https://www.notion.so/my-integrations>.
2. Create an internal integration.
3. Copy the integration token.
4. Open the Notion data source/page.
5. Use **Share** or **Connections** to invite the integration.

The integration needs permission to read the data source and insert/update pages.

### 3. Add the Apps Script

In the Google Sheet that receives form responses:

1. Go to **Extensions -> Apps Script**.
2. Paste the contents of `google-apps-script/form_to_notion.gs`.
3. Save the project.

### 4. Add Script Properties

In Apps Script:

1. Go to **Project Settings**.
2. Under **Script Properties**, add:

| Property | Value |
| --- | --- |
| `NOTION_TOKEN` | Your Notion integration token |
| `NOTION_DATA_SOURCE_ID` | `34d72568-b32a-814e-9e2b-000b7b75a88a` |
| `NOTIFICATION_EMAIL` | The email address that should receive alerts |

Optional properties:

| Property | Default | Purpose |
| --- | --- | --- |
| `NOTION_VERSION` | `2025-09-03` | Notion API version |
| `TITLE_PROPERTY` | `Name` | Notion title property |
| `TITLE_FIELD` | auto-detects common fields | Form question used as Notion title |
| `EMAIL_FIELD` | `Email Address` | Form question used to find existing pages |
| `MATCH_PROPERTY` | `Email` | Notion property used for upsert matching |
| `APPLY_DEFAULT_TEMPLATE` | `false` | Set `true` to apply the data source default template |
| `NOTION_FIELD_MAP` | `{}` | JSON mapping of Notion property names to form question titles |

Example `NOTION_FIELD_MAP`:

```json
{
  "Email": "Email Address",
  "Phone": "Phone Number",
  "Goals": "Goals",
  "Medical History": "Medical History",
  "Training History": "Training History",
  "Nutrition History": "Nutrition History",
  "Notes": "Any other details"
}
```

If you want the Notion page title to come from the form's "Full Name" question,
set `TITLE_FIELD` to `Full Name`.

If your Notion property names exactly match your Google Form question titles,
you can leave `NOTION_FIELD_MAP` empty.

### 5. Install the submit trigger

In Apps Script:

1. Select the function `installSubmitTrigger`.
2. Click **Run**.
3. Approve the Google permissions.

This creates the trigger that runs `onFormSubmit` every time the linked Google
Sheet receives a new Form response.

### 6. Test

1. Submit a test Google Form response.
2. Confirm a page was created or updated in Notion.
3. Confirm the notification email arrived.

If it fails, open Apps Script **Executions** to see the Notion or permission
error.

## Notion property behavior

The script maps form values into these Notion property types:

- Title
- Rich text
- Email
- Phone number
- URL
- Number
- Date
- Checkbox
- Select
- Multi-select

Unsupported property types are skipped.

## Upsert behavior

By default, the script tries to find an existing Notion page where:

- Google Form field: `Email Address`
- matches Notion property: `Email`

If a match is found, the page is updated. If no match is found, a new page is
created.

To change this, update `EMAIL_FIELD` and `MATCH_PROPERTY` in Script Properties.
