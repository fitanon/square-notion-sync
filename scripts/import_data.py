#!/usr/bin/env python3
"""
Import historical data from CSV/Excel files into Notion.

This script reads data files exported from Square or other sources
and imports them into the configured Notion databases.

Usage:
    python scripts/import_data.py --file customers.csv --type customers
    python scripts/import_data.py --file transactions.csv --type transactions
    python scripts/import_data.py --dir ./data --type all
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from core.config import Config
from core.notion import NotionClient


def read_csv(file_path: str) -> List[Dict[str, Any]]:
    """Read CSV file and return list of dictionaries."""
    records = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Clean up keys (remove BOM, whitespace)
            clean_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
            records.append(clean_row)
    return records


def read_json(file_path: str) -> List[Dict[str, Any]]:
    """Read JSON file and return list of dictionaries."""
    with open(file_path, 'r') as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        return [data]


def detect_file_type(file_path: str) -> str:
    """Detect file type from extension."""
    ext = Path(file_path).suffix.lower()
    if ext == '.csv':
        return 'csv'
    elif ext in ['.json']:
        return 'json'
    elif ext in ['.xlsx', '.xls']:
        return 'excel'
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def import_customers(
    notion: NotionClient,
    database_id: str,
    records: List[Dict],
    account_code: str = "PA",
) -> Dict[str, int]:
    """Import customer records to Notion."""
    stats = {"created": 0, "updated": 0, "failed": 0, "skipped": 0}

    for record in records:
        try:
            # Try to extract name - handle various column name formats
            name = (
                record.get('Name') or
                record.get('name') or
                f"{record.get('First Name', '')} {record.get('Last Name', '')}".strip() or
                f"{record.get('given_name', '')} {record.get('family_name', '')}".strip() or
                "Unknown"
            )

            if not name or name == "Unknown":
                stats["skipped"] += 1
                continue

            # Extract other fields
            email = record.get('Email') or record.get('email') or record.get('email_address')
            phone = record.get('Phone') or record.get('phone') or record.get('phone_number')
            square_id = record.get('Square ID') or record.get('id') or record.get('customer_id')

            properties = {
                "Name": notion.title(name),
                "Account": notion.select(account_code),
                "Last Synced": notion.date(datetime.utcnow()),
            }

            if email:
                properties["Email"] = notion.email(email)
            if phone:
                properties["Phone"] = notion.phone(phone)
            if square_id:
                properties["Square ID"] = notion.rich_text(square_id)

            # Check for session data
            sessions_purchased = record.get('Sessions Purchased') or record.get('sessions_purchased')
            sessions_used = record.get('Sessions Used') or record.get('sessions_used')
            if sessions_purchased:
                properties["Sessions Purchased"] = notion.number(int(sessions_purchased))
            if sessions_used:
                properties["Sessions Used"] = notion.number(int(sessions_used))

            # Upsert to Notion
            if square_id:
                existing = notion.find_page_by_property(database_id, "Square ID", square_id)
                if existing:
                    notion.update_page(existing.id, properties)
                    stats["updated"] += 1
                else:
                    notion.create_page(database_id, properties)
                    stats["created"] += 1
            else:
                notion.create_page(database_id, properties)
                stats["created"] += 1

            print(f"  Imported: {name}")

        except Exception:
            print(f"  Failed: {record}")
            stats["failed"] += 1

    return stats


def import_transactions(
    notion: NotionClient,
    database_id: str,
    records: List[Dict],
    account_code: str = "PA",
) -> Dict[str, int]:
    """Import transaction/payment records to Notion."""
    stats = {"created": 0, "updated": 0, "failed": 0, "skipped": 0}

    for record in records:
        try:
            payment_id = (
                record.get('Payment ID') or
                record.get('payment_id') or
                record.get('id') or
                record.get('Transaction ID')
            )

            if not payment_id:
                stats["skipped"] += 1
                continue

            # Extract amount (handle various formats)
            amount_str = record.get('Amount') or record.get('amount') or record.get('Total') or '0'
            # Remove currency symbols and commas
            amount_str = amount_str.replace('$', '').replace(',', '').strip()
            try:
                amount = float(amount_str)
            except ValueError:
                amount = 0.0

            # Extract date
            date_str = record.get('Date') or record.get('date') or record.get('created_at')
            date = None
            if date_str:
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                    try:
                        date = datetime.strptime(date_str.split('T')[0] if 'T' in date_str else date_str, fmt.split('T')[0])
                        break
                    except ValueError:
                        continue

            properties = {
                "Payment ID": notion.title(payment_id),
                "Account": notion.select(account_code),
                "Amount": notion.number(amount),
                "Status": notion.select(record.get('Status') or record.get('status') or 'COMPLETED'),
                "Last Synced": notion.date(datetime.utcnow()),
            }

            if date:
                properties["Date"] = notion.date(date)

            customer_id = record.get('Customer ID') or record.get('customer_id')
            if customer_id:
                properties["Customer ID"] = notion.rich_text(customer_id)

            # Upsert
            existing = notion.find_page_by_property(database_id, "Payment ID", payment_id, "title")
            if existing:
                notion.update_page(existing.id, properties)
                stats["updated"] += 1
            else:
                notion.create_page(database_id, properties)
                stats["created"] += 1

            print(f"  Imported: {payment_id} - ${amount}")

        except Exception:
            print(f"  Failed: {record}")
            stats["failed"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import data files to Notion")
    parser.add_argument("--file", "-f", help="Path to data file (CSV, JSON)")
    parser.add_argument("--dir", "-d", help="Directory containing data files")
    parser.add_argument("--type", "-t", choices=["customers", "transactions", "all"],
                        default="all", help="Type of data to import")
    parser.add_argument("--account", "-a", default="PA",
                        help="Account code (PA, TFC, FWM)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be imported without making changes")
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("Must specify --file or --dir")

    # Load config
    config = Config.from_env()
    if not config.notion:
        print("Error: Notion not configured. Set NOTION_TOKEN in .env")
        sys.exit(1)

    notion = NotionClient(config.notion)

    # Determine database IDs
    clients_db = config.notion.db_clients or config.notion.db_sessions
    transactions_db = config.notion.db_transactions

    if not clients_db:
        print("Error: No clients/sessions database configured")
        sys.exit(1)

    # Collect files to process
    files_to_process = []
    if args.file:
        files_to_process.append(args.file)
    elif args.dir:
        for ext in ['*.csv', '*.json']:
            files_to_process.extend(Path(args.dir).glob(ext))

    print(f"\n{'=' * 60}")
    print(f"Square-Notion Data Import")
    print(f"{'=' * 60}")
    print(f"Account: {args.account}")
    print(f"Files: {len(files_to_process)}")
    print(f"Dry run: {args.dry_run}")
    print(f"{'=' * 60}\n")

    total_stats = {"created": 0, "updated": 0, "failed": 0, "skipped": 0}

    for file_path in files_to_process:
        file_path = str(file_path)
        print(f"\nProcessing: {file_path}")

        try:
            file_type = detect_file_type(file_path)

            if file_type == 'csv':
                records = read_csv(file_path)
            elif file_type == 'json':
                records = read_json(file_path)
            else:
                print(f"  Skipping unsupported file type: {file_type}")
                continue

            print(f"  Found {len(records)} records")

            if args.dry_run:
                print(f"  [DRY RUN] Would import {len(records)} records")
                continue

            # Determine import type from filename or args
            filename_lower = Path(file_path).stem.lower()
            import_type = args.type

            if import_type == "all":
                if "customer" in filename_lower or "client" in filename_lower:
                    import_type = "customers"
                elif "transaction" in filename_lower or "payment" in filename_lower:
                    import_type = "transactions"
                else:
                    import_type = "customers"  # default

            if import_type == "customers" and clients_db:
                stats = import_customers(notion, clients_db, records, args.account)
            elif import_type == "transactions" and transactions_db:
                stats = import_transactions(notion, transactions_db, records, args.account)
            else:
                print(f"  Skipping - no matching database configured")
                continue

            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

            print(f"  Done: {stats}")

        except Exception:
            print(f"  Error processing file")

    print(f"\n{'=' * 60}")
    print(f"Import Complete")
    print(f"{'=' * 60}")
    print(f"Created: {total_stats['created']}")
    print(f"Updated: {total_stats['updated']}")
    print(f"Failed: {total_stats['failed']}")
    print(f"Skipped: {total_stats['skipped']}")


if __name__ == "__main__":
    main()
