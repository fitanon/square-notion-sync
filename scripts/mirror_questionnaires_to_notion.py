#!/usr/bin/env python3
"""Mirror questionnaire responses from Google Sheets into a new Notion database.

Example:
  export NOTION_TOKEN="secret_..."
  export NOTION_PARENT_PAGE_ID="..."
  export GOOGLE_SHEETS_SPREADSHEET_ID="..."
  export GOOGLE_SERVICE_ACCOUNT_FILE="/path/to/service-account.json"

  python scripts/mirror_questionnaires_to_notion.py \
    --worksheet "Questionnaire Responses" \
    --database-title "Questionnaire Responses Mirror" \
    --limit 25 \
    --contains "completed"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Sequence, Tuple

import requests

try:
    import gspread
except ImportError:  # pragma: no cover - handled at runtime
    gspread = None


NOTION_API_BASE = "https://api.notion.com/v1"
DEFAULT_NOTION_VERSION = "2022-06-28"
DEFAULT_TITLE = "Questionnaire Responses Mirror"
MAX_NOTION_TEXT_LENGTH = 2000
QUESTIONNAIRE_DEFAULT_FIELDS = [
    "first and last name",
    "goals",
    "phone number",
    "email",
    "ai summary of medical history",
    "training history",
    "nutrition history",
    "any other details",
    "date of submission",
]
QUESTIONNAIRE_FIELD_ALIASES: Dict[str, List[str]] = {
    "goals": ["goals", "goal", "fitness goals", "primary goals"],
    "phone number": ["phone number", "phone", "mobile", "cell", "contact number"],
    "email": ["email", "email address", "e-mail"],
    "ai summary of medical history": [
        "ai summary of medical history",
        "medical history ai summary",
        "medical history summary",
        "medical history",
    ],
    "training history": ["training history", "trainiing history", "exercise history", "workout history"],
    "nutrition history": ["nutrition history", "diet history", "nutrition", "dietary history"],
    "any other details": ["any other details", "additional details", "other details", "notes", "comments"],
    "date of submission": ["date of submission", "submission date", "submitted at", "timestamp", "created at"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read questionnaire rows from Google Sheets and mirror selected rows "
            "into a newly created Notion database."
        )
    )
    parser.add_argument(
        "--spreadsheet-id",
        default=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID"),
        help="Google Sheets spreadsheet ID (or env GOOGLE_SHEETS_SPREADSHEET_ID).",
    )
    parser.add_argument(
        "--worksheet",
        default=os.getenv("GOOGLE_SHEETS_WORKSHEET"),
        help="Worksheet tab name. Defaults to first worksheet when omitted.",
    )
    parser.add_argument(
        "--service-account-file",
        default=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        help="Path to Google service account JSON file.",
    )
    parser.add_argument(
        "--service-account-json",
        default=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        help="Raw Google service account JSON string (alternative to --service-account-file).",
    )
    parser.add_argument(
        "--notion-token",
        default=os.getenv("NOTION_TOKEN"),
        help="Notion integration token (or env NOTION_TOKEN).",
    )
    parser.add_argument(
        "--notion-parent-page-id",
        default=os.getenv("NOTION_PARENT_PAGE_ID") or os.getenv("PARENT_PAGE_ID"),
        help="Notion parent page ID where new DB will be created.",
    )
    parser.add_argument(
        "--notion-version",
        default=os.getenv("NOTION_VERSION", DEFAULT_NOTION_VERSION),
        help="Notion API version header value.",
    )
    parser.add_argument(
        "--database-title",
        default=f"{DEFAULT_TITLE} - {datetime.now(timezone.utc).date().isoformat()}",
        help="Title for the new Notion database.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum rows to mirror after filtering (0 means all matched rows).",
    )
    parser.add_argument(
        "--contains",
        default="",
        help="Case-insensitive substring filter applied across each row's values.",
    )
    parser.add_argument(
        "--row-numbers",
        default="",
        help="Comma-separated Google Sheet row numbers to mirror (e.g. 2,5,9).",
    )
    parser.add_argument(
        "--columns",
        default="",
        help="Comma-separated list of column headers to include. Defaults to all headers.",
    )
    parser.add_argument(
        "--use-questionnaire-default-fields",
        action="store_true",
        help=(
            "Use a built-in questionnaire field set: first/last name, goals, phone, email, "
            "AI medical summary, training history, nutrition history, other details, submission date."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan only (no Notion writes).",
    )
    return parser.parse_args()


def parse_comma_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_row_numbers(raw: str) -> List[int]:
    row_numbers: List[int] = []
    for item in parse_comma_list(raw):
        try:
            row_numbers.append(int(item))
        except ValueError as exc:
            raise ValueError(f"Invalid row number '{item}'. Use integers like 2,5,9.") from exc
    return row_numbers


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def find_best_header(headers: Sequence[str], aliases: Sequence[str]) -> str | None:
    best_header = None
    best_score = 0
    for alias in aliases:
        alias_norm = normalize(alias)
        if not alias_norm:
            continue
        for header in headers:
            header_norm = normalize(header)
            score = 0
            if header_norm == alias_norm:
                score = 3
            elif alias_norm in header_norm:
                score = 2
            elif header_norm in alias_norm:
                score = 1

            if score > best_score:
                best_score = score
                best_header = header
    return best_header


def resolve_requested_columns(requested_columns: Sequence[str], headers: Sequence[str]) -> Tuple[List[str], List[str]]:
    selected: List[str] = []
    unresolved: List[str] = []

    for requested in requested_columns:
        requested_norm = normalize(requested)

        # Prefer direct case-insensitive exact match first.
        exact_header = find_best_header(headers, [requested])
        if exact_header:
            if exact_header not in selected:
                selected.append(exact_header)
            continue

        # Handle "first and last name" as either two columns or one full-name column.
        if requested_norm in {"firstandlastname", "firstnameandlastname"}:
            first_header = find_best_header(headers, ["first name", "firstname", "given name"])
            last_header = find_best_header(headers, ["last name", "lastname", "family name", "surname"])
            if first_header and last_header:
                if first_header not in selected:
                    selected.append(first_header)
                if last_header not in selected:
                    selected.append(last_header)
                continue

            full_name_header = find_best_header(headers, ["full name", "client name", "name"])
            if full_name_header:
                if full_name_header not in selected:
                    selected.append(full_name_header)
                continue

            unresolved.append(requested)
            continue

        aliases = QUESTIONNAIRE_FIELD_ALIASES.get(requested.lower().strip(), [requested])
        matched = find_best_header(headers, aliases)
        if matched:
            if matched not in selected:
                selected.append(matched)
        else:
            unresolved.append(requested)

    return selected, unresolved


def notion_headers(token: str, notion_version: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": notion_version,
        "Content-Type": "application/json",
    }


def load_google_sheet_rows(
    spreadsheet_id: str,
    worksheet_name: str | None,
    service_account_file: str | None,
    service_account_json: str | None,
) -> Tuple[str, List[str], List[Dict[str, str]]]:
    if gspread is None:
        raise RuntimeError(
            "Missing dependency 'gspread'. Install dependencies with: pip install -r requirements.txt"
        )

    if service_account_json:
        credentials = json.loads(service_account_json)
        client = gspread.service_account_from_dict(credentials)
    elif service_account_file:
        client = gspread.service_account(filename=service_account_file)
    else:
        # Fall back to Application Default Credentials (ADC).
        # Works when the user has run: gcloud auth application-default login
        # This bypasses the need for a service account key file entirely.
        try:
            import google.auth
            from google.auth.transport.requests import Request as GoogleAuthRequest
            from google.oauth2.credentials import Credentials

            SCOPES = [
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
            creds, _ = google.auth.default(scopes=SCOPES)
            # Refresh if needed
            creds.refresh(GoogleAuthRequest())
            client = gspread.authorize(creds)
        except Exception as adc_exc:
            raise ValueError(
                "Missing Google credentials. Either:\n"
                "  1. Run: gcloud auth application-default login\n"
                "  2. Set --service-account-file or --service-account-json\n"
                f"ADC error: {adc_exc}"
            )

    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.get_worksheet(0)
    values = worksheet.get_all_values()

    if not values:
        return worksheet.title, [], []

    raw_headers = values[0]
    headers: List[str] = []
    for idx, header in enumerate(raw_headers, start=1):
        normalized = header.strip() or f"Column {idx}"
        headers.append(normalized)

    rows: List[Dict[str, str]] = []
    for row_index, row in enumerate(values[1:], start=2):
        padded = row + ([""] * (len(headers) - len(row)))
        data = {headers[i]: padded[i].strip() for i in range(len(headers))}
        if any(value for value in data.values()):
            data["_sheet_row_number"] = str(row_index)
            rows.append(data)

    return worksheet.title, headers, rows


def select_rows(
    rows: Sequence[Dict[str, str]],
    row_numbers: Sequence[int],
    contains_filter: str,
    limit: int,
) -> List[Dict[str, str]]:
    selected = list(rows)

    if row_numbers:
        wanted = set(row_numbers)
        selected = [row for row in selected if int(row["_sheet_row_number"]) in wanted]

    if contains_filter:
        needle = contains_filter.lower()
        selected = [
            row
            for row in selected
            if needle in " ".join(value for key, value in row.items() if key != "_sheet_row_number").lower()
        ]

    if limit and limit > 0:
        selected = selected[:limit]

    return selected


def pick_title(row: Dict[str, str]) -> str:
    preferred_fields = [
        "Name",
        "Full Name",
        "Client Name",
        "First Name",
        "Email",
        "Email Address",
        "Timestamp",
    ]
    for field in preferred_fields:
        value = row.get(field, "").strip()
        if value:
            return value[:MAX_NOTION_TEXT_LENGTH]
    return f"Response Row {row.get('_sheet_row_number', '?')}"


def safe_property_name(name: str, used_names: set[str]) -> str:
    collapsed = re.sub(r"\s+", " ", name.strip())
    candidate = collapsed if collapsed else "Unnamed Column"
    if len(candidate) > 100:
        candidate = candidate[:100]

    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    suffix = 2
    while True:
        alt = f"{candidate} ({suffix})"
        if alt not in used_names:
            used_names.add(alt)
            return alt
        suffix += 1


def create_notion_database(
    token: str,
    notion_version: str,
    parent_page_id: str,
    database_title: str,
    selected_headers: Sequence[str],
) -> Tuple[str, Dict[str, str]]:
    used = {"Name", "Sheet Row", "Imported At"}
    column_mapping: Dict[str, str] = {}
    properties: Dict[str, Dict[str, dict]] = {
        "Name": {"title": {}},
        "Sheet Row": {"number": {}},
        "Imported At": {"date": {}},
    }

    for header in selected_headers:
        property_name = safe_property_name(header, used)
        column_mapping[header] = property_name
        properties[property_name] = {"rich_text": {}}

    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": database_title[:MAX_NOTION_TEXT_LENGTH]}}],
        "properties": properties,
    }
    response = requests.post(
        f"{NOTION_API_BASE}/databases",
        headers=notion_headers(token, notion_version),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["id"], column_mapping


def create_notion_page(
    token: str,
    notion_version: str,
    database_id: str,
    row: Dict[str, str],
    column_mapping: Dict[str, str],
) -> str:
    properties: Dict[str, dict] = {
        "Name": {"title": [{"text": {"content": pick_title(row)}}]},
        "Sheet Row": {"number": int(row["_sheet_row_number"])},
        "Imported At": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
    }

    for source_col, notion_col in column_mapping.items():
        value = row.get(source_col, "")
        if not value:
            continue
        properties[notion_col] = {"rich_text": [{"text": {"content": value[:MAX_NOTION_TEXT_LENGTH]}}]}

    payload = {"parent": {"database_id": database_id}, "properties": properties}
    response = requests.post(
        f"{NOTION_API_BASE}/pages",
        headers=notion_headers(token, notion_version),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["id"]


def main() -> int:
    args = parse_args()

    if not args.spreadsheet_id:
        print("ERROR: Missing spreadsheet id. Set --spreadsheet-id or GOOGLE_SHEETS_SPREADSHEET_ID.")
        return 1
    if not args.notion_token:
        print("ERROR: Missing Notion token. Set --notion-token or NOTION_TOKEN.")
        return 1
    if not args.notion_parent_page_id:
        print("ERROR: Missing Notion parent page id. Set --notion-parent-page-id or NOTION_PARENT_PAGE_ID.")
        return 1

    try:
        explicit_row_numbers = parse_row_numbers(args.row_numbers)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    requested_columns = parse_comma_list(args.columns)
    if args.use_questionnaire_default_fields:
        requested_columns = list(QUESTIONNAIRE_DEFAULT_FIELDS)

    try:
        worksheet_title, headers, rows = load_google_sheet_rows(
            spreadsheet_id=args.spreadsheet_id,
            worksheet_name=args.worksheet,
            service_account_file=args.service_account_file,
            service_account_json=args.service_account_json,
        )
    except Exception as exc:
        print(f"ERROR: Failed reading Google Sheet: {exc}")
        return 1

    if not headers:
        print("No headers found in worksheet. Nothing to mirror.")
        return 0

    if requested_columns:
        selected_headers, missing_headers = resolve_requested_columns(requested_columns, headers)
        if missing_headers:
            print(f"ERROR: Requested columns not found: {missing_headers}")
            print(f"Available headers: {headers}")
            return 1
    else:
        selected_headers = headers

    selected_rows = select_rows(
        rows=rows,
        row_numbers=explicit_row_numbers,
        contains_filter=args.contains,
        limit=args.limit,
    )

    if not selected_rows:
        print("No rows matched your filters; no Notion database/page created.")
        return 0

    print(f"Worksheet: {worksheet_title}")
    print(f"Total non-empty rows: {len(rows)}")
    print(f"Rows selected for mirror: {len(selected_rows)}")
    print(f"Columns selected: {selected_headers}")

    if args.dry_run:
        print("\nDry run enabled. No Notion API writes performed.")
        print("Sample selected row:")
        print(json.dumps(selected_rows[0], indent=2))
        return 0

    try:
        database_id, column_mapping = create_notion_database(
            token=args.notion_token,
            notion_version=args.notion_version,
            parent_page_id=args.notion_parent_page_id,
            database_title=args.database_title,
            selected_headers=selected_headers,
        )
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else str(exc)
        print(f"ERROR: Failed to create Notion database ({body})")
        return 1

    print(f"Created Notion database: {database_id}")

    created = 0
    for row in selected_rows:
        slim_row = {"_sheet_row_number": row["_sheet_row_number"]}
        for header in selected_headers:
            slim_row[header] = row.get(header, "")
        try:
            create_notion_page(
                token=args.notion_token,
                notion_version=args.notion_version,
                database_id=database_id,
                row=slim_row,
                column_mapping=column_mapping,
            )
            created += 1
        except requests.HTTPError as exc:
            body = exc.response.text if exc.response is not None else str(exc)
            print(f"WARNING: Failed to mirror row {row['_sheet_row_number']}: {body}")

    print(f"Mirrored {created}/{len(selected_rows)} rows to Notion.")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
