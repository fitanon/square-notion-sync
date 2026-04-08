import os
import requests
import json

NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
NOTION_VERSION = os.getenv('NOTION_VERSION', '2022-06-28')

HEADERS = {
    'Authorization': f'Bearer {NOTION_TOKEN}' if NOTION_TOKEN else '',
    'Notion-Version': NOTION_VERSION,
    'Content-Type': 'application/json',
}

API_BASE = 'https://api.notion.com/v1'


def upsert_connection_row(customer_name: str, payload: dict):
    """Upsert a simple page into the configured Notion database.

    If `NOTION_TOKEN` or `NOTION_DATABASE_ID` are not set, this prints the payload
    so you can inspect and paste into a manual call.
    """
    page_payload = {
        'parent': {'database_id': NOTION_DATABASE_ID},
        'properties': {
            'Name': {'title': [{'text': {'content': customer_name}}]},
            'Notes': {'rich_text': [{'text': {'content': json.dumps(payload, default=str)}}]},
        }
    }

    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print('Notion token/database not configured. Sample payload:')
        print(json.dumps(page_payload, indent=2))
        return {'status': 'skipped', 'payload': page_payload}

    url = f"{API_BASE}/pages"
    resp = requests.post(url, headers=HEADERS, json=page_payload)
    resp.raise_for_status()
    return resp.json()
