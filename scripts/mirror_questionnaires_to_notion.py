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
        raise ValueError(
            "Missing Google credentials. Set --service-account-file or --service-account-json."
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

    selected_headers = requested_columns if requested_columns else headers
    missing_headers = [header for header in selected_headers if header not in headers]
    if missing_headers:
        print(f"ERROR: Requested columns not found: {missing_headers}")
        print(f"Available headers: {headers}")
        return 1

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
