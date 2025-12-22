#!/usr/bin/env python3
"""
Create a Notion database (under a provided parent page) and insert a sample row.

Usage:
  export NOTION_TOKEN="secret"
  export PARENT_PAGE_ID="your-parent-page-id"
  python3 scripts/create_notion_page.py

Notes:
- Requires `requests` package. Install with `pip install requests`.
- The script only creates the DB if `PARENT_PAGE_ID` is set; otherwise it prints the payload for manual use.
"""

import os
import sys
import requests
import json

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PARENT_PAGE_ID = os.getenv("PARENT_PAGE_ID")
NOTION_VERSION = os.getenv("NOTION_VERSION", "2022-06-28")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}" if NOTION_TOKEN else "",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

API_BASE = "https://api.notion.com/v1"


def create_database(parent_page_id: str) -> dict:
    url = f"{API_BASE}/databases"
    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "Square Accounts"}}],
        "properties": {
            "Name": {"title": {}},
            "Square Account ID": {"rich_text": {}},
            "Square Environment": {"select": {"options": [{"name": "sandbox"}, {"name": "production"}]}},
            "Data Type": {"multi_select": {}},
            "Last Synced": {"date": {}},
            "Connection URL": {"url": {}},
            "Notes": {"rich_text": {}},
        },
    }

    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code >= 400:
        print("Failed to create database:", resp.status_code, resp.text)
        sys.exit(1)
    return resp.json()


def create_sample_row(database_id: str) -> dict:
    url = f"{API_BASE}/pages"
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": "Sample Account — Demo"}}]},
            "Square Account ID": {"rich_text": [{"text": {"content": "sq-account-demo-123"}}]},
            "Square Environment": {"select": {"name": "sandbox"}},
            "Data Type": {"multi_select": [{"name": "Payments"}, {"name": "Orders"}]},
            "Last Synced": {"date": {"start": "2025-12-08T00:00:00Z"}},
            "Connection URL": {"url": "https://squareup.com/dashboard"},
            "Notes": {"rich_text": [{"text": {"content": "Created by create_notion_page.py"}}]},
        },
    }

    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code >= 400:
        print("Failed to create page:", resp.status_code, resp.text)
        sys.exit(1)
    return resp.json()


if __name__ == '__main__':
    if not NOTION_TOKEN:
        print("ERROR: NOTION_TOKEN not set in environment. Create an integration and set the token as NOTION_TOKEN.")
        sys.exit(1)

    if not PARENT_PAGE_ID:
        print("No PARENT_PAGE_ID provided. The script can print the DB payload for manual use if you want to create it via API or the Notion UI.")
        print("Set PARENT_PAGE_ID and re-run to create the DB programmatically.")
        # Print out payload template for manual creation if the user prefers
        from pprint import pprint
        sample_payload = {
            "title": [{"type": "text", "text": {"content": "Square Accounts"}}],
            "properties": {
                "Name": {"title": {}},
                "Square Account ID": {"rich_text": {}},
                "Square Environment": {"select": {"options": [{"name": "sandbox"}, {"name": "production"}]}},
                "Data Type": {"multi_select": {}},
                "Last Synced": {"date": {}},
                "Connection URL": {"url": {}},
                "Notes": {"rich_text": {}},
            },
        }
        pprint(sample_payload)
        sys.exit(0)

    print("Creating Notion database under parent page id:", PARENT_PAGE_ID)
    db = create_database(PARENT_PAGE_ID)
    database_id = db.get('id')
    print("Created database_id:", database_id)

    print("Inserting sample row into database...")
    page = create_sample_row(database_id)
    print("Created sample page id:", page.get('id'))

    print("Done. Save these IDs for your automation:")
    print("DATABASE_ID=", database_id)
    print("SAMPLE_PAGE_ID=", page.get('id'))

